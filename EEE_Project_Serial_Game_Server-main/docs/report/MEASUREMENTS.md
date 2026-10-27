# What the report may claim, and where each number comes from

Rule: every number in the report is copied from a file below, and says whether it came from the
**board** or from the **PC**. If it is not in this list, do not write it.

## A. Already measured (evidence is in the repo)

| Claim | Number | Where | Source |
|---|---|---|---|
| Full test suite on the real board | 100 passed in 91.96 s (29 required/win-line, 18 state-table, 53 robustness) | docs/evidence/stage7_board_pytest.txt | BOARD |
| UART link works | TX lines and echo correct at 115200 8N1 on COM9; PA9/PA10 use AF1 | docs/evidence/stage4_bringup_check.txt, datasheet Table 14 p.37 | BOARD + datasheet |
| SW0 = PA0 active low; PB10 red, PB11 green | confirmed | docs/evidence/stage4_bringup_check.txt | BOARD |
| LED states in the game (green X, red O, flashing game over, SW0 -> off) | observed by owner | docs/bringup-log.md, D-021 | BOARD (no photo/video yet) |
| Same C logic passes all tests on a PC | 100/100 | docs/evidence/stage5_6_host_pytest.txt | PC build of server.c + game.c |
| Game core exhaustive checks | 50,546,417 checks, 0 failed; 549,946 positions; 6,859,116 illegal attempts left the game byte-identical; 2,000,000 random calls | docs/evidence/stage2_core_tests.txt | PC |
| Independent game count | 255,168 games: 131,184 X wins, 77,904 O wins, 46,080 draws | tests/core/count_games.py | PC |
| Tests can fail | 15/15 injected faults caught (first run 14/15: a missing 2-4-6 diagonal test was added) | docs/evidence/stage3_mutation_check.txt, D-014 | PC mock |
| Checksum limits | 0 of 2,512 single-bit errors missed; 11.40% of two-bit errors missed; 100% of adjacent byte swaps missed; 0.417% of random bodies pass | docs/evidence/checksum_analysis.txt | PC calculation |
| Code size | game image 6,420 B code + 12 B data in 64 KB flash; 1,772 B bss (static RAM of 8 KB) | `arm-none-eabi-size firmware/build/SerialGameServer.elf` | build |

## B. Still to measure on the board (run once, keep the output)

`python tests/measure_board.py COM9 --out docs/evidence/board_measurements.txt` (about 4 minutes,
close every terminal first). It prints and saves:

| Id | Measures | Why the report needs it |
|---|---|---|
| M1 | request -> reply latency, 300 samples (min / median / p95 / max) | "give measured numbers" (robustness section). Includes ST-Link USB delay, say so. |
| M2 | partial-frame timeout, 20 samples; spec is 500 ms | the observed timeout the template asks for |
| M3 | 2000 sustained requests, count of wrong/missing replies | reliability number |
| M4 | bursts of 1-64 frames in one write: replies missing or wrong | evidence the ring buffer and main loop keep up |
| M5 | 100 random garbage frames each followed by CONNECT | recovery number |

Then run the full suite once more and save it: `python -m pytest tests --port COM9 -v > ...` (see below).

## C. Evidence only you can capture

- GUI running on the board (screenshots: connected, mid-game, rejected move, win). The ones in docs/evidence/gui are from the mock.
- Photos or video of the LED in each state (green, red, flashing) and SW0 pressed; photo of the board plugged into the PC (circuit diagram).
- Sound check on your PC (D-020 says not yet heard).
- Names of both students and who did what (task allocation); the video link; confirm the repository link opens when logged out (it is public: checked).
- A clean-folder run of your own README on Windows (clone, build, flash, tests, GUI).

## D. Do NOT claim (not measured)

- Button debounce time (30 ms is the code constant, nobody measured contact bounce): write "set to 30 ms", not "measured".
- LED blink frequency (250 ms half period is the code constant; you only saw it flash): write "configured for 2 Hz" unless you time a video.
- Stack headroom, power, or UART overrun counts on the board (the counters exist but cannot be read without writing to the game UART).
- Anything about AI, timer or undo: not implemented.
- Two-client play, hidden information: not implemented.
- That the board was unplugged/ replugged mid-game: not tested; the GUI handles a lost reply by design and is tested on the mock only.
