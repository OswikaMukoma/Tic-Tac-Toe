#!/usr/bin/env python3
"""Manual play: type one command per line, Enter sends it as a complete frame
(with checksum) and the reply is printed. Works with the board or the mock.

    python tests/play.py COM9
    python tests/play.py socket://127.0.0.1:5555

Type: CONNECT, NEW, MOVE:4, MOVE:0:O, STATE, RESIGN, DISCONNECT. Empty line or Ctrl+C quits.
Prefix a line with '!' to send it exactly as typed, with no checksum (e.g. !HELLO).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import serial  # noqa: E402

from link import Link  # noqa: E402
from protocol_lib import frame  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)
lk = Link(sys.argv[1])
print("connected; type a command and press Enter (empty line quits)")
try:
    while True:
        line = input("> ").strip()
        if not line:
            break
        lk.send(line[1:].encode("ascii", "replace") + b"\n" if line.startswith("!") else frame(line))
        try:
            reply = lk.read_reply(1.0)
        except AssertionError as exc:
            reply = "BAD REPLY: %s" % exc
        print("  <-", reply if reply is not None else "(no reply)")
except (KeyboardInterrupt, EOFError):
    pass
lk.close()
