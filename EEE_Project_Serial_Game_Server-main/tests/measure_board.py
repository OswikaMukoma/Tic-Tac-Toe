#!/usr/bin/env python3
"""Measurements for the report. Run on the REAL board (or any server) and keep the output.

    python tests/measure_board.py COM9 --out docs/evidence/board_measurements.txt

Every number printed here is measured, nothing is estimated. All timings include the USB
virtual-COM-port path (ST-Link + Windows driver), which adds a little latency of its own.
Close every terminal on the port first.
"""
import argparse
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link import Link  # noqa: E402
from protocol_lib import frame  # noqa: E402


def stats(values_ms):
    v = sorted(values_ms)
    p95 = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    return "n=%d min=%.2f median=%.2f mean=%.2f p95=%.2f max=%.2f ms" % (
        len(v), v[0], statistics.median(v), statistics.mean(v), p95, v[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--out", default="")
    ap.add_argument("--rtt", type=int, default=300, help="round-trip samples")
    ap.add_argument("--timeouts", type=int, default=20, help="partial-frame timeout samples")
    ap.add_argument("--sustained", type=int, default=2000, help="one-at-a-time requests")
    ap.add_argument("--bursts", type=int, default=30, help="repeats per burst size")
    args = ap.parse_args()
    lines = []

    def out(text=""):
        print(text)
        lines.append(text)

    lk = Link(args.port)
    lk.sync_to_idle()
    out("Measurements on port %s, %s" % (args.port, time.strftime("%Y-%m-%d %H:%M:%S")))

    # M1 round-trip latency: last byte written -> full reply line received
    samples = []
    for _ in range(args.rtt):
        data = frame("STATE")
        lk.drain(0.0)
        t0 = time.perf_counter()
        lk.send(data)
        reply = lk.read_reply(1.0)
        t1 = time.perf_counter()
        assert reply == "NACK:NOGAME", reply
        samples.append((t1 - t0) * 1000)
    out("M1 request->reply latency (STATE in IDLE, 9-byte frame, ~14-byte reply): " + stats(samples))

    # M2 partial-frame timeout: last byte sent -> NACK:TIMEOUT received
    samples = []
    for _ in range(args.timeouts):
        lk.send(b"MOV")
        t0 = time.perf_counter()
        reply = lk.read_reply(2.0)
        t1 = time.perf_counter()
        assert reply == "NACK:TIMEOUT", reply
        samples.append((t1 - t0) * 1000)
    out("M2 partial-frame timeout (spec 500 ms; last byte sent -> NACK:TIMEOUT received): " + stats(samples))

    # M3 sustained one-at-a-time exchange: any wrong or missing reply is counted
    lk.request("NEW")
    moves = ["MOVE:%d" % i for i in range(9)]
    bad = 0
    t0 = time.perf_counter()
    for k in range(args.sustained):
        cmd = ["STATE", "MOVE:9", "MOVE:4:O", "HELLO", "MOVE:-1"][k % 5]
        want = {"STATE": "BOARD:.........", "MOVE:9": "NACK:RANGE", "MOVE:4:O": "NACK:NOTURN",
                "HELLO": "NACK:BADCMD", "MOVE:-1": "NACK:RANGE"}[cmd]
        if lk.request(cmd) != want:
            bad += 1
    dt = time.perf_counter() - t0
    out("M3 sustained exchange: %d requests, %d wrong/missing replies, %.1f requests/s"
        % (args.sustained, bad, args.sustained / dt))
    lk.request("RESIGN")
    lk.request("DISCONNECT")

    # M4 pipelined bursts: N frames in ONE write; every reply must arrive, in order
    out("M4 pipelined bursts (N frames sent in one write, STATE with checksum; each repeated %d times):" % args.bursts)
    for n in (1, 2, 4, 8, 16, 32, 64):
        lost = 0
        for _ in range(args.bursts):
            lk.drain(0.05)
            lk.send(frame("STATE") * n)
            got = 0
            while got < n:
                r = lk.read_reply(1.0)
                if r is None:
                    break
                if r != "NACK:NOGAME":
                    lost += 1
                got += 1
            lost += n - got
            lk.drain(0.05)
        out("   N=%-3d (%3d bytes): %d replies missing or wrong out of %d" % (n, n * len(frame("STATE")), lost, n * args.bursts))

    # M5 recovery after random garbage (seeded): the next valid request must work
    rng = random.Random(2026)
    fails = 0
    for _ in range(100):
        junk = bytes(rng.choice([b for b in range(256) if b != 10]) for _ in range(rng.randint(1, 31))) + b"\n"
        lk.send(junk)
        lk.drain(0.02)
        if lk.request("CONNECT") != "OK":
            fails += 1
    out("M5 recovery: 100 random garbage frames, each followed by CONNECT: %d failed recoveries" % fails)

    lk.sync_to_idle()
    lk.close()
    if args.out:
        with open(args.out, "w") as f:
            f.write("\n".join(lines) + "\n")
        print("saved", args.out)


if __name__ == "__main__":
    main()
