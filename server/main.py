import contextlib
import json
import mimetypes
import os
import re
import signal
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config as config_mod
from .config import EDITABLE, cfg, validate_setting
from .hub import Hub
from .store import DEFAULT_APPS, Store
from .ws import WSConn, accept_key

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = (ROOT / "ui").resolve()

store = Store(cfg["paths"]["db"])

if (cfg.get("apps") or {}).get("seed_defaults", True):
    store.seed_apps(DEFAULT_APPS)

for key, value in store.get_settings().items():
    try:
        value = validate_setting(key, value)
    except (KeyError, ValueError, TypeError):
        continue
    config_mod._set(cfg, key, value)

hub = Hub(cfg, store)

CLIENTS: set = set()
STOP = threading.Event()
START_TIME = time.time()
MAX_BODY = 64 * 1024
APP_KINDS = {"nav", "embed", "browser", "web"}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:24] or "app"


def _clean_app(payload):
    if not isinstance(payload, dict):
        return None, "payload invalido"
    name = str(payload.get("name") or "").strip()[:40]
    url = str(payload.get("url") or "").strip()[:512]
    if not name:
        return None, "nome obrigatorio"
    if not url:
        return None, "url obrigatoria"
    kind = payload.get("kind") or "web"
    if kind not in APP_KINDS:
        kind = "web"
    app_id = str(payload.get("id") or "").strip()[:40]
    if not app_id:
        app_id = _slug(name)
        if store.app(app_id):
            app_id = f"{app_id}-{uuid.uuid4().hex[:4]}"
    try:
        sort = int(payload.get("sort") or 0)
    except (TypeError, ValueError):
        sort = 0
    return {
        "id": app_id,
        "name": name,
        "url": url,
        "icon": str(payload.get("icon") or "globe")[:24],
        "color": str(payload.get("color") or "#4aa8ff")[:16],
        "kind": kind,
        "sort": sort,
    }, None


def log(msg):
    if os.environ.get("CARDASH_LOG") not in ("0", "quiet"):
        print(f"[cardash] {msg}", flush=True)


def ticker():
    period = 1.0 / max(1.0, float(cfg["rates"].get("broadcast_hz", 10)))
    while not STOP.is_set():
        try:
            snap = hub.tick()
            payload = json.dumps({"type": "state", "data": snap}, default=str)
        except Exception as exc:
            log(f"tick error: {exc}")
            STOP.wait(period)
            continue
        for conn in list(CLIENTS):
            try:
                conn.send_text(payload)
            except Exception:
                CLIENTS.discard(conn)
        STOP.wait(period)


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenDash/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("CARDASH_LOG") == "1":
            super().log_message(fmt, *args)

    def _json(self, obj, code=200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, text):
        body = json.dumps({"error": text}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _static(self, path):
        if path in ("/", "/index.html"):
            path = "/index.html"
        target = (UI_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(UI_DIR)) or not target.is_file():
            self._error(404, "not found")
            return
        data = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in (
            "application/javascript", "application/json",
        ):
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _settings(self):
        values = {}
        for key, _ in EDITABLE:
            values[key] = config_mod._get(cfg, key)
        return {"settings": values, "path": str(config_mod.CONFIG_PATH)}

    def _save_settings(self, payload):
        values = payload.get("settings") if isinstance(payload, dict) and "settings" in payload else payload
        clean = {}
        for key, value in (values or {}).items():
            try:
                clean[key] = validate_setting(key, value)
            except KeyError:
                return None, f"chave desconhecida: {key}"
            except (ValueError, TypeError) as exc:
                return None, f"valor invalido para {key}"
        if not clean:
            return None, "nada para salvar"
        store.set_settings(clean)
        hub.apply_settings(clean)
        for key, value in clean.items():
            config_mod._set(cfg, key, value)
        return {"ok": True, "settings": clean}, None

    def _power(self, payload):
        if os.environ.get("CARDASH_ALLOW_POWER") != "1":
            return None, "power desabilitado (defina CARDASH_ALLOW_POWER=1)"
        action = (payload or {}).get("action")
        cmd = {"reboot": ["systemctl", "reboot"], "shutdown": ["systemctl", "poweroff"]}.get(action)
        if not cmd:
            return None, "action invalido"
        try:
            import subprocess
            subprocess.Popen(["sudo"] + cmd)
        except Exception:
            return None, "falha ao executar comando"
        return {"ok": True}, None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/ws":
            self._websocket()
            return
        if path == "/api/state":
            return self._json(hub.snapshot())
        if path == "/api/history":
            minutes = int((parse_qs(parsed.query).get("minutes") or ["15"])[0])
            return self._json(store.history(max(1, min(1440, minutes))))
        if path == "/api/trips":
            limit = int((parse_qs(parsed.query).get("limit") or ["20"])[0])
            return self._json({"trips": store.trips(max(1, min(200, limit)))})
        if path == "/api/dtc":
            return self._json({"dtc": store.dtcs(), "mil": hub.snapshot().get("mil", 0)})
        if path == "/api/apps":
            return self._json({
                "apps": store.apps(),
                "maps": {
                    "provider": config_mod._get(cfg, "maps.provider"),
                    "tile_url": config_mod._get(cfg, "maps.tile_url"),
                    "google_key": config_mod._get(cfg, "maps.google_key"),
                    "zoom": config_mod._get(cfg, "maps.zoom"),
                },
            })
        if path == "/api/gps/track":
            minutes = int((parse_qs(parsed.query).get("minutes") or ["180"])[0])
            minutes = max(1, min(1440, minutes))
            return self._json({"track": store.track(minutes)})
        if path == "/api/settings":
            return self._json(self._settings())
        if path == "/api/system":
            snap = hub.snapshot()
            mode = snap.get("mode") or {}
            return self._json({
                "uptime_s": int(time.time() - START_TIME),
                "python": sys.version.split()[0],
                "hostname": os.uname().nodename,
                "conn": snap.get("conn"),
                "port": mode.get("port"),
                "link": mode.get("link"),
                "sim": mode.get("sim"),
                "config": str(config_mod.CONFIG_PATH),
                "data_dir": cfg["paths"]["data_dir"],
                "clients": len(CLIENTS),
            })
        if path == "/health":
            return self._json({"ok": True, "ts": int(time.time())})
        if path.startswith("/api/"):
            return self._error(404, "rota desconhecida")
        return self._static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self._body()
        if path == "/api/settings":
            result, err = self._save_settings(payload)
            if err:
                return self._error(400, err)
            return self._json(result)
        if path in ("/api/command", "/api/command/"):
            return self._json(hub.command(payload))
        if path == "/api/apps":
            app, err = _clean_app(payload)
            if err:
                return self._error(400, err)
            store.add_app(app)
            return self._json({"ok": True, "app": store.app(app["id"])})
        if path == "/api/dtc/clear":
            return self._json(hub.command({"cmd": "dtc_clear"}))
        if path == "/api/system/power":
            result, err = self._power(payload)
            if err:
                return self._error(403, err)
            return self._json(result)
        if path == "/api/trips":
            return self._json({"trips": store.trips(20)})
        if path.startswith("/api/"):
            return self._error(404, "rota desconhecida")
        self._error(404, "not found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        prefix = "/api/apps/"
        if path.startswith(prefix):
            app_id = unquote(path[len(prefix):]).strip()
            if not app_id:
                return self._error(400, "id obrigatorio")
            ok = store.delete_app(app_id)
            return self._json({"ok": ok, "id": app_id})
        self._error(404, "not found")

    def _websocket(self):
        key = self.headers.get("Sec-WebSocket-Key")
        upgrade = (self.headers.get("Upgrade") or "").lower()
        if not key or upgrade != "websocket":
            return self._error(400, "websocket esperado")
        accept = accept_key(key)
        self.close_connection = True
        self.wfile.write(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: " + accept.encode("ascii") + b"\r\n\r\n"
        )
        conn = WSConn(self.rfile, self.wfile, self.client_address)
        CLIENTS.add(conn)
        try:
            snap = hub.snapshot()
            conn.send_text(json.dumps({"type": "state", "data": snap}, default=str))
            while True:
                text = conn.recv()
                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if "cmd" in msg or msg.get("type") in ("cmd", "command"):
                    result = hub.command(msg)
                    conn.send_text(json.dumps({"type": "reply", "data": result}, default=str))
        except Exception:
            pass
        finally:
            CLIENTS.discard(conn)
            with contextlib.suppress(Exception):
                conn.close()


def main():
    host = cfg["server"]["host"]
    port = int(cfg["server"]["port"])
    hub.start()
    threading.Thread(target=ticker, daemon=True, name="ticker").start()

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True

    def shutdown(signum, _frame):
        log(f"encerrando (sinal {signum})")
        STOP.set()
        hub.shutdown()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log(f"OpenDash em http://{host}:{port}  (ctrl+c encerra)")
    log(f"config: {config_mod.CONFIG_PATH}")
    mode = "simulacao" if hub.force_sim else "serial+sim"
    log(f"modo inicial: {mode}")
    try:
        server.serve_forever(poll_interval=0.4)
    finally:
        STOP.set()
        hub.shutdown()
        server.server_close()
        log("servidor parado")


if __name__ == "__main__":
    main()
