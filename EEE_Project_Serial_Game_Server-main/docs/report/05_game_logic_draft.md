# Report draft - Game logic and server authority (brief section 5)

DRAFT written from the actual code and test output on 12 Oct. **Rewrite in your own
words** and have the partner who did not drive this stage check every claim against
`firmware/Core/Src/game.c` and `docs/evidence/stage2_core_tests.txt`. Cut to fit the
10-page limit; the claims and the numbers are what matter.

## 5.1 Where the rules live

All game state is one 10-byte structure (`game_t`: nine cells and a state byte) owned by
the STM32. The rules are in `game.c`, a portable C file with no hardware calls, so the same
source is compiled for the Cortex-M0 (about 530 bytes of flash) and unit-tested on a PC.
The client never sees this structure; it receives only confirmed text replies.

The server state machine (IDLE, IN_PROGRESS, GAME_OVER) is implemented as one function per
protocol command (`game_connect`, `game_new`, `game_move`, `game_query`, `game_resign`,
`game_disconnect`). Each function returns `GAME_OK` or exactly one error that maps to one
`NACK` code, so the reply for every cell of the state table is decided in one place.

## 5.2 Validation and turn control

`MOVE` checks run in a fixed order (protocol.md 6.1): game running (`NOGAME`), index in 0..8
(`RANGE`), the claimed mark equals the side to move (`NOTURN`), target cell empty
(`OCCUPIED`). The side to move is derived from the board (X when the counts are equal,
otherwise O), so there is no separate turn variable that could disagree with the board.

Excerpt for the Implementation section (`game_move`):

```c
/* ---- validate: nothing below this line up to "commit" writes to *g ---- */
if (g->state != GAME_IN_PROGRESS)  { return GAME_ERR_NOGAME; }
if (index < 0 || index >= GAME_CELLS) { return GAME_ERR_RANGE; }
const char side = game_side_to_move(g);
if (mark != 0 && mark != side)     { return GAME_ERR_NOTURN; }
if (g->board[index] != '.')        { return GAME_ERR_OCCUPIED; }

/* ---- commit ---- */
g->board[index] = side;
const game_result_t r = game_evaluate(g->board);
if (r != GAME_RESULT_NONE) { g->state = GAME_OVER; }
```

## 5.3 Win and draw detection

After every committed move the whole board is evaluated against the eight winning lines
(three rows, three columns, two diagonals). A completed line ends the game with `WIN:<mark>`;
a full board with no line is a draw. The line check runs before the full-board check, so a
move that fills the last cell and completes a line is a win, not a draw.

## 5.4 Why a rejected request cannot change state

Argument by construction: in `game_move` every `return` of an error code comes before the
first write to the game (the commit block), and the checks only read it. The other commands
are the same shape: one condition, then at most one state change. There is no error path
that has already modified anything, so there is nothing to undo.

Evidence that the argument holds (all in `docs/evidence/stage2_core_tests.txt`):

- **Byte comparison.** Every test that expects an error copies the whole 10-byte game first
  and compares it with `memcmp` afterwards.
- **Whole game tree.** The test visits all 549,946 positions reachable by legal play and, at
  each one, tries every index with no claim, an X claim and an O claim. It rejected
  6,859,116 illegal attempts, and every one left the game byte-identical.
- **Random calls.** 2,000,000 random calls with a fixed seed (all six commands, indices from
  -3 to 12, marks 0, X, O and a nonsense one), checking invariants after each call. About 1.75
  million were move attempts; 22,948 games ended in a win and 3,003 in a draw.
- **Independent check of the rules.** A separate Python brute force counts every possible
  game: 255,168 games, of which 131,184 are X wins, 77,904 are O wins and 46,080 are draws.
  The C code, driven only through `game_move`, reproduces these numbers and also the number of
  games of each length (for example 1,440 X wins in five moves).

## 5.5 Limits of this evidence

These tests cover the game core on its own. They do not cover framing, checksums or reply
formatting (Stages 5 and 6), and they run on a PC, not on the board. The claim for the whole
system rests on the same invariants being tested over the serial link (Stages 3 and 7).
The random test uses one fixed seed, so it is repeatable rather than broad.
