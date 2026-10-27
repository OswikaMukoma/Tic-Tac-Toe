/**
  * server.c - framer, parser and dispatcher (docs/protocol.md v1.0 sections 2-7).
  * Portable C, no HAL. See server.h.
  */
#include <string.h>
#include "server.h"
#include "ai.h"

#define LF 0x0A
#define CR 0x0D

static const char HEX_DIGITS[] = "0123456789ABCDEF";

void server_checksum_hex(const char *body, size_t n, char out[3])
{
    uint8_t x = 0;
    for (size_t i = 0; i < n; i++) { x ^= (uint8_t)body[i]; }
    out[0] = HEX_DIGITS[x >> 4];
    out[1] = HEX_DIGITS[x & 0x0F];
    out[2] = '\0';
}

/* Build "<body>*HH\n" into out. Returns its length, or 0 if it does not fit. */
static size_t make_reply(const char *body, char *out, size_t cap)
{
    size_t n = strlen(body);
    if (n + 4u > cap) { return 0; }
    memcpy(out, body, n);
    out[n] = '*';
    server_checksum_hex(body, n, &out[n + 1]);   /* writes 2 hex digits + NUL */
    out[n + 3] = '\n';
    return n + 4u;
}

static void reply_board(char *body, const char *prefix, const game_t *g)
{
    size_t p = strlen(prefix);
    memcpy(body, prefix, p);
    memcpy(body + p, g->board, GAME_CELLS);
    body[p + GAME_CELLS] = '\0';
}

static int is_hex_upper(char c) { return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'); }

/* ---- dispatch: one parsed, verified frame -> reply body ------------------------- */

static void reply_error(char *body, game_err_t e)
{
    strcpy(body, "NACK:");
    strcat(body, game_err_name(e));
}

static void do_move(server_t *s, const char *arg, size_t n, char *body)
{
    char mark = 0;
    if (n >= 2 && arg[n - 2] == ':') {                 /* optional ":X" / ":O" claim */
        mark = arg[n - 1];
        if (mark != 'X' && mark != 'O') { strcpy(body, "NACK:BADCMD"); return; }
        n -= 2;
    }
    size_t i = 0;
    int neg = 0;
    if (n > 0 && arg[0] == '-') { neg = 1; i = 1; }
    size_t digits = n - i;
    if (digits < 1u || digits > 3u) { strcpy(body, "NACK:BADCMD"); return; }
    int value = 0;
    for (; i < n; i++) {
        if (arg[i] < '0' || arg[i] > '9') { strcpy(body, "NACK:BADCMD"); return; }
        value = value * 10 + (arg[i] - '0');
    }
    if (neg) { value = -value; }

    game_result_t result;
    game_err_t e = game_move(&s->game, value, mark, &result);
    if (e != GAME_OK) { reply_error(body, e); return; }
    if (s->ai && result == GAME_RESULT_NONE && game_side_to_move(&s->game) == 'O') {
        /* NEW:AI game: the server answers with O's move, made through game_move() so it
         * is validated like any other move. The reply shows the board after both moves. */
        const int cell = ai_pick(s->game.board);
        if (cell >= 0) { (void)game_move(&s->game, cell, 'O', &result); }
    }
    switch (result) {
    case GAME_RESULT_WIN_X: reply_board(body, "WIN:X:BOARD:", &s->game); break;
    case GAME_RESULT_WIN_O: reply_board(body, "WIN:O:BOARD:", &s->game); break;
    case GAME_RESULT_DRAW:  reply_board(body, "DRAW:BOARD:", &s->game);  break;
    default:                reply_board(body, "OK:BOARD:", &s->game);    break;
    }
}

static void dispatch(server_t *s, const char *b, size_t n, char *body)
{
    game_err_t e;
    if (n == 7 && memcmp(b, "CONNECT", 7) == 0) {
        e = game_connect(&s->game);
        if (e == GAME_OK) { strcpy(body, "OK"); } else { reply_error(body, e); }
    } else if ((n == 3 && memcmp(b, "NEW", 3) == 0) || (n == 6 && memcmp(b, "NEW:AI", 6) == 0)) {
        e = game_new(&s->game);
        if (e == GAME_OK) { s->ai = (n == 6); reply_board(body, "OK:BOARD:", &s->game); } else { reply_error(body, e); }
    } else if (n == 5 && memcmp(b, "STATE", 5) == 0) {
        e = game_query(&s->game);
        if (e == GAME_OK) { reply_board(body, "BOARD:", &s->game); } else { reply_error(body, e); }
    } else if (n == 6 && memcmp(b, "RESIGN", 6) == 0) {
        e = game_resign(&s->game);
        if (e == GAME_OK) { strcpy(body, "OK:GAMEOVER"); } else { reply_error(body, e); }
    } else if (n == 10 && memcmp(b, "DISCONNECT", 10) == 0) {
        e = game_disconnect(&s->game);
        if (e == GAME_OK) { strcpy(body, "OK"); } else { reply_error(body, e); }
    } else if (n >= 5 && memcmp(b, "MOVE:", 5) == 0) {
        do_move(s, b + 5, n - 5, body);
    } else {
        strcpy(body, "NACK:BADCMD");
    }
}

/* ---- parse a complete frame (protocol.md 4): checks run in the documented order -- */

static size_t handle_frame(server_t *s, const char *raw, size_t n, char *out, size_t cap)
{
    char body[SERVER_REPLY_MAX];

    if (n > 0 && raw[n - 1] == (char)CR) { n--; }       /* one CR before the LF is dropped */

    int printable = (n > 0);
    for (size_t i = 0; i < n; i++) {
        uint8_t c = (uint8_t)raw[i];
        if (c < 0x20u || c > 0x7Eu) { printable = 0; break; }
    }
    if (!printable) {
        strcpy(body, "NACK:BADCMD");
        return make_reply(body, out, cap);
    }

    size_t blen = n;
    const char *star = memchr(raw, '*', n);
    if (star != NULL) {
        blen = (size_t)(star - raw);
        size_t rest = n - blen - 1u;
        const char *hh = star + 1;
        if (rest != 2u || !is_hex_upper(hh[0]) || !is_hex_upper(hh[1])) {
            strcpy(body, "NACK:BADSUM");              /* also covers a second '*' */
            return make_reply(body, out, cap);
        }
        char want[3];
        server_checksum_hex(raw, blen, want);
        if (want[0] != hh[0] || want[1] != hh[1]) {
            strcpy(body, "NACK:BADSUM");
            return make_reply(body, out, cap);
        }
    }

    dispatch(s, raw, blen, body);
    return make_reply(body, out, cap);
}

/* ---- framer (protocol.md 3): IDLE_RX / RECEIVING / DISCARDING -------------------- */

void server_reset_framer(server_t *s)
{
    s->rx = RX_IDLE;
    s->len = 0;
}

void server_init(server_t *s)
{
    game_init(&s->game);
    s->ai = 0;
    server_reset_framer(s);
    s->last_ms = 0;
}

void server_reset(server_t *s)
{
    server_init(s);
}

size_t server_rx(server_t *s, uint8_t byte, uint32_t now_ms, char *out, size_t cap)
{
    size_t n = 0;
    s->last_ms = now_ms;

    switch (s->rx) {
    case RX_IDLE:
    case RX_RECEIVING:
        if (byte == LF) {
            n = handle_frame(s, s->buf, s->len, out, cap);   /* len 0 = empty frame */
            server_reset_framer(s);
        } else if (s->len >= SERVER_MAX_FRAME) {              /* this is the 33rd byte */
            char body[SERVER_REPLY_MAX];
            strcpy(body, "NACK:TOOLONG");
            n = make_reply(body, out, cap);
            s->len = 0;
            s->rx = RX_DISCARDING;
        } else {
            s->buf[s->len++] = (char)byte;
            s->rx = RX_RECEIVING;
        }
        break;
    case RX_DISCARDING:
        if (byte == LF) { server_reset_framer(s); }           /* silent resync */
        break;
    }
    return n;
}

size_t server_tick(server_t *s, uint32_t now_ms, char *out, size_t cap)
{
    size_t n = 0;
    if (s->rx != RX_IDLE && (uint32_t)(now_ms - s->last_ms) >= SERVER_TIMEOUT_MS) {
        if (s->rx == RX_RECEIVING) {
            char body[SERVER_REPLY_MAX];
            strcpy(body, "NACK:TIMEOUT");
            n = make_reply(body, out, cap);
        }                                                     /* DISCARDING: silent */
        server_reset_framer(s);
    }
    return n;
}
