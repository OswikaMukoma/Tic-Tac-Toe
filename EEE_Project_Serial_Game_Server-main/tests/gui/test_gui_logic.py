"""GUI logic without a screen: gui/client.py against the mock server."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "gui"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from client import Connection, GameView, ReplyError, make_frame, parse_reply  # noqa: E402
from mock_server import MockServer  # noqa: E402


@pytest.fixture
def server():
    s = MockServer().start()
    yield s
    s.stop()


@pytest.fixture
def pair(server):
    conn = Connection(server.url)
    view = GameView()
    yield conn, view
    conn.close()


def do(pair, body):
    conn, view = pair
    reply = conn.request(body)
    view.apply(body, reply)
    return reply


def test_frame_and_reply_checksum():
    assert make_frame("MOVE:4:X") == b"MOVE:4:X*7D\n"
    assert parse_reply(b"OK:BOARD:....X....*06") == "OK:BOARD:....X...."
    for bad in (b"OK*00", b"OK", b"OK*6", b"\xff*00"):
        with pytest.raises(ReplyError):
            parse_reply(bad)


def test_full_game_is_drawn_only_from_replies(pair):
    conn, view = pair
    assert do(pair, "CONNECT") == "OK" and view.state == "IDLE"
    do(pair, "NEW")
    assert view.state == "IN_PROGRESS" and view.board == "........." and view.message == "X to move."
    for i in (4, 0, 3, 1):
        do(pair, view.command_for_move(i))
    assert view.board == "OO.XX...."
    do(pair, view.command_for_move(5))
    assert view.board == "OO.XXX..." and view.state == "GAME_OVER" and view.result == "X wins!"
    assert not any(view.can_move(i) for i in range(9))          # moves disabled after game over


def test_rejected_move_changes_nothing_but_the_message(pair):
    do(pair, "NEW")
    do(pair, "MOVE:4:X")
    before = (pair[1].board, pair[1].state)
    do(pair, "MOVE:4:O")                                         # occupied
    assert (pair[1].board, pair[1].state) == before
    assert pair[1].message == "That cell is already taken."
    do(pair, "MOVE:9")
    assert pair[1].message.startswith("That cell does not exist")
    do(pair, "MOVE:0:X")                                         # O to move
    assert pair[1].message == "It is not that player's turn."
    assert (pair[1].board, pair[1].state) == before


def test_draw(pair):
    do(pair, "NEW")
    for i in (0, 1, 2, 4, 3, 5, 7, 6, 8):
        do(pair, pair[1].command_for_move(i))
    assert pair[1].result == "Draw" and pair[1].board == "XOXXOOOXX"


def test_resign_then_new_game_then_clean_disconnect(pair):
    do(pair, "NEW")
    do(pair, "RESIGN")
    assert pair[1].state == "GAME_OVER" and "resigned" in pair[1].result
    do(pair, "NEW")
    assert pair[1].state == "IN_PROGRESS" and pair[1].board == "........."
    do(pair, "RESIGN")
    do(pair, "DISCONNECT")
    assert pair[1].state == "IDLE" and pair[1].message == "Disconnected."


def test_device_reset_is_noticed_on_next_request(server, pair):
    do(pair, "NEW")
    do(pair, "MOVE:4:X")
    server.logic.state, server.logic.board = "IDLE", ["."] * 9      # what the SW0 button does
    do(pair, pair[1].command_for_move(0))
    assert pair[1].state == "IDLE" and pair[1].board == "........."
    assert "no active game" in pair[1].message


def test_stale_view_cannot_reach_the_board(pair):
    # a move on a cell the device holds but the view does not: the device decides
    do(pair, "NEW")
    pair[0].request("MOVE:4:X")                                   # played behind the view's back
    assert pair[1].board == "........."                           # view not updated: no optimism
    do(pair, "MOVE:4:X")
    assert pair[1].message in ("It is not that player's turn.", "That cell is already taken.")


def test_no_reply_and_damaged_reply_raise(server):
    bad = MockServer(faults=["reply_without_checksum"]).start()
    try:
        conn = Connection(bad.url)
        with pytest.raises(ReplyError):
            conn.request("CONNECT")
        conn.close()
    finally:
        bad.stop()


def test_score_counts_only_confirmed_results(pair):
    v = pair[1]
    assert v.score == {"X": 0, "O": 0, "draws": 0}
    do(pair, "NEW")
    for i in (4, 0, 3, 1):
        do(pair, v.command_for_move(i))
    assert v.score["X"] == 0                                   # nothing counted before the game ends
    do(pair, v.command_for_move(5))
    assert v.score == {"X": 1, "O": 0, "draws": 0}
    do(pair, "STATE")                                          # resync of the same finished game
    assert v.score["X"] == 1
    do(pair, "NEW")
    do(pair, "RESIGN")
    assert v.score == {"X": 1, "O": 0, "draws": 0}             # resign is not scored
    do(pair, "NEW")
    for i in (0, 1, 2, 4, 3, 5, 7, 6, 8):
        do(pair, v.command_for_move(i))
    assert v.score == {"X": 1, "O": 0, "draws": 1}
    do(pair, "DISCONNECT")
    assert v.score == {"X": 1, "O": 0, "draws": 1}             # survives a disconnect


def test_sound_wavs_are_valid():
    import io
    import wave
    import sounds
    for kind, notes in sounds.NOTES.items():
        w = wave.open(io.BytesIO(sounds.make_wav(notes)))
        ms = sum(m for _, m in notes)
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert abs(w.getnframes() - sounds.RATE * ms / 1000) < len(notes) + 1, kind


def test_play_uses_a_file_not_async_memory(monkeypatch, tmp_path):
    """winsound raises RuntimeError for SND_MEMORY | SND_ASYNC; mimic that and check play() works."""
    import sounds

    class FakeWinsound:
        SND_MEMORY, SND_ASYNC, SND_FILENAME = 0x4, 0x1, 0x20000
        calls = []

        @classmethod
        def PlaySound(cls, sound, flags):
            if flags & cls.SND_MEMORY and flags & cls.SND_ASYNC:
                raise RuntimeError("Cannot play asynchronously from memory")
            cls.calls.append((sound, flags))

    monkeypatch.setattr(sounds, "winsound", FakeWinsound)
    monkeypatch.setattr(sounds, "_files", {})
    monkeypatch.setattr(sounds.tempfile, "gettempdir", lambda: str(tmp_path))
    for kind in sounds.NOTES:
        sounds.play(kind)
    assert len(FakeWinsound.calls) == len(sounds.NOTES)          # every effect really played
    path, flags = FakeWinsound.calls[0]
    assert flags == FakeWinsound.SND_FILENAME | FakeWinsound.SND_ASYNC and os.path.exists(path)


def test_ai_game_reply_with_both_moves_is_drawn_and_x_moves_next():
    """NEW:AI then a MOVE whose reply already contains the computer's O (GameView.apply, no port)."""
    v = GameView()
    v.apply("NEW:AI", "OK:BOARD:.........")
    assert v.state == "IN_PROGRESS" and v.message == "X to move."
    v.apply("MOVE:0:X", "OK:BOARD:X...O....")
    assert v.board == "X...O...." and v.next_mark() == "X"
    v.apply("MOVE:1:X", "WIN:O:BOARD:XXO.O.O..")
    assert v.state == "GAME_OVER" and v.score["O"] == 1
