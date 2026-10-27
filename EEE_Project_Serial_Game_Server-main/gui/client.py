"""GUI-side protocol client and game view (docs/protocol.md v1.0). No Tkinter here, so the
logic is unit-tested without a screen (tests/gui).

The GUI is an UNTRUSTED client: `GameView` is changed ONLY by a valid, checksum-verified
server reply (never optimistically, never by a click). A rejected request changes nothing
except the message shown.
"""
import time

import serial

MAX_REPLY_WAIT_S = 1.0          # protocol.md section 10: client reply timeout 1 s
EMPTY = "........."

NACK_TEXT = {
    "OCCUPIED": "That cell is already taken.",
    "RANGE": "That cell does not exist (use 0-8).",
    "NOTURN": "It is not that player's turn.",
    "NOGAME": "No game in progress. Press New Game.",
    "BADCMD": "The device did not understand that command.",
    "BADSUM": "The command arrived damaged (bad checksum). Try again.",
    "STATE": "That action is not allowed right now.",
    "TOOLONG": "The command was too long.",
    "TIMEOUT": "The command was incomplete and timed out.",
}


def xor_checksum(body):
    value = 0
    for byte in body.encode("ascii"):
        value ^= byte
    return "%02X" % value


def make_frame(body):
    return ("%s*%s\n" % (body, xor_checksum(body))).encode("ascii")


class ReplyError(Exception):
    """A reply that is missing, damaged or breaks the framing rules."""


def parse_reply(line):
    """Verify '<body>*HH' and return the body, or raise ReplyError."""
    try:
        text = line.decode("ascii")
    except UnicodeDecodeError:
        raise ReplyError("reply is not ASCII")
    body, star, hh = text.rpartition("*")
    if not star or len(hh) != 2 or xor_checksum(body) != hh:
        raise ReplyError("reply failed its checksum: %r" % text)
    return body


class Connection:
    """One serial link (COM port, /dev/tty*, or socket://host:port for the mock)."""

    def __init__(self, port, baud=115200):
        self.ser = serial.serial_for_url(port, baudrate=baud, timeout=0.05)
        self.buf = bytearray()
        self.log = []                                   # (direction, text) for the GUI log

    def close(self):
        self.ser.close()

    def _read_line(self, timeout):
        end = time.monotonic() + timeout
        while True:
            i = self.buf.find(b"\n")
            if i >= 0:
                line = bytes(self.buf[:i]).rstrip(b"\r")
                del self.buf[:i + 1]
                return line
            if time.monotonic() >= end:
                return None
            self.buf += self.ser.read(max(1, self.ser.in_waiting))   # returns as soon as a byte is there

    def request(self, body):
        """Send one command, return the verified reply body. ReplyError if none/damaged."""
        self.ser.reset_input_buffer()
        self.buf.clear()
        self.ser.write(make_frame(body))
        self.ser.flush()
        self.log.append(("tx", body))
        line = self._read_line(MAX_REPLY_WAIT_S)
        if line is None:
            self.log.append(("err", "no reply"))
            raise ReplyError("no reply from the device")
        try:
            reply = parse_reply(line)
        except ReplyError as exc:
            self.log.append(("err", str(exc)))
            raise
        self.log.append(("rx", reply))
        return reply


class GameView:
    """What the window shows. Updated only through apply()."""

    def __init__(self):
        self.score = {"X": 0, "O": 0, "draws": 0}
        self.reset()

    def reset(self):
        self.state = "IDLE"          # IDLE / IN_PROGRESS / GAME_OVER (as last confirmed)
        self.board = EMPTY
        self.result = ""             # "", "X wins!", "O wins!", "Draw", "Game over (resigned)"
        self.message = "Press Connect."

    # The score survives reset(): it is only ever increased by a confirmed WIN/DRAW reply to a MOVE.
    score = None

    # -- helpers
    def next_mark(self):
        """X when marks are equal, else O: derived from the confirmed board."""
        return "X" if self.board.count("X") == self.board.count("O") else "O"

    def can_move(self, i):
        return self.state == "IN_PROGRESS" and self.board[i] == "."

    def command_for_move(self, i):
        return "MOVE:%d:%s" % (i, self.next_mark())

    # -- the one place state changes
    def apply(self, request, reply):
        """request: the body we sent; reply: the verified reply body."""
        if reply.startswith("NACK:"):
            code = reply[5:]
            self.message = NACK_TEXT.get(code, "Rejected: " + code)
            if code == "NOGAME" and self.state == "IN_PROGRESS" and request not in ("NEW", "NEW:AI"):
                # The device no longer has our game (button reset): back to the start screen.
                self.reset()
                self.message = "The device has no active game (it was reset or has finished). Press New Game."
            return
        if reply == "OK" and request in ("CONNECT", "DISCONNECT"):
            self.reset()
            self.message = "Connected. Press New Game." if request == "CONNECT" else "Disconnected."
            return
        if reply == "OK:GAMEOVER":
            self.state, self.result = "GAME_OVER", "Game over: resigned"
            self.message = "You resigned. Press New Game to play again."
            return
        for prefix, state, result in (
                ("OK:BOARD:", None, ""), ("BOARD:", None, None),
                ("WIN:X:BOARD:", "GAME_OVER", "X wins!"), ("WIN:O:BOARD:", "GAME_OVER", "O wins!"),
                ("DRAW:BOARD:", "GAME_OVER", "Draw")):
            if reply.startswith(prefix):
                board = reply[len(prefix):]
                if len(board) != 9 or any(c not in ".XO" for c in board):
                    self.message = "Ignored a malformed board from the device."
                    return
                self.board = board
                if state is not None:
                    self.state = state
                    self.result = result
                    if request.startswith("MOVE:"):          # not for a STATE resync of an old game
                        if result == "Draw":
                            self.score["draws"] += 1
                        else:
                            self.score[result[0]] += 1
                    self.message = "Game over. Press New Game to play again."
                elif prefix == "OK:BOARD:":
                    self.state, self.result = "IN_PROGRESS", ""
                    self.message = "%s to move." % self.next_mark()
                else:                                    # BOARD: (STATE reply)
                    if self.state == "IDLE":
                        self.state = "IN_PROGRESS"       # joined a game already running
                    self.message = ("Game over." if self.state == "GAME_OVER"
                                    else "%s to move." % self.next_mark())
                return
        self.message = "Ignored an unexpected reply: " + reply
