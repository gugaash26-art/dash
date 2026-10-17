import os
import re
import shutil
import subprocess
from pathlib import Path

# Ressonancia de referencia: um painel "tipico" tem ~160 px por polegada.
# A escala automatica e dpi/REF_DPI quando a diagonal (polegadas) e informada.
REF_DPI = 160.0

_OUT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)\s+connected"
    r"(?P<rest>\s+primary)?"
    r"(?:\s+(?P<w>\d+)x(?P<h>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+))?",
    re.MULTILINE,
)
_DIS_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)\s+disconnected", re.MULTILINE)


class Display:
    """Detecta a resolucao/tamanho das telas (xrandr) e calcula a escala ideal
    da interface, para funcionar em qualquer monitor/resolucao/polegadas.

    O cliente (navegador/app nativo) tambem le /api/display e aplica a escala,
    mas o calculo fica no servidor para valer no kiosk sem configuracao.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    # ------------------------------------------------------------- config
    def _cfg(self):
        return self.cfg.get("display") or {}

    def _display_env(self):
        env = dict(os.environ)
        env["DISPLAY"] = str((self.cfg.get("screens") or {}).get("display") or ":0")
        if not env.get("XAUTHORITY"):
            for cand in (Path.home() / ".Xauthority", Path("/root/.Xauthority")):
                if cand.is_file():
                    env["XAUTHORITY"] = str(cand)
                    break
        return env

    def _xrandr(self):
        if not shutil.which("xrandr"):
            return None
        try:
            return subprocess.run(
                ["xrandr", "--query"], capture_output=True, text=True,
                env=self._display_env(), timeout=6,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def detect(self):
        """Lista as saidas conectadas (nome, resolucao, posicao, primaria)."""
        res = self._xrandr()
        if res is None or res.returncode != 0:
            return []
        out = []
        for m in _OUT_RE.finditer(res.stdout or ""):
            w, h = m.group("w"), m.group("h")
            out.append({
                "name": m.group("name"),
                "primary": bool(m.group("rest")),
                "width": int(w) if w else 0,
                "height": int(h) if h else 0,
                "x": int(m.group("x")) if w else 0,
                "y": int(m.group("y")) if w else 0,
                "resolution": f"{w}x{h}" if w and h else "—",
            })
        out.sort(key=lambda o: (not o["primary"], o["name"]))
        return out

    # --------------------------------------------------------------- escala
    def _resolve_size(self, d, screens):
        width = int(d.get("width") or 0)
        height = int(d.get("height") or 0)
        if width and height:
            return width, height
        primary = next((s for s in screens if s["primary"]), None)
        primary = primary or (screens[0] if screens else None)
        if primary and primary["width"] and primary["height"]:
            return primary["width"], primary["height"]
        return width, height

    @staticmethod
    def compute_scale(scale, width, height, inches):
        if scale not in (None, "", "auto"):
            try:
                return round(max(0.5, min(3.0, float(scale))), 3)
            except (TypeError, ValueError):
                pass
        try:
            width = int(width)
            height = int(height)
            inches = float(inches or 0)
        except (TypeError, ValueError):
            return 1.0
        if inches > 0 and width > 0 and height > 0:
            dpi = (width * width + height * height) ** 0.5 / inches
            return round(max(0.5, min(2.5, dpi / REF_DPI)), 3)
        return 1.0

    def status(self):
        d = self._cfg()
        screens = self.detect()
        width, height = self._resolve_size(d, screens)
        inches = float(d.get("inches") or 0)
        scale = self.compute_scale(d.get("scale", "auto"), width, height, inches)
        dpi = None
        if inches > 0 and width and height:
            dpi = round((width * width + height * height) ** 0.5 / inches, 1)
        return {
            "scale": d.get("scale", "auto"),
            "inches": inches,
            "orientation": d.get("orientation", "auto"),
            "width": width,
            "height": height,
            "dpi": dpi,
            "ref_dpi": REF_DPI,
            "computed_scale": scale,
            "available": bool(screens),
            "screens": screens,
            "reason": "" if screens else "xrandr nao encontrado ou servidor X inacessivel",
        }
