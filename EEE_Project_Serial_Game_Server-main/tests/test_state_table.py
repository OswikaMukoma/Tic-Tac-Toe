"""Every cell of the protocol.md section 5 state table (6 commands x 3 states)."""
import pytest

CMDS = ["CONNECT", "NEW", "MOVE:0", "STATE", "RESIGN", "DISCONNECT"]
STATES = ["IDLE", "IN_PROGRESS", "GAME_OVER"]

# (state, command) -> (reply prefix, next state)
TABLE = {
    ("IDLE", "CONNECT"): ("OK", "IDLE"),
    ("IDLE", "NEW"): ("OK:BOARD:.........", "IN_PROGRESS"),
    ("IDLE", "MOVE:0"): ("NACK:NOGAME", "IDLE"),
    ("IDLE", "STATE"): ("NACK:NOGAME", "IDLE"),
    ("IDLE", "RESIGN"): ("NACK:NOGAME", "IDLE"),
    ("IDLE", "DISCONNECT"): ("OK", "IDLE"),
    ("IN_PROGRESS", "CONNECT"): ("NACK:STATE", "IN_PROGRESS"),
    ("IN_PROGRESS", "NEW"): ("NACK:STATE", "IN_PROGRESS"),
    ("IN_PROGRESS", "MOVE:0"): ("OK:BOARD:X........", "IN_PROGRESS"),
    ("IN_PROGRESS", "STATE"): ("BOARD:.........", "IN_PROGRESS"),
    ("IN_PROGRESS", "RESIGN"): ("OK:GAMEOVER", "GAME_OVER"),
    ("IN_PROGRESS", "DISCONNECT"): ("NACK:STATE", "IN_PROGRESS"),
    ("GAME_OVER", "CONNECT"): ("NACK:STATE", "GAME_OVER"),
    ("GAME_OVER", "NEW"): ("OK:BOARD:.........", "IN_PROGRESS"),
    ("GAME_OVER", "MOVE:0"): ("NACK:NOGAME", "GAME_OVER"),
    ("GAME_OVER", "STATE"): ("BOARD:.........", "GAME_OVER"),
    ("GAME_OVER", "RESIGN"): ("NACK:NOGAME", "GAME_OVER"),
    ("GAME_OVER", "DISCONNECT"): ("OK", "IDLE"),
}


def enter(link, state):
    if state != "IDLE":
        assert link.request("NEW") == "OK:BOARD:........."
    if state == "GAME_OVER":
        assert link.request("RESIGN") == "OK:GAMEOVER"


def probe(link):
    """Observe the state without changing it: STATE, then an out-of-range MOVE."""
    if link.request("STATE") == "NACK:NOGAME":
        return "IDLE"
    return "IN_PROGRESS" if link.request("MOVE:9") == "NACK:RANGE" else "GAME_OVER"


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("cmd", CMDS)
def test_cell(link, state, cmd):
    enter(link, state)
    reply, nxt = TABLE[(state, cmd)]
    assert link.request(cmd) == reply
    assert probe(link) == nxt
