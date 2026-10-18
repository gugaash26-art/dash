#!/usr/bin/env python3
"""Converte os SVG de hardware/out/ em PNG (para o README e para imprimir).

Usa GTK/GdkPixbuf (librsvg). Rode com o python que tem `gi` (normalmente o do
sistema):

  python3 hardware/render_svg.py

Gera schematic.png e board.png ao lado dos SVG.
"""
import os
import sys

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
TARGETS = [("schematic.svg", "schematic.png", 1700),
           ("board.svg", "board.png", 1500)]


def main():
    ok = True
    for svg, png, width in TARGETS:
        src = os.path.join(OUT, svg)
        dst = os.path.join(OUT, png)
        if not os.path.exists(src):
            print("faltando", src, file=sys.stderr)
            ok = False
            continue
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(src, width, -1, True)
        pb.savev(dst, "png", [], [])
        print("ok", png, os.path.getsize(dst), "bytes")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
