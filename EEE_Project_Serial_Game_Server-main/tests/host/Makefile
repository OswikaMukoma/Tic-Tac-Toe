# make -C tests/host        -> tests/host/host_server  (real firmware logic on the PC)
CFLAGS = -std=c11 -Wall -Wextra -Werror -O1 -I../../firmware/Core/Inc
host_server: host_server.c ../../firmware/Core/Src/server.c ../../firmware/Core/Src/game.c ../../firmware/Core/Src/ai.c
	$(CC) $(CFLAGS) -D_POSIX_C_SOURCE=200809L -o $@ $^
clean:
	rm -f host_server
