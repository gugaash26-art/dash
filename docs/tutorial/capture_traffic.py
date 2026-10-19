#!/usr/bin/env python3
"""Captura a cena de TRANSITO AO VIVO (onibus SPTrans / Olho Vivo).

Sem credencial da apilib o servidor nao devolve veiculos; para a foto do
tutorial injetamos uma resposta de demonstracao (mesmo formato de /api/traffic)
e ligamos a camada pela propria interface. O mapa, o carro e o resto da tela
continuam sendo a UI real.

Variaveis:
  SHOT_URL  base da UI      (padrao http://127.0.0.1:8080/)
  SHOT_OUT  arquivo saida   (padrao docs/tutorial/assets/page_traffic.png)
  BOOT_MS   espera pelo boot/mapa (padrao 8000)
Use: xvfb-run -a -s "-screen 0 1024x600x24" python3 docs/tutorial/capture_traffic.py
"""
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

W, H = 1024, 600
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("SHOT_URL", "http://127.0.0.1:8080/")
OUT = os.environ.get("SHOT_OUT", os.path.join(HERE, "assets", "page_traffic.png"))
BOOT_MS = int(os.environ.get("BOOT_MS", "8000"))

DEMO = r"""(function(){
  var cen = null, vs = [];
  var names = ['8000','875A','477P','609F','702U','517J','177Y','857P',
               '5614','917H','857A','702P'];
  var orig = window.fetch;
  function fake(obj){
    return Promise.resolve(new Response(JSON.stringify(obj),
      {status:200, headers:{'Content-Type':'application/json'}}));
  }
  function build(){
    vs = [];
    for (var i=0;i<16;i++){
      var a = i*0.42+0.3, r = 0.0012+(i%5)*0.00055;
      vs.push({lat: cen.lat + r*Math.sin(a),
               lon: cen.lon + r*Math.cos(a)*1.1,
               c: names[i%names.length],
               lt0: 'Terminal', lt1: 'Centro', sl: i%2});
    }
  }
  window.fetch = function(u, o){
    var s = String(u);
    if (s.indexOf('/api/traffic') === 0) {
      return fake({enabled:true, count:vs.length, vehicles:vs, hr:'ao vivo'});
    }
    if (s.indexOf('/api/apps') === 0) {
      return orig.apply(this, arguments).then(function(r){return r.json();})
        .then(function(d){ d.traffic = {enabled:true, hr:'ao vivo'};
                           return fake(d); });
    }
    return orig.apply(this, arguments);
  };
  orig.call(window, '/api/state').then(function(r){return r.json();})
    .then(function(st){
      var g = (st && st.gps) || {};
      cen = {lat: g.lat || -23.5568, lon: g.lon || -46.6574};
      build();
      var apps = document.querySelector('.tab[data-page-go="apps"]');
      if (apps) apps.click();
      setTimeout(function(){
        var nav = document.querySelector('.tab[data-page-go="nav"]');
        if (nav) nav.click();
        setTimeout(function(){
          var cb = document.getElementById('navTraffic');
          if (cb) { cb.checked = true; cb.dispatchEvent(new Event('change')); }
        }, 2600);
      }, 500);
    });
})();"""


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
        self.view.load_uri(BASE)

    def on_load(self, view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(BOOT_MS, self.demo)

    def demo(self):
        self.view.run_javascript(DEMO, None, None, None)
        GLib.timeout_add(7000, self.grab)
        return False

    def grab(self):
        pb = Gdk.pixbuf_get_from_window(self.win.get_window(), 0, 0, W, H)
        if pb is not None:
            pb.savev(OUT, "png", [], [])
        print("saved", OUT, flush=True)
        Gtk.main_quit()
        return False


App()
Gtk.main()
