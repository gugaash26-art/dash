import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

# Aplicativos de desktop (GNOME) que o painel pode abrir no Orange Pi.
# Somente estes apps (allowlist) podem ser lancados; nada de comando arbitrario.
APPS = {
    "gnome-maps": {
        "name": "GNOME Maps",
        "bin": "gnome-maps",
        "flatpak": "org.gnome.Maps",
        "apt": "gnome-maps",
        "icon": "map",
        "color": "#5b9e4a",
    },
}

COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class Native:
    """Abre/feche aplicativos GUI nativos (GNOME Maps) no display do carro.

    A acao so acontece se `CARDASH_ALLOW_NATIVE=1` (igual a energia) e
    `native.enabled` no config.yaml. Sem o app instalado, informa como instalar.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    # ------------------------------------------------------------------ conf
    def _conf(self):
        return self.cfg.get("native") or {}

    def _display_env(self):
        env = dict(os.environ)
        env["DISPLAY"] = str(self._conf().get("display") or env.get("DISPLAY") or ":0")
        if not env.get("XAUTHORITY"):
            for cand in (Path.home() / ".Xauthority", Path("/root/.Xauthority")):
                if cand.is_file():
                    env["XAUTHORITY"] = str(cand)
                    break
        return env

    def _bin(self, spec):
        path = shutil.which(spec["bin"])
        if path:
            return [path]
        if spec.get("flatpak") and shutil.which("flatpak"):
            try:
                res = subprocess.run(
                    ["flatpak", "info", spec["flatpak"]],
                    capture_output=True, text=True, timeout=6,
                )
                if res.returncode == 0:
                    return ["flatpak", "run", spec["flatpak"]]
            except (OSError, subprocess.SubprocessError):
                return None
        return None

    def _running(self, spec):
        try:
            res = subprocess.run(["pgrep", "-x", spec["bin"]],
                                 capture_output=True, text=True, timeout=4)
            if res.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            return False
        if spec.get("flatpak") and shutil.which("flatpak"):
            try:
                res = subprocess.run(["flatpak", "ps", "--columns=application"],
                                     capture_output=True, text=True, timeout=6)
                return spec["flatpak"] in res.stdout
            except (OSError, subprocess.SubprocessError):
                return False
        return False

    # --------------------------------------------------------------- consulta
    def status(self):
        conf = self._conf()
        apps = []
        for key, spec in APPS.items():
            cmd = self._bin(spec)
            apps.append({
                "key": key,
                "name": spec["name"],
                "icon": spec.get("icon", "globe"),
                "color": spec.get("color", "#4aa8ff"),
                "installed": bool(cmd),
                "running": self._running(spec) if cmd else False,
                "apt": spec.get("apt"),
                "flatpak": spec.get("flatpak"),
            })
        return {
            "enabled": bool(conf.get("enabled", True)),
            "allowed": os.environ.get("CARDASH_ALLOW_NATIVE") == "1",
            "display": self._display_env().get("DISPLAY"),
            "apps": apps,
        }

    # ------------------------------------------------------------------ acoes
    def _uri(self, key, lat=None, lon=None, query=None):
        if key != "gnome-maps":
            return None
        if lat is not None and lon is not None:
            try:
                return f"geo:{float(lat):.6f},{float(lon):.6f}"
            except (TypeError, ValueError):
                return None
        q = str(query or "").strip()
        if not q:
            return None
        m = COORD_RE.match(q)
        if m:
            return f"geo:{float(m.group(1)):.6f},{float(m.group(2)):.6f}"
        return "maps:q=" + quote(q)

    def launch(self, key, lat=None, lon=None, query=None):
        key = (key or "gnome-maps").strip()
        spec = APPS.get(key)
        if not spec:
            return None, f"aplicativo nativo desconhecido: {key}"
        if not bool(self._conf().get("enabled", True)):
            return None, "apps nativos desabilitados (Ajustes > native.enabled)"
        if os.environ.get("CARDASH_ALLOW_NATIVE") != "1":
            return None, "recurso desabilitado (defina CARDASH_ALLOW_NATIVE=1)"
        cmd = self._bin(spec)
        if not cmd:
            hint = f"sudo apt install {spec.get('apt')}" if spec.get("apt") else "instale o app"
            return None, f"{spec['name']} nao instalado ({hint})"
        uri = self._uri(key, lat, lon, query)
        if uri:
            cmd = cmd + [uri]
        try:
            subprocess.Popen(
                cmd, env=self._display_env(),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"falha ao abrir {spec['name']}: {exc}"
        return {
            "ok": True, "app": key, "name": spec["name"],
            "uri": uri, "command": " ".join(shlex.quote(c) for c in cmd),
        }, None

    def close(self, key):
        spec = APPS.get((key or "gnome-maps").strip())
        if not spec:
            return None, "aplicativo nativo desconhecido"
        if os.environ.get("CARDASH_ALLOW_NATIVE") != "1":
            return None, "recurso desabilitado (defina CARDASH_ALLOW_NATIVE=1)"
        try:
            subprocess.run(["pkill", "-x", spec["bin"]], timeout=4)
        except (OSError, subprocess.SubprocessError):
            pass
        if spec.get("flatpak") and shutil.which("flatpak"):
            try:
                subprocess.run(["flatpak", "kill", spec["flatpak"]], timeout=6)
            except (OSError, subprocess.SubprocessError):
                pass
        return {"ok": True, "app": key}, None
