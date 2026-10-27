#!/usr/bin/env python3
"""Tic-Tac-Toe GUI for the STM32 serial game server (docs/protocol.md v1.0).

    python gui/app.py                       # pick the port in the window
    python gui/app.py --port COM9           # preselect the port
    python gui/app.py --port socket://127.0.0.1:5555   # the PC mock server

The window draws ONLY what the device confirms. A click sends a command; nothing on the
board changes until a valid reply arrives. Serial I/O runs in a worker thread so the
window never freezes.
"""
import argparse
import os
import queue
import random
import sys
import threading
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import Connection, GameView, ReplyError  # noqa: E402
import sounds  # noqa: E402

try:
    from serial.tools import list_ports
except Exception:                                    # pragma: no cover
    list_ports = None

# Warm amber palette (wooden tiles, brown X, white O) with drifting petals.
BG = "#7a4320"
BOARD = "#c8803a"
TILE = "#f3b552"
TILE_EDGE = "#ffd98a"
TILE_SHADOW = "#e0902f"
TILE_HOVER = "#ffc96a"
X_COLOR = "#6b3411"
O_COLOR = "#ffffff"
TEXT = "#fff3dc"
PETAL = "#f6c9d0"
BTN = "#f3b552"
BTN_ACTIVE = "#ffc96a"
SIZE = 408          # board canvas, pixels
PAD = 14
GAP = 10


class App:
    def __init__(self, root, port=""):
        self.root = root
        root.title("Serial Game Server - Tic-Tac-Toe")
        root.configure(bg=BG)
        root.minsize(560, 800)
        self.view = GameView()
        self.conn = None
        self.busy = False
        self.results = queue.Queue()
        self.sound_on = tk.BooleanVar(value=True)
        self.hover = None
        self.last_board = self.view.board

        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="Port", bg=BG, fg=TEXT, font=("Helvetica", 11)).pack(side="left")
        self.port_var = tk.StringVar(value=port)
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=30, values=self.ports())
        self.port_box.pack(side="left", padx=6)
        self.connect_btn = self.button(top, "Connect", self.on_connect)
        self.connect_btn.pack(side="left")
        self.disconnect_btn = self.button(top, "Disconnect", self.on_disconnect)
        self.disconnect_btn.pack(side="left", padx=6)
        self.vs_computer = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="Play vs computer (you are X)", variable=self.vs_computer, bg=BG, fg=TEXT,
                       selectcolor=BG, activebackground=BG, activeforeground=TEXT).pack(side="right", padx=8)
        tk.Checkbutton(top, text="Sound", variable=self.sound_on, bg=BG, fg=TEXT, selectcolor=BG,
                       activebackground=BG, activeforeground=TEXT).pack(side="right")

        # score board: confirmed wins / draws only
        score = tk.Frame(root, bg=BG)
        score.pack(pady=(6, 2))
        self.score_vars = {k: tk.StringVar(value="0") for k in ("X", "draws", "O")}
        for key, title, color in (("X", "X wins", "#ffb199"), ("draws", "Draws", TEXT), ("O", "O wins", "#bfe3ff")):
            box = tk.Frame(score, bg=BOARD, padx=14, pady=4)
            box.pack(side="left", padx=6)
            tk.Label(box, text=title, bg=BOARD, fg=TEXT, font=("Helvetica", 10)).pack()
            tk.Label(box, textvariable=self.score_vars[key], bg=BOARD, fg="white",
                     font=("Helvetica", 24, "bold")).pack()
        self.reset_score_btn = self.button(score, "Reset score", self.on_reset_score)
        self.reset_score_btn.pack(side="left", padx=10)

        self.status = tk.StringVar()
        tk.Label(root, textvariable=self.status, bg=BG, fg=TEXT, font=("Helvetica", 14, "bold"),
                 wraplength=500, justify="center").pack(fill="x", padx=8, pady=(8, 0))
        self.result = tk.StringVar()
        tk.Label(root, textvariable=self.result, bg=BG, fg="#ffe07a", font=("Helvetica", 22, "bold"),
                 height=1).pack()

        self.canvas = tk.Canvas(root, width=SIZE, height=SIZE, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=6)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", lambda e: self.set_hover(None))
        self.petals = [(random.Random(i).uniform(0, SIZE), random.Random(i + 99).uniform(0, SIZE),
                        random.Random(i + 7).uniform(5, 11)) for i in range(26)]

        bar = tk.Frame(root, bg=BG)
        bar.pack(pady=4)
        self.new_btn = self.button(bar, "New Game", lambda: self.send(["NEW:AI" if self.vs_computer.get() else "NEW"]))
        self.new_btn.pack(side="left", padx=4)
        self.resign_btn = self.button(bar, "Resign", lambda: self.send(["RESIGN"]))
        self.resign_btn.pack(side="left", padx=4)
        self.refresh_btn = self.button(bar, "Refresh (STATE)", lambda: self.send(["STATE"]))
        self.refresh_btn.pack(side="left", padx=4)

        tk.Label(root, text="Messages on the wire (TX = sent, RX = checksum-verified reply)",
                 bg=BG, fg=TEXT, font=("Helvetica", 9)).pack(anchor="w", padx=12)
        self.log = tk.Text(root, height=7, state="disabled", font=("Consolas", 9), bg="#4a2410", fg=TEXT,
                           relief="flat")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.log.tag_config("tx", foreground="#d9b48a")
        self.log.tag_config("rx", foreground="#a8e6a1")
        self.log.tag_config("err", foreground="#ff9c8f")

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        self.root.after(30, self.poll)

    # ---------------------------------------------------------------- look
    @staticmethod
    def button(parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=BTN, fg="#4a2410", activebackground=BTN_ACTIVE,
                         disabledforeground="#a9824f", relief="flat", padx=12, pady=5, bd=0,
                         font=("Helvetica", 10, "bold"))

    @staticmethod
    def ports():
        found = [p.device for p in list_ports.comports()] if list_ports else []
        return found + ["socket://127.0.0.1:5555"]

    def cell_box(self, i):
        cell = (SIZE - 2 * PAD - 2 * GAP) / 3
        r, c = divmod(i, 3)
        x0 = PAD + c * (cell + GAP)
        y0 = PAD + r * (cell + GAP)
        return x0, y0, x0 + cell, y0 + cell

    def round_rect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
               x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def draw_board(self):
        cv = self.canvas
        cv.delete("all")
        for x, y, r in self.petals:                                     # background petals
            cv.create_oval(x - r, y - r / 1.6, x + r, y + r / 1.6, fill=PETAL, outline="")
        self.round_rect(2, 2, SIZE - 2, SIZE - 2, 26, fill=BOARD, outline="")
        playable = self.playable_cells()
        for i in range(9):
            x0, y0, x1, y1 = self.cell_box(i)
            fill = TILE_HOVER if (i == self.hover and i in playable) else TILE
            self.round_rect(x0, y0 + 3, x1, y1 + 3, 14, fill=TILE_SHADOW, outline="")
            self.round_rect(x0, y0, x1, y1, 14, fill=fill, outline="")
            cv.create_line(x0 + 10, y0 + 3, x1 - 10, y0 + 3, fill=TILE_EDGE, width=2)
            ch = self.view.board[i]
            cx, cy, m = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.26
            if ch == "X":
                for a, b in ((-1, -1), (-1, 1)):
                    cv.create_line(cx + a * m, cy + b * m, cx - a * m, cy - b * m, fill=X_COLOR, width=13,
                                   capstyle="round")
            elif ch == "O":
                cv.create_oval(cx - m * 1.1, cy - m * 1.1, cx + m * 1.1, cy + m * 1.1, outline=O_COLOR, width=12)

    def playable_cells(self):
        if self.conn is None or self.busy:
            return set()
        return {i for i in range(9) if self.view.can_move(i)}

    def cell_at(self, x, y):
        for i in range(9):
            x0, y0, x1, y1 = self.cell_box(i)
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.draw_board()

    def on_canvas_motion(self, e):
        self.set_hover(self.cell_at(e.x, e.y))

    def on_canvas_click(self, e):
        i = self.cell_at(e.x, e.y)
        if i is not None:
            self.on_cell(i)

    def write_log(self, kind, text):
        self.log.config(state="normal")
        label = {"tx": "TX  ", "rx": "RX  ", "err": "ERR "}[kind]
        self.log.insert("end", label + text + "\n", kind)
        self.log.see("end")
        self.log.config(state="disabled")

    def refresh(self):
        """Redraw from the GameView (which only changes on a valid server reply)."""
        v = self.view
        connected = self.conn is not None
        self.draw_board()
        for k, var in self.score_vars.items():
            var.set(str(v.score[k]))
        self.status.set(v.message)
        self.result.set(v.result)
        idle_ok = connected and not self.busy
        self.connect_btn.config(state="normal" if (not connected and not self.busy) else "disabled")
        self.disconnect_btn.config(state="normal" if idle_ok else "disabled")
        self.new_btn.config(state="normal" if idle_ok and v.state in ("IDLE", "GAME_OVER") else "disabled")
        self.resign_btn.config(state="normal" if idle_ok and v.state == "IN_PROGRESS" else "disabled")
        self.refresh_btn.config(state="normal" if idle_ok else "disabled")
        self.port_box.config(state="normal" if not connected and not self.busy else "disabled")

    def play_sound(self, kind):
        if self.sound_on.get():
            sounds.play(kind, self.root)

    def sound_for(self, request, reply, old_board):
        """Choose an effect from a CONFIRMED reply only."""
        if reply.startswith("NACK:"):
            return "error"
        if reply.startswith("WIN:"):
            return "win"
        if reply.startswith("DRAW:"):
            return "draw"
        if reply == "OK:GAMEOVER":
            return "resign"
        if request in ("NEW", "NEW:AI") and reply.startswith("OK:BOARD:"):
            return "new"
        if request == "CONNECT" and reply == "OK":
            return "connect"
        if request.startswith("MOVE:") and reply.startswith("OK:BOARD:"):
            new = reply[len("OK:BOARD:"):]
            for a, b in zip(old_board, new):
                if a == "." and b in "XO":
                    return b.lower()
        return None

    # ---------------------------------------------------------------- worker thread
    def run_in_thread(self, work):
        """work() runs off the UI thread and returns a list of (request, reply) or raises."""
        self.busy = True
        self.refresh()

        def target():
            try:
                self.results.put(("ok", work()))
            except ReplyError as exc:
                self.results.put(("err", str(exc)))
            except Exception as exc:                      # port missing, busy, unplugged ...
                self.results.put(("fatal", str(exc)))
        threading.Thread(target=target, daemon=True).start()

    def exchange(self, body):
        """One request; if the reply is lost, ask STATE once (protocol.md section 10)."""
        try:
            return [(body, self.conn.request(body))]
        except ReplyError as exc:
            if "no reply" not in str(exc):
                raise
            return [("STATE", self.conn.request("STATE"))]

    def poll(self):
        try:
            while True:
                kind, payload = self.results.get_nowait()
                self.finish(kind, payload)
        except queue.Empty:
            pass
        if self.conn is not None:
            while self.conn.log:
                self.write_log(*self.conn.log.pop(0))
        self.root.after(30, self.poll)

    def finish(self, kind, payload):
        self.busy = False
        if kind == "ok":
            for request, reply in payload:
                old = self.view.board
                self.view.apply(request, reply)
                effect = self.sound_for(request, reply, old)
                if effect:
                    self.play_sound(effect)
        elif kind == "err":
            self.view.message = "Problem: " + payload                 # board is NOT touched
            self.play_sound("error")
        else:
            self.view.message = "Port error: " + payload
            self.drop_connection()
        self.refresh()

    def drop_connection(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None

    # ---------------------------------------------------------------- actions
    def on_connect(self):
        port = self.port_var.get().strip()
        if not port:
            self.view.message = "Choose a port first."
            self.refresh()
            return

        def work():
            self.conn = Connection(port)
            pairs = self.exchange("CONNECT")
            if pairs[0][1] == "NACK:STATE":                  # device is not idle: find out why
                d = self.conn.request("DISCONNECT")
                pairs.append(("DISCONNECT", d))
                if d == "OK":                                # it was a finished game: now idle
                    pairs.append(("CONNECT", self.conn.request("CONNECT")))
                else:                                        # a game is running: resync the board
                    pairs.append(("STATE", self.conn.request("STATE")))
            return pairs
        self.view.reset()
        self.run_in_thread(work)

    def send(self, bodies):
        if self.conn is None or self.busy:
            return
        self.run_in_thread(lambda: [p for b in bodies for p in self.exchange(b)])

    def on_reset_score(self):
        self.view.score = {"X": 0, "O": 0, "draws": 0}
        self.refresh()

    def on_cell(self, i):
        # A click only SENDS; no drawing here. Occupied cells are sent too (the server, not the GUI,
        # decides legality), so its NACK:OCCUPIED shows up as a message. Not sent when no game runs.
        if self.view.state == "IN_PROGRESS" and not self.busy:
            self.send([self.view.command_for_move(i)])

    def on_disconnect(self):
        def work():
            pairs = []
            if self.view.state == "IN_PROGRESS":
                pairs += self.exchange("RESIGN")
            pairs += self.exchange("DISCONNECT")
            return pairs
        self.run_in_thread(work)
        self.root.after(100, self.close_when_done)

    def close_when_done(self):
        if self.busy:
            self.root.after(100, self.close_when_done)
            return
        self.drop_connection()
        self.refresh()

    def on_close(self):
        if self.conn is not None and not self.busy:
            try:
                if self.view.state == "IN_PROGRESS":
                    self.conn.request("RESIGN")
                self.conn.request("DISCONNECT")
            except Exception:
                pass
        self.drop_connection()
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=os.environ.get("GAME_PORT", ""))
    args = ap.parse_args()
    root = tk.Tk()
    App(root, args.port)
    root.mainloop()


if __name__ == "__main__":
    main()
