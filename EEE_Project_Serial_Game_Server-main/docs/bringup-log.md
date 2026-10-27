# Hardware bring-up log

Append what you tried on the real board, with the exact result. Feeds the
validation and circuit-diagram sections. Save screenshots to docs/evidence/.

| Date | Who | What was tried | Result |
|---|---|---|---|
| | | | |

Paper checks (12 Oct, from the supplied PDFs, not yet bench-verified):
- STM32F051 datasheet DocID022265 Rev 4, Table 14, p.37: PA9 AF1 = USART1_TX, PA10 AF1 = USART1_RX.
- UCT dev board schematic v1.06 sheet 1: ST-Link VCP lines on PA9/PA10; SW0 PA0; R/G LED
  PB10 (via R12, red) and PB11 (via R13, green); D8 power LED.

| 2026-10-21 | owner | Installed ST-Link driver from CubeIDE_1.19.0\drivers\STLinkUSBDriver (stlink_winusb_install.bat, admin); `STM32_Programmer_CLI -l` then listed the probe (FW V2J48M35) and COM9 | OK (before this: "No ST-Link detected") |
| 2026-10-21 | owner | Flashed BringUp.elf with STM32_Programmer_CLI -c port=SWD -w ... -v -rst | Download verified successfully |
| 2026-10-21 | owner | miniterm COM9 115200: "BRINGUP TX n" every second, clean text | T2 PASS: USART1 PA9/PA10, AF1, 115200 confirmed |
| 2026-10-21 | owner | tests\bringup_check.py COM9 | T2 PASS, T3 echo PASS (docs/evidence/stage4_bringup_check.txt) |
| 2026-10-21 | owner | T1 LED: after reset red x3 then green x3. T4: hold SW0 -> LED red, terminal "SW0 DOWN" / release "SW0 UP" (3 presses seen) | T1 PASS (PB10 = red, PB11 = green confirmed), T4 PASS (SW0 = PA0 active low confirmed) |

Notes: CubeIDE's Debug button stays disabled for this Makefile project (no device settings); flashing is done with STM32_Programmer_CLI instead. Two CubeIDE versions are installed (1.19.0 and 2.2.0).
| 2026-10-21 | owner | Flashed game firmware (commit a86f8c5) and ran `pytest tests --port COM9 -m "not slow"` | 95 passed, 5 deselected (docs/evidence/stage7_board_pytest_partial.txt) |
| 2026-10-21 | owner | Game firmware, tests/play.py COM9: NEW -> LED green; MOVE:4 -> red; RESIGN -> LED flashes; press SW0 -> LED off | Stage 6 hardware behaviour PASS (owner's report; no screenshot yet) |
