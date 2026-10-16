#!/usr/bin/env python3
"""Gera um video curto comparando as vozes neurais pt-BR (edge-tts).

Uso: python3 compare_voices.py
Saida: voz-comparacao.mp4 (mesma pasta)
"""
import asyncio
import os
import shutil
import subprocess
import sys

from edge_tts import Communicate

W, H = 1280, 720
FPS = 30
BG = "0x0d1117"
WHITE = "0xf0f6fc"
GREY = "0xc9d1d9"
DIM = "0x8b949e"
ACCENT = "0x2ea043"

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build_voices")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = os.path.join(HERE, "voz-comparacao.mp4")

TEXT = (
    "Olá! Bem-vindo ao guia de instalação do OpenDash, um painel automotivo que roda no Orange Pi. "
    "O Arduino lê o barramento CAN OBD dois e envia os dados pela porta USB. "
    "Configure a ignição no pino vinte e dois e a bateria no divisor de trinta e dez quilo ohms."
)

VOICES = [
    ("Antônio", "pt-BR-AntonioNeural", "Masculina"),
    ("Francisca", "pt-BR-FranciscaNeural", "Feminina"),
    ("Thalita", "pt-BR-ThalitaMultilingualNeural", "Feminina · multilíngue"),
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


def make_slide(idx, name, desc):
    title_file = os.path.join(BUILD, f"title_{idx}.txt")
    body_file = os.path.join(BUILD, f"body_{idx}.txt")
    write(title_file, f"Voz {idx}: {name}")
    write(body_file, f"Voz neural pt-BR · {desc}\nO mesmo texto, para comparar a fluência")
    png = os.path.join(BUILD, f"slide_{idx}.png")
    parts = [
        f"drawbox=x=0:y=0:w={W}:h=8:color={ACCENT}:t=fill",
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color={ACCENT}:t=fill",
        f"drawbox=x=60:y=150:w=90:h=6:color={ACCENT}:t=fill",
        f"drawtext=fontfile={FONT_BOLD}:text=OpenDash:fontcolor={ACCENT}:fontsize=26:x=60:y=44",
        f"drawtext=fontfile={FONT}:text=comparação de vozes:fontcolor={DIM}:fontsize=20:x=214:y=50",
        f"drawtext=fontfile={FONT_BOLD}:textfile={title_file}:fontcolor={WHITE}:fontsize=56:x=60:y=180",
        f"drawtext=fontfile={FONT}:textfile={body_file}:fontcolor={GREY}:fontsize=30:x=64:y=320:line_spacing=16",
        f"drawtext=fontfile={FONT}:text='{idx} / 3':fontcolor={DIM}:fontsize=22:x=w-tw-60:y={H-60}",
    ]
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


async def synth(name, voice):
    mp3 = os.path.join(BUILD, f"{name}.mp3")
    c = Communicate(TEXT, voice)
    await c.save(mp3)
    wav = os.path.join(BUILD, f"{name}.wav")
    run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
    return wav


def make_segment(idx, png, wav):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    dur = duration(wav) + 1.2
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png,
         "-i", wav, "-t", f"{dur:.3f}",
         "-vf", "fade=t=in:st=0:d=0.3,format=yuv420p", "-af", "apad",
         "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
         "-shortest", seg])
    return seg


def main():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD, exist_ok=True)
    segments = []
    for i, (name, voice, desc) in enumerate(VOICES, 1):
        print(f"[{i}/3] {name} ({voice})")
        wav = asyncio.run(synth(name, voice))
        png = make_slide(i, name, desc)
        segments.append(make_segment(i, png, wav))
    listfile = os.path.join(BUILD, "list.txt")
    write(listfile, "".join(f"file '{s}'\n" for s in segments))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", "-movflags", "+faststart", OUT])
    d = duration(OUT)
    print(f"\nOK -> {OUT}  ({int(d // 60)}m{int(d % 60):02d}s, "
          f"{os.path.getsize(OUT) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
