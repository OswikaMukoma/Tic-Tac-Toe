"""Serial link used by every test: pyserial on a real port, or socket:// for the mock."""
import time

import serial

from protocol_lib import frame, split_reply


class Link:
    def __init__(self, url, baud=115200):
        self.ser = serial.serial_for_url(url, baudrate=baud, timeout=0.05)
        self.buf = bytearray()

    def close(self):
        self.ser.close()

    def send(self, data):
        if isinstance(data, str):
            data = data.encode("ascii")
        self.ser.write(data)
        self.ser.flush()

    def read_line(self, timeout=1.0):
        """Next line without its LF, or None on timeout."""
        end = time.monotonic() + timeout
        while True:
            i = self.buf.find(b"\n")
            if i >= 0:
                line = bytes(self.buf[:i])
                del self.buf[:i + 1]
                return line
            if time.monotonic() >= end:
                return None
            # read(n) waits for n bytes or the timeout, which would quantise every latency to the
            # 50 ms port timeout; asking for what is already waiting (at least 1) returns at once.
            self.buf += self.ser.read(max(1, self.ser.in_waiting))

    def read_reply(self, timeout=1.0):
        """Next reply body (checksum verified), or None on timeout."""
        line = self.read_line(timeout)
        return None if line is None else split_reply(line)

    def expect_silence(self, duration=0.3):
        line = self.read_line(duration)
        assert line is None, "unexpected reply: %r" % (line,)

    def drain(self, quiet=0.1):
        """Throw away anything arriving until the line is quiet."""
        while self.read_line(quiet) is not None:
            pass

    def request(self, body, checksum=True, timeout=1.0):
        self.send(frame(body, checksum))
        return self.read_reply(timeout)

    def sync_to_idle(self):
        """Bring the server to IDLE from any state using only protocol commands."""
        self.send(b"\n")
        self.drain()
        if self.request("STATE") == "NACK:NOGAME":
            return
        if self.request("MOVE:9") == "NACK:RANGE":      # IN_PROGRESS
            assert self.request("RESIGN") == "OK:GAMEOVER"
        assert self.request("DISCONNECT") == "OK"
        assert self.request("STATE") == "NACK:NOGAME"
