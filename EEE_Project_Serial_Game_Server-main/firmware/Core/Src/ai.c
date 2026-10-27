/**
  * ai.c - perfect-play O opponent (minimax with alpha-beta pruning, portable C).
  * Scores are from O's point of view: +1 O wins, 0 draw, -1 X wins.
  * Recursion depth is at most 9 and the working board is a 9-byte copy.
  */
#include "ai.h"

static int search(char b[GAME_CELLS], char turn, int alpha, int beta)
{
    switch (game_evaluate(b)) {
    case GAME_RESULT_WIN_O: return 1;
    case GAME_RESULT_WIN_X: return -1;
    case GAME_RESULT_DRAW:  return 0;
    default: break;
    }
    const char other = (turn == 'O') ? 'X' : 'O';
    int best = (turn == 'O') ? -2 : 2;
    for (int i = 0; i < GAME_CELLS; i++) {
        if (b[i] != '.') { continue; }
        b[i] = turn;
        const int v = search(b, other, alpha, beta);
        b[i] = '.';
        if (turn == 'O') {
            if (v > best) { best = v; }
            if (best > alpha) { alpha = best; }
        } else {
            if (v < best) { best = v; }
            if (best < beta) { beta = best; }
        }
        if (alpha >= beta) { break; }
    }
    return best;
}

int ai_pick(const char board[GAME_CELLS])
{
    char b[GAME_CELLS];
    for (int i = 0; i < GAME_CELLS; i++) { b[i] = board[i]; }
    int best = -2, pick = -1;
    for (int i = 0; i < GAME_CELLS; i++) {
        if (b[i] != '.') { continue; }
        b[i] = 'O';
        const int v = search(b, 'X', -2, 2);
        b[i] = '.';
        if (v > best) { best = v; pick = i; }
    }
    return pick;
}
