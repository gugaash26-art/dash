#!/usr/bin/env python3
"""Captura telas reais da UI do OpenDash usando WebKitGTK + Xvfb.

Variaveis de ambiente:
  SHOT_URL   URL base (padrao http://127.0.0.1:8099/)
  SHOT_OUT   diretorio de saida (padrao /tmp/opencode/shot/out)
  SHOT_MODE  "shots" (uma imagem por pagina) ou "video" (sequencia de frames)
  SHOT_HOLD  segundos por pagina no modo shots (padrao 1.5)
  SHOT_FPS   fps efetiva no modo video (padrao 8)
"""
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

W, H = 1024, 600
URL = os.environ.get("SHOT_URL", "http://127.0.0.1:8099/")
OUT = os.environ.get("SHOT_OUT", "/tmp/opencode/shot/out")
MODE = os.environ.get("SHOT_MODE", "shots")
HOLD = float(os.environ.get("SHOT_HOLD", "1.6"))
FPS = float(os.environ.get("SHOT_FPS", "8"))
BOOT_MS = int(os.environ.get("SHOT_BOOT_MS", "7500"))

PAGES = ["drive", "energy", "nav", "apps", "media", "climate", "diag", "settings"]

# Linha do tempo do modo video: (segundo, pagina)
TIMELINE = [
    (0.0, "drive"),
    (4.6, "energy"),
    (9.2, "nav"),
    (14.5, "apps"),
    (18.5, "media"),
    (22.0, "climate"),
    (25.5, "diag"),
    (29.0, "settings"),
    (33.0, "drive"),
]
DURATION = 37.0


class App:
    def __init__(self):
        os.makedirs(OUT, exist_ok=True)
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
            if MODE == "boot":
                GLib.timeout_add(50, self.start)
            else:
                GLib.timeout_add(BOOT_MS, self.start)

    def grab(self, path):
        win = self.win.get_window()
        pb = Gdk.pixbuf_get_from_window(win, 0, 0, W, H)
        if pb is not None:
            pb.savev(path, "png", [], [])
            return True
        return False

    def goto(self, name):
        js = ("document.querySelector('.tab[data-page-go=\"%s\"]')"
              "&&document.querySelector('.tab[data-page-go=\"%s\"]').click();"
              % (name, name))
        self.view.run_javascript(js, None, None, None)

    # ---- modo shots ----
    def start(self):
        if MODE == "boot":
            self.start_boot()
        elif MODE == "video":
            self.start_video()
        else:
            self.i = 0
            self.next_shot()
        return False

    def next_shot(self):
        if self.i >= len(PAGES):
            Gtk.main_quit()
            return False
        page = PAGES[self.i]
        self.goto(page)
        GLib.timeout_add(int(HOLD * 1000), self.snap_shot, page)
        return False

    def snap_shot(self, page):
        self.grab(os.path.join(OUT, "page_%s.png" % page))
        print("shot:", page, flush=True)
        self.i += 1
        self.next_shot()
        return False

    # ---- modo boot ----
    def start_boot(self):
        self.t0 = GLib.get_monotonic_time()
        self.frame = 0
        self.boot_dur = float(os.environ.get("SHOT_DUR", "4.5"))
        GLib.timeout_add(int(1000 / FPS), self.grab_boot)
        return False

    def grab_boot(self):
        self.grab(os.path.join(OUT, "boot_%04d.png" % self.frame))
        self.frame += 1
        now = (GLib.get_monotonic_time() - self.t0) / 1e6
        if now >= self.boot_dur:
            print("boot frames:", self.frame, flush=True)
            Gtk.main_quit()
            return False
        return True

    # ---- modo video ----
    def start_video(self):
        self.t0 = GLib.get_monotonic_time()
        for at, page in TIMELINE:
            GLib.timeout_add(int(at * 1000), self.goto, page)
        GLib.timeout_add(int(DURATION * 1000), self.stop_video)
        self.frame = 0
        GLib.timeout_add(int(1000 / FPS), self.grab_frame)
        return False

    def grab_frame(self):
        self.grab(os.path.join(OUT, "frame_%05d.png" % self.frame))
        self.frame += 1
        now = (GLib.get_monotonic_time() - self.t0) / 1e6
        if now >= DURATION:
            return False
        return True

    def stop_video(self):
        print("frames:", self.frame, flush=True)
        Gtk.main_quit()
        return False


def main():
    app = App()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
