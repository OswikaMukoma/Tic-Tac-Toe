/**
  * game.c - Tic-Tac-Toe rules and server state machine (portable C, no HAL).
  * See game.h and docs/protocol.md sections 6 and 6.1.
  */
#include <stddef.h>
#include "game.h"

_Static_assert(sizeof(game_t) == GAME_CELLS + 1, "game_t must have no padding (tests memcmp it)");

/* The 8 winning lines: 3 rows, 3 columns, 2 diagonals. */
static const uint8_t LINES[8][3] = {
    {0, 1, 2}, {3, 4, 5}, {6, 7, 8},
    {0, 3, 6}, {1, 4, 7}, {2, 5, 8},
    {0, 4, 8}, {2, 4, 6}
};

static void clear_board(game_t *g)
{
    for (int i = 0; i < GAME_CELLS; i++) {
        g->board[i] = '.';
    }
}

static int has_line(const char board[GAME_CELLS], char mark)
{
    for (int l = 0; l < 8; l++) {
        if (board[LINES[l][0]] == mark &&
            board[LINES[l][1]] == mark &&
            board[LINES[l][2]] == mark) {
            return 1;
        }
    }
    return 0;
}

void game_init(game_t *g)
{
    clear_board(g);
    g->state = GAME_IDLE;
}

game_state_t game_get_state(const game_t *g)
{
    return (game_state_t)g->state;
}

char game_side_to_move(const game_t *g)
{
    int x = 0, o = 0;
    for (int i = 0; i < GAME_CELLS; i++) {
        if (g->board[i] == 'X') { x++; }
        else if (g->board[i] == 'O') { o++; }
    }
    return (x == o) ? 'X' : 'O';
}

game_result_t game_evaluate(const char board[GAME_CELLS])
{
    if (has_line(board, 'X')) { return GAME_RESULT_WIN_X; }
    if (has_line(board, 'O')) { return GAME_RESULT_WIN_O; }
    for (int i = 0; i < GAME_CELLS; i++) {
        if (board[i] == '.') { return GAME_RESULT_NONE; }
    }
    return GAME_RESULT_DRAW;
}

/* ---- state table (docs/protocol.md section 6) -------------------------------- */

game_err_t game_connect(game_t *g)
{
    /* IDLE: OK (stay).  IN_PROGRESS / GAME_OVER: NACK:STATE. */
    return (g->state == GAME_IDLE) ? GAME_OK : GAME_ERR_STATE;
}

game_err_t game_new(game_t *g)
{
    /* IDLE and GAME_OVER start a game; IN_PROGRESS must resign first. */
    if (g->state == GAME_IN_PROGRESS) {
        return GAME_ERR_STATE;                      /* validate ... */
    }
    clear_board(g);                                 /* ... then commit */
    g->state = GAME_IN_PROGRESS;
    return GAME_OK;
}

game_err_t game_query(const game_t *g)
{
    /* STATE: IDLE has no game; IN_PROGRESS and GAME_OVER reply with the board. */
    return (g->state == GAME_IDLE) ? GAME_ERR_NOGAME : GAME_OK;
}

game_err_t game_resign(game_t *g)
{
    if (g->state != GAME_IN_PROGRESS) {
        return GAME_ERR_NOGAME;
    }
    g->state = GAME_OVER;
    return GAME_OK;
}

game_err_t game_disconnect(game_t *g)
{
    if (g->state == GAME_IN_PROGRESS) {
        return GAME_ERR_STATE;                      /* resign first */
    }
    game_init(g);                                   /* IDLE stays IDLE; GAME_OVER -> IDLE */
    return GAME_OK;
}

/* ---- MOVE: validate-then-commit (docs/protocol.md section 6.1) ---------------- */

game_err_t game_move(game_t *g, int index, char mark, game_result_t *result)
{
    if (result != NULL) {
        *result = GAME_RESULT_NONE;
    }

    /* ---- validate: nothing below this line up to "commit" writes to *g ---- */
    if (g->state != GAME_IN_PROGRESS) {
        return GAME_ERR_NOGAME;
    }
    if (index < 0 || index >= GAME_CELLS) {
        return GAME_ERR_RANGE;
    }
    const char side = game_side_to_move(g);
    if (mark != 0 && mark != side) {
        return GAME_ERR_NOTURN;
    }
    if (g->board[index] != '.') {
        return GAME_ERR_OCCUPIED;
    }

    /* ---- commit ---- */
    g->board[index] = side;

    const game_result_t r = game_evaluate(g->board);
    if (r != GAME_RESULT_NONE) {
        g->state = GAME_OVER;
    }
    if (result != NULL) {
        *result = r;
    }
    return GAME_OK;
}

const char *game_err_name(game_err_t e)
{
    switch (e) {
    case GAME_ERR_NOGAME:   return "NOGAME";
    case GAME_ERR_STATE:    return "STATE";
    case GAME_ERR_RANGE:    return "RANGE";
    case GAME_ERR_NOTURN:   return "NOTURN";
    case GAME_ERR_OCCUPIED: return "OCCUPIED";
    default:                return NULL;
    }
}
