#!/usr/bin/env python3
"""Gera o VIDEO DE PROPAGANDA (promo) do painel completo do OpenDash.

Diferente dos tutoriais, aqui o foco e apresentar o produto com animacoes 2D:
Zoom/Pan (Ken Burns) sobre as telas reais, titulos e chamadas que entram
animados, avatar narrando, transicoes em fade e trilha sonora. Mostra o painel
COMPLETO em uso: Painel, Navegacao, Midia, Clima, Diagnostico, Ajustes, Apps e
o sistema rodando ao vivo.

Requer: ffmpeg, ffprobe e edge-tts (internet para a voz). Se o edge-tts falhar,
gera a cena com trilha/silencio para nao quebrar o video.

Antes (uma vez), garanta o avatar e as telas:
  python3 docs/tutorial/capture_avatar.py
  python3 docs/tutorial/capture_new_ui.py     # opcional: telas novas
Depois:
  /car-dash/.venv/bin/python docs/tutorial/build_promo.py
Saida: opendash-propaganda.mp4 (mesma pasta)

Atalhos:
  TUT_ONLY=3 python3 docs/tutorial/build_promo.py   # gera so as 3 primeiras cenas
"""
import asyncio
import os
import subprocess
import sys
import time

from edge_tts import Communicate

W, H = 1280, 720
FPS = 30
BG = "0x0b0f16"
WHITE = "0xf0f6fc"
GREY = "0xc9d1d9"
DIM = "0x8b949e"

VOICE = "pt-BR-ThalitaMultilingualNeural"
RATE = "+4%"
PITCH = "+0Hz"
MUSIC_LEVEL = 0.18

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
BUILD = os.path.join(HERE, "build_promo")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = os.path.join(HERE, "opendash-propaganda.mp4")

AV_IDLE = os.path.join(ASSETS, "avatar_idle.png")
AV_TALK = os.path.join(ASSETS, "avatar_talk.png")
AV_BLINK = os.path.join(ASSETS, "avatar_blink.png")
AV_WAVE = os.path.join(ASSETS, "avatar_wave.png")
PIP_H = 380
PIP_X = W - 356
PIP_Y = H - PIP_H + 20

ANIM = os.path.join(ASSETS, "ui-anim.mp4")

RED = "0xe82127"
BLUE = "0x2f81f7"
GREEN = "0x2ea043"
AMBER = "0xd29922"
PURPLE = "0x8957e5"
CYAN = "0x1f9bd1"

SCENES = [
    # ------------------------------------------------------------------ abertura
    {
        "kind": "hero", "avatar": "wave", "kicker": "OPENDASH",
        "title": "O painel do seu carro",
        "sub": "inteligente, bonito e de código aberto",
        "color": RED,
        "narration": (
            "Apresento o OpenDash: o painel automotivo que transforma qualquer tela num "
            "computador de bordo completo. Bonito, rápido e totalmente de código aberto."),
    },
    # --------------------------------------------------------------- visao geral
    {
        "kind": "grid", "kicker": "VISÃO GERAL",
        "title": "Tudo em um só lugar",
        "items": ["Painel esportivo", "Navegação com GPS",
                  "Trânsito ao vivo", "Mini mapa no painel",
                  "Mídia e papel de parede", "Ar-condicionado (clima)",
                  "Diagnóstico do motor", "Aplicativos e mapas",
                  "Câmera de ré ao engatar", "Dez temas de marcas"],
        "color": BLUE,
        "narration": (
            "Um só sistema reúne tudo o que você precisa na estrada: painel esportivo, navegação "
            "com trânsito ao vivo, mini mapa, mídia, climatização, diagnóstico, aplicativos, "
            "câmera de ré e dez temas inspirados em marcas."),
    },
    # -------------------------------------------------------------- feature: painel
    {
        "kind": "feature", "image": "page_drive.png", "kicker": "PAINEL",
        "title": "Visual esportivo",
        "caption": "Setas, lâmpadas, velocímetro com arco de RPM, mini mapa e sensores OBD-II",
        "callouts": [
            {"x": 75, "y": 165, "w": 305, "h": 395, "at": 1.0, "color": AMBER, "label": "Setas e lâmpadas"},
            {"x": 455, "y": 228, "w": 298, "h": 200, "at": 1.6, "color": RED, "label": "Velocímetro e RPM"},
            {"x": 872, "y": 120, "w": 320, "h": 82, "at": 2.2, "color": GREEN, "label": "Mini mapa"},
        ],
        "color": RED,
        "narration": (
            "Comece pelo Painel, agora com visual esportivo: setas e lâmpadas à esquerda, "
            "velocímetro com arco de RPM no centro, o mini mapa logo abaixo do velocímetro, "
            "e à direita seis sensores do motor atualizando em tempo real."),
    },
    # ---------------------------------------------------------------- feature: temas
    {
        "kind": "feature", "image": "page_temas.png", "kicker": "TEMAS",
        "title": "Do seu jeito",
        "caption": "Dez temas inspirados em marcas: Ferrari, Porsche, BMW, AMG e mais",
        "callouts": [
            {"x": 75, "y": 385, "w": 540, "h": 230, "at": 1.0, "color": PURPLE, "label": "Troca na hora"},
        ],
        "color": PURPLE,
        "narration": (
            "E o visual muda quando você quiser: são dez temas inspirados nas maiores marcas, "
            "da Ferrari ao Porsche, passando por BMW, AMG e Lamborghini. Cada tema troca fundo, "
            "brilho, tipografia, velocímetro e ícones. A troca é instantânea."),
    },
    # ------------------------------------------------------------ feature: navegacao
    {
        "kind": "feature", "image": "page_nav.png", "kicker": "NAVEGAÇÃO",
        "title": "Mapa e GPS",
        "caption": "Mapa OpenStreetMap offline, rastro e busca de destino",
        "callouts": [
            {"x": 250, "y": 220, "w": 460, "h": 380, "at": 1.0, "color": BLUE, "label": "Mapa"},
            {"x": 900, "y": 250, "w": 300, "h": 200, "at": 1.7, "color": CYAN, "label": "Sensores GPS"},
        ],
        "color": BLUE,
        "narration": (
            "A Navegação traz o mapa do OpenStreetMap, funciona offline, mostra a posição do GPS, "
            "o rastro do percurso e a busca de destino."),
    },
    # ------------------------------------------------------------ feature: transito
    {
        "kind": "feature", "image": "page_traffic.png", "kicker": "TRÂNSITO AO VIVO",
        "title": "Ônibus em tempo real",
        "caption": "Posições dos ônibus da SPTrans (Olho Vivo) desenhadas no mapa",
        "callouts": [
            {"x": 355, "y": 432, "w": 145, "h": 138, "at": 1.0, "color": GREEN, "label": "ônibus ao vivo"},
        ],
        "color": GREEN,
        "narration": (
            "E tem trânsito ao vivo: o OpenDash consulta o Olho Vivo, da SPTrans, e mostra no mapa "
            "as posições dos ônibus perto do carro. Basta ativar a camada na Navegação."),
    },
    # ---------------------------------------------------------------- feature: midia
    {
        "kind": "feature", "image": "page_media.png", "kicker": "MÍDIA",
        "title": "Som e estilo",
        "caption": "Rádio, controles de mídia e papel de parede personalizado",
        "callouts": [
            {"x": 250, "y": 230, "w": 320, "h": 320, "at": 1.0, "color": AMBER, "label": "Player"},
            {"x": 700, "y": 300, "w": 380, "h": 240, "at": 1.6, "color": PURPLE, "label": "Papel de parede"},
        ],
        "color": AMBER,
        "narration": (
            "Na Mídia você controla o som e ainda troca o papel de parede do painel, deixando o "
            "visual com a sua cara."),
    },
    # ---------------------------------------------------------------- feature: clima
    {
        "kind": "feature", "image": "page_climate.png", "kicker": "CLIMA",
        "title": "Ar-condicionado",
        "caption": "Ventilação, temperatura, AC, recirculação e desembaçador",
        "callouts": [
            {"x": 260, "y": 250, "w": 360, "h": 320, "at": 1.0, "color": CYAN, "label": "Controles"},
        ],
        "color": CYAN,
        "narration": (
            "O Clima regula a ventilação, a temperatura, o ar-condicionado e o desembaçador, tudo "
            "com um toque na tela."),
    },
    # ----------------------------------------------------------- feature: diagnostico
    {
        "kind": "feature", "image": "page_diag.png", "kicker": "DIAGNÓSTICO",
        "title": "O motor sob controle",
        "caption": "Sensores ao vivo, códigos de falha (DTC) e leitura de dados",
        "callouts": [
            {"x": 250, "y": 240, "w": 440, "h": 360, "at": 1.0, "color": GREEN, "label": "Sensores"},
            {"x": 780, "y": 250, "w": 420, "h": 260, "at": 1.6, "color": AMBER, "label": "Códigos DTC"},
        ],
        "color": GREEN,
        "narration": (
            "O Diagnóstico mostra os sensores ao vivo e lê os códigos de falha do motor, como num "
            "scanner profissional."),
    },
    # --------------------------------------------------------------- feature: apps
    {
        "kind": "feature", "image": "page_apps.png", "kicker": "APLICATIVOS",
        "title": "Seus apps na tela",
        "caption": "Abra YouTube, Spotube, mapas e apps Android (Waydroid)",
        "callouts": [
            {"x": 300, "y": 250, "w": 640, "h": 320, "at": 1.0, "color": PURPLE, "label": "Apps"},
        ],
        "color": PURPLE,
        "narration": (
            "Na página de Aplicativos, você abre YouTube, Spotube, mapas e até aplicativos Android "
            "diretamente no painel."),
    },
    # ------------------------------------------------------------- feature: ajustes
    {
        "kind": "feature", "image": "page_settings_net.png", "kicker": "AJUSTES",
        "title": "Wi-Fi, Bluetooth e mais",
        "caption": "Rede, telas HDMI, unidades, temas e atualização pelo GitHub",
        "callouts": [
            {"x": 250, "y": 240, "w": 430, "h": 300, "at": 1.0, "color": BLUE, "label": "Conectividade"},
            {"x": 760, "y": 250, "w": 440, "h": 300, "at": 1.7, "color": GREEN, "label": "Ajustes"},
        ],
        "color": BLUE,
        "narration": (
            "Nos Ajustes, você configura o Wi-Fi e o Bluetooth, escolhe as telas, define as "
            "unidades, escolhe entre dez temas e atualiza o sistema direto pelo GitHub."),
    },
    # ------------------------------------------------------- feature: tela e escala
    {
        "kind": "feature", "image": "page_settings_display.png", "kicker": "QUALQUER TELA",
        "title": "Do tamanho que precisar",
        "caption": "Detecta a resolução e ajusta a escala da interface automaticamente",
        "callouts": [
            {"x": 647, "y": 175, "w": 534, "h": 290, "at": 1.0, "color": BLUE, "label": "Escala automática"},
            {"x": 655, "y": 558, "w": 215, "h": 44, "at": 1.7, "color": GREEN, "label": "Resolução detectada"},
        ],
        "color": BLUE,
        "narration": (
            "E ele se adapta: o OpenDash detecta a resolução do seu monitor e ajusta a escala da "
            "interface sozinho. Funciona em telas pequenas ou grandes, do jeito certo."),
    },
    # --------------------------------------------------------- feature: camera de re
    {
        "kind": "feature", "image": "page_reverse.png", "kicker": "CÂMERA DE RÉ",
        "title": "Manobra sem susto",
        "caption": "Ao engatar a ré, a câmera aparece na hora, com linhas guia",
        "callouts": [
            {"x": 150, "y": 268, "w": 300, "h": 74, "at": 1.0, "color": GREEN, "label": "Linhas guia"},
            {"x": 830, "y": 268, "w": 300, "h": 74, "at": 1.6, "color": CYAN, "label": "Entra em ré"},
        ],
        "color": GREEN,
        "narration": (
            "Engatou a marcha à ré? A câmera entra na tela automática, com linhas guia para "
            "facilitar a manobra. Apoio de câmera de fábrica, sem custo extra."),
    },
    # ------------------------------------------------------------------- ao vivo
    {
        "kind": "demo", "kicker": "AO VIVO",
        "title": "O sistema rodando",
        "caption": "Veja o OpenDash em uso, trocando de página pelo toque",
        "color": RED,
        "narration": (
            "E aqui está o OpenDash rodando ao vivo. Repare no arco de RPM, no mini mapa e nos "
            "sensores se atualizando, além da troca de páginas pelo toque. É assim, no seu carro."),
    },
    # ------------------------------------------------------------ segunda tela
    {
        "kind": "feature", "image": "page_bar.png", "wide": True, "kicker": "DUAS TELAS",
        "title": "Painel + cluster",
        "caption": "Multimídia com menus e um painel de velocidade dedicado, sem menus",
        "callouts": [
            {"x": 320, "y": 210, "w": 300, "h": 300, "at": 1.0, "x2": 0, "color": GREEN, "label": "Velocímetro"},
            {"x": 900, "y": 250, "w": 340, "h": 200, "at": 1.6, "color": AMBER, "label": "Indicadores"},
        ],
        "color": PURPLE,
        "narration": (
            "E dá para ligar duas telas: a multimídia completa, com menus, e um painel de velocidade "
            "dedicado, sem menus, do jeito que um carro moderno tem."),
    },
    # ------------------------------------------------------------------- encerramento
    {
        "kind": "outro", "avatar": "wave", "kicker": "ENCERRAMENTO", "big": True,
        "title": "OpenDash",
        "sub": "código aberto · grátis · Debian e Armbian",
        "items": ["Instale em minutos", "Orange Pi e Raspberry Pi", "Contribua no GitHub"],
        "color": RED,
        "narration": (
            "OpenDash: código aberto, grátis, feito para rodar em placas como a Orange Pi ou a "
            "Raspberry Pi com Debian ou Armbian. Instale em minutos e bom passeio!"),
    },
]


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.stderr.write(r.stdout.decode("utf-8", "ignore"))
        raise SystemExit(f"falhou: {' '.join(cmd)}")


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return float(r.stdout.decode().strip())


def textfile(idx, tag, text):
    path = os.path.join(BUILD, f"txt_{idx}_{tag}.txt")
    write(path, text)
    return path


# --------------------------------------------------------------- base (fundo 2D)
def base_hero(idx, scene):
    color = scene["color"]
    parts = [
        f"drawbox=x=0:y=0:w={W}:h={H}:color={BG}:t=fill",
        f"drawbox=x=0:y=0:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y=0:w=12:h={H}:color={color}@0.35:t=fill",
        f"drawbox=x={W-12}:y=0:w=12:h={H}:color={color}@0.35:t=fill",
        f"drawbox=x=120:y=0:w=6:h={H}:color={BLUE}@0.18:t=fill",
        f"drawbox=x={W-126}:y=0:w=6:h={H}:color={GREEN}@0.18:t=fill",
        f"drawtext=fontfile={FONT_BOLD}:text='OpenDash':fontcolor={WHITE}:"
        f"fontsize=128:x=(w-tw)/2:y=120",
        f"drawbox=x=(w-420)/2:y=290:w=420:h=8:color={color}:t=fill",
    ]
    png = os.path.join(BUILD, f"base_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def base_outro(idx, scene):
    color = scene["color"]
    parts = [
        f"drawbox=x=0:y=0:w={W}:h={H}:color={BG}:t=fill",
        f"drawbox=x=0:y=0:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y=0:w=12:h={H}:color={color}@0.35:t=fill",
        f"drawbox=x={W-12}:y=0:w=12:h={H}:color={color}@0.35:t=fill",
        f"drawbox=x=120:y=0:w=6:h={H}:color={BLUE}@0.18:t=fill",
        f"drawbox=x={W-126}:y=0:w=6:h={H}:color={GREEN}@0.18:t=fill",
    ]
    png = os.path.join(BUILD, f"base_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def base_grid(idx, scene):
    color = scene["color"]
    parts = [
        f"drawbox=x=0:y=0:w={W}:h={H}:color={BG}:t=fill",
        f"drawbox=x=0:y=0:w={W}:h=150:color={BG}:t=fill",
        f"drawbox=x=0:y=150:w={W}:h=5:color={color}:t=fill",
        f"drawbox=x=0:y=0:w={W}:h=8:color={color}@0.5:t=fill",
    ]
    png = os.path.join(BUILD, f"base_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def base_frame(idx, scene):
    """Fundo com a tela real enquadrada (para o Ken Burns)."""
    img = os.path.join(ASSETS, scene["image"])
    wide = scene.get("wide")
    if wide:
        sw, sh = 1180, 295
    else:
        sw, sh = 1160, 680
    sx, sy = (W - sw) // 2, (H - sh) // 2
    png = os.path.join(BUILD, f"base_{idx}.png")
    vf = (f"scale={sw}:{sh},pad={W}:{H}:{sx}:{sy}:color={BG},"
          f"drawbox=x={sx-2}:y={sy-2}:w={sw+4}:h={sh+4}:color=0x30363d:t=3")
    run(["ffmpeg", "-y", "-i", img, "-vf", vf, "-frames:v", "1", png])
    return png


# ----------------------------------------------------------- overlays animados 2D
def anim_overlay(idx, scene):
    color = scene["color"]
    parts = []
    center = scene["kind"] in ("hero", "outro")

    kf = textfile(idx, "kicker", scene["kicker"])
    bf = textfile(idx, "brand", "OpenDash")
    parts.append(f"drawtext=fontfile={FONT_BOLD}:textfile={bf}:fontcolor={color}:"
                 f"fontsize=24:x=44:y=34:alpha='min(1,max(0,(t-0.1)/0.5))'")
    parts.append(f"drawtext=fontfile={FONT_BOLD}:textfile={kf}:fontcolor=white:fontsize=20:"
                 f"x=w-tw-44:y=38:box=1:boxcolor={color}:boxborderw=12:"
                 f"alpha='min(1,max(0,(t-0.1)/0.5))'")

    tf = textfile(idx, "title", scene["title"])
    if center:
        ts = 96 if scene.get("big") else 64
        parts.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile={tf}:fontcolor={WHITE}:fontsize={ts}:"
            f"x=(w-tw)/2:y='{340 if not scene.get('big') else 250}"
            f"+(1-min(1,max(0,(t-0.3)/0.7)))*40':"
            f"alpha='min(1,max(0,(t-0.3)/0.7))'")
    else:
        parts.append(f"drawbox=x=0:y=0:w={W}:h=150:color={BG}@0.55:t=fill:"
                     f"enable='gt(t,0.05)'")
        parts.append(f"drawbox=x=0:y=150:w={W}:h=5:color={color}:t=fill")
        parts.append(
            f"drawtext=fontfile={FONT_BOLD}:textfile={tf}:fontcolor={WHITE}:fontsize=52:"
            f"x=44:y='78+(1-min(1,max(0,(t-0.15)/0.6)))*30':"
            f"alpha='min(1,max(0,(t-0.15)/0.6))'")

    sub = scene.get("sub")
    if sub:
        sf = textfile(idx, "sub", sub)
        parts.append(f"drawtext=fontfile={FONT}:textfile={sf}:fontcolor={color}:fontsize=32:"
                     f"x=(w-tw)/2:y=430:alpha='min(1,max(0,(t-0.7)/0.7))'")

    # lista de itens que entram um a um (grade / encerramento)
    items = scene.get("items")
    if items:
        cols = 2
        n = len(items)
        rows = (n + cols - 1) // cols
        y0 = 220 if not center else 500
        dx = 560
        dy = 70 if rows > 4 else 84
        for k, item in enumerate(items):
            col = k % cols
            row = k // cols
            x = 90 + col * dx
            y = y0 + row * dy
            d = 0.4 + k * 0.28
            itf = textfile(idx, f"it{k}", item)
            alpha = f"min(1,max(0,(t-{d:.2f})/0.4))"
            slide = f"(1-min(1,max(0,(t-{d:.2f})/0.5)))*36"
            parts.append(f"drawbox=x='{x}-{slide}':y={y+8}:w=16:h=16:color={color}:t=fill:"
                         f"enable='gte(t,{d:.2f})'")
            parts.append(
                f"drawtext=fontfile={FONT}:textfile={itf}:fontcolor={GREY}:fontsize=30:"
                f"x='{x+34}-{slide}':y={y}:alpha='{alpha}'")

    # chamadas (boxes) que aparecem
    for j, c in enumerate(scene.get("callouts", [])):
        at = c.get("at", 0.8 + j * 0.4)
        cc = c.get("color", color)
        parts.append(f"drawbox=x={c['x']}:y={c['y']}:w={c['w']}:h={c['h']}:"
                     f"color={cc}@0.92:t=3:enable='gte(t,{at})'")
        if c.get("label"):
            lf = textfile(idx, f"co{j}", c["label"])
            parts.append(f"drawtext=fontfile={FONT_BOLD}:textfile={lf}:fontcolor=white:"
                         f"fontsize=20:x={c['x']}:y={c['y']-33}:box=1:boxcolor={cc}@0.92:"
                         f"boxborderw=8:enable='gte(t,{at})'")

    cap = scene.get("caption")
    if cap:
        cf = textfile(idx, "cap", cap)
        parts.append(f"drawbox=x=0:y={H-92}:w={W}:h=92:color={BG}@0.74:t=fill:"
                     f"enable='gte(t,0.75)'")
        parts.append(f"drawtext=fontfile={FONT}:textfile={cf}:fontcolor={GREY}:fontsize=27:"
                     f"x=44:y={H-68}:alpha='min(1,max(0,(t-0.75)/0.6))'")
    return parts


def pip_tail(bg_label):
    return (
        f"[2:v]scale=-1:{PIP_H}[ai];[3:v]scale=-1:{PIP_H}[at];[4:v]scale=-1:{PIP_H}[ab];"
        f"[{bg_label}][ai]overlay={PIP_X}:{PIP_Y}[p1];"
        f"[p1][at]overlay={PIP_X}:{PIP_Y}:enable='lt(mod(t,0.26),0.13)'[p2];"
        f"[p2][ab]overlay={PIP_X}:{PIP_Y}:enable='lt(mod(t+1.0,3.4),0.13)'")


def pip_inputs(loop=True):
    flag = ["-loop", "1"] if loop else []
    return [*flag, "-i", AV_IDLE, *flag, "-i", AV_TALK, *flag, "-i", AV_BLINK]


def make_segment_motion(idx, dur, base, scene, is_presenter):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    if seg_ready(seg):
        return seg
    frames = max(2, int(dur * FPS))
    color = scene["color"]
    og = ",".join(anim_overlay(idx, scene))
    fade = (f"fade=t=in:st=0:d=0.5,fade=t=out:st={max(0.0, dur-0.5):.2f}:d=0.5")
    if is_presenter:
        # avatar grande a esquerda; sem Ken Burns
        ax, ay, ah = 80, 170, 520
        fc = (f"[2:v]scale=-1:{ah}[ai];[0:v]{og}[bg];"
              f"[bg][ai]overlay={ax}:'{ay}+8*sin(2*PI*t/2.4)',"
              f"{fade},format=yuv420p[v]")
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", base,
             "-i", os.path.join(BUILD, f"voice_{idx}.wav"),
             "-loop", "1", "-i", AV_WAVE,
             "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
             "-t", f"{dur:.3f}", "-af", "apad",
             "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
             "-ar", "44100", "-ac", "2", "-shortest", seg])
        return seg
    src = (f"[0:v]scale=1408:792,zoompan=z='min(1+0.00035*on,1.10)':"
           f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
           f"setsar=1")
    fc = (f"{src},{og}[bg];" + pip_tail("bg") + f",{fade},format=yuv420p[v]")
    run(["ffmpeg", "-y", "-i", base, "-i", os.path.join(BUILD, f"voice_{idx}.wav"),
         *pip_inputs(), "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
         "-t", f"{dur:.3f}", "-af", "apad",
         "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-ar", "44100", "-ac", "2", "-shortest", seg])
    return seg


def make_segment_demo(idx, dur, scene):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    if seg_ready(seg):
        return seg
    color = scene["color"]
    og = ",".join(anim_overlay(idx, scene))
    fade = f"fade=t=in:st=0:d=0.4,fade=t=out:st={max(0.0, dur-0.5):.2f}:d=0.5"
    fc = (f"[0:v]scale={W}:{H},fps={FPS},setsar=1,{og}[bg];"
          + pip_tail("bg") + f",{fade},format=yuv420p[v]")
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", ANIM,
         "-i", os.path.join(BUILD, f"voice_{idx}.wav"), *pip_inputs(),
         "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
         "-t", f"{dur:.3f}", "-af", "apad",
         "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-ar", "44100", "-ac", "2", "-shortest", seg])
    return seg


# ------------------------------------------------------------------ voz / trilha
def estimate_dur(text):
    words = len(text.split())
    return max(3.0, words / 2.6 + 0.8)


def silence_wav(path, dur):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
         "-t", f"{dur:.3f}", path])


def make_voice(idx, scene):
    wav = os.path.join(BUILD, f"voice_{idx}.wav")
    mp3 = os.path.join(BUILD, f"voice_{idx}.mp3")
    if seg_ready(wav):
        return wav

    async def synth():
        await Communicate(scene["narration"], VOICE, rate=RATE, pitch=PITCH).save(mp3)

    last = None
    for attempt in range(12):
        try:
            asyncio.run(synth())
            break
        except Exception as exc:  # noqa: BLE001 - rede/edge-tts pode oscilar
            last = exc
            print(f"  edge-tts cena {idx} tentativa {attempt + 1} falhou: {exc}", flush=True)
            time.sleep(min(20.0, 2.0 * (attempt + 1)))
    else:
        print(f"  AVISO: sem voz na cena {idx} ({last}); usando silencio", flush=True)
        silence_wav(wav, estimate_dur(scene["narration"]))
        return wav
    run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
    return wav


def seg_ready(seg):
    return os.path.exists(seg) and os.path.getsize(seg) > 2000


def make_music(total):
    music = os.path.join(BUILD, "music.wav")
    fade_out = max(0.0, total - 5)
    run(["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"sine=f=110:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=164.8:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=220:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=277.2:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=329.6:d={total:.2f}",
         "-filter_complex",
         "[0][1][2][3][4]amix=inputs=5:normalize=1,"
         "lowpass=f=720,tremolo=f=0.18:d=0.32,volume=0.30,"
         f"afade=t=in:st=0:d=3,afade=t=out:st={fade_out:.2f}:d=5",
         "-ar", "44100", "-ac", "2", music])
    return music


def main():
    for need in (AV_IDLE, AV_TALK, AV_BLINK, AV_WAVE):
        if not os.path.exists(need):
            raise SystemExit(f"falta {need} — rode capture_avatar.py primeiro")
    os.makedirs(BUILD, exist_ok=True)
    scenes = SCENES
    only = int(os.environ.get("TUT_ONLY", "0") or 0)
    if only > 0:
        scenes = scenes[:only]
    total = len(scenes)
    segments = []
    for i, scene in enumerate(scenes, 1):
        kind = scene["kind"]
        print(f"[{i}/{total}] {scene['kicker']} - {scene['title']} ({kind})", flush=True)
        wav = make_voice(i, scene)
        dur = duration(wav) + 1.0
        time.sleep(0.6)
        if kind == "demo":
            seg = make_segment_demo(i, dur, scene)
        else:
            if kind == "hero":
                base = base_hero(i, scene)
            elif kind == "outro":
                base = base_outro(i, scene)
            elif kind == "grid":
                base = base_grid(i, scene)
            else:
                base = base_frame(i, scene)
            is_presenter = kind in ("hero", "outro")
            seg = make_segment_motion(i, dur, base, scene, is_presenter)
        segments.append(seg)

    listfile = os.path.join(BUILD, "list.txt")
    write(listfile, "".join(f"file '{s}'\n" for s in segments))
    narration = os.path.join(BUILD, "narration.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", narration])

    print("[mix] trilha e mixagem final", flush=True)
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
    print(f"\nOK -> {OUT}")
    print(f"duracao: {int(d // 60)}m{int(d % 60):02d}s  |  tamanho: {size:.1f} MB  "
          f"|  cenas: {total}")


if __name__ == "__main__":
    main()
