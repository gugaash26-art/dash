import os
import re
import shutil
import subprocess
from pathlib import Path

OUT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)\s+connected"
    r"(?P<rest>\s+primary)?"
    r"(?:\s+(?P<w>\d+)x(?P<h>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+))?",
    re.MULTILINE,
)
DIS_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)\s+disconnected", re.MULTILINE)


class Screens:
    """Detect X11 outputs (xrandr) and place the kiosk windows on the chosen
    monitors by writing data/screens.env, which the kiosk systemd units read."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.env_path = Path(cfg["paths"]["data_dir"]) / "screens.env"

    # ------------------------------------------------------------------ probe
    def _display_env(self):
        env = dict(os.environ)
        env["DISPLAY"] = str((self.cfg.get("screens") or {}).get("display") or ":0")
        if not env.get("XAUTHORITY"):
            for cand in (Path.home() / ".Xauthority", Path("/root/.Xauthority")):
                if cand.is_file():
                    env["XAUTHORITY"] = str(cand)
                    break
        return env

    def _run(self, args, timeout=6):
        return subprocess.run(
            args, capture_output=True, text=True,
            env=self._display_env(), timeout=timeout,
        )

    def probe(self):
        if not shutil.which("xrandr"):
            return [], {"available": False,
                        "reason": "xrandr nao encontrado (instale x11-xserver-utils)"}
        try:
            res = self._run(["xrandr", "--query"])
        except (OSError, subprocess.SubprocessError) as exc:
            return [], {"available": False, "reason": f"falha ao executar xrandr: {exc}"}
        if res.returncode != 0:
            reason = (res.stderr or res.stdout or "").strip().splitlines()
            return [], {"available": False,
                        "reason": reason[-1] if reason else "xrandr falhou (servidor X acessivel?)"}

        outputs = []
        for m in OUT_RE.finditer(res.stdout):
            w, h = m.group("w"), m.group("h")
            geom = None
            if w and h:
                geom = {"width": int(w), "height": int(h),
                        "x": int(m.group("x")), "y": int(m.group("y"))}
            outputs.append({
                "name": m.group("name"),
                "connected": True,
                "primary": bool(m.group("rest")),
                "geometry": geom,
                "resolution": f"{w}x{h}" if w and h else "—",
            })
        for m in DIS_RE.finditer(res.stdout):
            outputs.append({"name": m.group("name"), "connected": False,
                            "primary": False, "geometry": None, "resolution": "—"})
        outputs.sort(key=lambda o: (not o["connected"], not o["primary"], o["name"]))
        return outputs, {"available": True, "reason": ""}

    # ------------------------------------------------------------------ state
    def _assignment(self):
        sc = self.cfg.get("screens") or {}
        return {
            "enabled": bool(sc.get("enabled")),
            "main": sc.get("main") or "",
            "bar": sc.get("bar") or "",
            "arrange": bool(sc.get("arrange")),
        }

    def _kiosk_state(self):
        units = ["cardash-kiosk.service", "cardash-kiosk-bar.service",
                 "cardash-kiosk-cluster.service"]
        present = []
        if shutil.which("systemctl"):
            for unit in units:
                for base in ("/etc/systemd/system", "/lib/systemd/system",
                             "/usr/lib/systemd/system"):
                    if (Path(base) / unit).exists():
                        present.append(unit)
                        break
        return {"installed": bool(present), "units": present}

    def _read_env(self):
        values = {}
        if self.env_path.is_file():
            for line in self.env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
        return values

    def status(self):
        outputs, info = self.probe()
        return {
            "available": info["available"],
            "reason": info["reason"],
            "outputs": outputs,
            "assignment": self._assignment(),
            "kiosk": self._kiosk_state(),
            "env_file": str(self.env_path),
            "env": self._read_env(),
        }

    # ------------------------------------------------------------------ apply
    def apply(self, main="", bar="", arrange=False, enabled=None):
        if enabled is None:
            enabled = (self.cfg.get("screens") or {}).get("enabled", False)
        main = (main or "").strip()[:64]
        bar = (bar or "").strip()[:64]
        if main and main == bar:
            return None, "escolha monitores diferentes para o painel e o cluster"

        outputs, info = self.probe()
        if not info["available"]:
            return None, info["reason"]
        connected = {o["name"]: o for o in outputs if o["connected"]}
        for role, name in (("painel", main), ("cluster", bar)):
            if name and name not in connected:
                return None, f"monitor '{name}' nao esta conectado ({role})"

        messages = []
        if enabled and arrange and main and bar:
            try:
                res = self._run(["xrandr", "--output", bar, "--auto", "--right-of", main])
                if res.returncode == 0:
                    messages.append(f"layout: {bar} a direita de {main}")
                    outputs, info = self.probe()
                    connected = {o["name"]: o for o in outputs if o["connected"]}
                else:
                    messages.append("xrandr: nao foi possivel organizar automaticamente")
            except (OSError, subprocess.SubprocessError):
                messages.append("xrandr: falha ao organizar automaticamente")

        def geom(name):
            o = connected.get(name)
            return o["geometry"] if o else None

        lines = ["# gerado por OpenDash (Ajustes > Telas); lido pelo kiosk"]
        touch_size = touch_pos = bar_size = bar_pos = ""
        main_geom, bar_geom = geom(main), geom(bar)
        if main_geom:
            touch_size = f"{main_geom['width']},{main_geom['height']}"
            touch_pos = f"{main_geom['x']},{main_geom['y']}"
        if bar_geom:
            bar_size = f"{bar_geom['width']},{bar_geom['height']}"
            bar_pos = f"{bar_geom['x']},{bar_geom['y']}"
        for k, v in (("CARDASH_TOUCH_SIZE", touch_size), ("CARDASH_TOUCH_POS", touch_pos),
                     ("CARDASH_BAR_SIZE", bar_size), ("CARDASH_BAR_POS", bar_pos)):
            if v:
                lines.append(f"{k}={v}")
        lines.append(f"# painel={main or '(padrao)'} cluster={bar or '(padrao)'}")
        try:
            self.env_path.parent.mkdir(parents=True, exist_ok=True)
            self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            return None, f"falha ao gravar {self.env_path}: {exc}"
        messages.append(f"geometria gravada em {self.env_path.name}")

        restarted = False
        kiosk = self._kiosk_state()
        if enabled and kiosk["installed"]:
            try:
                res = self._run(["sudo", "systemctl", "restart", *kiosk["units"]],
                                timeout=20)
                restarted = res.returncode == 0
                messages.append("kiosk reiniciado" if restarted
                                else "nao foi possivel reiniciar o kiosk (sudo? systemd?)")
            except (OSError, subprocess.SubprocessError):
                messages.append("nao foi possivel reiniciar o kiosk")

        result = self.status()
        result["messages"] = messages
        result["restarted"] = restarted
        return result, None
