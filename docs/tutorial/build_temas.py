#!/usr/bin/env python3
"""Gera o video 'Temas do painel' do OpenDash (opendash-temas.mp4).

Duas fases, por causa dos modulos disponiveis em cada python:
  1. python3  build_temas.py --render     (renders es dos slides com cairo+Pango)
  2. /car-dash/.venv/bin/python build_temas.py   (narracao edge-tts + ffmpeg final)

Saida: opendash-temas.mp4 nesta pasta.
"""
import os
import shutil
import subprocess
import sys

W, H = 1280, 720
FPS = 30
VOICE = "pt-BR-ThalitaMultilingualNeural"
MUSIC_LEVEL = 0.16

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
BUILD = os.path.join(HERE, "build_temas")
OUT = os.path.join(HERE, "opendash-temas.mp4")

MEDIA_FIX = {  # paleta padrao usada na pagina Midia (nao muda com o tema)
    "panel": "#141416", "panel2": "#1c1d20", "line": "#2a2b30",
    "text": "#f5f5f7", "muted": "#9a9aa2", "accent": "#4a9eff",
    "bg": "#000000",
}

THEMES = [
    {"key": "ferrari", "label": "Ferrari — Rosso Corsa",
     "desc": "vermelho de corrida com amarelo Modena",
     "bg": "#0a0303", "bg2": "#120505", "panel": "#1a0a0a", "panel2": "#241010",
     "panel3": "#341616", "line": "#341414", "line2": "#4d1e1e", "text": "#fff2ee",
     "muted": "#d18b8b", "dim": "#8a4d4d", "accent": "#ff2800", "accent2": "#ff5a33",
     "red": "#ff2800", "amber": "#ffc400", "green": "#21c36b", "blue": "#4a8dff"},
    {"key": "porsche", "label": "Porsche — Guards",
     "desc": "prata e ouro sob o vermelho Guards",
     "bg": "#04070a", "bg2": "#080d12", "panel": "#0d141b", "panel2": "#131d26",
     "panel3": "#1c2a36", "line": "#18242f", "line2": "#2a3b4a", "text": "#eef4fa",
     "muted": "#8aa0b3", "dim": "#5a6f80", "accent": "#d8b24a", "accent2": "#f0d488",
     "red": "#c8102e", "amber": "#e9c14a", "green": "#22c07a", "blue": "#4a90d9"},
    {"key": "bmw", "label": "BMW — M Azul",
     "desc": "painel claro com azul M e vermelho",
     "bg": "#020608", "bg2": "#050b10", "panel": "#c9d3dd", "panel2": "#acb8c6",
     "panel3": "#8b98a8", "line": "#0e2438", "line2": "#1d3f5c", "text": "#05101c",
     "muted": "#3a5169", "dim": "#6b7f93", "accent": "#1c69d4", "accent2": "#5f9ceb",
     "red": "#e2231a", "amber": "#e0a020", "green": "#1fae76", "blue": "#1c69d4"},
    {"key": "amg", "label": "Mercedes-AMG — Petronas",
     "desc": "cinza AMG com verde petronas",
     "bg": "#0a0b0d", "bg2": "#101216", "panel": "#17191e", "panel2": "#1e2127",
     "panel3": "#262a32", "line": "#262a31", "line2": "#3a4049", "text": "#f2f4f7",
     "muted": "#979ca6", "dim": "#63676f", "accent": "#00a19b", "accent2": "#4fd9d2",
     "red": "#d5001c", "amber": "#e0a020", "green": "#21c07a", "blue": "#4a90d9"},
    {"key": "lambo", "label": "Lamborghini — Giallo",
     "desc": "amarelo Giallo sobre preto, estilo hexagonal",
     "bg": "#08090a", "bg2": "#0f1012", "panel": "#16181b", "panel2": "#1f2226",
     "panel3": "#2b2f35", "line": "#2a2e34", "line2": "#414750", "text": "#f5f6f8",
     "muted": "#a2a7af", "dim": "#6b7078", "accent": "#d4a017", "accent2": "#f2c94c",
     "red": "#e02020", "amber": "#d4a017", "green": "#21c45a", "blue": "#4a90d9"},
    {"key": "audi", "label": "Audi — Sport",
     "desc": "grafite limpo com vermelho Sport",
     "bg": "#08090b", "bg2": "#0e1013", "panel": "#17191d", "panel2": "#202329",
     "panel3": "#2a2e35", "line": "#262a31", "line2": "#3c424b", "text": "#f4f5f7",
     "muted": "#9aa0a8", "dim": "#646a73", "accent": "#e2231a", "accent2": "#ff6b60",
     "red": "#e2231a", "amber": "#e0a020", "green": "#21c07a", "blue": "#4a90d9"},
    {"key": "tesla", "label": "Tesla — Minimalista",
     "desc": "claro e minimalista, painel de eletrico",
     "bg": "#f5f6f8", "bg2": "#ffffff", "panel": "#ffffff", "panel2": "#eef0f3",
     "panel3": "#e2e5ea", "line": "#dde0e6", "line2": "#c3c8d0", "text": "#14161a",
     "muted": "#62666e", "dim": "#9498a0", "accent": "#e82127", "accent2": "#ff5a5f",
     "red": "#e82127", "amber": "#d99a12", "green": "#1fae76", "blue": "#2f7fd6"},
    {"key": "gr", "label": "Toyota GR — JDM",
     "desc": "preto japones com vermelho GR",
     "bg": "#05070a", "bg2": "#0a0e14", "panel": "#10151d", "panel2": "#171e28",
     "panel3": "#202936", "line": "#1b2430", "line2": "#2e3d50", "text": "#eef2f7",
     "muted": "#8697a8", "dim": "#566574", "accent": "#e60012", "accent2": "#ff5a48",
     "red": "#e60012", "amber": "#e0a020", "green": "#21c07a", "blue": "#4a90d9"},
    {"key": "mustang", "label": "Ford Mustang",
     "desc": "azul Mustang com listras e vermelho",
     "bg": "#05070d", "bg2": "#0a0e17", "panel": "#101624", "panel2": "#161e30",
     "panel3": "#1f2940", "line": "#1c2740", "line2": "#2f3f63", "text": "#eef2fb",
     "muted": "#8896b5", "dim": "#586787", "accent": "#4a7bd0", "accent2": "#7aa0ff",
     "red": "#e2231a", "amber": "#e0a020", "green": "#21c07a", "blue": "#4a7bd0"},
    {"key": "corvette", "label": "Chevrolet Corvette",
     "desc": "amarelo Corvette sobre couro escuro",
     "bg": "#0a0703", "bg2": "#120d05", "panel": "#1a1408", "panel2": "#241c0d",
     "panel3": "#332810", "line": "#322508", "line2": "#4d3a10", "text": "#fff6e0",
     "muted": "#c2a266", "dim": "#8a7038", "accent": "#f5c518", "accent2": "#ffe27a",
     "red": "#d02020", "amber": "#f5c518", "green": "#21c07a", "blue": "#4a90d9"},
]

NARRA = {
    "intro": (
        "O painel do OpenDash agora tem uma secao chamada Temas, inspirada nas maiores marcas "
        "de carro do mundo. Nao e so a cor que muda: cada tema troca o fundo, o brilho, a "
        "tipografia, o velocimetro, as lampadas e os icones do painel. Neste video eu mostro "
        "cada um deles. E o mais importante: o tema muda apenas o painel. A pagina de Midia "
        "continua com o fundo padrao de sempre."),
    "themalist": [
        "Tema Ferrari: vermelho Rosso Corsa com amarelo Modena e arcos bem esportivos.",
        "Tema Porsche: prata e ouro, com o vermelho Guards nas zonas de alerta.",
        "Tema BMW: um painel claro com o azul M e os aneis tipicos da marca.",
        "Tema Mercedes AMG: cinza escuro com o verde petronas das pistas.",
        "Tema Lamborghini: amarelo Giallo sobre preto, com as formas hexagonais.",
        "Tema Audi: grafite limpo com vermelho Sport e aneis finos.",
        "Tema Tesla: o mais claro e minimalista, sem brilho, estilo painel de eletrico.",
        "Tema Toyota GR: preto japones com o vermelho GR das pistas.",
        "Tema Ford Mustang: azul Mustang com listras e detalhes em vermelho.",
        "Tema Chevrolet Corvette: amarelo Corvette sobre couro escuro, muito anos setenta.",
    ],
    "trocar": (
        "Para trocar o tema, abra Ajustes e escolha o Tema do painel. Ou edite o arquivo "
        "config ponto yaml, na secao temas, e coloque o nome da marca em ativo. Isso funciona "
        "tanto no painel principal quanto no painel de velocidade. No modo automatico, o "
        "painel fica claro de dia e escuro de noite."),
    "fim": (
        "Sao dez temas de marca, cada um com seu fundo, sua tipografia e seu velocimetro "
        "proprio. A troca e instantanea. Ande com o painel da sua marca favorita. Bom passeio."),
}


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.stderr.write(r.stdout.decode("utf-8", "ignore"))
        raise SystemExit("falhou: " + " ".join(cmd))


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return float(r.stdout.decode().strip())


# ---------------------------------------------------------------- fase 1: PNGs
def render_all():
    import cairo
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo
    FONT = "DejaVu Sans"
    FONT_B = "DejaVu Sans Bold"
    FONT_M = "DejaVu Sans Mono"

    def rgb(h, alpha=1.0):
        h = h.lstrip("#")
        return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255,
                int(h[4:6], 16) / 255, alpha)

    class C:
        def __init__(self, path):
            self.path = path
            self.s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
            self.x = cairo.Context(self.s)

        def bg(self, color):
            self.x.set_source_rgba(*rgb(color))
            self.x.paint()

        def text(self, x, y, s, size, color, bold=False, mono=False, anchor="start",
                 alpha=1.0):
            lay = PangoCairo.create_layout(self.x)
            fam = FONT_B if bold else (FONT_M if mono else FONT)
            lay.set_font_description(Pango.FontDescription(f"{fam} {size}"))
            lay.set_text(s, -1)
            tw, _ = lay.get_pixel_size()
            if anchor == "end":
                x -= tw
            elif anchor == "middle":
                x -= tw / 2
            r, g, b = rgb(color)[:3]
            self.x.set_source_rgba(r, g, b, alpha)
            self.x.move_to(x, y)
            PangoCairo.show_layout(self.x, lay)
            self.x.new_path()
            return tw

        def rect(self, x, y, w, h, fill, stroke, sw=2, radius=12):
            xq = self.x
            xq.new_sub_path()
            xq.arc(x + w - radius, y + radius, radius, -1.5708, 0)
            xq.arc(x + w - radius, y + h - radius, radius, 0, 1.5708)
            xq.arc(x + radius, y + h - radius, radius, 1.5708, 3.1416)
            xq.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
            xq.close_path()
            xq.set_source_rgba(*rgb(fill))
            xq.fill_preserve()
            if stroke:
                xq.set_source_rgba(*rgb(stroke))
                xq.set_line_width(sw)
                xq.stroke()
            xq.new_path()

        def line(self, x1, y1, x2, y2, color, sw=2):
            self.x.set_source_rgba(*rgb(color))
            self.x.set_line_width(sw)
            self.x.move_to(x1, y1)
            self.x.line_to(x2, y2)
            self.x.stroke()
            self.x.new_path()

        def arcseg(self, cx, cy, r, a0, a1, color, sw):
            self.x.new_path()
            self.x.set_source_rgba(*rgb(color))
            self.x.set_line_width(sw)
            self.x.set_line_cap(cairo.LINE_CAP_BUTT)
            self.x.arc(cx, cy, r, a0, a1)
            self.x.stroke()
            self.x.new_path()

        def dot(self, x, y, r, color):
            self.x.new_path()
            self.x.arc(x, y, r, 0, 6.2832)
            self.x.set_source_rgba(*rgb(color))
            self.x.fill()
            self.x.new_path()

        def save(self):
            self.s.write_to_png(self.path)

    def arc_gauge(c, cx, cy, r, pct, color, caption, val, unit, t):
        start = 2.35619
        span = 4.71239
        c.arcseg(cx, cy, r, start, start + span, t["line"], 14)
        c.arcseg(cx, cy, r, start, start + span * pct, color, 14)
        c.text(cx, cy - r - 38, caption, 16, t["muted"], anchor="middle")
        c.text(cx, cy - 56, val, 56, t["text"], bold=True, anchor="middle")
        c.text(cx, cy + 28, unit, 18, t["muted"], anchor="middle")

    def tile(c, x, y, w, h, title, value, color, t):
        c.rect(x, y, w, h, t["panel"], t["line"], 2)
        big = h >= 100
        ty = y + (24 if big else 14)
        vy = y + (62 if big else 32)
        vs = 30 if big else 22
        c.text(x + 16, ty, title, 15 if big else 13, t["muted"])
        c.text(x + 16, vy, value, vs, color, bold=True)
        c.dot(x + w - 22, ty + 8, 5, color)

    def media_card(c, x, y, w, h):
        m = MEDIA_FIX
        c.rect(x, y, w, h, m["panel"], m["line"], 2)
        c.text(x + 16, y + 20, "Midia", 15, m["muted"])
        c.text(x + 16, y + 52, "Rádio FM", 26, m["text"], bold=True)
        c.text(x + 16, y + 92, "OpenDash Player", 15, m["muted"])
        c.rect(x + 16, y + 118, w - 32, 8, m["panel2"], None, 0, 4)
        c.rect(x + 16, y + 118, (w - 32) * 0.48, 8, m["accent"], None, 0, 4)
        c.text(x + 16, y + 136, "tema fixo: nao acompanha o painel",
               13, m["muted"])

    def dashboard(theme, idx, total):
        c = C(os.path.join(BUILD, f"slide_t{idx}.png"))
        t = theme
        c.bg(t["bg"])
        topbar_h = 64
        c.rect(0, 0, W, topbar_h, t["bg2"], None, 0, 0)
        c.rect(0, topbar_h - 2, W, 2, t["line"], None, 0, 0)
        wbrand = c.text(40, 18, "OpenDash", 22, t["accent"], bold=True)
        c.text(40 + wbrand + 16, 24, "temas de marcas", 13, t["muted"])
        c.text(W - 40, 14, "19:42", 22, t["text"], bold=True, anchor="end")
        c.text(W - 40, 40, "sab 31 jan", 15, t["muted"], anchor="end")

        c.text(40, 92, t["label"], 40, t["text"], bold=True)
        c.text(40, 154, t["desc"], 18, t["muted"])
        chips = [t["accent"], t["accent2"], t["green"], t["amber"], t["red"],
                 t.get("blue") or t.get("purple") or t["accent"]]
        for i, col in enumerate(chips):
            c.dot(48 + i * 30, 186, 7, col)
        widx = c.text(W - 40, 100, f"{idx} / {total}", 22, t["dim"], bold=True,
                      anchor="end")

        lx, ly, lw = 40, 214, 640
        c.rect(lx, ly, lw, 356, t["panel"], t["line"], 2)
        gy = ly + 148
        arc_gauge(c, lx + 170, gy, 80, 0.55, t["accent"],
                  "velocidade", "86", "km/h", t)
        arc_gauge(c, lx + lw - 170, gy, 80, 0.38, t["green"],
                  "motor", "2.4", "x1000 rpm", t)
        tw_ = (lw - 44) / 2
        bl = t.get("blue") or t.get("cyan") or t["accent"]
        tile(c, lx + 16, ly + 280, tw_, 70, "combustivel", "62%", bl, t)
        tile(c, lx + 28 + tw_, ly + 280, tw_, 70, "temperatura", "92C",
             t["amber"], t)

        rx, ry, rw = lw + 92, 214, W - lw - 132
        tile(c, rx, ry, rw, 112, "voltagem", "12.9V", t["green"], t)
        tile(c, rx, ry + 126, rw, 112, "carga", "1.2kW",
             t.get("cyan") or t.get("purple") or t["green"], t)
        media_card(c, rx, ry + 252, rw, 168)

        tabs = ["dirigir", "energia", "navegacao", "midia", "apps", "clima",
                "diag", "ajustes"]
        tx = 40
        for i, name in enumerate(tabs):
            wpx = c.text(tx, 616, name, 14, t["text"] if i == 0 else t["dim"],
                         bold=(i == 0))
            tx += wpx + 16
        c.rect(0, 650, W, 70, t["bg2"], None, 0, 0)
        c.rect(0, 650, W, 2, t["line"], None, 0, 0)
        c.text(40, 676, "OpenDash", 16, t["accent"], bold=True)
        c.text(W - 40, 676, "o painel muda | a Midia NAO", 15, t["muted"],
               anchor="end")
        c.save()

    def slide_list():
        c = C(os.path.join(BUILD, "slide_list.png"))
        c.bg("#0b0f14")
        cols = [("#ff2800", "Ferrari"), ("#d8b24a", "Porsche"),
                ("#1c69d4", "BMW"), ("#00a19b", "AMG"),
                ("#d4a017", "Lamborghini"), ("#e2231a", "Audi"),
                ("#e82127", "Tesla"), ("#e60012", "Toyota GR"),
                ("#4a7bd0", "Mustang"), ("#f5c518", "Corvette")]
        wbrand = c.text(60, 40, "OpenDash", 28, "#2f81f7", bold=True)
        c.text(60 + wbrand + 18, 48, "temas de marcas", 18, "#8b949e")
        c.text(60, 120, "Dez marcas, dez paineis", 50, "#f0f6fc", bold=True)
        c.text(W - 60, 48, "1 / 13", 20, "#8b949e", anchor="end")
        x0, y0, tw_, th_ = 60, 210, (W - 120 - 40) / 2, 160
        for i, (col, label) in enumerate(cols):
            x = x0 + (i % 2) * (tw_ + 40)
            y = y0 + (i // 2) * (th_ + 24)
            c.rect(x, y, tw_, th_, "#121a24", "#2d3b4d", 2)
            c.rect(x, y, 10, th_, col, None, 0, 0)
            c.text(x + 34, y + 34, f"{i + 1:02d}", 15, "#8b949e", mono=True)
            c.text(x + 34, y + 72, label, 30, "#f0f6fc", bold=True)
            c.dot(x + 34, y + 118, 8, col)
        c.save()

    # 13 slides: lista incial + 10 temas + trocar + fim
    slide_list()
    for i, t in enumerate(THEMES, 1):
        dashboard(t, i, 10)
    return sorted(
        [f for f in os.listdir(BUILD) if f.startswith("slide_") and
         f.endswith(".png")])


# ---------------------------------------------------------------- fase 2: a/v
def main_av():
    from edge_tts import Communicate
    import asyncio

    def make_voice(idx, text):
        mp3 = os.path.join(BUILD, f"voice_{idx}.mp3")
        wav = os.path.join(BUILD, f"voice_{idx}.wav")

        async def synth():
            await Communicate(text, VOICE).save(mp3)

        asyncio.run(synth())
        run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
        return wav

    def make_segment(idx, png, wav):
        seg = os.path.join(BUILD, f"seg_{idx}.mp4")
        dur = duration(wav) + 1.1
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png,
             "-i", wav, "-t", f"{dur:.3f}",
             "-vf", "fade=t=in:st=0:d=0.4,format=yuv420p", "-af", "apad",
             "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
             "-shortest", seg])
        return seg

    def make_music(total):
        music = os.path.join(BUILD, "music.wav")
        fade_out = max(0.0, total - 5)
        run(["ffmpeg", "-y",
             "-f", "lavfi", "-i", f"sine=f=110:d={total:.2f}",
             "-f", "lavfi", "-i", f"sine=f=164.8:d={total:.2f}",
             "-f", "lavfi", "-i", f"sine=f=220:d={total:.2f}",
             "-f", "lavfi", "-i", f"sine=f=277.2:d={total:.2f}",
             "-filter_complex",
             "[0][1][2][3]amix=inputs=4:normalize=1,"
             "lowpass=f=650,tremolo=f=0.15:d=0.35,volume=0.32,"
             f"afade=t=in:st=0:d=3,afade=t=out:st={fade_out:.2f}:d=5",
             "-ar", "44100", "-ac", "2", music])
        return music

    slides = []
    list_png = sorted(
        [f for f in os.listdir(BUILD) if f.startswith("slide_") and
         f.endswith(".png")])
    order = ["slide_list.png"]
    order += [f"slide_t{i}.png" for i in range(1, 11)]
    trocar = os.path.join(BUILD, "slide_trocar.png")
    fim = os.path.join(BUILD, "slide_fim.png")
    order += ["slide_trocar.png", "slide_fim.png"]
    missing = [f for f in order if not os.path.isfile(os.path.join(BUILD, f))]
    if missing:
        raise SystemExit("renders faltando: " + ", ".join(missing) +
                         " - rode `python3 build_temas.py --render` primeiro")
    slides = order

    print("1/3 narracao (edge-tts)...")
    texts = [NARRA["intro"], *NARRA["themalist"], NARRA["trocar"], NARRA["fim"]]
    wavs = []
    for i, (png, txt) in enumerate(zip(slides, texts), 1):
        wavs.append(make_voice(i, txt))
    print("2/3 segmentos...")
    segs = []
    for i, (png, wav) in enumerate(zip(slides, wavs), 1):
        seg = make_segment(i, os.path.join(BUILD, png), wav)
        print(f"  seg {i:02d} ({png})")
        segs.append(seg)
    listfile = os.path.join(BUILD, "list.txt")
    write(listfile, "".join(f"file '{s}'\n" for s in segs))
    narration = os.path.join(BUILD, "narration.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", narration])
    print("3/3 musica + final...")
    total_dur = duration(narration)
    music = make_music(total_dur)
    run(["ffmpeg", "-y", "-i", narration, "-i", music,
         "-filter_complex",
         f"[1:a]volume={MUSIC_LEVEL}[m];"
         "[0:a][m]amix=inputs=2:duration=first:normalize=0,"
         "loudnorm=I=-16:TP=-1.5:LRA=11[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", OUT])
    d = duration(OUT)
    size = os.path.getsize(OUT) / 1e6
    print(f"OK -> {OUT}")
    print(f"duracao: {int(d // 60)}m{int(d % 60):02d}s | tamanho: {size:.1f} MB "
          f"| cenas: {len(slides)}")


def main():
    global kicker_box
    kicker_box = "TEMAS DO PAINEL"
    if "--render" in sys.argv:
        if os.path.isdir(BUILD):
            shutil.rmtree(BUILD)
        os.makedirs(BUILD, exist_ok=True)
        render_all()
        make_text_slides()
        print("renders ok em", BUILD)
    else:
        os.makedirs(BUILD, exist_ok=True)
        main_av()


def make_text_slides():
    import cairo
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo

    def rgb(h, alpha=1.0):
        h = h.lstrip("#")
        return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255,
                int(h[4:6], 16) / 255, alpha)

    def slide(path, kicker, title, lines, color, footer=None, img=None):
        c = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        x = cairo.Context(c)
        x.set_source_rgba(*rgb("#0b0f14"))
        x.paint()
        x.set_source_rgba(*rgb(color))
        x.rectangle(0, 0, W, 8)
        x.fill()
        x.rectangle(0, H - 8, W, 8)
        x.fill()
        lay = PangoCairo.create_layout(x)
        lay.set_font_description(Pango.FontDescription("DejaVu Sans Bold 26"))
        lay.set_text("OpenDash", -1)
        x.set_source_rgba(*rgb(color))
        x.move_to(60, 36)
        PangoCairo.show_layout(x, lay)
        lay2 = PangoCairo.create_layout(x)
        lay2.set_font_description(Pango.FontDescription("DejaVu Sans 18"))
        lay2.set_text("temas de marcas", -1)
        x.set_source_rgba(*rgb("#8b949e"))
        x.move_to(60 + lay.get_pixel_size()[0] + 18, 46)
        PangoCairo.show_layout(x, lay2)
        layk = PangoCairo.create_layout(x)
        layk.set_font_description(Pango.FontDescription("DejaVu Sans Bold 20"))
        layk.set_text(kicker, -1)
        kw, _ = layk.get_pixel_size()
        bx = W - 60 - kw - 24
        x.set_source_rgba(*rgb(color))
        x.rectangle(bx, 30, kw + 24, 34)
        x.fill()
        x.set_source_rgba(*rgb("#ffffff"))
        x.move_to(bx + 12, 34)
        PangoCairo.show_layout(x, layk)
        if img:
            ic = cairo.ImageSurface.create_from_png(img)
            s = min(1100 / ic.get_width(), 260 / ic.get_height())
            x.save()
            x.translate((W - ic.get_width() * s) / 2, 168)
            x.scale(s, s)
            x.set_source_surface(ic)
            x.paint()
            x.restore()
            ty = 460
        else:
            ty = 150
        layt = PangoCairo.create_layout(x)
        layt.set_font_description(Pango.FontDescription(
            "DejaVu Sans Bold 50"))
        layt.set_text(title, -1)
        x.set_source_rgba(*rgb("#f0f6fc"))
        x.move_to(60, ty)
        PangoCairo.show_layout(x, layt)
        yy = ty + 92
        for ln in lines:
            layb = PangoCairo.create_layout(x)
            layb.set_font_description(Pango.FontDescription(
                "DejaVu Sans 26"))
            layb.set_text(ln, -1)
            x.set_source_rgba(*rgb(color))
            x.arc(66, yy + 14, 7, 0, 6.2832)
            x.fill()
            x.set_source_rgba(*rgb("#c9d1d9"))
            x.move_to(94, yy)
            PangoCairo.show_layout(x, layb)
            yy += 48
        if footer:
            layf = PangoCairo.create_layout(x)
            layf.set_font_description(Pango.FontDescription(
                "DejaVu Sans 17"))
            layf.set_text(footer, -1)
            x.set_source_rgba(*rgb("#8b949e"))
            x.move_to(W - 60 - layf.get_pixel_size()[0], H - 60)
            PangoCairo.show_layout(x, layf)
        c.write_to_png(path)

    mono_dirs = os.path.join(ASSETS, "page_settings.png")
    img = mono_dirs if os.path.isfile(mono_dirs) else None
    slide(os.path.join(BUILD, "slide_trocar.png"), "COMO TROCAR",
          "Ajustes ou config.yaml",
          ["Ajustes -> Tema do painel (seletor)",
           "config.yaml -> temas: ativo: ferrari",
           "auto = claro de dia, escuro de noite",
          ],
          "#2f81f7", footer="a pagina de Midia nunca muda de tema", img=img)
    slide(os.path.join(BUILD, "slide_fim.png"), "FIM",
          "Escolha a sua marca",
          ["A troca e instantanea em todas as telas",
           "Ferrari, Porsche, BMW, AMG, Lamborghini,",
           "Audi, Tesla, Toyota GR, Mustang e Corvette",
          ],
          "#e82127", footer="OpenDash - temas de marcas")


if __name__ == "__main__":
    main()
