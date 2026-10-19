#!/usr/bin/env python3
"""Captura dedicada da tela do painel de velocidade com o mapa da rota.

A navegacao (destino + rota) deve estar ativa no servidor antes da execucao
(por exemplo via POST /api/nav), de modo que o cluster mostre o mini-mapa com o
carro e a linha da rota. Use um servidor com GPS habilitado para o marcador do
carro aparecer.

Variaveis:
  SHOT_URL  base da UI      (padrao http://127.0.0.1:8099/)
  SHOT_OUT  arquivo saida   (padrao docs/tutorial/assets/page_cluster_nav.png)
  BOOT_MS   espera pelo boot + tiles do mapa (padrao 9000)
Use: xvfb-run -a -s "-screen 0 1024x600x24" python3 docs/tutorial/capture_cluster_nav.py
"""
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

W, H = 1024, 600
HERE = os.path.dirname(os.path.abspath(__file__))
URL = os.environ.get("SHOT_URL", "http://127.0.0.1:8099/") + "?screen=cluster"
OUT = os.environ.get("SHOT_OUT", os.path.join(HERE, "assets", "page_cluster_nav.png"))
BOOT_MS = int(os.environ.get("BOOT_MS", "9000"))


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
        self.view.load_uri(URL)

    def on_load(self, view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(BOOT_MS, self.grab)

    def grab(self):
        win = self.win.get_window()
        self.win.resize(W + 1, H + 1)
        self.win.resize(W, H)
        self.view.queue_draw()
        pb = Gdk.pixbuf_get_from_window(win, 0, 0, W, H)
        if pb is not None:
            pb.savev(OUT, "png", [], [])
        print("saved", OUT, flush=True)
        Gtk.main_quit()
        return False


App()
Gtk.main()
