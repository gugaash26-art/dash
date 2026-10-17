#!/usr/bin/env python3
"""Captura dedicada do overlay de camera de re.

A marcha a re e ligada no servidor antes da execucao (curl), de modo que o
proprio app mantem o overlay aberto. O fundo sintetico e o texto de
"indisponivel" sao tratados por CSS injetado (persiste entre os ticks).
"""
import os
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2

W, H = 1024, 600
URL = os.environ.get("SHOT_URL", "http://127.0.0.1:8099/")
OUT = os.environ.get("SHOT_OUT", "/tmp/opencode/page_reverse.png")
BOOT_MS = int(os.environ.get("BOOT_MS", "8000"))

CSS = ("#reverseCam{background:radial-gradient(120% 95% at 50% 118%,"
       "#3d444d 0%,#262a30 42%,#0b0d10 100%) !important}"
       "#reverseCam.is-empty .rev-empty{display:none !important}"
       "#reverseImg{display:none !important}")


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
            GLib.timeout_add(BOOT_MS, self.demo)

    def demo(self):
        js = ("(function(){var st=document.createElement('style');"
              "st.textContent=%r;document.head.appendChild(st);})();"
              % CSS)
        self.view.run_javascript(js, None, None, None)
        GLib.timeout_add(1500, self.grab)
        return False

    def grab(self):
        win = self.win.get_window()
        pb = Gdk.pixbuf_get_from_window(win, 0, 0, W, H)
        if pb is not None:
            pb.savev(OUT, "png", [], [])
        print("saved", OUT, flush=True)
        Gtk.main_quit()
        return False


App()
Gtk.main()
