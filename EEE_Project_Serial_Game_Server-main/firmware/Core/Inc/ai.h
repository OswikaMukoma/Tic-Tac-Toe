/**
  * ai.h - server-side opponent for Tic-Tac-Toe (portable C, no HAL).
  *
  * The AI plays O. It only CHOOSES a cell; the move is then made through
  * game_move(), the same validate-then-commit path a client's move takes, so the
  * AI cannot make an illegal move or bypass the rules.
  */
#ifndef AI_H
#define AI_H
#include "game.h"

/* Best cell for O on this board (minimax with alpha-beta, lowest index on ties):
 * O never loses. Returns -1 if the board has no empty cell. Read-only on `board`. */
int ai_pick(const char board[GAME_CELLS]);

#endif
