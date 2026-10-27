/**
  * test_game.c - host-side unit tests for the portable game core (firmware/Core/Src/game.c).
  *
  * Built with the host compiler plus AddressSanitizer and UndefinedBehaviorSanitizer:
  *     make -C tests/core test
  *
  * What these tests prove (each maps to a requirement in the brief / protocol.md):
  *   1. Win/draw detection         - all 8 lines for both marks, and the full game tree.
  *   2. State table (section 6)    - every command in every state: reply AND next state.
  *   3. Move validation (6.1)      - RANGE / NOTURN / OCCUPIED / NOGAME and their order.
  *   4. "A rejection changes nothing" - memcmp of the whole game before and after,
  *      on hand-written cases, on every node of the full game tree, and on random calls.
  *   5. Scripted games from protocol.md section 8 (X win, O win, draw).
  */
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "game.h"

/* ------------------------------------------------------------------ tiny harness */
static long g_checks = 0;
static long g_failed = 0;

#define CHECK(cond)                                                            \
    do {                                                                       \
        g_checks++;                                                            \
        if (!(cond)) {                                                         \
            g_failed++;                                                        \
            if (g_failed <= 25) {                                              \
                printf("    FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);     \
            }                                                                  \
        }                                                                      \
    } while (0)

#define RUN(fn)                                                                \
    do {                                                                       \
        long before_fail = g_failed, before_checks = g_checks;                 \
        fn();                                                                  \
        printf("%s  %-34s (%ld checks)\n", (g_failed == before_fail) ? "PASS" : "FAIL", \
               #fn, g_checks - before_checks);                                 \
    } while (0)

/* ------------------------------------------------------------------ helpers */
static int same(const game_t *a, const game_t *b)
{
    return memcmp(a, b, sizeof(game_t)) == 0;
}

static int board_is(const game_t *g, const char *nine)
{
    return memcmp(g->board, nine, GAME_CELLS) == 0;
}

static int is_empty_board(const game_t *g)
{
    return board_is(g, ".........");
}

/* Play one accepted move for the side to move (no mark claimed). */
static game_result_t play(game_t *g, int index)
{
    game_result_t r = GAME_RESULT_NONE;
    game_err_t e = game_move(g, index, 0, &r);
    CHECK(e == GAME_OK);
    return r;
}

/* The four ways the tests reach each server state. */
enum { S_IDLE, S_IN_PROGRESS, S_OVER_WIN, S_OVER_RESIGN, S_COUNT };

static void make_state(game_t *g, int which)
{
    game_init(g);
    switch (which) {
    case S_IDLE:
        break;
    case S_IN_PROGRESS:                     /* X has played cell 0 */
        CHECK(game_new(g) == GAME_OK);
        play(g, 0);
        break;
    case S_OVER_WIN:                        /* protocol.md 8.1: X wins on 3-4-5 */
        CHECK(game_new(g) == GAME_OK);
        play(g, 4); play(g, 0); play(g, 3); play(g, 1);
        CHECK(play(g, 5) == GAME_RESULT_WIN_X);
        break;
    case S_OVER_RESIGN:
        CHECK(game_new(g) == GAME_OK);
        play(g, 0);
        CHECK(game_resign(g) == GAME_OK);
        break;
    default:
        break;
    }
}

/* Whole-game invariants that must hold after ANY sequence of calls. */
static void check_invariants(const game_t *g)
{
    int x = 0, o = 0;
    for (int i = 0; i < GAME_CELLS; i++) {
        CHECK(g->board[i] == '.' || g->board[i] == 'X' || g->board[i] == 'O');
        if (g->board[i] == 'X') { x++; }
        if (g->board[i] == 'O') { o++; }
    }
    CHECK(x == o || x == o + 1);                       /* X moves first, strict alternation */
    CHECK(g->state <= GAME_OVER);
    if (g->state == GAME_IDLE) {
        CHECK(is_empty_board(g));
    }
    if (g->state == GAME_IN_PROGRESS) {
        CHECK(game_evaluate(g->board) == GAME_RESULT_NONE);   /* a finished board never stays IN_PROGRESS */
    }
    CHECK(game_side_to_move(g) == ((x == o) ? 'X' : 'O'));
}

/* ------------------------------------------------------------------ 1. init and evaluate */
static void test_init(void)
{
    game_t g;
    memset(&g, 0xA5, sizeof g);                        /* start from garbage */
    game_init(&g);
    CHECK(game_get_state(&g) == GAME_IDLE);
    CHECK(is_empty_board(&g));
    CHECK(game_side_to_move(&g) == 'X');
}

static void test_evaluate_all_lines(void)
{
    static const int lines[8][3] = {
        {0,1,2},{3,4,5},{6,7,8},{0,3,6},{1,4,7},{2,5,8},{0,4,8},{2,4,6}
    };
    const char marks[2] = { 'X', 'O' };
    for (int l = 0; l < 8; l++) {
        for (int m = 0; m < 2; m++) {
            char b[GAME_CELLS];
            memset(b, '.', sizeof b);
            for (int k = 0; k < 2; k++) {              /* two in a row is NOT a win */
                b[lines[l][k]] = marks[m];
            }
            CHECK(game_evaluate(b) == GAME_RESULT_NONE);
            b[lines[l][2]] = marks[m];                  /* three in a row is */
            CHECK(game_evaluate(b) == (marks[m] == 'X' ? GAME_RESULT_WIN_X : GAME_RESULT_WIN_O));
        }
    }
    CHECK(game_evaluate(".........") == GAME_RESULT_NONE);
    CHECK(game_evaluate("XOXXOOOXX") == GAME_RESULT_DRAW);   /* protocol.md 8.3 */
    CHECK(game_evaluate("XXXOOXOXO") == GAME_RESULT_WIN_X);  /* full board, but a line: win beats draw */
    CHECK(game_evaluate("XO.XO.O.X") == GAME_RESULT_NONE);   /* empty cells and no line: game goes on */
}

/* ------------------------------------------------------------------ 2. state table */
typedef game_err_t (*cmd_fn)(game_t *);

static game_err_t cmd_connect(game_t *g)    { return game_connect(g); }
static game_err_t cmd_new(game_t *g)        { return game_new(g); }
static game_err_t cmd_query(game_t *g)      { return game_query(g); }
static game_err_t cmd_resign(game_t *g)     { return game_resign(g); }
static game_err_t cmd_disconnect(game_t *g) { return game_disconnect(g); }
static game_err_t cmd_move4(game_t *g)      { return game_move(g, 4, 0, NULL); }

typedef struct {
    const char  *name;
    cmd_fn       fn;
    /* Expected reply and next state for IDLE, IN_PROGRESS, GAME_OVER (protocol.md section 6). */
    game_err_t   err[3];
    game_state_t next[3];
} row_t;

static const row_t TABLE[] = {
    /* name          fn              IDLE                 IN_PROGRESS           GAME_OVER */
    { "CONNECT",    cmd_connect,
        { GAME_OK,          GAME_ERR_STATE,      GAME_ERR_STATE },
        { GAME_IDLE,        GAME_IN_PROGRESS,    GAME_OVER } },
    { "NEW",        cmd_new,
        { GAME_OK,          GAME_ERR_STATE,      GAME_OK },
        { GAME_IN_PROGRESS, GAME_IN_PROGRESS,    GAME_IN_PROGRESS } },
    { "MOVE",       cmd_move4,
        { GAME_ERR_NOGAME,  GAME_OK,             GAME_ERR_NOGAME },
        { GAME_IDLE,        GAME_IN_PROGRESS,    GAME_OVER } },
    { "STATE",      cmd_query,
        { GAME_ERR_NOGAME,  GAME_OK,             GAME_OK },
        { GAME_IDLE,        GAME_IN_PROGRESS,    GAME_OVER } },
    { "RESIGN",     cmd_resign,
        { GAME_ERR_NOGAME,  GAME_OK,             GAME_ERR_NOGAME },
        { GAME_IDLE,        GAME_OVER,           GAME_OVER } },
    { "DISCONNECT", cmd_disconnect,
        { GAME_OK,          GAME_ERR_STATE,      GAME_OK },
        { GAME_IDLE,        GAME_IN_PROGRESS,    GAME_IDLE } },
};

static void test_state_table(void)
{
    /* GAME_OVER is reached two ways (a win and a resign); the table must hold for both. */
    static const int how[S_COUNT] = { 0, 1, 2, 2 };     /* column in the table */
    for (size_t r = 0; r < sizeof TABLE / sizeof TABLE[0]; r++) {
        for (int s = 0; s < S_COUNT; s++) {
            game_t g, before;
            make_state(&g, s);
            before = g;
            const int col = how[s];
            game_err_t e = TABLE[r].fn(&g);
            if (e != TABLE[r].err[col] || game_get_state(&g) != TABLE[r].next[col]) {
                printf("    table mismatch: %s in state %d\n", TABLE[r].name, s);
            }
            CHECK(e == TABLE[r].err[col]);
            CHECK(game_get_state(&g) == TABLE[r].next[col]);
            if (e != GAME_OK) {
                CHECK(same(&g, &before));                /* a NACK changes nothing */
            }
            check_invariants(&g);
        }
    }
}

static void test_state_table_side_effects(void)
{
    game_t g;

    make_state(&g, S_OVER_WIN);                          /* NEW from GAME_OVER: fresh board */
    CHECK(game_new(&g) == GAME_OK);
    CHECK(is_empty_board(&g));

    make_state(&g, S_OVER_WIN);                          /* DISCONNECT from GAME_OVER: back to IDLE, board cleared */
    CHECK(game_disconnect(&g) == GAME_OK);
    CHECK(game_get_state(&g) == GAME_IDLE);
    CHECK(is_empty_board(&g));

    make_state(&g, S_IN_PROGRESS);                       /* RESIGN keeps the board for STATE */
    CHECK(game_resign(&g) == GAME_OK);
    CHECK(board_is(&g, "X........"));
    CHECK(game_query(&g) == GAME_OK);

    make_state(&g, S_IN_PROGRESS);                       /* local reset (button) from any state */
    game_init(&g);
    CHECK(game_get_state(&g) == GAME_IDLE);
    CHECK(is_empty_board(&g));
    CHECK(game_move(&g, 4, 0, NULL) == GAME_ERR_NOGAME); /* the client finds out on its next MOVE */
}

/* ------------------------------------------------------------------ 3 + 4. move rejections */
static void expect_reject(game_t *g, int index, char mark, game_err_t want)
{
    game_t before = *g;
    game_result_t r = GAME_RESULT_WIN_X;                 /* must be reset by the call */
    game_err_t e = game_move(g, index, mark, &r);
    CHECK(e == want);
    CHECK(r == GAME_RESULT_NONE);
    CHECK(same(g, &before));
}

static void test_move_rejections(void)
{
    game_t g;
    game_init(&g);
    CHECK(game_new(&g) == GAME_OK);
    play(&g, 4);                                         /* "....X....", O to move */
    CHECK(game_side_to_move(&g) == 'O');

    /* RANGE */
    static const int bad_idx[] = { -1, 9, 10, 99, 100, 999, INT_MIN, INT_MAX, -9 };
    for (size_t i = 0; i < sizeof bad_idx / sizeof bad_idx[0]; i++) {
        expect_reject(&g, bad_idx[i], 0, GAME_ERR_RANGE);
        expect_reject(&g, bad_idx[i], 'O', GAME_ERR_RANGE);
    }
    /* NOTURN: X claims while O is to move; 'Z' is never the side to move */
    expect_reject(&g, 0, 'X', GAME_ERR_NOTURN);
    expect_reject(&g, 8, 'X', GAME_ERR_NOTURN);
    expect_reject(&g, 0, 'Z', GAME_ERR_NOTURN);
    /* OCCUPIED: with and without the right claim */
    expect_reject(&g, 4, 0,   GAME_ERR_OCCUPIED);
    expect_reject(&g, 4, 'O', GAME_ERR_OCCUPIED);

    /* Order of checks (protocol.md 6.1): state, range, turn, occupancy. */
    expect_reject(&g, 9, 'X', GAME_ERR_RANGE);           /* range beats turn */
    expect_reject(&g, 4, 'X', GAME_ERR_NOTURN);          /* turn beats occupancy */

    game_t idle;
    game_init(&idle);
    expect_reject(&idle, 99, 'Z', GAME_ERR_NOGAME);      /* state beats everything */
    game_t over;
    make_state(&over, S_OVER_WIN);
    expect_reject(&over, 99, 'Z', GAME_ERR_NOGAME);
    expect_reject(&over, 2, 0,   GAME_ERR_NOGAME);       /* move after game over */

    /* Recovery: after all those rejections a legal move still works. */
    game_result_t r;
    CHECK(game_move(&g, 0, 'O', &r) == GAME_OK);
    CHECK(r == GAME_RESULT_NONE);
    CHECK(board_is(&g, "O...X...."));
    check_invariants(&g);
}

static void test_claimed_mark_matches_unclaimed(void)
{
    /* A correct claim must behave exactly like no claim. */
    for (int first = 0; first < GAME_CELLS; first++) {
        game_t a, b;
        game_init(&a); game_new(&a); play(&a, first);
        b = a;
        const int idx = (first + 1) % GAME_CELLS;
        game_result_t ra, rb;
        CHECK(game_move(&a, idx, 0, &ra) == GAME_OK);
        CHECK(game_move(&b, idx, game_side_to_move(&b), &rb) == GAME_OK);
        CHECK(same(&a, &b));
        CHECK(ra == rb);
    }
}

/* ------------------------------------------------------------------ 5. scripted games */
static void test_scripted_x_win(void)
{
    /* protocol.md 8.1 */
    static const struct { int idx; const char *board; game_result_t res; } steps[] = {
        { 4, "....X....", GAME_RESULT_NONE },
        { 0, "O...X....", GAME_RESULT_NONE },
        { 3, "O..XX....", GAME_RESULT_NONE },
        { 1, "OO.XX....", GAME_RESULT_NONE },
        { 5, "OO.XXX...", GAME_RESULT_WIN_X },
    };
    game_t g;
    game_init(&g);
    CHECK(game_connect(&g) == GAME_OK);
    CHECK(game_new(&g) == GAME_OK);
    for (size_t i = 0; i < sizeof steps / sizeof steps[0]; i++) {
        game_result_t r;
        CHECK(game_move(&g, steps[i].idx, 0, &r) == GAME_OK);
        CHECK(r == steps[i].res);
        CHECK(board_is(&g, steps[i].board));
        CHECK(game_get_state(&g) == (steps[i].res == GAME_RESULT_NONE ? GAME_IN_PROGRESS : GAME_OVER));
    }
    expect_reject(&g, 2, 'O', GAME_ERR_NOGAME);          /* game is over */
    CHECK(game_query(&g) == GAME_OK);
    CHECK(game_disconnect(&g) == GAME_OK);
    CHECK(game_get_state(&g) == GAME_IDLE);
}

static void test_scripted_o_win(void)
{
    static const int moves[] = { 0, 3, 1, 4, 8, 5 };     /* O completes 3-4-5 */
    game_t g;
    game_init(&g); game_new(&g);
    for (size_t i = 0; i < sizeof moves / sizeof moves[0]; i++) {
        game_result_t r = play(&g, moves[i]);
        CHECK(r == (i == 5 ? GAME_RESULT_WIN_O : GAME_RESULT_NONE));
    }
    CHECK(board_is(&g, "XX.OOO..X"));
    CHECK(game_get_state(&g) == GAME_OVER);
    check_invariants(&g);
}

static void test_scripted_draw(void)
{
    /* protocol.md 8.3: X:0,2,3,7,8  O:1,4,5,6 - no earlier position has a winner. */
    static const int moves[] = { 0, 1, 2, 4, 7, 6, 3, 5, 8 };
    game_t g;
    game_init(&g); game_new(&g);
    for (size_t i = 0; i < sizeof moves / sizeof moves[0]; i++) {
        game_result_t r = play(&g, moves[i]);
        CHECK(r == (i == 8 ? GAME_RESULT_DRAW : GAME_RESULT_NONE));
    }
    CHECK(board_is(&g, "XOXXOOOXX"));
    CHECK(game_get_state(&g) == GAME_OVER);
    expect_reject(&g, 0, 0, GAME_ERR_NOGAME);
}

/* ------------------------------------------------------------------ exhaustive game tree */
typedef struct {
    long terminal, win_x, win_o, draw;
    long by_len_win_x[10], by_len_win_o[10], by_len_draw[10];
    long positions;                 /* every reachable position, including terminal ones */
    long illegal_probes;
} tree_t;

/* Visit every position reachable by legal play. At every position, try every
 * (index, mark) pair: legal ones recurse, illegal ones must be rejected without
 * touching a single byte. */
static void walk(const game_t *node, int depth, tree_t *t)
{
    t->positions++;
    check_invariants(node);

    static const char marks[3] = { 0, 'X', 'O' };
    const char side = game_side_to_move(node);
    for (int idx = 0; idx < GAME_CELLS; idx++) {
        for (int m = 0; m < 3; m++) {
            const int legal = (node->board[idx] == '.') && (marks[m] == 0 || marks[m] == side);
            game_t g = *node;
            game_result_t r = GAME_RESULT_WIN_X;
            game_err_t e = game_move(&g, idx, marks[m], &r);
            if (!legal) {
                t->illegal_probes++;
                CHECK(e != GAME_OK);
                CHECK(same(&g, node));
                continue;
            }
            CHECK(e == GAME_OK);
            if (m != 0) {
                continue;                      /* claimed-mark twin of the unclaimed move: don't recurse twice */
            }
            const int len = depth + 1;
            if (r == GAME_RESULT_NONE) {
                CHECK(game_get_state(&g) == GAME_IN_PROGRESS);
                walk(&g, len, t);
            } else {
                CHECK(game_get_state(&g) == GAME_OVER);
                t->terminal++;
                if (r == GAME_RESULT_WIN_X)      { t->win_x++; t->by_len_win_x[len]++; }
                else if (r == GAME_RESULT_WIN_O) { t->win_o++; t->by_len_win_o[len]++; }
                else                             { t->draw++;  t->by_len_draw[len]++;  }
                t->positions++;
                check_invariants(&g);
                CHECK(game_move(&g, 0, 0, NULL) == GAME_ERR_NOGAME);   /* nothing is playable after the end */
            }
        }
    }
}

static void test_exhaustive_game_tree(void)
{
    static tree_t t;
    memset(&t, 0, sizeof t);
    game_t g;
    game_init(&g);
    CHECK(game_new(&g) == GAME_OK);
    walk(&g, 0, &t);

    /* Reference numbers: counted independently with a separate Python brute force
     * (see docs/evidence/stage2_core_tests.txt) and matching the published totals. */
    CHECK(t.terminal == 255168);
    CHECK(t.win_x == 131184);
    CHECK(t.win_o == 77904);
    CHECK(t.draw == 46080);
    CHECK(t.by_len_win_x[5] == 1440);
    CHECK(t.by_len_win_o[6] == 5328);
    CHECK(t.by_len_win_x[7] == 47952);
    CHECK(t.by_len_win_o[8] == 72576);
    CHECK(t.by_len_win_x[9] == 81792);
    CHECK(t.by_len_draw[9] == 46080);
    CHECK(t.positions == 549946);
    printf("      games %ld (X wins %ld, O wins %ld, draws %ld), positions %ld, illegal probes rejected %ld\n",
           t.terminal, t.win_x, t.win_o, t.draw, t.positions, t.illegal_probes);
}

/* ------------------------------------------------------------------ random call sequences */
static uint32_t g_rng = 12345u;
static uint32_t rnd(void)
{
    g_rng = g_rng * 1664525u + 1013904223u;     /* numerical-recipes LCG: fixed seed, repeatable */
    return g_rng >> 8;
}

static void test_random_calls(void)
{
    enum { N = 2000000 };
    long applied[6] = {0}, rejected[6] = {0}, wins = 0, draws = 0;
    game_t g;
    game_init(&g);

    for (long i = 0; i < N; i++) {
        game_t before = g;
        /* Mostly MOVEs, so that games really reach a win or a draw. The five other
         * commands are interleaved at 2.5% each. (An earlier version picked all six
         * uniformly; a coverage guard below caught that it almost never finished a game.) */
        const uint32_t pick = rnd() % 40u;
        const int op = (pick < 5u) ? (int)pick : 5;                /* 0..4 commands, 5 = MOVE */
        game_err_t e;
        game_result_t res = GAME_RESULT_NONE;
        int idx;
        if (rnd() % 4u != 0u) {                                    /* 3 times in 4: aim at an empty cell */
            int empties[GAME_CELLS], n = 0;
            for (int c = 0; c < GAME_CELLS; c++) {
                if (g.board[c] == '.') { empties[n++] = c; }
            }
            idx = (n > 0) ? empties[rnd() % (uint32_t)n] : 0;
        } else {
            idx = (int)(rnd() % 16u) - 3;                          /* -3 .. 12, mostly invalid or occupied */
        }
        const char side_now = game_side_to_move(&g);
        const uint32_t pm = rnd() % 6u;
        const char mark = (pm < 2u) ? 0                            /* no claim            */
                        : (pm < 4u) ? side_now                     /* correct claim       */
                        : (pm == 4u) ? (side_now == 'X' ? 'O' : 'X')   /* wrong side      */
                        : 'Z';                                     /* not a side at all   */

        switch (op) {
        case 0:  e = game_connect(&g);                     break;
        case 1:  e = game_new(&g);                         break;
        case 2:  e = game_query(&g);                       break;
        case 3:  e = game_resign(&g);                      break;
        case 4:  e = game_disconnect(&g);                  break;
        default: e = game_move(&g, idx, mark, &res);       break;
        }

        if (e != GAME_OK) {
            rejected[op]++;
            CHECK(same(&g, &before));                      /* the central claim */
        } else {
            applied[op]++;
            switch (op) {
            case 0: CHECK(before.state == GAME_IDLE && same(&g, &before)); break;
            case 1: CHECK(before.state != GAME_IN_PROGRESS);
                    CHECK(g.state == GAME_IN_PROGRESS && is_empty_board(&g)); break;
            case 2: CHECK(before.state != GAME_IDLE && same(&g, &before)); break;
            case 3: CHECK(before.state == GAME_IN_PROGRESS && g.state == GAME_OVER);
                    CHECK(memcmp(g.board, before.board, GAME_CELLS) == 0); break;
            case 4: CHECK(before.state != GAME_IN_PROGRESS);
                    CHECK(g.state == GAME_IDLE && is_empty_board(&g)); break;
            default: {
                int diff = 0;
                for (int c = 0; c < GAME_CELLS; c++) {
                    if (g.board[c] != before.board[c]) {
                        diff++;
                        CHECK(before.board[c] == '.' && g.board[c] == game_side_to_move(&before) && c == idx);
                    }
                }
                CHECK(before.state == GAME_IN_PROGRESS && diff == 1);
                CHECK(res == game_evaluate(g.board));
                CHECK(g.state == (res == GAME_RESULT_NONE ? GAME_IN_PROGRESS : GAME_OVER));
                if (res == GAME_RESULT_WIN_X || res == GAME_RESULT_WIN_O) { wins++; }
                if (res == GAME_RESULT_DRAW) { draws++; }
                break; }
            }
        }
        check_invariants(&g);
    }
    static const char *names[6] = { "CONNECT", "NEW", "STATE", "RESIGN", "DISCONNECT", "MOVE" };
    printf("      %d random calls, seed 12345 (applied/rejected):", (int)N);
    for (int o = 0; o < 6; o++) { printf(" %s %ld/%ld;", names[o], applied[o], rejected[o]); }
    printf("\n      games ended by a win %ld, by a draw %ld\n", wins, draws);
    /* Coverage guard: the random run must really exercise both outcomes of every command. */
    for (int o = 0; o < 6; o++) {
        CHECK(applied[o] > 1000);
        CHECK(rejected[o] > 1000);
    }
    CHECK(wins > 1000);
    CHECK(draws > 100);
}

/* ------------------------------------------------------------------ error names */
static void test_error_names(void)
{
    CHECK(strcmp(game_err_name(GAME_ERR_NOGAME), "NOGAME") == 0);
    CHECK(strcmp(game_err_name(GAME_ERR_STATE), "STATE") == 0);
    CHECK(strcmp(game_err_name(GAME_ERR_RANGE), "RANGE") == 0);
    CHECK(strcmp(game_err_name(GAME_ERR_NOTURN), "NOTURN") == 0);
    CHECK(strcmp(game_err_name(GAME_ERR_OCCUPIED), "OCCUPIED") == 0);
    CHECK(game_err_name(GAME_OK) == NULL);
}

int main(void)
{
    printf("game core tests (firmware/Core/Src/game.c)\n");
    RUN(test_init);
    RUN(test_evaluate_all_lines);
    RUN(test_state_table);
    RUN(test_state_table_side_effects);
    RUN(test_move_rejections);
    RUN(test_claimed_mark_matches_unclaimed);
    RUN(test_scripted_x_win);
    RUN(test_scripted_o_win);
    RUN(test_scripted_draw);
    RUN(test_exhaustive_game_tree);
    RUN(test_random_calls);
    RUN(test_error_names);
    printf("\n%ld checks, %ld failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}
