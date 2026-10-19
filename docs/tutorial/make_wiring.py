#!/usr/bin/env python3
"""Gera os diagramas de ligacao do OpenDash para ESP32 (PNG 1600x900)."""
import os

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

W, H = 1600, 900
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")

BG = "#0b0f14"
PANEL = "#121a24"
PANEL2 = "#172231"
BORDER = "#2d3b4d"
TEXT = "#e6edf3"
DIM = "#93a1b1"
GREEN = "#3fb950"
BLUE = "#58a6ff"
YELLOW = "#d29922"
RED = "#f85149"
PURPLE = "#bc8cff"
ORANGE = "#db6d28"
GREY = "#8b949e"

FONT = "DejaVu Sans"
FONT_BOLD = "DejaVu Sans Bold"
FONT_MONO = "DejaVu Sans Mono"


def rgb(hexstr, alpha=1.0):
    h = hexstr.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255,
            int(h[4:6], 16) / 255, alpha)


class Canvas:
    def __init__(self, path, title, kicker):
        self.path = path
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.ctx = cairo.Context(self.surface)
        self.ctx.set_source_rgb(*rgb(BG)[:3])
        self.ctx.paint()
        self.ctx.select_font_face(FONT_BOLD, cairo.FONT_SLANT_NORMAL,
                                  cairo.FONT_WEIGHT_BOLD)
        # header
        self.text(60, 42, kicker.upper(), 18, GREEN, bold=True)
        self.text(60, 84, title, 40, TEXT, bold=True)
        self.line(60, 104, W - 60, 104, BORDER, 2)
        self.text(W - 60, 42, "OpenDash", 20, BLUE, bold=True, anchor="end")
        self.text(W - 60, 68, "ESP32 DevKit", 15, DIM, anchor="end")

    def text(self, x, y, text, size, color=TEXT, bold=False, mono=False,
             anchor="start"):
        layout = PangoCairo.create_layout(self.ctx)
        desc = Pango.FontDescription(
            f"{FONT_BOLD if bold else (FONT_MONO if mono else FONT)} {size}")
        layout.set_font_description(desc)
        layout.set_text(text, -1)
        tw, th = layout.get_pixel_size()
        if anchor == "end":
            x -= tw
        elif anchor == "middle":
            x -= tw / 2
        self.ctx.set_source_rgba(*rgb(color))
        self.ctx.move_to(x, y)
        PangoCairo.show_layout(self.ctx, layout)
        return tw, th

    def rect(self, x, y, w, h, fill=PANEL, stroke=BORDER, sw=2, radius=12):
        self.ctx.new_sub_path()
        self.ctx.arc(x + w - radius, y + radius, radius, -1.5708, 0)
        self.ctx.arc(x + w - radius, y + h - radius, radius, 0, 1.5708)
        self.ctx.arc(x + radius, y + h - radius, radius, 1.5708, 3.1416)
        self.ctx.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
        self.ctx.close_path()
        self.ctx.set_source_rgba(*rgb(fill))
        self.ctx.fill_preserve()
        self.ctx.set_source_rgba(*rgb(stroke))
        self.ctx.set_line_width(sw)
        self.ctx.stroke()

    def line(self, x1, y1, x2, y2, color=BORDER, sw=2):
        self.ctx.set_source_rgba(*rgb(color))
        self.ctx.set_line_width(sw)
        self.ctx.move_to(x1, y1)
        self.ctx.line_to(x2, y2)
        self.ctx.stroke()

    def wire(self, pts, color=GREEN, sw=4):
        self.ctx.set_source_rgba(*rgb(color))
        self.ctx.set_line_width(sw)
        self.ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        self.ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        self.ctx.move_to(*pts[0])
        for p in pts[1:]:
            self.ctx.line_to(*p)
        self.ctx.stroke()

    def circle(self, x, y, r, fill, stroke=None, sw=2):
        self.ctx.arc(x, y, r, 0, 6.2832)
        self.ctx.set_source_rgba(*rgb(fill))
        self.ctx.fill_preserve()
        if stroke:
            self.ctx.set_source_rgba(*rgb(stroke))
            self.ctx.set_line_width(sw)
            self.ctx.stroke()
        else:
            self.ctx.new_path()

    def pin(self, x, y, label, side="right", color=GREEN):
        self.circle(x, y, 6, color)
        if side == "right":
            self.text(x + 14, y - 8, label, 15, TEXT, mono=True)
        else:
            self.text(x - 14, y - 8, label, 15, TEXT, mono=True, anchor="end")

    def pill(self, x, y, text, color, size=15, padx=10):
        tw, th = self.text(x + padx, y + 5, text, size, color, bold=True)
        self.rect(x, y - 18, tw + padx * 2, 30, fill=PANEL2, stroke=color,
                  sw=1.5, radius=6)

    def save(self):
        self.surface.write_to_png(self.path)


def can_diagram():
    c = Canvas(os.path.join(OUT, "conexao-can-esp32.png"),
               "Ligação CAN / OBD-II", "Montagem")
    c.text(60, 148, "MCP2515 usa SPI. No ESP32 clássico: CS=5, SCK=18, MISO=19, MOSI=23.",
           17, DIM)

    # ESP32
    c.rect(90, 200, 360, 500, fill=PANEL, stroke=BORDER, radius=18)
    c.text(270, 236, "ESP32 DevKit", 22, TEXT, bold=True, anchor="middle")
    c.text(270, 262, "lado direito / GPIO", 14, DIM, anchor="middle")
    pins = [("3V3", 300, RED), ("GND", 350, GREY), ("GPIO18", 400, GREEN),
            ("GPIO19", 450, GREEN), ("GPIO23", 500, GREEN), ("GPIO5", 550, YELLOW),
            ("GPIO14", 600, BLUE)]
    for name, y, color in pins:
        c.circle(450, y, 6, color)
        c.text(436, y + 5, name, 15, TEXT, mono=True, anchor="end")
        c.line(430, y, 450, y, BORDER, 3)
    c.text(270, 655, "USB", 14, DIM, anchor="middle")
    c.rect(220, 670, 100, 18, fill="#1f2937", stroke=BORDER, radius=4)

    # MCP2515
    c.rect(720, 250, 330, 380, fill=PANEL, stroke=BORDER, radius=18)
    c.text(885, 286, "MCP2515", 22, TEXT, bold=True, anchor="middle")
    c.text(885, 312, "+ transceptor 3,3 V", 14, DIM, anchor="middle")
    mcp = [("VCC", 300, RED), ("GND", 350, GREY), ("SCK", 400, GREEN),
           ("SO", 450, GREEN), ("SI", 500, GREEN), ("CS", 550, YELLOW)]
    for name, y, color in mcp:
        c.circle(720, y, 6, color)
        c.text(734, y + 5, name, 15, TEXT, mono=True)
    # wires (orthogonal, each with its own vertical lane)
    lanes = [500, 530, 560, 590, 620, 650]
    for i, (name, y, color) in enumerate(pins[:6]):
        dy = mcp[i][1]
        lx = lanes[i]
        c.wire([(456, y), (lx, y), (lx, dy), (714, dy)], color, 4)
    c.text(885, 590, "VCC: 3,3 V", 15, RED, bold=True, anchor="middle")
    c.text(885, 612, "use SN65HVD230 ou level shifter", 13, DIM, anchor="middle")

    # OBD connector
    c.rect(1260, 275, 270, 330, fill=PANEL, stroke=BORDER, radius=18)
    c.text(1395, 312, "OBD-II fêmea", 21, TEXT, bold=True, anchor="middle")
    c.text(1395, 338, "vista do conector", 13, DIM, anchor="middle")
    c.rect(1290, 360, 210, 190, fill="#1c2735", stroke=BORDER, radius=16)
    for row, nums in enumerate(([1, 2, 3, 4, 5, 6, 7, 8],
                                 [9, 10, 11, 12, 13, 14, 15, 16])):
        for col, n in enumerate(nums):
            x = 1310 + col * 23
            y = 390 + row * 100
            color = YELLOW if n in (6, 14) else "#546273"
            c.circle(x, y, 6, color)
            c.text(x, y + 24, str(n), 10, YELLOW if n in (6, 14) else DIM,
                   anchor="middle", mono=True)

    # MCP CAN pins
    c.circle(1050, 430, 6, YELLOW)
    c.text(1036, 435, "CAN-H", 15, TEXT, mono=True, anchor="end")
    c.circle(1050, 490, 6, ORANGE)
    c.text(1036, 495, "CAN-L", 15, TEXT, mono=True, anchor="end")
    c.wire([(1056, 430), (1140, 430), (1140, 390), (1425, 390)], YELLOW, 4)
    c.wire([(1056, 490), (1425, 490)], ORANGE, 4)
    c.text(1200, 380, "pino 6", 13, YELLOW, bold=True, anchor="middle")
    c.text(1200, 515, "pino 14", 13, ORANGE, bold=True, anchor="middle")

    # notes
    c.rect(90, 730, 1440, 118, fill=PANEL2, stroke=BORDER, radius=12)
    c.text(112, 768, "GPS (opcional): TX do NEO-6M → GPIO14 (RX do ESP32); VCC 3,3 V; GND comum; 9600 baud.",
           16, BLUE, bold=True)
    c.text(112, 800, "Terminação: 120 Ω entre CAN-H e CAN-L (a maioria dos módulos já tem).",
           16, TEXT)
    c.text(112, 828, "Nunca ligue 5 V nos GPIOs do ESP32. Alimente o módulo CAN em 3,3 V.",
           15, RED, bold=True)
    c.save()


def sensors_diagram():
    c = Canvas(os.path.join(OUT, "conexao-sensores-esp32.png"),
               "Sensores analógicos", "Montagem")
    c.text(60, 148, "Sensores de 5 V exigem divisor de tensão: a entrada do ESP32 vai de 0 a 3,3 V.",
           17, DIM)
    c.circle(1220, 143, 6, PURPLE)
    c.text(1232, 150, "sinal", 13, DIM)
    c.circle(1300, 143, 6, GREY)
    c.text(1312, 150, "GND", 13, DIM)
    c.circle(1376, 143, 6, RED)
    c.text(1388, 150, "VCC", 13, DIM)

    c.rect(80, 200, 360, 520, fill=PANEL, stroke=BORDER, radius=18)
    c.text(260, 236, "ESP32 DevKit", 22, TEXT, bold=True, anchor="middle")
    c.text(260, 262, "entradas analógicas", 14, DIM, anchor="middle")
    pins = [("GPIO34", 310, "óleo"), ("GPIO35", 420, "combustível"),
            ("GPIO36", 530, "temp. óleo"), ("GPIO39", 600, "bateria")]
    for name, y, _ in pins:
        c.circle(440, y, 6, PURPLE)
        c.text(426, y + 5, name, 15, TEXT, mono=True, anchor="end")

    boxes = [
        ("Pressão do óleo", "0,5–4,5 V  •  divisor 2:1", 310),
        ("Nível de combustível", "boia 0–5 V  •  divisor / pull-up", 420),
        ("Temperatura do óleo", "0,5–4,5 V  •  divisor 2:1", 530),
    ]
    for title, sub, y in boxes:
        c.rect(700, y - 46, 370, 92, fill=PANEL, stroke=PURPLE, sw=2, radius=14)
        c.text(724, y - 17, title, 19, TEXT, bold=True)
        c.text(724, y + 8, sub, 13, DIM)
        c.circle(790, y + 32, 7, PURPLE)
        c.circle(830, y + 32, 7, GREY)
        c.circle(870, y + 32, 7, RED)
        c.wire([(446, y), (694, y)], PURPLE, 4)

    # battery divider
    c.rect(700, 590, 700, 130, fill=PANEL, stroke=BORDER, radius=14)
    c.text(724, 622, "Bateria 12 V — divisor 39 kΩ / 10 kΩ", 19, TEXT, bold=True)
    c.text(724, 650, "+12 V ── R1 39k ──●── R2 10k ── GND", 16, TEXT, mono=True)
    c.text(724, 678, "● = nó do divisor → GPIO39 (2,45 V em 12 V; máx. 2,94 V)", 15, YELLOW, bold=True)
    c.text(724, 704, "Ajuste BATT_DIVIDER no config.h e confira com multímetro.",
           13, DIM)
    c.wire([(446, 600), (620, 600), (620, 654), (724, 654)], PURPLE, 4)

    c.rect(80, 760, 1320, 90, fill=PANEL2, stroke=RED, sw=2, radius=12)
    c.text(104, 795, "ATENÇÃO: nunca aplique 5 V ou 12 V direto em GPIO34/35/36/39.",
           18, RED, bold=True)
    c.text(104, 824, "Use divisor, sensor de 3,3 V ou interface de condicionamento. A leitura deve ficar entre 0 e 3,3 V.",
           15, TEXT)
    c.save()


def io_diagram():
    c = Canvas(os.path.join(OUT, "conexao-entradas-saidas-esp32.png"),
               "Entradas, saídas e GPS", "Montagem")
    c.text(60, 148, "Chaves ligam para GND (INPUT_PULLUP). Saídas acionam buzzer, LED e relés.",
           17, DIM)

    # board
    c.rect(560, 200, 420, 600, fill=PANEL, stroke=BORDER, radius=18)
    c.text(770, 236, "ESP32 DevKit", 22, TEXT, bold=True, anchor="middle")
    c.text(770, 262, "GPIOs do perfil esp32", 14, DIM, anchor="middle")

    inputs = [
        ("GPIO25", "seta esquerda", YELLOW), ("GPIO26", "seta direita", YELLOW),
        ("GPIO27", "farol baixo", YELLOW), ("GPIO32", "farol alto", YELLOW),
        ("GPIO33", "freio de mão", YELLOW), ("GPIO4", "cinto", YELLOW),
        ("GPIO13", "porta", YELLOW), ("GPIO16", "alerta", YELLOW),
        ("GPIO17", "ignição", YELLOW), ("GPIO21", "ré", YELLOW),
    ]
    for i, (name, label, color) in enumerate(inputs):
        y = 370 + i * 40
        c.circle(560, y, 6, color)
        c.line(540, y, 560, y, BORDER, 2)

    outputs = [
        ("GPIO22", "buzzer", GREEN), ("GPIO2", "LED status", GREEN),
        ("GPIO12", "relé ventilador", ORANGE), ("GPIO15", "relé A/C", ORANGE),
        ("GPIO14", "GPS RX (TX do módulo)", BLUE),
        ("3V3", "GPS VCC", RED), ("GND", "GPS GND", GREY),
    ]
    for i, (name, label, color) in enumerate(outputs):
        y = 370 + i * 43
        c.circle(980, y, 6, color)
        c.line(980, y, 1000, y, BORDER, 2)

    # left panel
    c.rect(80, 275, 420, 485, fill=PANEL, stroke=BORDER, radius=14)
    c.text(104, 306, "Chaves / entradas digitais", 18, TEXT, bold=True)
    c.text(104, 330, "uma ponta no GPIO, outra no GND", 13, DIM)
    for i, (name, label, color) in enumerate(inputs):
        yy = 370 + i * 40
        c.rect(104, yy - 17, 372, 32, fill=PANEL2, stroke=BORDER, sw=1, radius=6)
        c.text(116, yy + 5, label, 13, TEXT)
        c.text(464, yy + 5, name, 12, color, anchor="end", mono=True)
        c.wire([(500, yy), (554, yy)], color, 2.5)

    # right panel
    c.rect(1040, 275, 480, 485, fill=PANEL, stroke=BORDER, radius=14)
    c.text(1064, 306, "Saídas e GPS", 18, TEXT, bold=True)
    c.text(1064, 330, "saídas chaveiam para GND ou +5 V", 13, DIM)
    for i, (name, label, color) in enumerate(outputs):
        yy = 370 + i * 43
        c.rect(1064, yy - 17, 432, 32, fill=PANEL2, stroke=BORDER, sw=1, radius=6)
        c.text(1076, yy + 5, label, 13, TEXT)
        c.text(1484, yy + 5, name, 12, color, anchor="end", mono=True)
        c.wire([(1006, yy), (1058, yy)], color, 2.5)

    c.rect(80, 780, 1440, 74, fill=PANEL2, stroke=BORDER, radius=12)
    c.text(104, 810, "Entradas ativas em LOW: a chave fecha para GND. Saídas não alimentam cargas diretamente; use relé/módulo.",
           15, YELLOW, bold=True)
    c.text(104, 836, "GPS: TX do módulo → GPIO14; GPIO14 é só RX. Alimente o GPS em 3,3 V e una os GNDs.",
           14, BLUE)
    c.save()


def power_diagram():
    c = Canvas(os.path.join(OUT, "conexao-alimentacao-esp32.png"),
               "Alimentação 12 V → 5 V", "Montagem")
    c.text(60, 148, "Alimente o ESP32 pelo VIN/5V. O pino 3V3 é saída regulada, não entrada de 5 V.",
           17, DIM)

    # battery
    c.rect(80, 280, 250, 230, fill=PANEL, stroke=BORDER, radius=16)
    c.text(205, 318, "Bateria", 22, TEXT, bold=True, anchor="middle")
    c.text(205, 344, "12 V do carro", 14, DIM, anchor="middle")
    c.text(205, 410, "+", 40, RED, bold=True, anchor="middle")
    c.text(205, 470, "−", 40, GREY, bold=True, anchor="middle")

    # fuse
    c.rect(390, 350, 150, 90, fill=PANEL, stroke=YELLOW, sw=2, radius=12)
    c.text(465, 386, "Fusível", 19, TEXT, bold=True, anchor="middle")
    c.text(465, 412, "3 A", 16, YELLOW, bold=True, anchor="middle")
    c.wire([(330, 400), (390, 400)], RED, 5)

    # DC-DC
    c.rect(620, 300, 300, 190, fill=PANEL, stroke=BORDER, radius=16)
    c.text(770, 340, "DC-DC", 22, TEXT, bold=True, anchor="middle")
    c.text(770, 368, "12 V → 5 V", 19, BLUE, bold=True, anchor="middle")
    c.text(770, 396, "3 A (mínimo)", 14, DIM, anchor="middle")
    c.wire([(540, 400), (620, 400)], RED, 5)

    # buses
    c.wire([(920, 360), (980, 360), (980, 690)], RED, 6)
    c.wire([(920, 430), (1030, 430), (1030, 690)], GREY, 6)
    c.text(1000, 338, "+5 V", 15, RED, bold=True)
    c.text(1048, 412, "GND", 15, GREY, bold=True)

    # loads
    loads = [
        ("ESP32", "VIN / 5V", 220),
        ("Tela HDMI", "5 V", 390),
    ]
    for title, sub, y in loads:
        c.rect(1160, y, 360, 130, fill=PANEL, stroke=BORDER, radius=14)
        c.text(1184, y + 35, title, 20, TEXT, bold=True)
        c.text(1184, y + 64, sub, 15, RED, bold=True)
        c.wire([(980, 360), (1100, 360), (1100, y + 45), (1160, y + 45)], RED, 4)
        c.wire([(1030, 430), (1120, 430), (1120, y + 100), (1160, y + 100)], GREY, 4)
        c.text(1340, y + 100, "GND", 12, GREY, anchor="end")

    c.rect(1160, 560, 360, 120, fill=PANEL, stroke=YELLOW, sw=2, radius=14)
    c.text(1184, 596, "MCP2515 / GPS", 20, TEXT, bold=True)
    c.text(1184, 624, "VCC → pino 3V3 do ESP32", 15, YELLOW, bold=True)
    c.text(1184, 650, "Nunca no barramento de 5 V.", 13, DIM)

    # notes
    c.rect(80, 740, 1440, 110, fill=PANEL2, stroke=BORDER, radius=12)
    c.text(104, 778, "GND comum entre bateria, DC-DC, ESP32, tela e módulo CAN.",
           17, TEXT, bold=True)
    c.text(104, 806, "Nunca alimente o ESP32 com 12 V. Use o VIN/5V com 5 V estabilizados.",
           15, RED, bold=True)
    c.text(104, 832, "Se o módulo CAN for 5 V, use level shifter nos sinais SPI; o ESP32 é 3,3 V.",
           14, YELLOW)
    c.save()


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in (can_diagram, sensors_diagram, io_diagram, power_diagram):
        fn()
        print("ok", fn.__name__)


if __name__ == "__main__":
    main()
