# Serial Game Server (EEE3095S CS project 2026)

An **STM32F051** (UCT dev board) is the authoritative Tic-Tac-Toe server; a **Tkinter PC GUI** is a thin, untrusted
client. They talk over USART1 through the board's ST-Link virtual COM port (115200 8N1). The server enforces every
rule; the GUI only sends requests and draws verified replies. Optional `NEW:AI` makes the server play O.

Authors: Hazel Kunyavapa (KNYCHI008), Oswika Mukoma (MKMOSW001).
Protocol (single source of truth): `docs/protocol.md`. Decisions: `docs/decisions.md`. Report: `report/` (`main.pdf`).

## 1. What you need
- A UCT dev board (STM32F051C8) with a USB cable, plugged into the PC (the on-board ST-Link gives power, programming and the COM port).
- Python 3.10+ with Tkinter (included in the python.org Windows installer): `pip install -r tests/requirements.txt` (pytest, pyserial).
- To rebuild the firmware: the Arm toolchain `arm-none-eabi-gcc` and `make` (STM32CubeIDE ships both), or just use STM32CubeIDE.
- To flash: STM32CubeProgrammer (`STM32_Programmer_CLI`) and the ST-Link USB driver (on Windows install it from the CubeIDE `Drivers\ST-LINK` folder; run `stlink_winusb_install.bat` as administrator). Find the board's COM port in Device Manager (ours was COM9).

## 2. Get the code
```
git clone https://github.com/OswikaMukoma/Tic-Tac-Toe.git
cd Tic-Tac-Toe
```

## 3. Build the firmware
```
make -C firmware
```
Output: `firmware/build/SerialGameServer.elf`, `.hex`, `.bin`. If `make` says `arm-none-eabi-gcc` cannot be found, add the
toolchain's `bin` folder to PATH for this window (in STM32CubeIDE's install folder). In STM32CubeIDE you can instead use
File > Import > C/C++ > Existing Code as Makefile Project, select `firmware/`, then Project > Build All.
`make -C firmware BRINGUP=1` builds a separate hardware bring-up image (`build/bringup/`); do not flash that for the game.

## 4. Flash the board
Close every program that uses the COM port, then from the repository root:
```
STM32_Programmer_CLI -c port=SWD -w firmware/build/SerialGameServer.hex -v -rst
```
On Windows PowerShell, where the tool is usually not on PATH, use this instead (it finds the tool itself):
```
$cli = (Get-ChildItem "C:\Program Files\STMicroelectronics","C:\ST" -Recurse -Filter STM32_Programmer_CLI.exe -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
& $cli -c port=SWD -w firmware\build\SerialGameServer.hex -v -rst
```
Expected end of output: `Download verified successfully` and `Software reset is performed`. If it says "No debug probe detected",
install the ST-Link driver (section 1) and replug the USB cable.

## 5. Play (run the GUI)
```
python gui/app.py --port COM9
```
Click **Connect**, then **New Game**, then click cells (hot-seat: X first). Tick **Play vs computer (you are X)** before New Game
to play against the board's AI. **Resign**, **Refresh** and **Disconnect** do what they say; **Reset score** clears the score.
Board hardware: **SW0** resets the game to IDLE; the LED is off in IDLE, green when X is to move, red when O is to move, and both blink in GAME_OVER.
No board? Run the PC mock instead: `python tests/mock_server.py --listen 5555` and `python gui/app.py --port socket://127.0.0.1:5555`.
More in `gui/README.md`.

## 6. Test
All from the repository root. The same pytest suite runs against three targets.
```
make -C tests/core test                       # (Linux/macOS, needs gcc) game core unit tests on the PC (50.5 million checks) + AI exhaustive check
python -m pytest tests --port mock            # Python mock server, no board (about 2 min)
# Linux/macOS only (needs gcc and a POSIX shell): the real server.c + game.c on the PC
make -C tests/host && ./tests/host/host_server 5556 &
python -m pytest tests --port socket://127.0.0.1:5556
python -m pytest tests --port COM9 -v         # the real board (flash it first; close other COM users); expect 125 passed
python tests/mutation_check.py                # injects 15 faults into the mock; all must be caught
python tests/measure_board.py COM9 --out docs/evidence/board_measurements.txt   # latency, timeout, bursts (about 4 min)
```
Run pytest from the repository root, not from `firmware/build`. A manual terminal: `python tests/play.py COM9` (type `CONNECT`, `NEW`, `MOVE:4` ...; checksums are optional on requests).
Saved results are in `docs/evidence/`.

## 7. Layout
`docs/` protocol, plan, decisions, evidence - `firmware/` STM32 server (`Core/Src/game.c`, `server.c`, `ai.c`, `uart.c`, `main.c`) -
`gui/` PC client - `tests/` pytest harness, mock server, PC host build - `report/` LaTeX report (`latexmk -pdf main.tex`).

## 8. Reused material and AI use
Firmware base (HAL/CMSIS drivers, startup, linker script, Makefile) adapted from the EEE3096S Practical 2A starter project.
AI assistance (Claude) was used to draft code, tests, diagrams and text; both authors reviewed, ran and understand every module.
