# HANDOFF (overwrite this file at the end of every turn)

Partners: A = Oswika Mukoma (MKMOSW001), B = Hazel Kunyavapa (KNYCHI008)   |   Due: 25 Oct 2026 23:59   |   Today: 21 Oct

## State
- Stages 1-4 done. Stage 4 confirmed on the real board (21 Oct): USART1 PA9/PA10 AF1 115200 via
  ST-Link VCP (COM9 on owner's PC), SW0 = PA0 active low, PB10 red, PB11 green. Evidence in
  docs/evidence/stage4_bringup_check.txt and docs/bringup-log.md. Circuit diagram photo still open.
- Stages 5+6 WRITTEN, host-tested, NOT yet flashed: firmware/Core/Src/server.c (framer, parser,
  dispatcher), uart.c (IRQ + ring), main.c (loop, button, LED). All 100 pytest tests pass against
  the same server.c+game.c on the PC (docs/evidence/stage5_6_host_pytest.txt, D-017).
- Flash size 6.4 KB of 64 KB.

## Update 21 Oct 20:05: Stage 7 suite PASSES on the real board (100/100, 91.96 s). See D-018.
LED/button hand-check still to report. Owner's evidence commit (stage7_board_pytest.txt) is local
until the GitHub permission issue is fixed (the PC is signed in as hazelkkkkk; repo owner is OswikaMukoma),
then `git pull --rebase` and `git push`.

## Update 21 Oct ~21:30: Stage 8 GUI written + mock-tested (D-019)
Run on the board: `python gui\app.py --port COM9` (close terminals first). LED/SW0 hand-check DONE (D-021, owner report). Still to capture for the report: video/photos of LED states, play.py transcript, GUI run on the board, sound check. Earlier note: via
`python tests\play.py COM9`. Screenshots: docs/evidence/gui/, flowchart docs/diagrams/gui_flow.png.

## Next (steps 1-3 below are DONE)
1. Build: `make -C firmware` (normal image, no BRINGUP) -> firmware/build/SerialGameServer.hex/.elf
2. Flash with STM32_Programmer_CLI as in bringup-log.md (-c port=SWD -w ...elf -v -rst).
3. LED should be OFF (IDLE). Close any terminal, then `pytest tests/ --port COM9` (Stage 7). Save
   output to docs/evidence/stage7_board_pytest.txt. Do NOT open a terminal at the same time.
4. Manually: NEW -> LED green; MOVE -> alternates green/red; win/resign -> both blink 2 Hz;
   press SW0 -> LED off (IDLE) with no reply.
Then Stage 8 GUI (against `python tests/mock_server.py --listen 5555`), Stage 9 stretch only if time,
Stage 10 package + report (10 pages max, disclose AI use).

## Caveats still open
- Partner sign-off on protocol v1.0 (D-013); Stage 1 explain-back; test_game.c was rewritten earlier;
  the plan PDF has the 6 Oct dates; rejected-move LED blink is only an idea (not in spec).
- Schedule: due 25 Oct 23:59; cut stretch features first (undo, timer, AI).

## Build and test
make -C firmware ; make -C tests/core test ; make -C tests/host ; pytest tests/ --port mock
Host firmware logic: tests/host/host_server 5556 &  then  pytest tests/ --port socket://127.0.0.1:5556

## Update 26 Oct (evening): stretch AI merged
`NEW:AI` (server plays O, minimax) merged into main: protocol.md section 15, D-022, `firmware/Core/Src/ai.c`, `tests/test_ai.py` (13), `tests/core/test_ai.c`,
GUI "Play vs computer" checkbox. PC: 113/113 on the real C logic. Board: owner tested the game works; the saved pytest output of the AI firmware
and a re-run of `tests/measure_board.py` (M1-M5) on it are still to be put in docs/evidence and the report (placeholders).
