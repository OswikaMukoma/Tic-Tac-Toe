#!/usr/bin/env python3
"""Drive the real GUI against the mock server and save screenshots (report evidence).

    xvfb-run -a -s "-screen 0 700x820x24" python3.12 gui/make_screenshots.py docs/evidence/gui
Needs ImageMagick `import`. Not needed to use the GUI.
"""
import os
import subprocess
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tests"))
from app import App  # noqa: E402
from mock_server import MockServer  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(out, exist_ok=True)
server = MockServer().start()
root = tk.Tk()
root.geometry("+0+0")
app = App(root, server.url)


def settle():
    t0 = time.time()
    while time.time() - t0 < 0.3 or app.busy:
        root.update()
        time.sleep(0.01)
        if time.time() - t0 > 5:
            break


def shot(name):
    settle()
    subprocess.run(["import", "-window", "root", "-crop", "%dx%d+0+0" % (root.winfo_width(), root.winfo_height()),
                    os.path.join(out, name)], check=True)
    print("saved", name)


def click(widget):
    widget.invoke()
    settle()


settle()
shot("gui_1_start.png")
click(app.connect_btn); shot("gui_2_connected.png")
click(app.new_btn)
for i in (4, 0, 3):
    app.on_cell(i); settle()
shot("gui_3_playing.png")
app.send(["MOVE:4:O"]); settle()
shot("gui_4_rejected_occupied.png")
for i in (1, 5):
    app.on_cell(i); settle()
shot("gui_5_x_wins.png")
click(app.disconnect_btn); shot("gui_6_disconnected.png")
server.stop()
root.destroy()
