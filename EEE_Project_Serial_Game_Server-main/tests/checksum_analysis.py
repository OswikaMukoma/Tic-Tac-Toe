#!/usr/bin/env python3
"""What the XOR checksum (protocol.md section 2) can and cannot detect. Pure PC calculation on
the checksum function; it does not involve the board. Output is for the report, with that label.

    python tests/checksum_analysis.py > docs/evidence/checksum_analysis.txt
"""
import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol_lib import xor_checksum  # noqa: E402

BODIES = (["CONNECT", "NEW", "STATE", "RESIGN", "DISCONNECT"]
          + ["MOVE:%d" % i for i in range(9)] + ["MOVE:%d:%s" % (i, m) for i in range(9) for m in "XO"]
          + ["OK", "NACK:OCCUPIED", "NACK:BADCMD", "OK:BOARD:XO.X..O.X", "WIN:X:BOARD:OO.XXX...", "DRAW:BOARD:XOXXOOOXX"])


def flip(data, bit):
    d = bytearray(data)
    d[bit // 8] ^= 1 << (bit % 8)
    return bytes(d)


def main():
    print("XOR checksum analysis over %d protocol messages (calculation, not a board test)" % len(BODIES))
    single = single_miss = pair = pair_miss = 0
    swaps = swap_total = 0
    for body in BODIES:
        data = body.encode()
        good = xor_checksum(data)
        bits = len(data) * 8
        for b in range(bits):
            single += 1
            single_miss += xor_checksum(flip(data, b)) == good
        for a, b in itertools.combinations(range(bits), 2):
            pair += 1
            pair_miss += xor_checksum(flip(flip(data, a), b)) == good
        for i in range(len(data) - 1):
            if data[i] != data[i + 1]:
                swap_total += 1
                d = bytearray(data)
                d[i], d[i + 1] = d[i + 1], d[i]
                swaps += xor_checksum(bytes(d)) == good
    print("single-bit errors:      %d tried, %d undetected" % (single, single_miss))
    print("two-bit errors:         %d tried, %d undetected (%.2f%%)" % (pair, pair_miss, 100.0 * pair_miss / pair))
    print("adjacent byte swaps:    %d tried, %d undetected (%.1f%%)" % (swap_total, swaps, 100.0 * swaps / swap_total))
    rng = random.Random(2026)
    trials, miss = 200000, 0
    for _ in range(trials):
        body = rng.choice(BODIES).encode()
        junk = bytes(rng.randrange(256) for _ in range(len(body)))
        if junk != body and xor_checksum(junk) == xor_checksum(body):
            miss += 1
    print("random replacement of the whole body: %d trials, %d undetected (%.3f%%; ideal 1/256 = 0.391%%)"
          % (trials, miss, 100.0 * miss / trials))
    print("Conclusion: all single-bit errors are caught; some two-bit errors and every byte swap are not.")


if __name__ == "__main__":
    main()
