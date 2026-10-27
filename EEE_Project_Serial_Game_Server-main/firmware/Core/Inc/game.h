/**
  * game.h - Tic-Tac-Toe rules and server state machine (portable C).
  *
  * NO HAL / CMSIS / hardware calls in game.c or this header, so the same code is
  * compiled for the Cortex-M0 and unit-tested on a PC (tests/core).
  *
  * Implements the state table and validation order of docs/protocol.md
  * (v1.0, sections 6 and 6.1):
  *
  *   - Every function that can fail follows VALIDATE-THEN-COMMIT: all checks run
  *     first and only read the game; the game is modified only after every check
  *     has passed. A function that returns an error has changed nothing.
  *   - The text protocol (framing, checksum, parsing, reply formatting) is NOT here;
  *     the dispatcher calls these functions and formats the reply.
  */
#ifndef GAME_H
#define GAME_H

#include <stdint.h>

#define GAME_CELLS 9

typedef enum {
    GAME_IDLE = 0,       /* boot, and after disconnect or local reset */
    GAME_IN_PROGRESS,
    GAME_OVER
} game_state_t;

/* Error codes map 1:1 to the move/state NACKs in protocol.md section 7.
 * Framing/parse errors (TOOLONG, TIMEOUT, BADSUM, BADCMD) belong to the parser. */
typedef enum {
    GAME_OK = 0,
    GAME_ERR_NOGAME,     /* needs an active game and there is none   -> NACK:NOGAME   */
    GAME_ERR_STATE,      /* valid command, not allowed in this state -> NACK:STATE    */
    GAME_ERR_RANGE,      /* move index outside 0..8                  -> NACK:RANGE    */
    GAME_ERR_NOTURN,     /* claimed mark is not the side to move     -> NACK:NOTURN   */
    GAME_ERR_OCCUPIED    /* target cell already holds a mark         -> NACK:OCCUPIED */
} game_err_t;

/* Outcome of an accepted move. */
typedef enum {
    GAME_RESULT_NONE = 0,   /* game continues       -> OK:BOARD:<9>   */
    GAME_RESULT_WIN_X,      /* X completed a line   -> WIN:X:BOARD:<9> */
    GAME_RESULT_WIN_O,      /* O completed a line   -> WIN:O:BOARD:<9> */
    GAME_RESULT_DRAW        /* board full, no line  -> DRAW:BOARD:<9>  */
} game_result_t;

/* The whole authoritative state. 10 bytes, no padding, so two copies can be
 * compared with memcmp (the tests rely on this to prove "NACK changes nothing"). */
typedef struct {
    char    board[GAME_CELLS];   /* '.', 'X' or 'O'; index 0..8; NOT NUL-terminated */
    uint8_t state;               /* a game_state_t value                            */
} game_t;

/* Boot state and local (button) reset: IDLE with an empty board. Never fails. */
void game_init(game_t *g);

/* Protocol commands. Each returns GAME_OK or one error and obeys the state table. */
game_err_t game_connect(game_t *g);      /* CONNECT    */
game_err_t game_new(game_t *g);          /* NEW        */
game_err_t game_query(const game_t *g);  /* STATE: OK means "reply with the board" */
game_err_t game_resign(game_t *g);       /* RESIGN     */
game_err_t game_disconnect(game_t *g);   /* DISCONNECT */

/* MOVE. `index` is the parsed decimal value (any int; out of 0..8 is RANGE).
 * `mark` is 0 for "no claim", or 'X'/'O' for "I claim to be this side". Any other
 * value never matches the side to move, so it is rejected as NOTURN.
 * Check order (protocol.md 6.1): state (NOGAME), range, turn, occupancy, commit.
 * `result` may be NULL; it is set to GAME_RESULT_NONE and only changed on success. */
game_err_t game_move(game_t *g, int index, char mark, game_result_t *result);

/* Helpers (read-only). */
game_state_t  game_get_state(const game_t *g);
char          game_side_to_move(const game_t *g);        /* 'X' when #X == #O, else 'O' */
game_result_t game_evaluate(const char board[GAME_CELLS]); /* win / draw / none for a board */

/* Suffix of the NACK for an error ("OCCUPIED" for NACK:OCCUPIED), NULL for GAME_OK. */
const char *game_err_name(game_err_t e);

#endif /* GAME_H */
