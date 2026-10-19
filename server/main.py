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
from .agent import Agent
from .camera import Camera
from .config import EDITABLE, cfg, validate_setting
from .display import Display
from .hub import Hub
from .native import Native
from .net import Net
from .screens import Screens
from .store import BUILTIN_APP_IDS, DEFAULT_APPS, Store
from .traffic import Traffic
from .updater import Updater
from .wallpaper import Wallpaper
from .ws import WSConn, accept_key

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = (ROOT / "ui").resolve()

store = Store(cfg["paths"]["db"])

if (cfg.get("apps") or {}).get("seed_defaults", True):
    store.seed_apps(DEFAULT_APPS)
    store.ensure_apps([a for a in DEFAULT_APPS if a["id"] in BUILTIN_APP_IDS])
    store.migrate_legacy_apps(DEFAULT_APPS)

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
MAX_WALLPAPER = 12 * 1024 * 1024
APP_KINDS = {"nav", "embed", "browser", "web", "native"}


def broadcast(obj):
    payload = json.dumps(obj, default=str)
    for conn in list(CLIENTS):
        try:
            conn.send_text(payload)
        except Exception:
            CLIENTS.discard(conn)


agent = Agent(cfg, hub, on_event=broadcast)
net = Net(cfg)
updater = Updater(cfg, ROOT)
screens = Screens(cfg)
wallpaper = Wallpaper(cfg)
native = Native(cfg)
display = Display(cfg)
camera = Camera(cfg, hub)
traffic = Traffic(cfg)


def auto_update_check():
    time.sleep(8)
    while not STOP.is_set():
        try:
            status = updater.check()
            if status.get("available_update"):
                log(f"atualizacao disponivel: {status.get('behind')} commit(s) - {status.get('latest')}")
                broadcast({"type": "update", "data": status})
        except Exception as exc:
            log(f"checagem de atualizacao falhou: {exc}")
        hours = float((cfg.get("update") or {}).get("check_hours", 6) or 6)
        STOP.wait(max(0.5, hours) * 3600)


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
        try:
            camera.sync(reverse=bool(snap.get("reverse")))
        except Exception as exc:
            log(f"camera sync error: {exc}")
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

    def _send_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self, max_bytes=MAX_BODY):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > max_bytes:
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

    def _persist(self, clean):
        store.set_settings(clean)
        for key, value in clean.items():
            config_mod._set(cfg, key, value)

    def _wallpaper(self, payload):
        payload = payload or {}
        try:
            if payload.get("clear"):
                value = wallpaper.clear()
            elif payload.get("data"):
                value = wallpaper.save_data(payload.get("data"))
            else:
                value = wallpaper.save_url(payload.get("url"))
        except ValueError as exc:
            return None, str(exc)
        self._persist({"media.wallpaper": value})
        return {"ok": True, "wallpaper": value, "fit": wallpaper.get()["fit"]}, None

    def _screens(self, payload):
        payload = payload or {}
        current = config_mod._get(cfg, "screens") or {}
        main = str(payload.get("main", current.get("main") or ""))[:64]
        bar = str(payload.get("bar", current.get("bar") or ""))[:64]
        arrange = bool(payload.get("arrange", current.get("arrange")))
        enabled = bool(payload.get("enabled", current.get("enabled")))
        result, err = screens.apply(main=main, bar=bar, arrange=arrange, enabled=enabled)
        if err:
            enabled = bool(current.get("enabled"))
        clean = {
            "screens.main": main,
            "screens.bar": bar,
            "screens.arrange": arrange,
            "screens.enabled": enabled,
        }
        self._persist(clean)
        if err:
            return None, err
        return {"ok": True, **result}, None

    def _native_launch(self, payload):
        payload = payload or {}
        app = payload.get("app") or config_mod._get(cfg, "native.maps_app") or "gnome-maps"
        result, err = native.launch(
            app,
            lat=payload.get("lat"),
            lon=payload.get("lon"),
            query=payload.get("query"),
        )
        if err:
            return self._error(400, err)
        return self._json(result)

    def _native_close(self, payload):
        payload = payload or {}
        result, err = native.close(payload.get("app"))
        if err:
            return self._error(400, err)
        return self._json(result)

    def _traffic_buses(self, parsed):
        qs = parse_qs(parsed.query)
        try:
            lat = float((qs.get("lat") or [""])[0])
            lon = float((qs.get("lon") or [""])[0])
        except ValueError:
            lat = lon = None
        try:
            radius = float((qs.get("radius") or qs.get("r") or ["0"])[0])
        except ValueError:
            radius = None
        if lat is None or lon is None:
            gps = (hub.snapshot() or {}).get("gps") or {}
            if gps.get("lat") is not None and gps.get("lon") is not None:
                try:
                    lat = float(gps.get("lat"))
                    lon = float(gps.get("lon"))
                except (TypeError, ValueError):
                    lat = lon = None
        if not traffic.enabled():
            return {"enabled": False, "hr": "", "updated": 0,
                    "count": 0, "vehicles": [], "status": traffic.status()}
        try:
            payload = traffic.buses(lat, lon, radius)
            payload["enabled"] = True
            return payload
        except Exception as exc:
            return {"enabled": True, "hr": "", "updated": 0, "count": 0,
                    "vehicles": [], "error": str(exc)[:200],
                    "status": traffic.status()}

    def _camera_action(self, payload):
        payload = payload or {}
        action = str(payload.get("action") or "status")
        if action == "start":
            camera.set_manual(True)
        elif action == "stop":
            if (config_mod._get(cfg, "camera.trigger") or "gear") == "manual":
                camera.set_manual(False)
            else:
                camera.stop()
        elif action == "toggle":
            if camera.active:
                if (config_mod._get(cfg, "camera.trigger") or "gear") == "manual":
                    camera.set_manual(False)
                else:
                    camera.stop()
            else:
                camera.set_manual(True)
        elif action != "status":
            return self._error(400, "action invalida")
        return self._json(camera.status())

    def _camera_frame(self):
        frame, _ts = camera.latest()
        if not frame:
            return self._error(503, "sem quadro da câmera")
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(frame)

    def _camera_stream(self):
        self.close_connection = True
        boundary = "opendashframe"
        self.send_response(200)
        self.send_header("Content-Type",
                         f"multipart/x-mixed-replace; boundary={boundary}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for chunk in camera.mjpeg(timeout_s=3600):
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

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
                "traffic": traffic.status(),
            })
        if path == "/api/traffic":
            return self._json(self._traffic_buses(parsed))
        if path == "/api/traffic/lines":
            q = (parse_qs(parsed.query).get("q") or [""])[0]
            try:
                return self._json(traffic.lines(q))
            except Exception as exc:
                return self._json({"lines": [], "error": str(exc)[:200]})
        if path == "/api/traffic/line":
            cl = (parse_qs(parsed.query).get("codigoLinha") or [""])[0]
            try:
                return self._json(traffic.line_vehicles(cl))
            except Exception as exc:
                return self._json({"vehicles": [], "error": str(exc)[:200]})
        if path == "/api/gps/track":
            minutes = int((parse_qs(parsed.query).get("minutes") or ["180"])[0])
            minutes = max(1, min(1440, minutes))
            return self._json({"track": store.track(minutes)})
        if path == "/api/agent":
            return self._json(agent.status())
        if path == "/api/network":
            return self._json(net.status())
        if path == "/api/wifi":
            scan = (parse_qs(parsed.query).get("scan") or ["0"])[0] in ("1", "true", "yes")
            return self._json(net.wifi_scan(rescan=scan) if scan else net.wifi_status())
        if path == "/api/bluetooth":
            return self._json(net.bt_devices())
        if path == "/api/update":
            return self._json(updater.status())
        if path == "/api/media":
            return self._json(wallpaper.get())
        if path == "/media/wallpaper":
            data, ctype = wallpaper.read()
            if not data:
                return self._error(404, "sem papel de parede")
            return self._send_bytes(data, ctype)
        if path == "/api/screens":
            return self._json(screens.status())
        if path == "/api/display":
            return self._json(display.status())
        if path == "/api/nav":
            return self._json(hub.nav_state())
        if path == "/api/camera":
            return self._json(camera.status())
        if path == "/camera/stream":
            return self._camera_stream()
        if path == "/camera/frame.jpg":
            return self._camera_frame()
        if path == "/api/native":
            return self._json(native.status())
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
        if path == "/api/media/wallpaper":
            result, err = self._wallpaper(self._body(MAX_WALLPAPER))
            if err:
                return self._error(400, err)
            return self._json(result)
        if path == "/api/screens":
            result, err = self._screens(self._body())
            if err:
                return self._error(400, err)
            return self._json(result)
        if path == "/api/native/launch":
            return self._native_launch(self._body())
        if path == "/api/native/close":
            return self._native_close(self._body())
        if path == "/api/camera":
            return self._camera_action(self._body())
        if path == "/api/nav":
            return self._json(hub.set_nav(self._body()))
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
        if path == "/api/agent/ask":
            return self._json(agent.run_ask(payload.get("text")))
        if path == "/api/agent/listen/start":
            return self._json(agent.start_listen())
        if path == "/api/agent/listen/stop":
            threading.Thread(target=agent.listen_finish, daemon=True).start()
            return self._json({"ok": True, "pending": True})
        if path == "/api/agent/say":
            return self._json({"ok": True, "audio": agent.tts_b64(payload.get("text"))})
        if path == "/api/wifi":
            return self._json(net.wifi_action(payload.get("action"),
                                              payload.get("ssid"), payload.get("password")))
        if path == "/api/bluetooth":
            return self._json(net.bt_action(payload.get("action"), payload.get("mac")))
        if path == "/api/update":
            action = payload.get("action")
            if action == "check":
                return self._json(updater.check())
            if action == "install":
                return self._json(updater.install(restart=bool(payload.get("restart"))))
            if action == "restart":
                return self._json(updater.restart())
            return self._error(400, "acao invalida")
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
            if app_id in BUILTIN_APP_IDS:
                return self._error(400, "app do sistema nao pode ser removido")
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
    if (cfg.get("update") or {}).get("auto_check", True):
        threading.Thread(target=auto_update_check, daemon=True, name="updater").start()

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True

    def shutdown(signum, _frame):
        log(f"encerrando (sinal {signum})")
        STOP.set()
        hub.shutdown()
        camera.shutdown()
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
        camera.shutdown()
        server.server_close()
        log("servidor parado")


if __name__ == "__main__":
    main()
