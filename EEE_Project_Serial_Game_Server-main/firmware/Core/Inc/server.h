/**
  * server.h - line framer, parser and dispatcher for docs/protocol.md v1.0.
  *
  * PORTABLE C: no HAL/CMSIS. The same file runs on the STM32 and in the PC host
  * build (tests/host) so the pytest suite can exercise the real firmware logic.
  *
  * Byte-driven and non-blocking: the caller feeds one received byte at a time
  * (server_rx) and calls server_tick regularly. Each call writes at most ONE reply
  * (complete, with *HH checksum and LF) into the caller's buffer and returns its
  * length (0 = no reply). Nothing here ever waits.
  */
#ifndef SERVER_H
#define SERVER_H

#include <stddef.h>
#include <stdint.h>
#include "game.h"

#define SERVER_MAX_FRAME   32u    /* bytes before the LF, incl. CR and *HH (protocol 3) */
#define SERVER_TIMEOUT_MS  500u   /* partial-frame inactivity timeout (protocol 3)      */
#define SERVER_REPLY_MAX   40u    /* longest reply is 25 bytes; callers give this much  */

typedef enum { RX_IDLE = 0, RX_RECEIVING, RX_DISCARDING } rx_state_t;

typedef struct {
    game_t     game;                       /* the authoritative game (10 bytes) */
    uint8_t    ai;                         /* 1 = O is played by the server (NEW:AI) */
    rx_state_t rx;
    uint8_t    len;                        /* bytes held in buf                 */
    uint32_t   last_ms;                    /* time of the last received byte    */
    char       buf[SERVER_MAX_FRAME];
} server_t;

void   server_init(server_t *s);                         /* boot: IDLE, empty board  */
void   server_reset(server_t *s);                        /* button: IDLE, no message */
void   server_reset_framer(server_t *s);                 /* new link: drop partial frame, keep game */
size_t server_rx(server_t *s, uint8_t byte, uint32_t now_ms, char *out, size_t cap);
size_t server_tick(server_t *s, uint32_t now_ms, char *out, size_t cap);

/* Helpers exposed for unit tests. */
void server_checksum_hex(const char *body, size_t n, char out[3]);

#endif /* SERVER_H */
