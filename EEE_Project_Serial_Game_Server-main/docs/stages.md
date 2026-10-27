# Stages and checklists

Each stage: Orient -> Build -> Verify -> Explain-back -> Break it -> Document
and hand off. Driver prompts; navigator reviews and signs off. Swap drivers each
stage. "Done" means tests run, both partners can explain it, docs updated.

Drivers below are a suggestion (A/B) - fill in names in HANDOFF.md.

## Stage 0 - Setup (both) - DONE
- [x] Repo layout, CLAUDE.md, HANDOFF.md, decisions.md, this file
- [x] Firmware base copied from course Practical2_A, builds with arm-none-eabi-gcc
- [ ] Create the GitHub repo and push (needed: report item 10 links to it)
- [ ] Partners confirm decisions D-001..D-004 in decisions.md
- [ ] Project plan (brief A.1) with milestones and task allocation

## Stage 1 - Protocol and FSM spec (A) - DONE 12 Oct (v1.0 frozen)
- [x] docs/protocol.md: framing, 32-byte max, 500 ms timeout, XOR checksum,
      every command and error, full state table, validation order, invariants
- [x] Diagrams in docs/diagrams (FSM, framer, two sequence diagrams) + render.sh
- [x] Example checksums verified by script; example games replayed on a model
- [x] Section 12 reviewed and accepted; frozen as v1.0 (D-013)
- [ ] Explain-back: each partner explains the framer states and the validation
      order in their own words (ask Claude for a quiz)

## Stage 2 - Portable game core (B)
- [x] game.c/.h, no HAL calls: board, validate-then-commit, win/draw, error codes
- [x] PC unit tests: all 8 win lines, draw, every rejection, rejected move leaves
      board byte-identical
- [x] Report section draft (game logic and server authority)

## Stage 3 - Mock server and pytest harness (A)
- [x] Python mock server implementing protocol.md
- [x] pytest covering every bullet of the brief's test list + garbage input
- [x] `--port` option / env var; first evidence saved

## Stage 4 - Hardware bring-up (B)
- [x] UART path settled: ST-Link VCP, USART1 PA9/PA10 (D-008). Confirm AF number and port name on the bench
- [x] (prepared, needs board) Transmit test ("Welcome to Binary" from the UART tutorial) readable in a terminal
- [x] Line-echo test: PC sends a line, board echoes it (proves RX before the framer)
- [x] Button and LED confirmed on the pins in firmware/Core/Inc/board.h
- [ ] Circuit diagram (brief A.3): one USB cable -> ST-Link -> USART1 PA9/PA10; label button and LED; photo of the setup
- [x] Terminal screenshot + notes in docs/bringup-log.md and docs/evidence/

### Q1 - UART path: RESOLVED (decision D-008)
Newer UCT dev board (lecturer's announcement): USART1 PA9 = TX, PA10 = RX is
wired to the on-board ST-Link, which appears as a virtual COM port on the PC
through the flashing USB cable. No adapter, no extra wiring. Do not use the
STM32USB2UART adapter.
Still to confirm at the bench:
1. Alternate-function number for PA9/PA10 from the STM32F051 datasheet AF table
   (do not guess; name the table in the report).
2. The PC port name (COMx / /dev/ttyACMx), recorded in bringup-log.md. It changes
   with machine and USB socket, so tests use `--port`, never a hard-coded name.
3. Only one program may hold the port: close PuTTY/screen before running pytest.
4. PA2/PA3 are buttons SW2/SW3; USART2 there is not free (not needed).

## Stage 5 - Firmware framing (A)
- [x] USART RX interrupt, ring buffer, line framer (max length, timeout, oversize -> NACK:BADCMD)
- [x] No blocking in parser; no extra output on the game UART
- [ ] Robustness report section draft

## Stage 6 - Firmware FSM and dispatcher (B)
- [x] Command handlers on game.c; state table enforced (NOGAME / NOTURN)
- [x] Button = new game, LED = turn / game over

## Stage 7 - Hardware integration (A)
- [x] Full pytest suite passing against the real board (100/100, 21 Oct); output saved to evidence/
- [ ] Serial captures of garbage / partial-frame recovery

## Stage 8 - GUI (B)
- [x] (mock-tested; board run pending) Connect, new game, move, specific NACK text, win/draw notice, moves disabled
      after game over, clean disconnect; redraw only from valid responses
- [x] GUI flowchart, screenshots (mock; redo screenshots on the board)

## Stage 9 - Stretch features (A then B)
- [ ] Server-side AI (test: never illegal)
- [ ] Hardware-timer move clock
- [ ] Move undo (documented protocol departure)

## Stage 10 - Freeze and package (both)
- [ ] Code freeze; demo video recorded and linked
- [ ] IEEE report, max 10 pages incl. references, items 1-11 of the brief
- [ ] Archive tested in a clean folder; build/run instructions followed literally
- [ ] 25 Oct is buffer only

## Revised schedule (12 Oct; replaces the 6 Oct dates)
Stage 4 does not depend on the protocol, so the partner with the board can start
it today while the other reviews Stage 1.

| Dates | Work | Who |
|---|---|---|
| 12-13 Oct | Stage 1 review + freeze. Stage 4 bring-up (blink, transmit, echo) in parallel | A reviews; B has the board |
| 13-15 Oct | Stage 2 game core (PC unit tests) and Stage 3 mock server + pytest, in parallel | B and A |
| 15-17 Oct | Stage 5 framing and Stage 6 FSM/dispatcher/button/LED | A and B |
| 17-19 Oct | Stage 7 integration: full pytest on the real board | both present |
| 17-20 Oct | Stage 8 GUI (can start against the mock as soon as Stage 3 is done) | B |
| 20-22 Oct | Stage 9 stretch: AI first; timer, undo only if time allows | A, then B |
| 22 Oct | Code freeze | |
| 22-24 Oct | Stage 10 video, report, clean-folder test | both |
| 25 Oct | buffer only | |

Milestones: M1 protocol frozen 13 Oct, M2 required tests pass on the mock 15 Oct,
M3 UART link works 13 Oct, M4 full suite passes on the board 19 Oct, M5 GUI
complete 20 Oct, M6 code freeze 22 Oct, M7 report and video done 24 Oct.
