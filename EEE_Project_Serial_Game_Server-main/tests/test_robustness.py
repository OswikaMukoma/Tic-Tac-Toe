"""Framing, checksum and garbage handling (protocol.md sections 2-4, invariants R1-R5)."""
import random
import time

import pytest

from protocol_lib import frame, xor_checksum

BAD = "NACK:BADCMD"


def playing(link):
    assert link.request("NEW").startswith("OK:BOARD:")
    assert link.request("MOVE:4") == "OK:BOARD:....X...."


def test_burst_of_frames_gets_one_reply_each_in_order(link):
    link.send(frame("CONNECT") + frame("NEW") + frame("STATE") + frame("MOVE:4"))
    assert link.read_reply() == "OK"
    assert link.read_reply() == "OK:BOARD:........."
    assert link.read_reply() == "BOARD:........."
    assert link.read_reply() == "OK:BOARD:....X...."
    link.expect_silence()


def test_crlf_terminator_accepted(link):
    link.send(b"CONNECT\r\n")
    assert link.read_reply() == "OK"
    link.send(("STATE*" + xor_checksum("STATE") + "\r\n").encode())
    assert link.read_reply() == "NACK:NOGAME"


def test_checksum_optional_but_verified(link):
    assert link.request("CONNECT", checksum=False) == "OK"
    assert link.request("CONNECT", checksum=True) == "OK"
    for bad in ("CONNECT*00", "CONNECT*zz", "CONNECT*6", "CONNECT*123", "CONNECT*", "CONNECT*c3"):
        link.send(bad + "\n")
        assert link.read_reply() == "NACK:BADSUM", bad
    link.send("CONNECT*" + xor_checksum("CONNECT") + "*00\n")
    assert link.read_reply() == "NACK:BADSUM"


def test_bad_checksum_never_executes_command(link):
    link.send("NEW*00\n")
    assert link.read_reply() == "NACK:BADSUM"
    assert link.request("STATE") == "NACK:NOGAME"          # still IDLE


@pytest.mark.parametrize("body", [
    "connect", "Connect", "CONNECT ", " CONNECT", "CONNECT:", "NEW:1", "STATE:X", "RESIGN:1",
    "MOVE", "MOVE:", "MOVE::", "MOVE:1:", "MOVE:1:Z", "MOVE:1:x", "MOVE:1:XX", "MOVE:1000",
    "MOVE:--1", "MOVE:+1", "MOVE:1.5", "MOVE:0x1", "MOVE: 1", "MOVE:1 ", "MOVE:1:X:Y", "M", "?",
])
def test_bad_command_variants(link, body):
    assert link.request(body) == BAD


def test_empty_frame_and_bare_cr(link):
    link.send(b"\n")
    assert link.read_reply() == BAD
    link.send(b"\r\n")
    assert link.read_reply() == BAD


@pytest.mark.parametrize("raw", [b"\x00\n", b"\x01CONNECT\n", b"CON\x07NECT\n", b"\x7f\n",
                                 b"\xff\xfe\n", b"CONNECT\xe9\n", b"\tCONNECT\n"])
def test_non_printable_is_badcmd(link, raw):
    link.send(raw)
    assert link.read_reply() == BAD
    assert link.request("CONNECT") == "OK"


def test_random_garbage_never_breaks_the_server(link):
    rng = random.Random(2026)
    for _ in range(40):
        n = rng.randint(1, 31)
        chunk = bytes(rng.choice([b for b in range(256) if b not in (10,)]) for _ in range(n))
        link.send(chunk + b"\n")
        reply = link.read_reply()
        assert reply is not None and reply.startswith("NACK:"), (chunk, reply)
    assert link.request("CONNECT") == "OK"                   # R5 recovery


def test_garbage_does_not_change_game(link):
    playing(link)
    for raw in (b"???\n", b"MOVE:9\x00\n", b"\n", b"MOVE:3*00\n", b"MOVE:3:X\n"):
        link.send(raw)
        assert link.read_reply().startswith("NACK:")
    assert link.request("STATE") == "BOARD:....X...."


def test_32_byte_frame_accepted_33_rejected(link):
    link.send(b"A" * 32 + b"\n")
    assert link.read_reply() == BAD                          # parsed, just unknown
    link.send(b"A" * 33 + b"\n")
    assert link.read_reply() == "NACK:TOOLONG"
    link.expect_silence()                                    # rest discarded silently
    assert link.request("CONNECT") == "OK"


def test_cr_counts_toward_the_limit(link):
    link.send(b"A" * 31 + b"\r\n")
    assert link.read_reply() == BAD
    link.send(b"A" * 32 + b"\r\n")
    assert link.read_reply() == "NACK:TOOLONG"
    link.expect_silence()
    assert link.request("CONNECT") == "OK"


def test_leading_zeros_in_index_are_legal(link):
    link.request("NEW")
    assert link.request("MOVE:000") == "OK:BOARD:X........"


@pytest.mark.parametrize("size", [34, 64, 200, 1000])
def test_oversize_frames_get_exactly_one_nack(link, size):
    link.send(b"B" * size + b"\n")
    assert link.read_reply() == "NACK:TOOLONG"
    link.expect_silence(0.3)
    assert link.request("CONNECT") == "OK"


def test_oversize_junk_then_next_frame_is_parsed_normally(link):
    link.send(b"A" * 40 + b"\n")
    assert link.read_reply() == "NACK:TOOLONG"
    link.send(b"NEW\n")
    assert link.read_reply() == "OK:BOARD:........."


def test_oversize_in_game_leaves_board(link):
    playing(link)
    link.send(b"MOVE:0:" + b"X" * 40 + b"\n")
    assert link.read_reply() == "NACK:TOOLONG"
    assert link.request("STATE") == "BOARD:....X...."


@pytest.mark.slow
def test_discarding_times_out_silently(link):
    link.send(b"C" * 40)                                     # no LF
    assert link.read_reply() == "NACK:TOOLONG"
    time.sleep(0.8)
    link.expect_silence(0.2)                                 # no NACK:TIMEOUT from DISCARDING
    assert link.request("CONNECT") == "OK"


@pytest.mark.slow
def test_partial_frame_times_out(link):
    link.send(b"MOV")
    t0 = time.monotonic()
    assert link.read_reply(2.0) == "NACK:TIMEOUT"
    elapsed = time.monotonic() - t0
    assert 0.4 <= elapsed <= 0.9, elapsed
    link.send(b"E:4\n")                                      # late remainder = new frame
    assert link.read_reply() == BAD


@pytest.mark.slow
def test_timeout_does_not_change_game(link):
    playing(link)
    link.send(b"MOVE:0")
    assert link.read_reply(2.0) == "NACK:TIMEOUT"
    assert link.request("STATE") == "BOARD:....X...."


@pytest.mark.slow
def test_inactivity_timer_restarts_on_each_byte(link):
    for part in (b"STA", b"TE", b"*", None):
        if part is None:
            link.send(("%s\n" % xor_checksum("STATE")).encode())
        else:
            link.send(part)
            time.sleep(0.3)
    assert link.read_reply() == "NACK:NOGAME"                # 0.9 s total, no timeout


@pytest.mark.slow
def test_no_unsolicited_replies(link):
    playing(link)
    link.expect_silence(1.0)
