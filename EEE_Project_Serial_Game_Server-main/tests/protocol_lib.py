"""Shared protocol helpers (docs/protocol.md v1.0).

Used by the mock server and by the tests. Nothing here talks to a port.
"""
import re

MAX_FRAME = 32               # bytes before the LF, including a CR and the *HH suffix
INACTIVITY_TIMEOUT_S = 0.5   # partial-frame timeout
EMPTY_BOARD = "........."

_REPLY_RE = re.compile(r"^(?P<body>[^*]*)\*(?P<hh>[0-9A-F]{2})$")


class ProtocolError(AssertionError):
    """A server reply that breaks the framing rules (missing or wrong checksum...)."""


def xor_checksum(body) -> str:
    """XOR of every body byte as two UPPERCASE hex digits (protocol.md section 2)."""
    data = body.encode("ascii") if isinstance(body, str) else bytes(body)
    value = 0
    for byte in data:
        value ^= byte
    return "%02X" % value


def frame(body: str, checksum: bool = True) -> bytes:
    """A request frame: body, optional *HH, LF."""
    text = body + ("*" + xor_checksum(body) if checksum else "")
    return text.encode("ascii") + b"\n"


def split_reply(line: bytes) -> str:
    """Check a reply line (without its LF) and return the body.

    Server replies MUST end in *HH with a correct checksum (protocol.md section 2).
    """
    try:
        text = line.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProtocolError("reply is not ASCII: %r" % (line,)) from exc
    match = _REPLY_RE.match(text)
    if not match:
        raise ProtocolError("reply has no valid *HH checksum field: %r" % (text,))
    if xor_checksum(match.group("body")) != match.group("hh"):
        raise ProtocolError("reply checksum is wrong: %r (expected *%s)"
                            % (text, xor_checksum(match.group("body"))))
    return match.group("body")
