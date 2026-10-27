# Decisions log (append-only)

Status: PROPOSED until both partners agree, then ACCEPTED. Never edit a past
entry; add a new one that supersedes it. This feeds report section A.4.

## D-001 Game: Tic-Tac-Toe - PROPOSED (2026-10-06)
Baseline game, 3x3 board, simple win/draw. Marks come from correctness,
robustness and evidence, not game complexity, so the time saved goes into tests
and the report. Alternative considered: Connect-4 (only if Tic-Tac-Toe is solid).

## D-002 Stretch features and order - PROPOSED (2026-10-06)
Compulsory system first. Then: server-side AI (minimax; server plays so the
client stays untrusted), hardware-timer move clock, move undo. Bonus is capped
at 5 marks, so none of this may endanger the core. Skipped: two-client play
(single UART), hidden-information games.

## D-003 UART driven through CMSIS registers, no HAL UART - PROPOSED (2026-10-06)
The course base includes no stm32f0xx_hal_uart.c. The brief allows "HAL
libraries or direct register access". Register-level USART with an RX interrupt
and ring buffer is small and easy to explain. Alternative: add HAL UART sources
from STM32CubeF0 and enable HAL_UART_MODULE_ENABLED in stm32f0xx_hal_conf.h.
UART instance and pins: see OPEN Q1 in docs/stages.md (not decided).

## D-004 Integrity: checksum scheme - OPEN
Brief recommends a per-message checksum or CRC. Options: `*XX` XOR of payload
bytes, or CRC-8. Decide when writing protocol.md (Stage 1).

## D-005 Separate project repo, base copied from Practical2_A - ACCEPTED (2026-10-06)
The brief requires a link to the repo housing the server, and the course repo
holds lab work. Copied only infrastructure from Practical_2/Practical2_A: HAL
and CMSIS drivers, startup file, linker script, system/syscalls/interrupt files
and the Makefile (adapted). Not copied: the practical's task files, handout or
board_io. List this as reused material in the report references.

## D-006 Build system: Makefile + arm-none-eabi-gcc - ACCEPTED (2026-10-06)
Matches the course base. Imports into STM32CubeIDE as "Existing Code as Makefile
Project". No .ioc file: peripherals are configured in code, so CubeMX is optional.
Stage 0 check: base builds (flash 3164 B, RAM 1584 B with the placeholder main).

## D-007 AI assistance - ACCEPTED (2026-10-06)
No course restriction on AI use. We use Claude for drafting; both partners must
be able to explain every line. Disclose in the report references.

## D-008 UART path: on-board ST-Link virtual COM port, USART1 PA9/PA10 - ACCEPTED (2026-10-06)
Supersedes open question Q1. Source: lecturer's announcement (newer UCT dev
board: USART1 PA9 = TX, PA10 = RX is already wired to the ST-Link, which shows
up as a serial port on the PC over the same USB cable used for flashing) and
Board.md. The external STM32USB2UART adapter is NOT used; the lecturer asked for
those to be returned. No extra wiring: the circuit diagram (A.3) shows one USB
cable, ST-Link, USART1 PA9/PA10. Still to confirm on the bench: alternate-function
number (STM32F051 datasheet AF table), baud (115200 8N1 proposed), and the PC
port name (changes per machine and USB socket; tests take --port).

## D-009 Team confirmation of the approach - ACCEPTED (2026-10-12)
Team confirmed the plan on 12 Oct. Records D-001 (Tic-Tac-Toe), D-002 (stretch
order AI, timer, undo), D-003 (UART via CMSIS registers) and the GUI library
(Tkinter) as accepted.

## D-010 Checksum: XOR, written *HH - ACCEPTED (2026-10-12), closes D-004
XOR of all body bytes as two uppercase hex digits. Chosen over CRC-8 because it
is trivial to implement on a Cortex-M0, easy to explain and test, and fits the
brief's "checksum or CRC recommended". Known limit: misses swapped bytes and
paired errors; state this in the report. Mandatory on server replies, optional
but verified on client requests (so a terminal can still be used by hand).

## D-011 Protocol v0.1 design choices - PROPOSED (2026-10-12), freeze after review
See docs/protocol.md section 12 for the six items to review: terminal replies
carry the board; optional :<mark> on MOVE (makes NACK:NOTURN testable with one
client); extra codes TOOLONG/TIMEOUT/BADSUM/STATE; checksum optional on
requests; DISCONNECT accepted in IDLE; button = local reset to IDLE with no
unsolicited message. Other fixed choices: 115200 8N1, LF terminator (CR
tolerated), max frame 32 bytes, 500 ms inactivity timeout, exactly one reply
per frame, no unsolicited server messages in the core protocol.

## D-012 Compressed schedule - ACCEPTED (2026-10-12)
Stage 1 started on 12 Oct, about four days behind the 6 Oct plan. Remaining
window is 12-24 Oct (25 Oct is a Sunday and buffer only). Required features
come first; if time runs short, cut stretch features in this order: undo,
timer, then AI. See docs/stages.md "Revised schedule".

## D-013 Protocol v1.0 frozen - ACCEPTED (2026-10-12), closes D-011
All six items in protocol.md section 12 were accepted unchanged by the project
owner on 12 Oct. The protocol is frozen at v1.0 and any later change goes through
the change log (protocol.md section 14). Note: acceptance was recorded from the
project owner's message; the second partner's separate sign-off is not recorded
here. If they object, raise it before Stage 5 so firmware is not built on a
changing spec.

## D-014 Stage 3 test design: mock over TCP + mutation check - ACCEPTED (2026-10-12)
The mock server is an independent Python implementation of protocol.md, served on a
local TCP port and opened with pyserial's `socket://127.0.0.1:PORT` URL, so tests, GUI
and the real board (a COM port) share one code path; works on Windows (no pty).
Tests only use the serial link and are written from the protocol, not the mock code.
To show the tests can fail, `tests/mutation_check.py` injects 15 deliberate faults
into the mock; each must make pytest fail. The first run caught 14/15: a broken
2-4-6 diagonal went unnoticed, so tests for all 8 lines x 2 players were added
(now 15/15, docs/evidence/stage3_mutation_check.txt). Limit: this validates the
tests, not the firmware; the same suite runs on the board in Stage 7.

## D-015 Stage 4 bring-up image is a separate build - ACCEPTED (2026-10-12)
`make -C firmware BRINGUP=1` builds firmware/build/bringup/BringUp.* from
Core/Src/bringup.c (polled USART1 at 115200, LED colour test, banner TX, echo,
SW0 test). It prints on the UART, which the game image must never do, so it is
a separate image, not a flag inside the game. UART_AF is deliberately NOT
defined in board.h: I could not read Table 14 of the datasheet from here (the
fetched text had Table 13 only; HAL gpio_ex.h lists USART1 under both AF0 and
AF1 without saying which pins), so the build stops with #error until a partner
reads the value from Table 14 and records it in bringup-log.md. BRR is
(8 MHz + 57600) / 115200 = 69, about 0.6 % baud error at 8 MHz HSI.

## D-016 USART1 alternate function = AF1 on PA9/PA10 - ACCEPTED (2026-10-12), closes the open part of D-015
Read from the STM32F051 datasheet (DocID022265 Rev 4) Table 14, page 37, in the PDF the
project owner supplied: PA9 AF1 = USART1_TX, PA10 AF1 = USART1_RX. board.h now defines
UART_AF 1u. The UCT dev board schematic v1.06 (supplied) agrees with the pin plan: ST-Link
VCP_RX/TX on PA9/PA10, SW0 on PA0, R/G LED on PB10/PB11 (R12 red, R13 green), D8 power LED.
This is paper confirmation only; the bench tests in HANDOFF still have to pass.

## D-017 Firmware architecture for Stages 5-6 - ACCEPTED (2026-10-21)
server.c/.h (portable, no HAL) holds the framer, parser and dispatcher and is driven one byte
at a time (server_rx) plus a periodic server_tick; each call writes at most one complete reply.
uart.c is the only USART1 code: RX interrupt into a 128-byte ring (drops are counted, never
silent), TX polled and bounded (a reply is at most 25 bytes, ~2.2 ms, while the RX interrupt
keeps filling the ring). main.c is only the loop: drain ring -> server_rx -> send reply, tick,
button (PA0, 30 ms debounce, press = server_reset, no message), LED (protocol.md section 9).
Proof method: tests/host/host_server.c builds the SAME server.c + game.c for the PC behind a TCP
socket; `pytest tests/ --port socket://127.0.0.1:5556` ran all 100 tests against it (100 passed,
docs/evidence/stage5_6_host_pytest.txt). That proves the logic, not the UART/LED/button glue,
which is verified on the board in Stage 7. Bug caught while writing: the tick timestamp had to be
read after draining the ring, otherwise now < last_ms underflows into a false NACK:TIMEOUT.

## D-018 Stage 7 result: full suite passes on the real board - RECORDED (2026-10-21)
`pytest tests --port COM9` against SerialGameServer.hex (built from a86f8c5): 100 passed in 91.96 s,
including the 5 slow timeout tests (partial-frame NACK:TIMEOUT within 0.4-0.9 s, silent DISCARDING
timeout, inactivity timer restart, no unsolicited replies). Evidence: docs/evidence/stage7_board_pytest.txt
(committed on the owner's PC; push pending a GitHub permission fix) and stage7_board_pytest_partial.txt.
Still to confirm by hand: LED (green = X, red = O, blink = game over) and SW0 reset.

## D-019 GUI design (Stage 8) - ACCEPTED (2026-10-21)
Tkinter (D-009), split into gui/client.py (protocol client + GameView, no Tk, unit-tested headless in
tests/gui, 8 tests) and gui/app.py (window). Rules: board drawn only from a verified reply, never from a
click; rejected moves change only the message; moves disabled after WIN/DRAW/RESIGN; NACK:NOGAME while the
GUI thinks a game runs = device was reset, go to start screen; a lost reply triggers one STATE (protocol 10);
CONNECT answered NACK:STATE is resolved with DISCONNECT (finished game -> idle, reconnect) or STATE (game
running -> resync) because BOARD: alone cannot tell IN_PROGRESS from GAME_OVER. MOVE sends the claimed mark
derived from the last confirmed board so a stale client gets NACK:NOTURN from the device. Worker thread for
serial I/O. Screenshots made headlessly (gui/make_screenshots.py, docs/evidence/gui/) against the mock; the
run on the real board is still to be done by the owner. Known limit: hot-seat only (one client, both sides).

## D-020 GUI theme, score and sound (owner's request) - ACCEPTED (2026-10-21)
Owner asked for a warm amber board (reference: wooden tiles, brown X, white O), a score counter and sound.
Board is now a Tk Canvas (gui/app.py); look is cosmetic only. Score = X wins / draws / O wins, kept in
GameView.score, increased ONLY by a confirmed WIN/DRAW reply to a MOVE (not by a STATE resync, not by RESIGN),
survives disconnect, "Reset score" button. Sound (gui/sounds.py): tones generated in memory, played with
winsound on Windows, Tk bell elsewhere; on/off checkbox; chosen only from confirmed replies (placed X/O,
error, win, draw, resign, new game, connect). Cannot be heard in the build sandbox: owner to confirm on Windows.

## D-021 Stage 6 hardware behaviour confirmed by the owner (2026-10-21)
With the game firmware on the board and tests/play.py: NEW turns the LED green (X to move), MOVE:4 turns it red
(O to move), RESIGN makes it flash (GAME_OVER), pressing SW0 switches it off (local reset to IDLE). Reported by
the owner in chat; for the report, capture a short video or photo of each LED state and a play.py transcript
showing STATE -> NACK:NOGAME after SW0 (not yet captured).

## D-022 (26 Oct 2026, branch stretch-ai) Server-side AI as `NEW:AI`
Chose an opt-in command instead of changing `NEW`, so v1.0 behaviour and all 100 existing tests are untouched. The AI flag lives in
`server_t`, not `game_t`, so the 10-byte game structure and the 50.5 M-check core tests are unchanged. The AI only picks a cell;
the move goes through `game_move()`. Reply carries the board after both moves, which keeps one reply per frame and needs no unsolicited
message. Minimax with alpha-beta rather than a heuristic so that "X never wins" can be proven by exhaustive test (tests/core/test_ai.c).
