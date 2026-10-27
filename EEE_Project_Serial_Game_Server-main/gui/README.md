# GUI (Stage 8)

Tkinter client for the STM32 game server. Python 3 with Tkinter (included with the python.org
Windows installer) and `pip install pyserial`.

```
python gui/app.py --port COM9                       # the real board
python tests/mock_server.py --listen 5555 &         # or the PC mock ...
python gui/app.py --port socket://127.0.0.1:5555    # ... and the GUI on it
```
Close any serial terminal first: only one program can hold the COM port.

How to play (hot-seat, X first): Connect, New Game, click cells, Resign / New Game, Disconnect.

## Rules the GUI follows (it is an untrusted client)
- The board is drawn **only** from a checksum-verified server reply. A click only *sends* `MOVE:<i>:<mark>`; the
  cell stays empty until `OK:BOARD:` / `WIN:` / `DRAW:` arrives. A rejected move changes nothing but the message.
- Specific NACKs become plain-language messages (`gui/client.py` `NACK_TEXT`).
- After `WIN` / `DRAW` / `RESIGN` all cells are disabled; only New Game (or Disconnect) works.
- If the board's SW0 reset the game, the next request returns `NACK:NOGAME`; the GUI returns to its start screen.
- A lost reply: the GUI sends `STATE` once (protocol.md section 10) and redraws from that.
- Disconnect resigns a running game first (the server refuses `DISCONNECT` mid-game), then closes the port.
- Serial I/O runs in a worker thread, so the window never freezes; one request is in flight at a time.

- Score (X wins / draws / O wins) counts only confirmed WIN/DRAW replies to a MOVE; Reset score clears it.
- Sound effects (checkbox "Sound") play only for confirmed replies; Windows uses the standard-library winsound.
- Appearance is a Tk Canvas; colours and sizes are the constants at the top of `app.py`.

## Files
`app.py` window, `sounds.py` generated tones, `client.py` protocol client + `GameView` (no Tkinter, unit-tested in `tests/gui`),
`make_screenshots.py` regenerates `docs/evidence/gui/*.png` headlessly (xvfb + ImageMagick),
flow chart in `docs/diagrams/gui_flow.png`.
