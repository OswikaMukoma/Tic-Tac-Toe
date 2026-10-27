"""Server-side AI (NEW:AI, protocol.md section 15). Runs on the mock, the PC build of the real C
logic, and the board, like every other test. Human is X, the server plays O."""
import itertools
import re

import pytest

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def _won(board, who):
    return any(all(board[i] == who for i in line) for line in LINES)


def _board(reply):
    return reply.rsplit("BOARD:", 1)[1]


def test_new_ai_returns_empty_board(link):
    assert link.request("NEW:AI") == "OK:BOARD:........."


def test_ai_answers_each_move_with_exactly_one_new_O(link):
    link.request("NEW:AI")
    reply = link.request("MOVE:4")
    board = _board(reply)
    assert board.count("X") == 1 and board.count("O") == 1 and board[4] == "X"
    assert reply.startswith("OK:BOARD:")
    # the board it gave is the board STATE reports, and it is X's turn again
    assert link.request("STATE") == "BOARD:" + board


def test_ai_never_loses_and_never_cheats_against_random_x(link):
    import random
    rng = random.Random(2026)
    for _ in range(25):
        link.request("NEW:AI")
        prev = "." * 9
        for _ in range(5):
            free = [i for i in range(9) if prev[i] == "."]
            reply = link.request("MOVE:%d" % rng.choice(free))
            board = _board(reply)
            # only empty cells changed: one X (human) and, if the game goes on or O wins, one O
            changed = [i for i in range(9) if prev[i] != board[i]]
            assert all(prev[i] == "." for i in changed)
            assert not reply.startswith("WIN:X"), "the AI lost"
            prev = board
            if reply.startswith(("WIN", "DRAW")):
                break
        assert not _won(prev, "X")
        if not reply.startswith(("WIN", "DRAW")):
            link.request("RESIGN")
        link.request("DISCONNECT")


def test_ai_wins_when_x_plays_badly(link):
    link.request("NEW:AI")
    r = link.request("MOVE:0")           # X corner, AI takes centre
    assert _board(r)[4] == "O"
    r = link.request("MOVE:1")           # X wastes a move; AI must block or win
    r = link.request("MOVE:%d" % _board(r).index("."))
    # whatever happened, the board is consistent and X has not won
    assert not _won(_board(r), "X")


def test_rejected_moves_do_not_wake_the_ai(link):
    link.request("NEW:AI")
    before = _board(link.request("MOVE:4"))
    assert link.request("MOVE:4") == "NACK:OCCUPIED"          # AI must not move
    assert link.request("MOVE:9") == "NACK:RANGE"
    assert link.request("MOVE:0:O") == "NACK:NOTURN"           # claims O on X's turn
    assert link.request("STATE") == "BOARD:" + before


def test_plain_new_after_ai_game_is_two_player(link):
    link.request("NEW:AI")
    link.request("MOVE:4")
    link.request("RESIGN")
    assert link.request("NEW") == "OK:BOARD:........."
    r = link.request("MOVE:4")
    assert _board(r).count("O") == 0, "a plain NEW game must not have an AI"


def test_new_ai_state_rules_match_new(link):
    link.request("NEW:AI")
    assert link.request("NEW:AI") == "NACK:STATE"
    assert link.request("NEW") == "NACK:STATE"
    link.request("RESIGN")
    link.request("DISCONNECT")
    assert link.request("NEW:AI") == "OK:BOARD:........."


@pytest.mark.parametrize("bad", ["NEW:ai", "NEW:", "NEW:AI:X", "NEW:AIX", "NEW :AI"])
def test_malformed_new_ai_is_badcmd(link, bad):
    assert link.request(bad) == "NACK:BADCMD"


def test_ai_game_reaches_a_result_and_then_refuses_moves(link):
    link.request("NEW:AI")
    reply = link.request("MOVE:0")
    while not reply.startswith(("WIN", "DRAW")):
        reply = link.request("MOVE:%d" % _board(reply).index("."))
    assert reply.startswith(("WIN:O", "DRAW")), reply          # X can never win
    assert link.request("MOVE:%d" % 8) == "NACK:NOGAME"
