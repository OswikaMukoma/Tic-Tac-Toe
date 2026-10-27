"""Tiny sound effects with no extra packages and no audio files.

Tones are generated as in-memory WAV data. On Windows they play through the standard
library's winsound (asynchronously); elsewhere the GUI falls back to the Tk bell.
Sounds are triggered only by confirmed server replies (see app.py), never by a click.
"""
import io
import math
import os
import struct
import sys
import tempfile
import wave

try:
    import winsound
except ImportError:                      # not Windows
    winsound = None

RATE = 22050
NOTES = {          # name -> list of (frequency Hz, milliseconds)
    "x": [(660, 90)],
    "o": [(520, 90)],
    "new": [(392, 70), (523, 110)],
    "connect": [(440, 60), (660, 90)],
    "error": [(180, 160), (150, 160)],
    "win": [(523, 110), (659, 110), (784, 110), (1047, 260)],
    "draw": [(440, 140), (392, 140), (349, 220)],
    "resign": [(330, 140), (247, 260)],
}
_cache = {}


def make_wav(notes):
    """notes: [(hz, ms), ...] -> WAV bytes (16-bit mono, short fade to avoid clicks)."""
    frames = bytearray()
    for hz, ms in notes:
        n = int(RATE * ms / 1000)
        for i in range(n):
            fade = min(1.0, i / 120.0, (n - i) / 240.0)
            frames += struct.pack("<h", int(9000 * fade * math.sin(2 * math.pi * hz * i / RATE)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


_files = {}
_warned = False


def _wav_path(kind):
    """Write the effect to a small WAV file in the temp folder once, and reuse it.
    (winsound cannot play SND_MEMORY data asynchronously, so we play from a file.)"""
    path = _files.get(kind)
    if path is None or not os.path.exists(path):
        path = os.path.join(tempfile.gettempdir(), "serialgame_%s.wav" % kind)
        with open(path, "wb") as f:
            f.write(make_wav(NOTES[kind]))
        _files[kind] = path
    return path


def play(kind, root=None):
    """Play a named effect. Never raises: sound must not break the game.
    A failure is printed once on stderr (not on the game UART) so it is not silent."""
    global _warned
    try:
        if winsound is not None:
            winsound.PlaySound(_wav_path(kind), winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif root is not None:
            root.bell()
    except Exception as exc:
        if not _warned:
            _warned = True
            print("sound disabled: %s" % exc, file=sys.stderr)
