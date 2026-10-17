import glob
import os
import shlex
import shutil
import subprocess
import threading
import time

SOI = b"\xff\xd8"  # inicio de JPEG
EOI = b"\xff\xd9"  # fim de JPEG
MAX_FRAME = 8 * 1024 * 1024


class Camera:
    """Câmera de ré: captura de vídeo e transmite MJPEG.

    Suporta webcam USB (V4L2/ffmpeg) e a câmera do Raspberry Pi
    (rpicam-vid / libcamera-vid). Cria um subprocesso que cospe JPEGs em
    sequência; uma thread separa os quadros e guarda o mais recente para o
    servidor HTTP reaproveitar em /camera/stream e /camera/frame.jpg.

    O disparo é configuravel: ao engatar a ré (marcha R), manual (botão) ou
    sempre ligada. Sem hardware, tudo degrada sem quebrar o servidor.
    """

    def __init__(self, cfg, hub=None):
        self.cfg = cfg
        self.hub = hub
        self.lock = threading.Lock()
        self.proc = None
        self.thread = None
        self.frame = None
        self.frame_ts = 0.0
        self.active = False
        self.manual = None  # None = automatico; True/False = forçado pelo usuário
        self.device = ""
        self.backend = ""
        self.last_error = ""

    # ------------------------------------------------------------------ config
    def _cfg(self):
        return self.cfg.get("camera") or {}

    @staticmethod
    def _rpicam_bin():
        for b in ("rpicam-vid", "libcamera-vid"):
            if shutil.which(b):
                return b
        return ""

    @staticmethod
    def _v4l2_devices():
        devs = []
        for path in glob.glob("/dev/video*"):
            tail = path.rsplit("video", 1)[-1]
            if tail.isdigit() and os.access(path, os.R_OK):
                devs.append((int(tail), path))
        devs.sort()
        return [p for _, p in devs]

    def _pick(self):
        """Escolhe backend e dispositivo conforme config/hardware."""
        c = self._cfg()
        backend = (c.get("backend") or "auto").lower()
        device = (c.get("device") or "auto").strip()
        v4l2 = self._v4l2_devices()
        rpicam = self._rpicam_bin()

        if backend == "auto":
            if device.startswith("/dev/"):
                backend = "v4l2"
            elif device in ("rpicam", "libcamera", rpicam) and rpicam:
                backend = "rpicam"
            elif v4l2:
                backend = "v4l2"
            elif rpicam:
                backend = "rpicam"
            else:
                backend = ""

        if backend == "v4l2":
            dev = device if device.startswith("/dev/") else (v4l2[0] if v4l2 else "")
            return ("v4l2", dev, "") if dev else ("", "", "nenhuma câmera /dev/video* encontrada")
        if backend == "rpicam":
            if not rpicam:
                return "", "", "rpicam-vid/libcamera-vid não encontrado"
            return "rpicam", rpicam, ""
        return "", "", "câmera não detectada"

    def detect(self):
        c = self._cfg()
        backend, dev, why = self._pick()
        return {
            "backend": backend,
            "device": dev,
            "rpicam": self._rpicam_bin(),
            "v4l2": self._v4l2_devices(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "available": bool(backend) and (backend != "v4l2" or bool(shutil.which("ffmpeg"))),
            "reason": why,
        }

    # ----------------------------------------------------------------- particao
    def _command(self):
        c = self._cfg()
        backend, dev, why = self._pick()
        if not backend:
            return None, backend, dev, why
        w = int(c.get("width") or 0)
        h = int(c.get("height") or 0)
        fps = int(c.get("fps") or 25)
        flips = []
        if c.get("flip_h"):
            flips.append("hflip")
        if c.get("flip_v"):
            flips.append("vflip")
        extra = shlex.split(c.get("extra_args") or "")

        if backend == "v4l2":
            if not shutil.which("ffmpeg"):
                return None, backend, dev, "ffmpeg não encontrado (instale ffmpeg)"
            cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "v4l2"]
            if w and h:
                cmd += ["-video_size", f"{w}x{h}"]
            if fps:
                cmd += ["-framerate", str(fps)]
            cmd += ["-i", dev]
            if flips:
                cmd += ["-vf", ",".join(flips)]
            cmd += ["-f", "mjpeg", "-q:v", "7", "-"] + extra
            return cmd, backend, dev, ""

        # rpicam-vid / libcamera-vid
        cmd = [dev, "-t", "0", "--codec", "mjpeg", "-n"]
        if w and h:
            cmd += ["--width", str(w), "--height", str(h)]
        if fps:
            cmd += ["--framerate", str(fps)]
        if c.get("flip_h"):
            cmd += ["--hflip"]
        if c.get("flip_v"):
            cmd += ["--vflip"]
        cmd += ["-o", "-"] + extra
        return cmd, backend, dev, ""

    def _reader(self, proc):
        buf = bytearray()
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                buf.extend(chunk)
                while True:
                    s = buf.find(SOI)
                    if s < 0:
                        if len(buf) > 2:
                            del buf[:-1]
                        break
                    e = buf.find(EOI, s + 2)
                    if e < 0:
                        if s > 0:
                            del buf[:s]
                        if len(buf) > MAX_FRAME:
                            del buf[:]
                        break
                    frame = bytes(buf[s:e + 2])
                    del buf[:e + 2]
                    with self.lock:
                        self.frame = frame
                        self.frame_ts = time.monotonic()
        except Exception as exc:  # noqa: BLE001 - queda da câmera não pode matar o servidor
            self.last_error = str(exc)
        finally:
            with self.lock:
                self.active = False
                if self.proc is proc:
                    self.proc = None

    # --------------------------------------------------------------- controle
    def start(self):
        with self.lock:
            if self.proc is not None and self.active:
                return True
        cmd, backend, dev, why = self._command()
        if not cmd:
            self.last_error = why or "câmera indisponível"
            return False
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, bufsize=0,
            )
        except (OSError, ValueError) as exc:
            self.last_error = f"falha ao iniciar câmera: {exc}"
            return False
        with self.lock:
            self.proc = proc
            self.backend = backend
            self.device = dev
            self.active = True
            self.frame = None
            self.frame_ts = 0.0
            self.last_error = ""
        self.thread = threading.Thread(target=self._reader, args=(proc,), daemon=True)
        self.thread.start()
        return True

    def stop(self):
        with self.lock:
            proc = self.proc
            self.proc = None
            self.active = False
            self.frame = None
            self.frame_ts = 0.0
        if proc is None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
        if proc.stdout:
            try:
                proc.stdout.close()
            except Exception:
                pass

    def toggle(self):
        if self.active:
            self.stop()
        else:
            self.start()

    def set_manual(self, on):
        self.manual = bool(on)
        if self.manual:
            self.start()
        else:
            self.stop()

    def sync(self, reverse=False):
        """Ajusta o estado conforme o disparo configurado e o sinal de ré."""
        c = self._cfg()
        if not c.get("enabled", True):
            if self.active:
                self.stop()
            return
        trigger = (c.get("trigger") or "gear").lower()
        if trigger == "off":
            want = False
        elif trigger == "always":
            want = True
        elif trigger == "manual":
            want = bool(self.manual)
        else:  # gear
            want = bool(reverse) or bool(self.manual)
        if want and not self.active:
            self.start()
        elif not want and self.active:
            self.stop()

    # ------------------------------------------------------------------ dados
    def latest(self):
        with self.lock:
            return self.frame, self.frame_ts

    def mjpeg(self, timeout_s=3600):
        """Gera o corpo multipart/x-mixed-replace com os quadros JPEG."""
        boundary = "opendashframe"
        last = 0.0
        deadline = time.monotonic() + timeout_s
        while not self.active and time.monotonic() < deadline:
            time.sleep(0.1)
        while time.monotonic() < deadline:
            frame, ts = self.latest()
            if frame and ts != last:
                last = ts
                head = (f"--{boundary}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(frame)}\r\n\r\n").encode("ascii")
                yield head + frame + b"\r\n"
            elif time.monotonic() > deadline:
                break
            else:
                time.sleep(0.03)

    def status(self, reverse=None):
        c = self._cfg()
        info = self.detect()
        if reverse is None and self.hub is not None:
            try:
                reverse = bool((self.hub.snapshot() or {}).get("reverse"))
            except Exception:
                reverse = False
        return {
            "enabled": bool(c.get("enabled", True)),
            "trigger": c.get("trigger") or "gear",
            "guidelines": bool(c.get("guidelines", True)),
            "flip_h": bool(c.get("flip_h")),
            "flip_v": bool(c.get("flip_v")),
            "width": int(c.get("width") or 0),
            "height": int(c.get("height") or 0),
            "fps": int(c.get("fps") or 25),
            "active": self.active,
            "manual": self.manual,
            "reverse": bool(reverse),
            "backend": self.backend or info["backend"],
            "device": self.device or info["device"],
            "available": info["available"],
            "rpicam": info["rpicam"],
            "v4l2": info["v4l2"][:12],
            "ffmpeg": info["ffmpeg"],
            "reason": info["reason"] if not info["available"] else "",
            "error": self.last_error,
            "stream": "/camera/stream",
            "frame": "/camera/frame.jpg",
        }

    def shutdown(self):
        self.stop()
