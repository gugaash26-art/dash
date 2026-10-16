#!/usr/bin/env python3
"""Aplicativo OpenDash para Linux (janela nativa WebKitGTK, sem navegador).

Abre a interface do OpenDash numa janela propria (sem barra de endereco, abas
ou qualquer cara de navegador), reaproveitando o mesmo servidor Python. Serve
tanto o painel completo (com menus) quanto o painel de velocidade (sem menus)
ou o cluster em barra, conforme CARDASH_SCREEN.

Variaveis de ambiente:
  CARDASH_URL            base (padrao http://127.0.0.1:8080/)
  CARDASH_SCREEN         full (padrao) | cluster | bar
  CARDASH_WINDOW_SIZE    LxA  (ex.: 1024,600). Se vazio -> tela cheia
  CARDASH_WINDOW_POS     X,Y
  CARDASH_TOUCH_SIZE/POS, CARDASH_CLUSTER_SIZE/POS, CARDASH_BAR_SIZE/POS
                         (fallbacks usados pelo CARDASH_SCREEN)
  CARDASH_FULLSCREEN     1 forca tela cheia (mesmo com geometria) ; 0 nao
  CARDASH_CURSOR         0 nao esconde o cursor (padrao: esconde)
  CARDASH_DEV            1 ativa as ferramentas de desenvolvedor do WebKit
  CARDASH_SOFTWARE       1 desativa aceleracao de hardware (util em SBC antigas)
"""
import os
import sys

try:
    import gi
except ImportError:
    sys.stderr.write(
        "OpenDash: falta o PyGObject (gi). Instale:\n"
        "  sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1\n")
    raise SystemExit(3)

# WebKitGTK 4.1 (GTK3). Tenta tambem 4.0 como fallback de distro.
for _wk in ("4.1", "4.0"):
    try:
        gi.require_version("WebKit2", _wk)
        break
    except ValueError:
        continue
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402


def env(name, default=""):
    return os.environ.get(name, default).strip()


def parse_size(value):
    if not value:
        return None
    parts = value.lower().replace("x", ",").split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def parse_pos(value):
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def target_url():
    base = env("CARDASH_URL", "http://127.0.0.1:8080/")
    base = base.rstrip("/")
    screen = env("CARDASH_SCREEN", "full") or "full"
    if screen == "bar":
        return base + "/bar.html"
    if screen == "cluster":
        return base + "/?screen=cluster"
    return base + "/"


def geometry():
    """Reproduz a logica do kiosk.sh para escolher tamanho e posicao."""
    screen = env("CARDASH_SCREEN", "full") or "full"
    size = env("CARDASH_WINDOW_SIZE")
    pos = env("CARDASH_WINDOW_POS")
    if not size:
        if screen == "cluster":
            size = env("CARDASH_CLUSTER_SIZE") or env("CARDASH_BAR_SIZE")
        elif screen == "bar":
            size = env("CARDASH_BAR_SIZE")
        else:
            size = env("CARDASH_TOUCH_SIZE")
    if not pos:
        if screen == "cluster":
            pos = env("CARDASH_CLUSTER_POS") or env("CARDASH_BAR_POS")
        elif screen == "bar":
            pos = env("CARDASH_BAR_POS")
        else:
            pos = env("CARDASH_TOUCH_POS")
    return parse_size(size), parse_pos(pos)


def hide_cursor(win):
    if env("CARDASH_CURSOR", "1") == "0":
        return
    try:
        display = Gdk.Display.get_default()
        cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.BLANK_CURSOR)
        win.get_window().set_cursor(cursor)
    except Exception:
        pass


class OpenDashApp:
    def __init__(self):
        self.url = target_url()
        self.size, self.pos = geometry()
        force_fs = env("CARDASH_FULLSCREEN") == "1"
        self.fullscreen = force_fs or not self.size

        self.win = Gtk.Window(title="OpenDash")
        self.win.set_wmclass("OpenDash", "OpenDash")
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        if self.size:
            self.win.set_default_size(*self.size)
        try:
            self.win.set_type_hint(Gdk.WindowTypeHint.DOCK)
        except Exception:
            pass
        self.win.connect("key-press-event", self.on_key)
        self.win.connect("realize", lambda *_: hide_cursor(self.win))

        self.view = WebKit2.WebView()
        self.view.set_background_color(Gdk.RGBA(red=0.02, green=0.027, blue=0.043, alpha=1))
        try:
            self.view.set_property(
                "hardware-acceleration-policy",
                WebKit2.HardwareAccelerationPolicy.NEVER
                if env("CARDASH_SOFTWARE") == "1"
                else WebKit2.HardwareAccelerationPolicy.ON_DEMAND)
        except Exception:
            pass
        self.apply_settings()

        self.view.connect("context-menu", lambda *a: True)
        self.view.connect("create", self.on_create)
        self.view.connect("load-failed", self.on_load_failed)
        self.win.add(self.view)
        self.win.show_all()

        if self.fullscreen:
            self.win.fullscreen()
        elif self.pos:
            self.win.move(*self.pos)
        self.view.load_uri(self.url)

    def apply_settings(self):
        s = self.view.get_settings()
        props = {
            "media-playback-requires-user-gesture": False,
            "enable-developer-extras": env("CARDASH_DEV") == "1",
            "enable-write-console-messages-to-stdout": env("CARDASH_DEV") == "1",
            "enable-smooth-scrolling": False,
        }
        for key, val in props.items():
            try:
                s.set_property(key, val)
            except Exception:
                pass

    def on_create(self, _view, nav_action):
        # abre links com target=_blank na mesma janela
        try:
            req = nav_action.get_request()
            uri = req.get_uri()
        except Exception:
            uri = None
        if uri:
            self.view.load_uri(uri)
        return None

    def on_load_failed(self, view, _event, uri, _error):
        # servidor ainda subindo? tenta de novo em 1s
        GLib.timeout_add_seconds(1, self._reload, uri or self.url)
        return True

    def _reload(self, uri):
        self.view.load_uri(uri)
        return False

    def on_key(self, _win, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        kv = event.keyval
        if ctrl and kv in (Gdk.KEY_q, Gdk.KEY_w):
            Gtk.main_quit()
            return True
        if kv == Gdk.KEY_F11:
            if self.fullscreen:
                self.win.unfullscreen()
            else:
                self.win.fullscreen()
            self.fullscreen = not self.fullscreen
            return True
        return False


def main():
    if "--print" in sys.argv or "-p" in sys.argv:
        import json
        size, pos = geometry()
        print(json.dumps({
            "url": target_url(),
            "size": size,
            "pos": pos,
            "fullscreen": env("CARDASH_FULLSCREEN") == "1" or not size,
        }))
        return 0
    OpenDashApp()
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
