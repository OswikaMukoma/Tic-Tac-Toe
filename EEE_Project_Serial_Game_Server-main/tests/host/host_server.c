/* PC build of the REAL firmware logic (server.c + game.c) behind a TCP socket, so the
 * pytest suite can run against it:  pytest tests/ --port socket://127.0.0.1:5556
 * Linux/macOS only (POSIX sockets). Not part of the firmware. */
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include "server.h"

static uint32_t now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000u + ts.tv_nsec / 1000000u);
}

int main(int argc, char **argv)
{
    int port = (argc > 1) ? atoi(argv[1]) : 5556;
    int ls = socket(AF_INET, SOCK_STREAM, 0);
    int one = 1;
    setsockopt(ls, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    a.sin_port = htons((uint16_t)port);
    if (bind(ls, (struct sockaddr *)&a, sizeof a) || listen(ls, 1)) { perror("bind"); return 1; }
    fprintf(stderr, "host server on socket://127.0.0.1:%d\n", port);

    static server_t srv;
    server_init(&srv);
    for (;;) {
        int c = accept(ls, NULL, NULL);
        if (c < 0) { continue; }
        setsockopt(c, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
        server_reset_framer(&srv);
        for (;;) {
            struct pollfd p = { c, POLLIN, 0 };
            int r = poll(&p, 1, 5);
            char out[SERVER_REPLY_MAX];
            if (r > 0) {
                uint8_t buf[256];
                ssize_t n = read(c, buf, sizeof buf);
                if (n <= 0) { break; }
                for (ssize_t i = 0; i < n; i++) {
                    size_t k = server_rx(&srv, buf[i], now_ms(), out, sizeof out);
                    if (k) { if (write(c, out, k) < 0) { break; } }
                }
            }
            size_t k = server_tick(&srv, now_ms(), out, sizeof out);
            if (k) { if (write(c, out, k) < 0) { break; } }
        }
        close(c);
    }
}
