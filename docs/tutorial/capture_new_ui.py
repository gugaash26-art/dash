#!/usr/bin/env python3
"""Captura as telas NOVAS do OpenDash para o tutorial com avatar.

Gera imagens 1024x600 reais da interface (WebKitGTK + Xvfb):
  page_settings_net.png   - Ajustes rolado ate os cartoes Wi-Fi / Bluetooth / Atualizacoes
  page_settings_agent.png - Ajustes rolado ate o cartao do Assistente de voz
  page_media_agent.png    - Pagina Midia com o cartao do assistente
  page_bar.png            - Cluster em barra (bar.html)

Variaveis:
  SHOT_URL  base da UI      (padrao http://127.0.0.1:8099/)
  SHOT_OUT  diretorio saida (padrao docs/tutorial/assets)
  SHOT_BOOT_MS espera pela animacao de boot (padrao 7000)
Use: xvfb-run -a -s "-screen 0 1024x600x24" python3 docs/tutorial/capture_new_ui.py
"""
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

W, H = 1024, 600
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("SHOT_URL", "http://127.0.0.1:8099/")
OUT = os.environ.get("SHOT_OUT", os.path.join(HERE, "assets"))
BOOT_MS = int(os.environ.get("SHOT_BOOT_MS", "7000"))

TAB = ("document.querySelector('.tab[data-page-go=\"%s\"]')"
       "&&document.querySelector('.tab[data-page-go=\"%s\"]').click();")
SCROLL = ("var p=document.querySelector('.page[data-page=\"settings\"]');"
          "var c=document.getElementById('%s').closest('.card');"
          "if(p&&c){p.scrollTop=c.offsetTop-70;}")
SIDE = ("var s=document.querySelector('.media-side');"
        "var c=document.getElementById('%s').closest('.card');"
        "if(s&&c){s.scrollTop=c.offsetTop-12;}")

# Icones em SVG (o dispositivo nao tem fonte de emoji):
_ICO = ("var W='<svg viewBox=\"0 0 24 24\" width=\"20\" height=\"20\" fill=\"none\" "
        "stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\">';"
        "var ICOWIFI=W+'<path d=\"M2 8.6a15 15 0 0 1 20 0\"/><path d=\"M5.5 12.2a10 10 0 0 1 13 0\"/>"
        "<path d=\"M9 15.8a5 5 0 0 1 6 0\"/><circle cx=\"12\" cy=\"19.2\" r=\"1.3\" fill=\"currentColor\"/></svg>';"
        "var ICOLOCK=W+'<rect x=\"4.5\" y=\"10.5\" width=\"15\" height=\"10\" rx=\"2.5\"/>"
        "<path d=\"M8 10.5V7.5a4 4 0 0 1 8 0v3\"/></svg>';"
        "var ICOBT=W+'<path d=\"M7 7.5l10 9-5 4.5V3l5 4.5-10 9\"/></svg>';"
        "var ICOHEAD=W+'<path d=\"M4 13.5v-1.5a8 8 0 0 1 16 0v1.5\"/>"
        "<rect x=\"3\" y=\"13\" width=\"4.5\" height=\"6.5\" rx=\"2\"/>"
        "<rect x=\"16.5\" y=\"13\" width=\"4.5\" height=\"6.5\" rx=\"2\"/></svg>';")
_BARS = ("function bars(s){var l=s>=75?4:s>=50?3:s>=25?2:1,h='<span class=\"net-bars\">';"
         "for(var i=1;i<=4;i++)h+='<i class=\"'+(i<=l?'on':'')+'\"></i>';return h+'</span>';}")

NET_DEMO = ("(function(){" + _ICO + _BARS +
            "var c=document.getElementById('wifiEnabled');if(c){c.disabled=false;c.checked=true;}"
            "var s=document.getElementById('wifiStatus');"
            "if(s){s.textContent='conectado a Casa-2.4G · 192.168.0.42';s.className='net-status ok';}"
            "var sc=document.getElementById('wifiScan');if(sc)sc.disabled=false;"
            "var l=document.getElementById('wifiList');"
            "if(l){l.dataset.loaded='1';l.innerHTML="
            "'<div class=\"net-item active\"><span class=\"net-ico\">'+ICOLOCK+'</span>"
            "<span class=\"info\"><b>Casa-2.4G</b><small>WPA2 · conectada</small></span>'+bars(88)+"
            "'<span class=\"actions\"><button class=\"btn btn-ghost\" data-wifi-action=\"disconnect\">Desconectar</button></span></div>'+"
            "'<div class=\"net-item\"><span class=\"net-ico\">'+ICOLOCK+'</span>"
            "<span class=\"info\"><b>Casa-5G</b><small>WPA2</small></span>'+bars(70)+"
            "'<span class=\"actions\"><button class=\"btn\" data-wifi-connect=\"Casa-5G\">Conectar</button></span></div>'+"
            "'<div class=\"net-item\"><span class=\"net-ico\">'+ICOWIFI+'</span>"
            "<span class=\"info\"><b>Cafe-do-Zeca</b><small>aberta</small></span>'+bars(34)+"
            "'<span class=\"actions\"><button class=\"btn\" data-wifi-connect=\"Cafe-do-Zeca\">Conectar</button></span></div>';}"
            "var bc=document.getElementById('btEnabled');if(bc){bc.disabled=false;bc.checked=true;}"
            "var bs=document.getElementById('btStatus');"
            "if(bs){bs.textContent='ligado · OrangePi';bs.className='net-status ok';}"
            "var bsc=document.getElementById('btScan');if(bsc)bsc.disabled=false;"
            "var bl=document.getElementById('btList');"
            "if(bl){bl.innerHTML="
            "'<div class=\"net-item active\"><span class=\"net-ico\">'+ICOHEAD+'</span>"
            "<span class=\"info\"><b>Fone do carro</b><small>A0:1B:2C:3D:4E:5F</small></span>"
            "<span class=\"net-badge on\">conectado</span><span class=\"actions\">"
            "<button class=\"btn btn-ghost\" data-bt-action=\"disconnect\" data-mac=\"A0:1B:2C:3D:4E:5F\">Desconectar</button></span></div>'+"
            "'<div class=\"net-item\"><span class=\"net-ico\">'+ICOBT+'</span>"
            "<span class=\"info\"><b>Celular</b><small>B1:2C:3D:4E:5F:60</small></span>"
            "<span class=\"net-badge\">pareado</span><span class=\"actions\">"
            "<button class=\"btn\" data-bt-action=\"connect\" data-mac=\"B1:2C:3D:4E:5F:60\">Conectar</button></span></div>';}"
            "})();")

UPDATE_DEMO = ("(function(){"
               "var s=document.getElementById('updateStatus');"
               "if(s){s.textContent='atualização disponível (2 commits)';s.className='net-status warn';}"
               "var b=document.getElementById('updateInstall');if(b)b.disabled=false;"
               "var i=document.getElementById('updateInfo');"
               "if(i){i.innerHTML="
               "'<div><small>Versão atual</small><b>a103408</b></div>'+"
               "'<div><small>Descrição</small><b>melhorias no cluster</b></div>'+"
               "'<div><small>Branch</small><b>main</b></div>'+"
               "'<div><small>Repositório</small><b>github.com/gugaash26-art/dash</b></div>'+"
               "'<div><small>Novidade</small><b>b71f2c9 assistente com novas ações</b></div>';}"
               "})();")

MEDIA_DEMO = ("(function(){"
              "var st=document.getElementById('agentStatus');"
              "if(st){st.classList.remove('think','rec');st.classList.add('ok');}"
              "var t=document.getElementById('agentStatusText');if(t)t.textContent='pronto';"
              "var y=document.getElementById('agentYou');if(y)y.textContent='\"abrir o YouTube\"';"
              "var r=document.getElementById('agentReply');"
              "if(r)r.textContent='Claro! Abrindo o YouTube para você.';"
              "var b=document.getElementById('agentSys');"
              "if(b){b.innerHTML="
              "'<div><small>Voz→texto</small><b>pronto</b></div>'+"
              "'<div><small>Microfone</small><b>ok</b></div>'+"
              "'<div><small>IA</small><b>pronta</b></div>'+"
              "'<div><small>Voz (TTS)</small><b>edge-tts</b></div>';}"
              "})();")

SHOTS = [
    {"out": "page_settings_display.png", "url": BASE,
     "steps": [(TAB % ("settings", "settings"), 1600),
               (SCROLL % "displayInfo", 1200)]},
    {"out": "page_settings_camera.png", "url": BASE,
     "steps": [(TAB % ("settings", "settings"), 1600),
               (SCROLL % "camStatus", 1200)]},
    {"out": "page_settings_net.png", "url": BASE,
     "steps": [(TAB % ("settings", "settings"), 1600),
               (SCROLL % "wifiEnabled", 1200),
               (NET_DEMO, 800)]},
    {"out": "page_settings_agent.png", "url": BASE,
     "steps": [(TAB % ("settings", "settings"), 1600),
               (SCROLL % "agentSpeak", 1200)]},
    {"out": "page_settings_update.png", "url": BASE,
     "steps": [(TAB % ("settings", "settings"), 1600),
               (SCROLL % "updateStatus", 1200),
               (UPDATE_DEMO, 800)]},
    {"out": "page_media_agent.png", "url": BASE,
     "steps": [(TAB % ("media", "media"), 1800),
               (SIDE % "agentMic", 1000),
               (MEDIA_DEMO, 800)]},
    {"out": "page_bar.png", "url": BASE + "bar.html", "steps": [], "size": (1920, 480)},
]


class App:
    def __init__(self):
        os.makedirs(OUT, exist_ok=True)
        self.win = Gtk.Window()
        self.win.set_title("OpenDash")
        self.win.set_default_size(W, H)
        self.win.set_resizable(True)
        self.view = WebKit2.WebView()
        self.win.add(self.view)
        self.view.connect("load-changed", self.on_load)
        self.win.show_all()
        self.idx = 0
        self.load_shot()

    def load_shot(self):
        self.spec = SHOTS[self.idx]
        self.steps = list(self.spec.get("steps", []))
        self.cw, self.ch = self.spec.get("size", (W, H))
        self.win.resize(self.cw, self.ch)
        self.view.load_uri(self.spec["url"])

    def on_load(self, view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(BOOT_MS, self.run_steps)

    def run_steps(self):
        if not self.steps:
            return self.grab_save()
        js, delay = self.steps.pop(0)
        if js:
            self.view.run_javascript(js, None, None, None)
        GLib.timeout_add(delay, self.run_steps)
        return False

    def grab(self, path):
        win = self.win.get_window()
        pb = Gdk.pixbuf_get_from_window(win, 0, 0, self.cw, self.ch)
        if pb is not None:
            pb.savev(path, "png", [], [])
            return True
        return False

    def grab_save(self):
        path = os.path.join(OUT, self.spec["out"])
        self.grab(path)
        print("shot:", self.spec["out"], flush=True)
        self.idx += 1
        if self.idx >= len(SHOTS):
            Gtk.main_quit()
            return False
        GLib.timeout_add(600, self.load_shot)
        return False


def main():
    App()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
