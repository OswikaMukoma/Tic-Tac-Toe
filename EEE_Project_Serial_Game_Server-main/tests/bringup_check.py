#!/usr/bin/env python3
"""Stage 4 helper: check the BringUp image over the VCP.

    python tests/bringup_check.py COM5      (or /dev/ttyACM0)

Verifies T2 (banner lines arrive) and T3 (bytes are echoed). Prints raw evidence
to paste into docs/bringup-log.md. T1 (LED colours) and T4 (SW0) are by eye / by hand.
"""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
ser = serial.Serial(port, 115200, timeout=0.2)
ser.reset_input_buffer()

print("T2: listening 3 s for 'BRINGUP TX n' ...")
t_end = time.time() + 3
seen = b""
while time.time() < t_end:
    seen += ser.read(64)
lines = [l for l in seen.decode("ascii", "replace").splitlines() if l.startswith("BRINGUP TX")]
print("   got:", lines)
t2 = len(lines) >= 2

print("T3: echo test ...")
probe = b"Hello 123 ~!\n"
ser.reset_input_buffer()
ser.write(probe)
time.sleep(0.5)
back = ser.read(200)
echo_ok = probe in back
print("   sent:", probe, " got:", back)

print("T2 transmit :", "PASS" if t2 else "FAIL")
print("T3 echo     :", "PASS" if echo_ok else "FAIL")
sys.exit(0 if (t2 and echo_ok) else 1)
