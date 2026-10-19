#!/usr/bin/env python3
"""Captura a cena de TEMAS: 4 paineis reais em temas diferentes, em grade 2x2.

Aplica temas.ativo via API do servidor, recarrega o painel e tira a foto de
cada um; depois monta tudo em assets/page_temas.png com o nome de cada tema.

Variaveis:
  SHOT_URL  base da UI      (padrao http://127.0.0.1:8080/)
  SHOT_OUT  arquivo saida   (padrao docs/tutorial/assets/page_temas.png)
  BOOT_MS   espera pelo boot/tema (padrao 7000)
Use: xvfb-run -a -s "-screen 0 1024x600x24" python3 docs/tutorial/capture_temas.py
"""
import json
import os
import subprocess
import tempfile
import urllib.request

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

W, H = 1024, 600
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("SHOT_URL", "http://127.0.0.1:8080/")
OUT = os.environ.get("SHOT_OUT", os.path.join(HERE, "assets", "page_temas.png"))
BOOT_MS = int(os.environ.get("BOOT_MS", "7000"))
THEMES = [("ferrari", "Ferrari"), ("bmw", "BMW"),
          ("lambo", "Lamborghini"), ("tesla", "Tesla")]
TMP = tempfile.mkdtemp(prefix="temas_")


def set_theme(name):
    req = urllib.request.Request(
        BASE.rstrip("/") + "/api/settings",
        data=json.dumps({"temas.ativo": name}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=5).read()


class App:
    def __init__(self):
        self.win = Gtk.Window()
        self.win.set_title("OpenDash")
        self.win.set_default_size(W, H)
        self.win.set_resizable(False)
        self.view = WebKit2.WebView()
        self.win.add(self.view)
        self.view.connect("load-changed", self.on_load)
        self.win.show_all()
        self.idx = 0
        self.load()

    def load(self):
        self.theme, self.label = THEMES[self.idx]
        set_theme(self.theme)
        self.view.load_uri(BASE)

    def on_load(self, view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(BOOT_MS, self.grab)

    def grab(self):
        pb = Gdk.pixbuf_get_from_window(self.win.get_window(), 0, 0, W, H)
        if pb is not None:
            pb.savev(os.path.join(TMP, "%d.png" % self.idx), "png", [], [])
        print("shot:", self.theme, flush=True)
        self.idx += 1
        if self.idx >= len(THEMES):
            self.compose()
            Gtk.main_quit()
            return False
        GLib.timeout_add(500, self.load)
        return False

    def compose(self):
        args = ["ffmpeg", "-y"]
        for i in range(len(THEMES)):
            args += ["-i", os.path.join(TMP, "%d.png" % i)]
        parts = []
        for i, (_, label) in enumerate(THEMES):
            parts.append(
                "[%d:v]scale=512:300,drawbox=x=0:y=264:w=512:h=36:"
                "color=0x05080d@0.72:t=fill,drawtext=fontfile=%s:"
                "text='%s':fontcolor=0xf0f6fc:fontsize=20:x=14:y=270[a%d]"
                % (i, FONT, label, i))
        layout = "0_0|w0_0|0_h0|w0_h0"
        parts.append("".join("[a%d]" % i for i in range(len(THEMES))) +
                     "xstack=inputs=%d:layout=%s[out]" % (len(THEMES), layout))
        args += ["-filter_complex", ";".join(parts), "-map", "[out]",
                 "-frames:v", "1", OUT]
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        print("saved", OUT, flush=True)


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

App()
Gtk.main()
