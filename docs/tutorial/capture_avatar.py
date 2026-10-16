#!/usr/bin/env python3
"""Renderiza o avatar do tutorial (avatar.html) como PNGs com fundo transparente.

Usa WebKitGTK para desenhar o SVG e captura um snapshot com canal alfa
(WebKit2.SnapshotOptions.TRANSPARENT_BACKGROUND). Gera alguns estados:
  avatar_idle.png   - boca fechada
  avatar_talk.png   - boca aberta (usado para "falar")
  avatar_blink.png  - olhos fechados (piscada)
  avatar_wave.png   - acenando (para a abertura)

Variaveis: AVATAR_OUT (padrao docs/tutorial/assets), AVATAR_W, AVATAR_H.
Use: xvfb-run -a -s "-screen 0 640x720x24" python3 docs/tutorial/capture_avatar.py
"""
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "avatar.html")
OUT = os.environ.get("AVATAR_OUT", os.path.join(HERE, "assets"))
W = int(os.environ.get("AVATAR_W", "480"))
H = int(os.environ.get("AVATAR_H", "540"))

STATES = [
    ("avatar_idle", "m=0"),
    ("avatar_talk", "m=1"),
    ("avatar_blink", "m=0&b=1"),
    ("avatar_wave", "m=0&w=1"),
]


class App:
    def __init__(self):
        os.makedirs(OUT, exist_ok=True)
        self.win = Gtk.Window()
        self.win.set_title("avatar")
        self.win.set_default_size(W, H)
        self.win.set_resizable(False)
        self.view = WebKit2.WebView()
        rgba = Gdk.RGBA()
        rgba.parse("rgba(0,0,0,0)")
        self.view.set_background_color(rgba)
        self.win.add(self.view)
        self.view.connect("load-changed", self.on_load)
        self.win.show_all()
        self.i = 0
        self._load_current()

    def _load_current(self):
        name, query = STATES[self.i]
        self.current = name
        self.view.load_uri("file://%s?%s" % (HTML, query))

    def on_load(self, view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(350, self.snap)

    def snap(self):
        self.view.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                               WebKit2.SnapshotOptions.TRANSPARENT_BACKGROUND,
                               None, self.on_snap, self.current)
        return False

    def on_snap(self, view, result, name):
        path = os.path.join(OUT, name + ".png")
        try:
            surface = view.get_snapshot_finish(result)
            surface.write_to_png(path)
            print("avatar:", path, flush=True)
        except Exception as exc:  # pragma: no cover
            sys.stderr.write("falha no snapshot %s: %s\n" % (name, exc))
        self.i += 1
        if self.i >= len(STATES):
            Gtk.main_quit()
            return
        self._load_current()


def main():
    App()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
