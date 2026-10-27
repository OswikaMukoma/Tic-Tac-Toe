/* Exhaustive check of the server-side AI (firmware/Core/Src/ai.c) on the PC.
 * X tries EVERY possible sequence of moves; O is played by ai_pick().
 * Claims checked: ai_pick never returns an occupied or out-of-range cell, and X never wins. */
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "../../firmware/Core/Inc/game.h"
#include "../../firmware/Core/Inc/ai.h"

static long games, ai_moves, illegal, x_wins, o_wins, draws, bad_state;

static void play(game_t g)
{
    for (int i = 0; i < GAME_CELLS; i++) {
        if (g.board[i] != '.') { continue; }
        game_t h = g;
        game_result_t r;
        if (game_move(&h, i, 'X', &r) != GAME_OK) { illegal++; continue; }
        if (r == GAME_RESULT_WIN_X) { x_wins++; games++; continue; }
        if (r == GAME_RESULT_DRAW)  { draws++;  games++; continue; }
        int c = ai_pick(h.board);
        ai_moves++;
        if (c < 0 || c >= GAME_CELLS || h.board[c] != '.') { illegal++; continue; }
        if (game_move(&h, c, 'O', &r) != GAME_OK) { illegal++; continue; }
        if (r == GAME_RESULT_WIN_O) { o_wins++; games++; continue; }
        if (r == GAME_RESULT_DRAW)  { draws++;  games++; continue; }
        if (h.state != GAME_IN_PROGRESS) { bad_state++; }
        play(h);
    }
}

int main(void)
{
    game_t g;
    game_init(&g);
    game_new(&g);
    play(g);
    printf("games X can force by playing every line: %ld (O wins %ld, draws %ld, X wins %ld)\n",
           games, o_wins, draws, x_wins);
    printf("AI moves checked: %ld; illegal picks/moves: %ld; bad states: %ld\n", ai_moves, illegal, bad_state);

    /* timing of the slowest pick (X in a corner, O to answer) on this PC */
    char b[GAME_CELLS]; memset(b, '.', 9); b[0] = 'X';
    clock_t t0 = clock(); volatile int sink = 0;
    for (int k = 0; k < 2000; k++) { sink += ai_pick(b); }
    double us = (double)(clock() - t0) * 1e6 / CLOCKS_PER_SEC / 2000.0;
    printf("ai_pick after X in corner: %.1f us per call on this PC (first AI move; sink %d)\n", us, sink);
    int ok = (x_wins == 0 && illegal == 0 && bad_state == 0);
    printf(ok ? "PASS\n" : "FAIL\n");
    return ok ? 0 : 1;
}
