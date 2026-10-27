# Host-side unit tests for the portable game core (no board needed).
#   make -C tests/core test      build with warnings as errors + ASan/UBSan, run
#   make -C tests/core clean
CC      ?= gcc
SRC      = ../../firmware/Core/Src/game.c
INC      = -I../../firmware/Core/Inc
CFLAGS   = -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined \
           -fno-sanitize-recover=undefined $(INC)

test_game: test_game.c $(SRC) ../../firmware/Core/Inc/game.h
	$(CC) $(CFLAGS) test_game.c $(SRC) -o $@

test: test_game
	./test_game

clean:
	rm -f test_game

.PHONY: test clean
