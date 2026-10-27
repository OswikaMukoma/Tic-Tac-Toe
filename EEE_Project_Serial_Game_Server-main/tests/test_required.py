"""Cases the brief requires, written from docs/protocol.md."""
from protocol_lib import EMPTY_BOARD


def test_connect_in_idle(link):
    assert link.request("CONNECT") == "OK"


def test_new_game_returns_empty_board(link):
    assert link.request("NEW") == "OK:BOARD:" + EMPTY_BOARD


def test_valid_move_updates_board(link):
    link.request("NEW")
    assert link.request("MOVE:4") == "OK:BOARD:....X...."
    assert link.request("MOVE:0") == "OK:BOARD:O...X...."


def test_occupied(link):
    link.request("NEW"); link.request("MOVE:4")
    assert link.request("MOVE:4") == "NACK:OCCUPIED"
    assert link.request("STATE") == "BOARD:....X...."


def test_range(link):
    link.request("NEW")
    for i in ("9", "-1", "99", "100", "999"):
        assert link.request("MOVE:" + i) == "NACK:RANGE"
    assert link.request("STATE") == "BOARD:" + EMPTY_BOARD


def test_wrong_turn(link):
    link.request("NEW")
    assert link.request("MOVE:0:O") == "NACK:NOTURN"
    assert link.request("MOVE:0:X") == "OK:BOARD:X........"
    assert link.request("MOVE:1:X") == "NACK:NOTURN"
    assert link.request("STATE") == "BOARD:X........"


def test_move_without_game(link):
    assert link.request("MOVE:0") == "NACK:NOGAME"


def test_bad_command(link):
    for body in ("HELLO", "move:0", "MOVE", "MOVE:", "MOVE:4X", "MOVE:a", "CONNECT:1"):
        assert link.request(body) == "NACK:BADCMD", body


def test_x_wins_then_no_more_moves(link):
    link.request("NEW")
    for i in (4, 0, 3, 1):
        assert link.request("MOVE:%d" % i).startswith("OK:BOARD:")
    assert link.request("MOVE:5") == "WIN:X:BOARD:OO.XXX..."
    assert link.request("MOVE:2") == "NACK:NOGAME"
    assert link.request("STATE") == "BOARD:OO.XXX..."


def test_o_wins(link):
    link.request("NEW")
    for i in (0, 3, 1, 4, 8):
        link.request("MOVE:%d" % i)
    assert link.request("MOVE:5") == "WIN:O:BOARD:XX.OOO..X"


def test_draw(link):
    link.request("NEW")
    seq = [0, 1, 2, 4, 3, 5, 7, 6]
    for i in seq:
        assert link.request("MOVE:%d" % i).startswith("OK:BOARD:")
    assert link.request("MOVE:8") == "DRAW:BOARD:XOXXOOOXX"
    assert link.request("MOVE:0") == "NACK:NOGAME"


def test_resign_and_new_after(link):
    link.request("NEW")
    assert link.request("RESIGN") == "OK:GAMEOVER"
    assert link.request("NEW") == "OK:BOARD:" + EMPTY_BOARD


def test_disconnect_returns_to_idle(link):
    link.request("NEW"); link.request("RESIGN")
    assert link.request("DISCONNECT") == "OK"
    assert link.request("STATE") == "NACK:NOGAME"


# ---- every winning line, for both players --------------------------------------
import itertools  # noqa: E402

import pytest  # noqa: E402

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def _has_line(cells):
    return any(set(l) <= set(cells) for l in LINES)


def _script(line, winner):
    """Move order (X first) in which `winner` completes `line` on its last move and the
    other side has no line."""
    others = [c for c in range(9) if c not in line]
    n_other = 2 if winner == "X" else 3
    for fill in itertools.permutations(others, n_other):
        if _has_line(fill):
            continue
        seq = []
        for k in range(3):
            if winner == "X":
                seq += [line[k]] + ([fill[k]] if k < 2 else [])
            else:
                seq += [fill[k]] + [line[k]]
        return seq
    raise AssertionError("no script")


@pytest.mark.parametrize("winner", ["X", "O"])
@pytest.mark.parametrize("line", LINES)
def test_each_line_wins(link, line, winner):
    seq = _script(line, winner)
    link.request("NEW")
    for i in seq[:-1]:
        assert link.request("MOVE:%d" % i).startswith("OK:BOARD:")
    board = ["."] * 9
    for n, i in enumerate(seq):
        board[i] = "XO"[n % 2]
    assert link.request("MOVE:%d" % seq[-1]) == "WIN:%s:BOARD:%s" % (winner, "".join(board))
    assert link.request("MOVE:%d" % next(c for c in range(9) if board[c] == ".")) == "NACK:NOGAME"
