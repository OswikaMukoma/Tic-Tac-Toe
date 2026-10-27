#!/usr/bin/env python3
"""Mock game server: speaks docs/protocol.md v1.0 so the GUI and the tests can be
developed and run without the board.

It is an independent Python re-implementation of the protocol, written from the
document (not from the C code). Run standalone for the GUI:

    python tests/mock_server.py --listen 5555
    # then connect a client to  socket://127.0.0.1:5555   (pyserial URL)

The tests start it automatically with `--port mock`.

FAULT INJECTION (test infrastructure only). `faults` deliberately breaks one rule so
that tests/mutation_check.py can prove the tests notice. A normal run uses none.
"""
import argparse
import socket
import threading
import time

from protocol_lib import EMPTY_BOARD, INACTIVITY_TIMEOUT_S, MAX_FRAME, xor_checksum

LF = 0x0A
CR = 0x0D
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]

ALL_FAULTS = {
    "occupied_overwrites": "MOVE onto an occupied cell overwrites it",
    "nack_changes_state": "a NACK:NOTURN flips the turn anyway",
    "range_off_by_one": "index 9 is accepted (plays cell 8)",
    "no_turn_check": "the claimed mark is ignored",
    "win_misses_diagonal": "the 2-4-6 diagonal is not checked",
    "moves_after_game_over": "MOVE is accepted after the game is over",
    "draw_reported_as_ok": "a full board is reported as OK:BOARD, game continues",
    "resign_in_idle": "RESIGN is accepted in IDLE",
    "oversize_no_reply": "an oversize frame gets no NACK:TOOLONG",
    "oversize_double_reply": "an oversize frame is answered twice",
    "limit_off_by_one": "frames of 32 bytes are rejected as too long",
    "no_timeout": "a stalled partial frame never times out",
    "timeout_too_short": "partial-frame timeout is 100 ms, not 500 ms",
    "accept_bad_checksum": "a wrong request checksum is ignored",
    "reply_without_checksum": "replies carry no *HH checksum",
}


# --------------------------------------------------------------------------- framing
class Framer:
    """Byte-fed framer: protocol.md section 3 (IDLE / RECEIVING / DISCARDING)."""
    IDLE, RECEIVING, DISCARDING = range(3)

    def __init__(self, faults=()):
        self.faults = set(faults)
        self.max_len = MAX_FRAME - 1 if "limit_off_by_one" in self.faults else MAX_FRAME
        self.timeout_ms = (100 if "timeout_too_short" in self.faults
                           else INACTIVITY_TIMEOUT_S * 1000)
        self.state = self.IDLE
        self.buf = bytearray()
        self.last_ms = 0.0

    def feed(self, byte, now_ms):
        events = []
        self.last_ms = now_ms
        if self.state == self.IDLE:
            if byte == LF:
                events.append(("frame", b""))               # empty frame
            else:
                self.buf = bytearray([byte])
                self.state = self.RECEIVING
        elif self.state == self.RECEIVING:
            if byte == LF:
                raw = bytes(self.buf)
                if raw.endswith(b"\r"):
                    raw = raw[:-1]                          # one CR before the LF is dropped
                events.append(("frame", raw))
                self.buf = bytearray()
                self.state = self.IDLE
            elif len(self.buf) >= self.max_len:             # this is the 33rd byte
                events.append(("toolong",))
                self.buf = bytearray()
                self.state = self.DISCARDING
            else:
                self.buf.append(byte)
        else:                                               # DISCARDING
            if byte == LF:
                self.state = self.IDLE
                if "oversize_double_reply" in self.faults:
                    events.append(("toolong",))
        return events

    def tick(self, now_ms):
        events = []
        if self.state != self.IDLE and now_ms - self.last_ms >= self.timeout_ms:
            if self.state == self.RECEIVING:
                events.append(("timeout",))
            self.buf = bytearray()
            self.state = self.IDLE                          # DISCARDING times out silently
        return events


# --------------------------------------------------------------------------- parsing
def _is_hex_upper(text):
    return len(text) == 2 and all(c in "0123456789ABCDEF" for c in text)


def parse_request(raw, faults=()):
    """protocol.md section 4. Returns ('err', code) or ('cmd', name, index, mark)."""
    if len(raw) == 0 or any(b < 0x20 or b > 0x7E for b in raw):
        return ("err", "BADCMD")
    text = raw.decode("ascii")
    if "*" in text:
        body, _, rest = text.partition("*")
        if "*" in rest or not _is_hex_upper(rest):
            return ("err", "BADSUM")
        if xor_checksum(body) != rest and "accept_bad_checksum" not in faults:
            return ("err", "BADSUM")
    else:
        body = text
    if body in ("CONNECT", "NEW", "STATE", "RESIGN", "DISCONNECT"):
        return ("cmd", body, None, None)
    if body == "NEW:AI":
        return ("cmd", "NEW", "AI", None)
    if body.startswith("MOVE:"):
        arg = body[5:]
        mark = None
        if len(arg) >= 2 and arg[-2] == ":":
            arg, mark = arg[:-2], arg[-1]
            if mark not in ("X", "O"):
                return ("err", "BADCMD")
        digits = arg[1:] if arg.startswith("-") else arg
        if 1 <= len(digits) <= 3 and digits.isdigit() and digits.isascii():
            return ("cmd", "MOVE", int(arg), mark)
    return ("err", "BADCMD")


# --------------------------------------------------------------------------- AI (mirror of ai.c)
def _line_won(board, who):
    return any(all(board[i] == who for i in line) for line in LINES)


def _search(board, turn, alpha, beta):
    if _line_won(board, "O"):
        return 1
    if _line_won(board, "X"):
        return -1
    if "." not in board:
        return 0
    other = "X" if turn == "O" else "O"
    best = -2 if turn == "O" else 2
    for i in range(9):
        if board[i] != ".":
            continue
        board[i] = turn
        v = _search(board, other, alpha, beta)
        board[i] = "."
        if turn == "O":
            best = max(best, v)
            alpha = max(alpha, best)
        else:
            best = min(best, v)
            beta = min(beta, best)
        if alpha >= beta:
            break
    return best


def _ai_pick(board):
    b = list(board)
    best, pick = -2, -1
    for i in range(9):
        if b[i] != ".":
            continue
        b[i] = "O"
        v = _search(b, "X", -2, 2)
        b[i] = "."
        if v > best:
            best, pick = v, i
    return pick


# --------------------------------------------------------------------------- game logic
class ReferenceServer:
    """The three-state machine of protocol.md sections 5 and 6."""

    def __init__(self, faults=()):
        self.faults = set(faults)
        self.state = "IDLE"
        self.board = ["."] * 9
        self.turn = "X"
        self.ai = False

    def board_str(self):
        return "".join(self.board)

    def on_event(self, event):
        """Framer event -> reply body (or None for 'no reply')."""
        kind = event[0]
        if kind == "toolong":
            return None if "oversize_no_reply" in self.faults else "NACK:TOOLONG"
        if kind == "timeout":
            return None if "no_timeout" in self.faults else "NACK:TIMEOUT"
        parsed = parse_request(event[1], self.faults)
        if parsed[0] == "err":
            return "NACK:" + parsed[1]
        _, name, index, mark = parsed
        return getattr(self, "do_" + name.lower())(index, mark)

    def do_connect(self, index, mark):
        return "OK" if self.state == "IDLE" else "NACK:STATE"

    def do_new(self, index, mark):
        if self.state == "IN_PROGRESS":
            return "NACK:STATE"
        self.board = ["."] * 9
        self.turn = "X"
        self.state = "IN_PROGRESS"
        self.ai = (index == "AI")
        return "OK:BOARD:" + EMPTY_BOARD

    def do_state(self, index, mark):
        return "NACK:NOGAME" if self.state == "IDLE" else "BOARD:" + self.board_str()

    def do_resign(self, index, mark):
        if self.state != "IN_PROGRESS" and not (self.state == "IDLE" and "resign_in_idle" in self.faults):
            return "NACK:NOGAME"
        self.state = "GAME_OVER"
        return "OK:GAMEOVER"

    def do_disconnect(self, index, mark):
        if self.state == "IN_PROGRESS":
            return "NACK:STATE"
        self.state = "IDLE"
        self.board = ["."] * 9
        self.turn = "X"
        return "OK"

    def _winner(self, who):
        lines = LINES[:-1] if "win_misses_diagonal" in self.faults else LINES
        return any(all(self.board[i] == who for i in line) for line in lines)

    def do_move(self, index, mark):
        if self.state != "IN_PROGRESS" and "moves_after_game_over" not in self.faults:
            return "NACK:NOGAME"
        if self.state == "IDLE":
            return "NACK:NOGAME"
        if "range_off_by_one" in self.faults and index == 9:
            index = 8
        elif not 0 <= index <= 8:
            return "NACK:RANGE"
        if mark is not None and mark != self.turn and "no_turn_check" not in self.faults:
            if "nack_changes_state" in self.faults:
                self.turn = "O" if self.turn == "X" else "X"
            return "NACK:NOTURN"
        if self.board[index] != "." and "occupied_overwrites" not in self.faults:
            return "NACK:OCCUPIED"
        who = self.turn
        self.board[index] = who                             # commit
        if self._winner(who):
            self.state = "GAME_OVER"
            return "WIN:%s:BOARD:%s" % (who, self.board_str())
        if "." not in self.board and "draw_reported_as_ok" not in self.faults:
            self.state = "GAME_OVER"
            return "DRAW:BOARD:" + self.board_str()
        self.turn = "O" if who == "X" else "X"
        if self.ai and self.turn == "O":
            # NEW:AI game: the server answers with O's move; the reply shows both moves.
            self.board[_ai_pick(self.board)] = "O"
            if self._winner("O"):
                self.state = "GAME_OVER"
                return "WIN:O:BOARD:" + self.board_str()
            if "." not in self.board:
                self.state = "GAME_OVER"
                return "DRAW:BOARD:" + self.board_str()
            self.turn = "X"
        return "OK:BOARD:" + self.board_str()


def encode_reply(body, faults=()):
    if "reply_without_checksum" in faults:
        return (body + "\n").encode("ascii")
    return ("%s*%s\n" % (body, xor_checksum(body))).encode("ascii")


# --------------------------------------------------------------------------- TCP front end
class MockServer:
    """Serves one client at a time on a local TCP port. pyserial opens it with
    serial.serial_for_url('socket://127.0.0.1:<port>'), so tests and GUI use the same
    code path as a real serial port. Game state survives reconnects, like the board."""

    def __init__(self, host="127.0.0.1", port=0, faults=()):
        self.faults = set(faults)
        self.logic = ReferenceServer(self.faults)
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, port))
        self._listener.listen(1)
        self.host, self.port = self._listener.getsockname()
        self._stop = threading.Event()
        self._thread = None

    @property
    def url(self):
        return "socket://%s:%d" % (self.host, self.port)

    def start(self):
        self._thread = threading.Thread(target=self._run, name="mock-server", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        try:
            self._listener.close()
        except OSError:
            pass
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        self._listener.settimeout(0.1)
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                self._serve(conn)

    def _serve(self, conn):
        conn.settimeout(0.01)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        framer = Framer(self.faults)
        while not self._stop.is_set():
            try:
                data = conn.recv(4096)
                if data == b"":
                    return                                  # client closed
            except socket.timeout:
                data = b""
            except OSError:
                return
            now_ms = time.monotonic() * 1000.0
            events = []
            for byte in data:
                events += framer.feed(byte, now_ms)
            events += framer.tick(now_ms)
            for event in events:
                body = self.logic.on_event(event)
                if body is not None:
                    try:
                        conn.sendall(encode_reply(body, self.faults))
                    except OSError:
                        return


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", type=int, default=5555, help="TCP port to listen on (default 5555)")
    ap.add_argument("--fault", action="append", default=[], choices=sorted(ALL_FAULTS),
                    help="inject a deliberate fault (test infrastructure only)")
    args = ap.parse_args()
    server = MockServer(port=args.listen, faults=args.fault).start()
    print("mock server on %s   (Ctrl-C to stop)" % server.url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
