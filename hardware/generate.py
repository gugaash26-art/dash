#!/usr/bin/env python3
"""Gera o esquema eletrico e o desenho da placa de juncao do OpenDash.

Saida (em hardware/out/):
  schematic.svg   esquema eletrico completo (alimentacao, CAN, GPS, entradas,
                  analogicos, saidas) com rotulos de rede
  board.svg       desenho mecanico da placa (shield do Arduino Mega) com
                  conectores, modulos, furos e tabela de brocas
  bom.csv         lista de materiais
  netlist.csv     lista de conexoes (net <-> componente/pino)

Sem dependencias externas. Depois, para PNG: python3 hardware/render_svg.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

WIRE = "#0f5132"
PWR = "#b00020"
GNDC = "#333333"
BODY = "#243b53"
VAL = "#555555"
NETBG = "#eef4ff"
NETBR = "#2f6fed"
PWRBG = "#ffe9ec"
PWRBR = "#d7263d"

DIGITAL_INPUTS = [
    ("IN_LEFT",   "Seta esquerda",   "D2",  "J6.1"),
    ("IN_RIGHT",  "Seta direita",    "D3",  "J6.2"),
    ("IN_HEAD",   "Farol baixo",     "D4",  "J6.3"),
    ("IN_HIGH",   "Farol alto",      "D5",  "J6.4"),
    ("IN_BRAKE",  "Freio de mao",    "D6",  "J6.5"),
    ("IN_BELT",   "Cinto",           "D7",  "J6.6"),
    ("IN_DOOR",   "Porta aberta",    "D8",  "J6.7"),
    ("IN_HAZARD", "Pisca alerta",    "D9",  "J6.8"),
    ("IN_IGN",    "Ignicao (pos-chave)", "D22", "J6.9"),
    ("IN_REV",    "Marcha a re",     "D46", "J6.10"),
]

ANALOG = [
    ("ANA_OILP", "Pressao do oleo (0,5-4,5 V)", "A0", "J7.1", "volt",
     "R201", "DZ201", "C201"),
    ("ANA_FUEL", "Nivel combustivel (boia)",    "A1", "J7.2", "res",
     "R202", "DZ202", "C202"),
    ("ANA_OILT", "Temperatura do oleo",         "A2", "J7.3", "volt",
     "R204", "DZ203", "C203"),
    ("ANA_BATT", "Tensao da bateria",           "A3", "J7.4", "div",
     "R205", "DZ204", "C204"),
]


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Sheet:
    def __init__(self, w, h, bg="#ffffff"):
        self.w, self.h, self.bg, self.el = w, h, bg, []

    def line(self, x1, y1, x2, y2, stroke=WIRE, w=2, dash=None, cap="round"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{w}" stroke-linecap="{cap}"{d}/>')

    def poly(self, pts, stroke=WIRE, w=2, fill="none", dash=None):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.el.append(f'<polyline points="{p}" fill="{fill}" stroke="{stroke}" '
                       f'stroke-width="{w}" stroke-linejoin="round"{d}/>')

    def rect(self, x, y, w, h, fill="none", stroke=BODY, sw=2, rx=0):
        self.el.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                       f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def circle(self, cx, cy, r, fill="none", stroke=BODY, sw=2):
        self.el.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                       f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def dot(self, x, y, r=3.4, fill=WIRE):
        self.el.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}"/>')

    def text(self, x, y, s, size=13, fill="#111111", anchor="start", weight="normal",
             family="DejaVu Sans, Arial, sans-serif"):
        self.el.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text>')

    def netlabel(self, x, y, s, color=NETBR, bg=NETBG, size=13, anchor="start"):
        w = 10 + len(s) * (size * 0.60)
        x0 = x - w if anchor == "end" else (x - w / 2 if anchor == "middle" else x)
        self.rect(x0, y - size - 3, w, size + 9, fill=bg, stroke=color, sw=1.4, rx=3)
        self.text(x0 + 5, y + 2, s, size=size, fill=color, weight="bold")
        return x0, w

    def gnd(self, x, y, label="GND"):
        self.line(x, y, x, y + 11)
        self.line(x - 12, y + 11, x + 12, y + 11, GNDC, 2)
        self.line(x - 8, y + 16, x + 8, y + 16, GNDC, 2)
        self.line(x - 4, y + 21, x + 4, y + 21, GNDC, 2)
        self.text(x, y + 36, label, size=10, fill=GNDC, anchor="middle")

    def power(self, x, y, s="+5V"):
        self.line(x, y, x, y - 9)
        self.line(x - 9, y - 9, x + 9, y - 9, PWR, 2)
        self.line(x - 5, y - 14, x + 5, y - 14, PWR, 2)
        self.text(x, y - 18, s, size=10, fill=PWR, anchor="middle", weight="bold")

    def res_h(self, cx, cy, label=""):
        self.line(cx - 30, cy, cx - 16, cy)
        self.rect(cx - 16, cy - 8, 32, 16, fill="#fff")
        self.line(cx + 16, cy, cx + 30, cy)
        if label:
            self.text(cx, cy - 13, label, size=10, fill=VAL, anchor="middle")

    def res_v(self, cx, cy, label=""):
        self.line(cx, cy - 30, cx, cy - 16)
        self.rect(cx - 8, cy - 16, 16, 32, fill="#fff")
        self.line(cx, cy + 16, cx, cy + 30)
        if label:
            self.text(cx + 12, cy + 4, label, size=10, fill=VAL)

    def cap_v(self, cx, cy, label=""):
        self.line(cx, cy - 30, cx, cy - 6)
        self.line(cx - 12, cy - 6, cx + 12, cy - 6, BODY, 2.5)
        self.line(cx - 12, cy + 6, cx + 12, cy + 6, BODY, 2.5)
        self.line(cx, cy + 6, cx, cy + 30)
        if label:
            self.text(cx + 14, cy + 4, label, size=10, fill=VAL)

    def zener_v(self, cx, cy, label=""):
        self.line(cx, cy - 30, cx, cy - 12)
        self.poly([(cx - 11, cy - 12), (cx + 11, cy - 12), (cx, cy + 10), (cx - 11, cy - 12)],
                  BODY, 2, fill="#fff")
        self.poly([(cx + 9, cy - 15), (cx + 15, cy - 12), (cx + 11, cy - 8)], BODY, 2)
        self.line(cx, cy + 10, cx, cy + 30)
        if label:
            self.text(cx + 16, cy + 2, label, size=10, fill=VAL)

    def diode_h(self, cx, cy, label=""):
        self.line(cx - 30, cy, cx - 11, cy)
        self.poly([(cx - 11, cy - 11), (cx - 11, cy + 11), (cx + 10, cy), (cx - 11, cy - 11)],
                  BODY, 2, fill="#fff")
        self.line(cx + 10, cy - 11, cx + 10, cy + 11, BODY, 2.5)
        self.line(cx + 10, cy, cx + 30, cy)
        if label:
            self.text(cx, cy - 15, label, size=10, fill=VAL, anchor="middle")

    def led_h(self, cx, cy, label=""):
        self.line(cx - 30, cy, cx - 11, cy)
        self.poly([(cx - 11, cy - 11), (cx - 11, cy + 11), (cx + 10, cy), (cx - 11, cy - 11)],
                  BODY, 2, fill="#fff")
        self.line(cx + 10, cy - 11, cx + 10, cy + 11, BODY, 2.5)
        self.line(cx + 10, cy, cx + 30, cy)
        self.poly([(cx - 4, cy - 13), (cx + 2, cy - 20)], BODY, 1.5)
        self.poly([(cx + 3, cy - 13), (cx + 9, cy - 20)], BODY, 1.5)
        if label:
            self.text(cx, cy - 25, label, size=10, fill=VAL, anchor="middle")

    def npn(self, cx, cy, label=""):
        self.circle(cx, cy, 20, fill="#fff")
        self.line(cx - 9, cy - 13, cx - 9, cy + 13, BODY, 2.5)
        self.line(cx - 28, cy, cx - 9, cy)
        self.line(cx - 9, cy - 7, cx + 12, cy - 17, BODY, 2)
        self.line(cx + 12, cy - 17, cx + 12, cy - 28)
        self.poly([(cx + 6, cy - 15), (cx + 12, cy - 21), (cx + 16, cy - 13)], BODY, 2, fill=BODY)
        self.line(cx - 9, cy + 7, cx + 12, cy + 17, BODY, 2)
        self.line(cx + 12, cy + 17, cx + 12, cy + 28)
        self.poly([(cx + 8, cy + 15), (cx + 14, cy + 21), (cx + 17, cy + 12)], BODY, 2, fill=BODY)
        if label:
            self.text(cx, cy + 42, label, size=10, fill=VAL, anchor="middle")

    def terminal(self, x, y, n, names, title="", pitch=26):
        h = 16 + n * pitch
        self.rect(x, y, 56, h, fill="#f3f3f3", rx=4)
        for i, nm in enumerate(names):
            py = y + 14 + i * pitch
            self.rect(x + 4, py - 5, 12, 10, fill="#dddddd", stroke="#888", sw=1)
            self.line(x + 16, py, x + 56, py, "#999", 1)
            self.text(x + 64, py + 4, nm, size=10, fill="#111")
        if title:
            self.text(x + 28, y - 6, title, size=11, fill=BODY, anchor="middle",
                      weight="bold")
        return [(x, y + 14 + i * pitch) for i in range(n)]

    def header(self, x, y, n, names, title="", pitch=24):
        h = 16 + n * pitch
        self.rect(x, y, 56, h, fill="#f3f3f3", rx=4)
        for i, nm in enumerate(names):
            py = y + 14 + i * pitch
            self.rect(x + 4, py - 5, 12, 10, fill="#dddddd", stroke="#888", sw=1)
            self.text(x + 64, py + 4, nm, size=10, fill="#111")
        if title:
            self.text(x + 28, y - 6, title, size=11, fill=BODY, anchor="middle",
                      weight="bold")
        return [(x, y + 14 + i * pitch) for i in range(n)]

    def conn_box(self, x, y, w, title, pins):
        h = 22 + len(pins) * 18
        self.rect(x, y, w, h, fill="#fbfbfb", rx=4)
        self.text(x + 8, y + 15, title, size=11, weight="bold", fill=BODY)
        for i, nm in enumerate(pins):
            self.text(x + 10, y + 33 + i * 18, f"{i + 1}  {nm}", size=10, fill="#111")
        return x, y, w, h

    def jumper3(self, x, y, title=""):
        self.rect(x - 9, y - 24, 18, 60, fill="#f3f3f3", stroke="#888", sw=1.5, rx=4)
        pts = []
        for py in (y - 15, y + 6, y + 27):
            self.circle(x, py, 5, fill="#dddddd", stroke="#666", sw=1.5)
            pts.append((x, py))
        if title:
            self.text(x, y - 30, title, size=9, fill=VAL, anchor="middle")
        return pts  # 1=topo, 2=meio(saida), 3=base

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f'<?xml version="1.0" encoding="UTF-8"?>\n'
                     f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
                     f'height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'
                     f'<rect width="{self.w}" height="{self.h}" fill="{self.bg}"/>\n')
            fh.write("\n".join(self.el))
            fh.write("\n</svg>\n")


def section(s, x, y, w, h, title, color="#2f6fed"):
    s.rect(x, y, w, h, fill="#fcfdff", stroke="#cdd7e5", sw=1.5, rx=8)
    s.rect(x, y, w, 30, fill="#eaf1ff", stroke="#cdd7e5", sw=1.5, rx=8)
    s.text(x + 12, y + 20, title, size=15, fill=color, weight="bold")


# =============================================================== SCHEMATIC
def build_schematic():
    s = Sheet(1720, 2640)
    s.text(40, 46, "OpenDash — Placa de junção (shield Arduino Mega 2560)", size=24,
           weight="bold", fill="#0b2545")
    s.text(40, 72, "Esquema elétrico · alimentação 12 V protegida, CAN/OBD-II, GPS, "
                   "10 entradas digitais, 4 analógicas e 3 saídas", size=13, fill=VAL)
    s.text(1680, 46, "Rev. A", size=14, fill=VAL, anchor="end", weight="bold")
    s.text(1680, 66, "github.com/gugaash26-art/dash", size=11, fill=VAL, anchor="end")

    build_power(s)
    build_mcu(s)
    build_can(s)
    build_gps(s)

    # ------------------------------------------------ entradas digitais
    ix, iy, iw, ih = 40, 760, 1660, 900
    section(s, ix, iy, iw, ih, "5. Entradas digitais (10×) — chave para GND ou sinal 12 V")
    cell_w, cell_h = 800, 156
    for k, (net, name, pin, term) in enumerate(DIGITAL_INPUTS):
        col, row = k % 2, k // 2
        cx = ix + 20 + col * (cell_w + 20)
        cy = iy + 46 + row * (cell_h + 8)
        draw_input_channel(s, cx, cy, dfmt(net, name, pin, term, k + 1))
    s.text(ix + 14, iy + ih - 12,
           "Cada canal: R série 22 k + R para GND 10 k (divisor p/ 12 V) + zener 5,1 V + "
           "100 nF.  JPx: 1-2 = sinal 12 V · 2-3 = chave-para-GND.", size=11, fill=VAL)

    # ------------------------------------------------ analogicos
    ax0, ay0, aw, ah = 40, 1680, 1660, 340
    section(s, ax0, ay0, aw, ah, "6. Entradas analógicas (A0..A3)")
    for k, spec in enumerate(ANALOG):
        cx = ax0 + 14 + k * 411
        draw_analog_channel(s, cx, ay0 + 42, spec, k)
    s.text(ax0 + 14, ay0 + ah - 12,
           "A3 usa divisor 30 k/10 k (12 V→4 V).  A1 tem pull-up 1 k opcional (JP201) "
           "para boia resistiva.", size=11, fill=VAL)

    # ------------------------------------------------ saidas
    ox0, oy0, ow, oh = 40, 2044, 1660, 510
    section(s, ox0, oy0, ow, oh, "7. Saídas (buzzer, LED e relés)")
    draw_buzz(s, ox0 + 20, oy0 + 46)
    draw_relay(s, ox0 + 433, oy0 + 46, "RELAY_FAN", "D44", "J9", "Ventilador", "302")
    draw_relay(s, ox0 + 846, oy0 + 46, "RELAY_AC", "D45", "J10", "Ar-condicionado", "303")
    draw_led(s, ox0 + 1260, oy0 + 46)
    s.text(ox0 + 20, oy0 + oh - 12,
           "Relés automotivos alimentados por +12 V e chaveados pelo lado GND "
           "(NPN + diodo de roda-livre).", size=11, fill=VAL)

    s.text(40, 2632, "OpenDash · hardware/ — gerado por hardware/generate.py",
           size=10, fill=VAL)
    s.save(os.path.join(OUT, "schematic.svg"))


def dfmt(net, name, pin, term, idx):
    return {"idx": idx, "net": net, "name": name, "pin": pin, "term": term}


def build_power(s):
    x, y, w, h = 40, 92, 560, 400
    section(s, x, y, w, h, "1. Alimentação (12 V → 5 V)")
    ty = y + 58
    pins = s.terminal(x + 24, ty, 2, ["+12V (após chave)", "GND (chassi)"], "J2 · 12 V")
    s.text(x + 24, ty + 82, "F1 = fusível de lâmina 3 A", size=11, fill=VAL)
    ax = pins[0][1]
    s.line(pins[0][0] + 56, ax, x + 150, ax)
    s.rect(x + 150, ax - 9, 40, 18, fill="#fff", rx=3)
    s.text(x + 170, ax + 4, "F1", size=10, fill=VAL, anchor="middle")
    s.line(x + 190, ax, x + 232, ax)
    s.dot(x + 232, ax)
    s.diode_h(x + 272, ax, "D1 SS54")
    s.line(x + 302, ax, x + 356, ax)
    s.netlabel(x + 360, ax + 5, "+12V", PWRBR, PWRBG, size=12)
    # TVS
    s.line(x + 232, ax, x + 232, ax + 46)
    s.zener_v(x + 232, ax + 76, "D2 SMBJ18A")
    s.line(x + 232, ax + 106, x + 232, ax + 124)
    s.gnd(x + 232, ax + 124)
    # GND do J2
    s.line(pins[1][0] + 56, pins[1][1], x + 90, pins[1][1])
    s.line(x + 90, pins[1][1], x + 90, ax + 124, GNDC, 1.5, dash="4 3")
    s.dot(x + 90, ax + 124)
    # buck  (IN em by+30, OUT em by+30)
    by = y + 214
    s.rect(x + 150, by, 210, 84, fill="#fff", rx=6)
    s.text(x + 255, by + 22, "U1  LM2596S-5.0", size=12, weight="bold", anchor="middle")
    s.text(x + 255, by + 42, "IN  →  OUT", size=10, anchor="middle", fill=VAL)
    # entrada: no do TVS desce e vai ao IN
    s.line(x + 232, ax, x + 232, by + 30)
    s.line(x + 110, by + 30, x + 150, by + 30)
    s.dot(x + 232, by + 30)
    # C1 de entrada
    s.line(x + 110, by + 30, x + 110, by + 48)
    s.cap_v(x + 110, by + 78, "C1 470µF")
    s.line(x + 110, by + 108, x + 110, by + 120)
    s.gnd(x + 110, by + 120)
    # saida +5V
    s.line(x + 360, by + 30, x + 470, by + 30)
    s.dot(x + 410, by + 30)
    s.line(x + 410, by + 30, x + 410, by + 48)
    s.cap_v(x + 410, by + 78, "C3 220µF")
    s.line(x + 410, by + 108, x + 410, by + 120)
    s.gnd(x + 410, by + 120)
    s.netlabel(x + 474, by + 35, "+5V", PWRBR, PWRBG, size=12)
    # LED de power (abaixo do buck)
    ly = y + 344
    s.netlabel(x + 24, ly + 5, "+5V", PWRBR, PWRBG, size=12)
    s.line(x + 24 + 48, ly, x + 90, ly)
    s.res_h(x + 126, ly, "R1 1k")
    s.led_h(x + 196, ly, "LED1 ON")
    s.line(x + 226, ly, x + 256, ly)
    s.gnd(x + 256, ly)
    s.text(x + 300, ly + 5, "LED de power", size=10, fill=VAL)
    s.text(x + 24, y + h - 12,
           "5 V: Arduino (JP_VUSB), módulos e J11 (Pi).", size=10, fill=VAL)


def build_mcu(s):
    mx, my, mw, mh = 630, 92, 440, 650
    section(s, mx, my, mw, mh, "2. Arduino Mega 2560 (U_ARDUINO)")
    s.rect(mx + 26, my + 46, mw - 52, mh - 96, fill="#fff", rx=6)
    s.text(mx + mw / 2, my + 74, "ARDUINO MEGA 2560", size=16, anchor="middle",
           weight="bold", fill=BODY)
    s.text(mx + mw / 2, my + 94, "o shield encaixa nos headers", size=10,
           anchor="middle", fill=VAL)
    left = [("D2", "IN_LEFT"), ("D3", "IN_RIGHT"), ("D4", "IN_HEAD"), ("D5", "IN_HIGH"),
            ("D6", "IN_BRAKE"), ("D7", "IN_BELT"), ("D8", "IN_DOOR"), ("D9", "IN_HAZARD"),
            ("D22", "IN_IGN"), ("D46", "IN_REV")]
    right = [("A0", "ANA_OILP"), ("A1", "ANA_FUEL"), ("A2", "ANA_OILT"), ("A3", "ANA_BATT"),
             ("D12", "BUZZ"), ("D13", "LED_ST")]
    bottom = [("D10", "CAN_CS"), ("D52", "CAN_SCK"), ("D51", "CAN_SI"), ("D50", "CAN_SO"),
              ("D18", "GPS_RX"), ("D19", "GPS_TX"), ("D44", "RELAY_FAN"),
              ("D45", "RELAY_AC"), ("5V", "+5V"), ("GND", "GND")]
    for i, (pin, net) in enumerate(left):
        py = my + 124 + i * 30
        s.line(mx + 36, py, mx + 66, py)
        s.dot(mx + 66, py)
        s.text(mx + 70, py - 2, pin, size=10, fill=BODY, weight="bold")
        s.netlabel(mx + 70, py + 16, net, size=9)
    for i, (pin, net) in enumerate(right):
        py = my + 132 + i * 32
        s.line(mx + mw - 36, py, mx + mw - 66, py)
        s.dot(mx + mw - 66, py)
        s.text(mx + mw - 70, py - 2, pin, size=10, fill=BODY, weight="bold", anchor="end")
        s.netlabel(mx + mw - 70, py + 16, net, size=9, anchor="end")
    for i, (pin, net) in enumerate(bottom):
        col, row = i % 5, i // 5
        px = mx + 62 + col * 64
        py = my + 452 + row * 62
        s.line(px, py, px, py + 18)
        s.dot(px, py + 18)
        s.text(px, py + 32, pin, size=9, fill=BODY, weight="bold", anchor="middle")
        s.netlabel(px, py + 50, net, size=8, anchor="middle")
    s.text(mx + mw / 2, my + mh - 14, "entradas com INPUT_PULLUP · ativo em LOW",
           size=9, anchor="middle", fill=VAL)


def build_can(s):
    cx0, cy0, cw, ch = 1100, 92, 580, 270
    section(s, cx0, cy0, cw, ch, "3. CAN bus / OBD-II (MCP2515 + TJA1050)")
    s.header(cx0 + 22, cy0 + 50, 7,
             ["VCC", "GND", "CS", "SCK", "SI", "SO", "INT"], "J3 · MCP2515")
    s.terminal(cx0 + 240, cy0 + 50, 4,
               ["CAN_H", "CAN_L", "+12V", "GND"], "J4 · OBD-II")
    # terminacao
    tx = cx0 + 400
    s.text(tx, cy0 + 52, "Terminação", size=11, weight="bold", fill=BODY)
    s.jumper3(tx + 20, cy0 + 102, "JP1")
    s.line(tx + 20, cy0 + 162, tx + 20, cy0 + 178)
    s.gnd(tx + 20, cy0 + 178)
    s.text(tx, cy0 + 128, "120 Ω (R2) se o", size=9, fill=VAL)
    s.text(tx, cy0 + 142, "carro não tiver", size=9, fill=VAL)
    s.text(tx, cy0 + 156, "terminação", size=9, fill=VAL)
    s.text(cx0 + 22, cy0 + ch - 30, "CS→D10 · SCK→D52 · SI→D51 · SO→D50",
           size=9, fill=VAL)
    s.text(cx0 + 22, cy0 + ch - 14,
           "OBD: H=6 · L=14 · +12V=16 · GND=4/5 · C6 100n no MCP2515",
           size=9, fill=VAL)


def build_gps(s):
    gx, gy, gw, gh = 1100, 378, 580, 170
    section(s, gx, gy, gw, gh, "4. GPS NMEA (NEO-6M / NEO-8M / M8N)")
    gp = s.header(gx + 22, gy + 40, 4,
                  ["VCC", "GND", "TX", "RX"], "J5 · GPS 9600 baud", pitch=22)
    ry = gp[3][1]
    s.line(gx + 78, ry, gx + 78, gy + 150)
    s.res_h(gx + 140, gy + 150, "R3 1k")
    s.line(gx + 170, gy + 150, gx + 230, gy + 150)
    s.netlabel(gx + 234, gy + 155, "D18 (TX1) → GPS RX", size=10)
    s.text(gx + 22, gy + gh - 8,
           "R3 1k limita o TX do Arduino (5 V) para o RX do GPS (3,3 V).",
           size=9, fill=VAL)


def draw_input_channel(s, x, y, d):
    idx, net, name, pin, term = d["idx"], d["net"], d["name"], d["pin"], d["term"]
    s.rect(x, y, 780, 156, fill="#ffffff", stroke="#dbe3ee", sw=1, rx=6)
    s.text(x + 10, y + 20, name, size=12, weight="bold", fill=BODY)
    s.text(x + 770, y + 20, f"Canal {idx}", size=10, fill=VAL, anchor="end")
    P1x, yy = x + 150, y + 58
    s.netlabel(x + 8, y + 48, term, size=11)
    s.line(x + 78, y + 40, P1x, y + 40)
    s.line(P1x, y + 40, P1x, yy)
    s.dot(P1x, yy)
    s.line(P1x, yy, P1x + 20, yy)
    s.res_h(P1x + 56, yy, f"R1{idx:02d} 22k")
    nx = P1x + 116
    s.dot(nx, yy)
    s.line(nx, yy, nx + 140, yy)
    for dx, kind in [(0, "rpd"), (70, "z"), (140, "c")]:
        bx = nx + dx
        s.line(bx, yy, bx, yy + 12)
        if kind == "rpd":
            s.res_v(bx, yy + 42, f"R1{10+idx} 10k")
        elif kind == "z":
            s.zener_v(bx, yy + 42, f"DZ1{idx:02d} 5V1")
        else:
            s.cap_v(bx, yy + 46, f"C1{idx:02d} 100n")
        s.line(bx, yy + 72, bx, yy + 92)
    s.line(nx, yy + 92, nx + 140, yy + 92, GNDC)
    s.gnd(nx + 70, yy + 92)
    jx = x + 560
    a, b, c = s.jumper3(jx, yy)
    s.line(nx + 140, yy, a[0] - 12, yy)
    s.line(a[0] - 12, yy, a[0] - 12, a[1])
    s.line(a[0] - 12, a[1], a[0], a[1])
    s.line(P1x, yy, P1x, y + 142)
    s.line(P1x, y + 142, c[0] + 16, y + 142)
    s.line(c[0] + 16, y + 142, c[0] + 16, c[1])
    s.line(c[0] + 16, c[1], c[0], c[1])
    s.line(b[0], b[1], b[0] + 30, b[1])
    s.netlabel(b[0] + 34, b[1] + 5, pin, size=11)
    s.text(jx, yy + 52, f"JP1{idx:02d} · 1-2=12V · 2-3=GND", size=8, fill=VAL,
           anchor="middle")


def draw_analog_channel(s, x, y, spec, k):
    net, name, pin, term, kind, rser, dz, cap = spec
    s.rect(x, y, 390, 280, fill="#ffffff", stroke="#dbe3ee", sw=1, rx=6)
    s.text(x + 10, y + 20, name, size=12, weight="bold", fill=BODY)
    yy = y + 140
    if kind == "div":
        s.netlabel(x + 8, y + 42, "+12V", PWRBR, PWRBG, size=11)
        s.line(x + 66, y + 34, x + 66, yy)
        s.line(x + 66, yy, x + 92, yy)
        s.res_h(x + 128, yy, f"{rser} 30k")
        nx = x + 186
    else:
        s.netlabel(x + 8, yy + 5, term, size=11)
        s.line(x + 74, yy, x + 92, yy)
        s.res_h(x + 128, yy, f"{rser} 1k")
        nx = x + 186
    s.dot(nx, yy)
    # zener + cap
    s.line(nx, yy, nx, yy + 16)
    s.zener_v(nx, yy + 46, f"{dz} 5V1")
    s.line(nx, yy + 76, nx, yy + 96)
    s.line(nx + 66, yy, nx + 66, yy + 20)
    s.cap_v(nx + 66, yy + 50, f"{cap} 100n")
    s.line(nx + 66, yy + 80, nx + 66, yy + 96)
    s.line(nx, yy + 96, nx + 66, yy + 96, GNDC)
    s.gnd(nx + 33, yy + 96)
    # saida
    s.line(nx, yy, nx + 96, yy)
    s.netlabel(nx + 100, yy + 5, pin, size=12)
    if kind == "res":
        # pull-up opcional +5V -> R203 1k -> A1
        bx = nx + 60
        s.dot(bx, yy)
        s.line(bx, yy, bx, yy - 54)
        s.res_v(bx, yy - 24, "R203 1k")
        s.line(bx, yy - 54, bx, yy - 66)
        s.power(bx, yy - 66)
        s.text(bx + 12, yy - 30, "JP201", size=9, fill=VAL)
    note = {"volt": "sensor 0,5–4,5 V: entra direto (RC + zener)",
            "res": "boia resistiva: pull-up 1 k (JP201)",
            "div": "12 V → ~4 V (BATT_DIVIDER = 4,0)"}[kind]
    s.text(x + 10, y + 262, note, size=10, fill=VAL)


def draw_buzz(s, x, y):
    s.rect(x, y, 400, 400, fill="#ffffff", stroke="#dbe3ee", sw=1, rx=6)
    s.text(x + 10, y + 22, "Buzzer (D12)", size=13, weight="bold", fill=BODY)
    yy = y + 110
    s.netlabel(x + 10, yy + 5, "D12", size=11)
    s.line(x + 76, yy, x + 96, yy)
    s.res_h(x + 132, yy, "R301 1k")
    s.npn(x + 200, yy, "Q301 2N2222")
    s.line(x + 212, yy + 28, x + 212, yy + 90)
    s.gnd(x + 212, yy + 90)
    s.line(x + 212, yy - 28, x + 212, y + 58)
    s.line(x + 212, y + 58, x + 300, y + 58)
    s.netlabel(x + 304, y + 63, "BUZZ+", size=11)
    s.diode_h(x + 250, y + 58, "D301")
    s.conn_box(x + 10, y + 200, 175, "J8 · buzzer", ["BUZZ+", "+5V"])
    s.text(x + 10, y + 388, "buzzer ativo de 5 V entre BUZZ+ e +5V/GND", size=10, fill=VAL)


def draw_relay(s, x, y, net, pin, jconn, label, rid):
    short = net.replace("RELAY_", "")
    s.rect(x, y, 400, 400, fill="#ffffff", stroke="#dbe3ee", sw=1, rx=6)
    s.text(x + 10, y + 22, f"Relé {label} ({pin})", size=13, weight="bold", fill=BODY)
    yy = y + 110
    s.netlabel(x + 10, yy + 5, pin, size=11)
    s.line(x + 76, yy, x + 96, yy)
    s.res_h(x + 132, yy, f"R3{rid} 1k")
    s.npn(x + 200, yy, f"Q3{rid} 2N2222")
    s.line(x + 212, yy + 28, x + 212, yy + 90)
    s.gnd(x + 212, yy + 90)
    s.line(x + 212, yy - 28, x + 212, y + 58)
    s.line(x + 212, y + 58, x + 300, y + 58)
    s.netlabel(x + 304, y + 63, f"COIL_{short}", size=11)
    s.diode_h(x + 250, y + 58, "1N4007")
    s.conn_box(x + 10, y + 200, 175, f"{jconn} · relé", ["+12V", f"COIL_{short}"])
    s.text(x + 10, y + 388, "bobina do relé entre +12 V e o coletor do driver",
           size=10, fill=VAL)


def draw_led(s, x, y):
    s.rect(x, y, 400, 400, fill="#ffffff", stroke="#dbe3ee", sw=1, rx=6)
    s.text(x + 10, y + 22, "LED de status (D13)", size=13, weight="bold", fill=BODY)
    yy = y + 110
    s.netlabel(x + 10, yy + 5, "D13", size=11)
    s.line(x + 76, yy, x + 96, yy)
    s.res_h(x + 132, yy, "R310 1k")
    s.led_h(x + 210, yy, "LED_ST")
    s.line(x + 240, yy, x + 280, yy)
    s.gnd(x + 280, yy)
    s.text(x + 10, y + 180, "pisca quando o OBD está online", size=10, fill=VAL)
    s.conn_box(x + 10, y + 220, 150, "J11 · 5 V → Pi", ["+5V", "GND"])
    s.text(x + 10, y + 388, "alimentação de 5 V para a Orange Pi / Raspberry Pi",
           size=10, fill=VAL)


# =============================================================== BOARD
def build_board():
    K = 9.0
    MW, MH = 101.5, 53.3
    m = 60
    w = int(MW * K) + 2 * m
    h = int(MH * K) + 2 * m + 250
    s = Sheet(w, h, "#f7f9fc")
    s.text(m, 40, "OpenDash — Placa de junção (shield Arduino Mega 2560)", size=22,
           weight="bold", fill="#0b2545")
    s.text(m, 66, "Desenho mecânico · vista superior · escala 9 px/mm "
                  "(101,5 × 53,3 mm)", size=12, fill=VAL)
    bx, by = m, 100
    bw, bh = MW * K, MH * K
    s.rect(bx, by, bw, bh, fill="#1f7a4d", stroke="#08351f", sw=2, rx=6)

    def mm(x, y):
        return bx + x * K, by + y * K

    def box(x0, y0, x1, y1, label, sub="", fill="#ffffff", stroke="#0b2545"):
        a, b = mm(x0, y0)
        c, d = mm(x1, y1)
        s.rect(a, b, c - a, d - b, fill=fill, stroke=stroke, sw=1.6, rx=4)
        s.text((a + c) / 2, (b + d) / 2 - 2, label, size=10, weight="bold",
               anchor="middle", fill="#0b2545")
        if sub:
            s.text((a + c) / 2, (b + d) / 2 + 11, sub, size=7, anchor="middle", fill=VAL)

    # headers do Arduino
    a, b = mm(6, 4)
    s.rect(a, b, 90 * K, 2.5 * K, fill="#1a1a1a", stroke="#000", rx=2)
    s.text(a + 2 * K, b - 5, "headers do Arduino Mega (encaixe)", size=8,
           fill="#dff5e6")
    a2, b2 = mm(6, 47)
    s.rect(a2, b2, 90 * K, 2.5 * K, fill="#1a1a1a", stroke="#000", rx=2)
    a3, b3 = mm(74, 4)
    s.rect(a3, b3, 22 * K, 2.5 * K, fill="#1a1a1a", stroke="#000", rx=2)

    box(30, 8, 58, 17, "MCP2515", "CAN/OBD", fill="#eef4ff")
    box(30, 18, 58, 25, "GPS NEO-6M", "", fill="#eef4ff")
    box(62, 8, 74, 19, "LM2596", "5 V", fill="#fff7e6")
    box(62, 20, 74, 31, "F1 + TVS", "12 V", fill="#fff7e6")
    box(76, 8, 96, 16, "RC analógico", "A0..A3", fill="#eafaf1", stroke="#1f7a4d")
    box(4, 8, 17, 15, "drivers de relé", "Q302/Q303")
    box(4, 17, 17, 24, "buzzer", "Q301")
    box(19, 8, 29, 15, "LED D13", "")

    for i in range(10):
        col, row = i % 5, i // 5
        x0 = 4 + col * 8.6
        y0 = 26 + row * 7.0
        box(x0, y0, x0 + 7.8, y0 + 6.2, f"IN{i+1}", "22k/10k",
            fill="#eafaf1", stroke="#1f7a4d")

    conns = [("J2 12V", 6), ("J4 CAN", 10), ("J6 entradas ×12", 20),
             ("J7 analóg ×5", 10), ("J8/J9/J10", 14), ("J5 GPS", 6), ("J11 5V→Pi", 6)]
    cy = 40.2
    ct = 4
    for name, width in conns:
        a, b = mm(ct, cy)
        s.rect(a, b, width * K, 4.0 * K, fill="#fde68a", stroke="#b45309", sw=1.4, rx=3)
        s.text(a + width * K / 2, b + 2.8 * K, name, size=8, anchor="middle", fill="#7c2d12")
        ct += width + 1.0

    # furos de montagem
    for (hx, hy) in [(3, 3), (98.5, 3), (3, 50), (98.5, 50)]:
        a, b = mm(hx, hy)
        s.circle(a, b, 7, fill="#f7f9fc", stroke="#0b2545", sw=1.4)
        s.circle(a, b, 3.2, fill="#0b2545")

    ly = by + bh + 60
    s.text(m, ly, "Furação (brocas):", size=13, weight="bold", fill="#0b2545")
    s.text(m, ly + 22, "• conectores/headers: ø1,0 mm   • fios/links: ø0,8 mm   "
                       "• montagem M3: ø3,2 mm   • bornes de parafuso: ø1,3 mm",
           size=11, fill=VAL)
    s.text(m, ly + 46, "Componentes de furo (THT) na face superior; trilhas na face "
                       "inferior (placa de face simples).", size=11, fill=VAL)
    s.text(m, ly + 70, "Para fabricar em casa: transferência térmica / UV da arte de "
                       "cobre na face inferior + corrosão.", size=11, fill=VAL)
    s.text(m, ly + 94, "Alternativa DIY: placa ilhada (perfboard) seguindo a lista de "
                       "ligações (netlist.csv).", size=11, fill=VAL)
    s.text(m, ly + 130, "OpenDash · hardware/board.svg (gerado por generate.py)",
           size=10, fill=VAL)
    s.save(os.path.join(OUT, "board.svg"))


# =============================================================== CSV
def build_csv():
    bom = [
        ("U_ARDUINO", "Arduino Mega 2560", "módulo", "Comutador de bordo (car_dash.ino)"),
        ("U1", "LM2596S-5.0", "TO-263-5", "Conversor buck 12V→5V 3A"),
        ("L1", "33 µH / 3 A", "THT", "Indutor do buck"),
        ("D3", "SS34", "DO-214AC", "Diodo Schottky do buck"),
        ("D1", "SS54", "SMC", "Proteção de polaridade reversa"),
        ("D2", "SMBJ18A", "SMB", "TVS / transientes automotivos"),
        ("F1", "Fusível 3 A", "porta-fusível", "Proteção da alimentação"),
        ("C1", "470 µF / 25 V", "eletrolítico", "Capacitor de entrada"),
        ("C2,C4", "100 nF", "cerâmico", "Desacoplamento do buck"),
        ("C3", "220 µF / 16 V", "eletrolítico", "Capacitor de saída"),
        ("C6", "100 nF", "cerâmico", "Desacoplamento do MCP2515"),
        ("C7", "100 nF", "cerâmico", "Desacoplamento do GPS"),
        ("JP_VUSB", "Jumper 3 pinos", "THT", "Fonte de 5 V do Arduino"),
        ("R1", "1 kΩ", "THT", "Resistor do LED de power"),
        ("LED1", "LED verde 5 mm", "THT", "Indicador de alimentação"),
        ("J2", "Borne 2 vias", "parafuso 5,08", "Entrada 12 V + GND"),
        ("J3", "Header 1×7 fêmea", "THT 2,54", "Módulo MCP2515"),
        ("JP1", "Jumper 2 pinos", "THT", "Terminação do CAN"),
        ("R2", "120 Ω", "THT", "Terminação do CAN"),
        ("J4", "Borne 4 vias", "parafuso", "OBD-II: CAN_H/L, +12 V, GND"),
        ("J5", "Header 1×4", "THT", "GPS (VCC, GND, TX, RX)"),
        ("R3", "1 kΩ", "THT", "Série TX Arduino → RX do GPS"),
        ("J6", "Borne 12 vias", "parafuso", "Entradas digitais (10 + GND)"),
        ("R101-R110", "22 kΩ", "THT", "Série das entradas digitais (10×)"),
        ("R111-R120", "10 kΩ", "THT", "Divisor das entradas digitais (10×)"),
        ("DZ101-DZ110", "Zener 5,1 V", "THT", "Proteção das entradas (10×)"),
        ("C101-C110", "100 nF", "cerâmico", "Filtro das entradas (10×)"),
        ("JP101-JP110", "Jumper 3 pinos", "THT", "Seleção 12 V / chave-GND (10×)"),
        ("J7", "Borne 5 vias", "parafuso", "Analógicas A0..A3 + GND"),
        ("R201", "1 kΩ", "THT", "Série A0 (pressão do óleo)"),
        ("R202,R203", "1 kΩ", "THT", "Série e pull-up de A1 (combustível)"),
        ("JP201", "Jumper 2 pinos", "THT", "Ativa pull-up do A1"),
        ("R204", "1 kΩ", "THT", "Série A2 (temperatura do óleo)"),
        ("R205", "30 kΩ", "THT", "Divisor A3 (topo)"),
        ("R206", "10 kΩ", "THT", "Divisor A3 (base)"),
        ("DZ201-DZ204", "Zener 5,1 V", "THT", "Proteção das analógicas (4×)"),
        ("C201-C204", "100 nF", "cerâmico", "Filtro das analógicas (4×)"),
        ("J8", "Borne 2 vias", "parafuso", "Buzzer"),
        ("R301", "1 kΩ", "THT", "Base do Q301"),
        ("Q301", "2N2222", "TO-92", "Driver do buzzer"),
        ("D301", "1N4148", "DO-35", "Roda-livre do buzzer"),
        ("J9", "Borne 2 vias", "parafuso", "Bobina do relé do ventilador"),
        ("J10", "Borne 2 vias", "parafuso", "Bobina do relé do ar-condicionado"),
        ("R302,R304", "1 kΩ", "THT", "Base dos drivers de relé"),
        ("R303,R305", "10 kΩ", "THT", "Pulldown base-emissor"),
        ("Q302,Q303", "2N2222 / BD135", "TO-92/TO-126", "Drivers dos relés"),
        ("D302,D303", "1N4007", "DO-41", "Roda-livre das bobinas"),
        ("R310", "1 kΩ", "THT", "Resistor do LED de status"),
        ("D310", "LED", "THT", "LED de status (D13)"),
        ("J11", "Borne 2 vias", "parafuso", "5 V/GND para Orange Pi/Raspberry"),
        ("—", "Placa de circuito", "face simples", "101,5 × 53,3 mm (shield Mega)"),
    ]
    with open(os.path.join(OUT, "bom.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Referencia", "Valor", "Encapsulamento", "Descricao"])
        w.writerows(bom)

    net = []
    n = lambda *a: net.append(a)
    n("+12V", "F1", "2", "após o fusível")
    n("+12V", "D1", "A", "anodo do SS54")
    n("+12V", "U1", "IN", "entrada do buck")
    n("+12V", "J4", "3", "12 V do OBD (opcional)")
    n("+12V", "J9/J10", "1", "bobinas dos relés")
    n("+5V", "U1", "OUT", "5,0 V")
    n("+5V", "U_ARDUINO", "5V", "alimenta o Arduino (JP_VUSB)")
    n("+5V", "J3", "1", "VCC do MCP2515")
    n("+5V", "J5", "1", "VCC do GPS")
    n("+5V", "LED1", "A", "via R1")
    n("+5V", "J11", "1", "para a Orange Pi/Raspberry")
    n("+5V", "R203", "1", "pull-up opcional de A1 (JP201)")
    n("+5V", "J8", "2", "buzzer")
    n("GND", "J2", "2", "terra do chassi")
    n("GND", "J4", "4", "GND do OBD")
    n("GND", "J6", "11/12", "referência das entradas")
    n("GND", "J7", "5", "referência das analógicas")
    n("GND", "U1", "GND", "terra do buck")
    n("GND", "J3", "2", "GND do MCP2515")
    n("GND", "J5", "2", "GND do GPS")
    n("GND", "Q301/Q302/Q303", "E", "emissores")
    n("GND", "J11", "2", "para a Orange Pi/Raspberry")
    for i, (nm, name, pin, term) in enumerate(DIGITAL_INPUTS, 1):
        n(nm, "J6", term.split(".")[1], f"{name} (borne {term})")
        n(nm, "U_ARDUINO", pin, "pino do Arduino (INPUT_PULLUP)")
        n(nm, f"R1{i:02d}", "1", "série 22k (lado do borne)")
        n(nm, f"JP1{i:02d}", "1", "jumper 1-2 = sinal 12 V")
        n(nm + "_GND", f"JP1{i:02d}", "3", "jumper 2-3 = chave-para-GND")
    for nm, name, pin, term, kind, rser, dz, cap in ANALOG:
        n(nm, "J7", term.split(".")[1], f"{name} (borne {term})")
        n(nm, "U_ARDUINO", pin, "pino analógico do Arduino")
    n("CAN_CS", "J3", "3", "CS")
    n("CAN_CS", "U_ARDUINO", "D10", "")
    n("CAN_SCK", "J3", "4", "SCK")
    n("CAN_SCK", "U_ARDUINO", "D52", "")
    n("CAN_SI", "J3", "5", "MOSI")
    n("CAN_SI", "U_ARDUINO", "D51", "")
    n("CAN_SO", "J3", "6", "MISO")
    n("CAN_SO", "U_ARDUINO", "D50", "")
    n("CAN_INT", "J3", "7", "INT (não usado pelo firmware)")
    n("CAN_H", "J4", "1", "para OBD pino 6")
    n("CAN_L", "J4", "2", "para OBD pino 14")
    n("GPS_TX", "J5", "3", "TX do GPS")
    n("GPS_TX", "U_ARDUINO", "D19", "RX1")
    n("GPS_RX", "J5", "4", "RX do GPS (via R3 1k)")
    n("GPS_RX", "U_ARDUINO", "D18", "TX1")
    n("BUZZ", "U_ARDUINO", "D12", "")
    n("BUZZ", "R301", "1", "via base do Q301")
    n("LED_ST", "U_ARDUINO", "D13", "via R310")
    n("RELAY_FAN", "U_ARDUINO", "D44", "")
    n("RELAY_FAN", "R302", "1", "base do Q302")
    n("COIL_FAN", "Q302", "C", "coletor (J9.2)")
    n("RELAY_AC", "U_ARDUINO", "D45", "")
    n("RELAY_AC", "R304", "1", "base do Q303")
    n("COIL_AC", "Q303", "C", "coletor (J10.2)")

    with open(os.path.join(OUT, "netlist.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Net", "Componente/Terminal", "Pino", "Observacao"])
        w.writerows(net)


def main():
    os.makedirs(OUT, exist_ok=True)
    build_schematic()
    build_board()
    build_csv()
    print("gerado em", OUT)
    for f in ("schematic.svg", "board.svg", "bom.csv", "netlist.csv"):
        print(" ", f, os.path.getsize(os.path.join(OUT, f)), "bytes")


if __name__ == "__main__":
    main()
