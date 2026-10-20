import json
import os
import threading
import time
from pathlib import Path

try:
    import serial

    HAVE_SERIAL = True
except ImportError:
    serial = None
    HAVE_SERIAL = False

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

from .alerts import AlertEngine
from .gps import GpsReader, GpsState
from .sim import Simulator


class SerialLink(threading.Thread):
    def __init__(self, cfg, on_line, on_status):
        super().__init__(daemon=True, name="obd-serial")
        self.cfg = cfg
        self.on_line = on_line
        self.on_status = on_status
        self._write_lock = threading.Lock()
        self._dev = None
        self._port = None
        self._stop = threading.Event()
        self.port_name = None

    def _candidates(self):
        if self.cfg.get("port"):
            yield self.cfg["port"]
        if self.cfg.get("auto_detect") and list_ports is not None:
            seen = set()
            for p in list_ports.comports():
                if p.device not in seen:
                    seen.add(p.device)
                    yield p.device
            for p in self.cfg.get("candidates") or []:
                if p not in seen:
                    yield p

    def _open(self):
        if serial is None:
            return None
        baud = int(self.cfg.get("baud", 115200))
        for cand in self._candidates():
            if self._stop.is_set():
                return None
            if not os.path.exists(cand):
                continue
            try:
                dev = serial.Serial(cand, baud, timeout=0.4, write_timeout=0.4)
                time.sleep(0.4)
                dev.reset_input_buffer()
                self.port_name = cand
                self.attach(dev)
                self.on_status("open", cand)
                return dev
            except (serial.SerialException, OSError):
                continue
        return None

    def run(self):
        while not self._stop.is_set():
            dev = self._open()
            if dev is None:
                self.on_status("down", None)
                self._stop.wait(float(self.cfg.get("reconnect_s", 2.0)))
                continue
            buf = b""
            while not self._stop.is_set():
                try:
                    chunk = dev.read(256)
                except (serial.SerialException, OSError):
                    break
                if chunk:
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip().replace(b"\r", b"")
                        if not line or len(line) > 900:
                            continue
                        try:
                            obj = json.loads(line.decode("utf-8", "ignore"))
                        except json.JSONDecodeError:
                            continue
                        if isinstance(obj, dict) and "speed" in obj:
                            self.on_line(obj)
                elif buf and len(buf) > 900:
                    buf = b""
            try:
                dev.close()
            except Exception:
                pass
            self.attach(None)
            self.port_name = None
            self.on_status("down", None)
            self._stop.wait(float(self.cfg.get("reconnect_s", 2.0)))

    def write(self, obj: dict):
        if not self._port_ok():
            return False
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self._write_lock:
            dev = getattr(self, "_dev", None)
            if dev is None:
                return False
            try:
                dev.write(data)
                dev.flush()
                return True
            except (serial.SerialException, OSError, TypeError):
                return False

    def _port_ok(self):
        return getattr(self, "_dev", None) is not None

    def attach(self, dev):
        self._dev = dev

    def stop(self):
        self._stop.set()


class Hub:
    def __init__(self, cfg, store):
        self.cfg = cfg
        self.store = store
        self.lock = threading.RLock()
        self.sim = Simulator()
        self.raw = None
        self.last_rx = 0.0
        self.conn = "off"
        self.link = None
        self.link_status = ("down", None)
        self.force_sim = bool(cfg["simulation"].get("enabled"))
        self.tr = cfg["thresholds"]
        self.trip_cap = float(cfg["trip"]["fuel_capacity_l"])
        self.trip_cons = float(cfg["trip"]["consumption_l100"])
        self.engine = AlertEngine(self.tr, self.trip_cap, self.trip_cons)
        self.trip = None
        self.trip_start_wall = None
        self.odo_base = float(cfg["trip"]["odometer_km"])
        self.session_km = 0.0
        self._last_fuel = None
        self._last_tick = time.monotonic()
        self._last_log = 0.0
        self._prev_ign = None
        self.climate = {"fan": 0, "ac": 0}
        self.gps_state = GpsState()
        self.gps_reader = None
        self._last_track = 0.0
        self.radio = {
            "power": False, "available": False, "freq": 89.1, "freq_khz": 89100,
            "stereo": False, "rssi": 0, "tuned": False, "seeking": False,
            "muted": False, "mono": False, "ps": "", "rt": "", "pi": "",
            "station": "FM 89.1",
        }
        self.state = self._blank()
        self.nav = {"dest": None, "route": [], "active": False, "updated": 0}

    def start(self):
        self._start_gps()
        if not HAVE_SERIAL:
            print("[cardash] pyserial ausente: use o modo simulação ou "
                  "instale pyserial (pip install pyserial)")
            return
        if self.cfg["serial"].get("enabled") and not self._serial_disabled():
            self.link = SerialLink(self.cfg["serial"], self._on_line, self._on_status)
            self.link.start()

    def _start_gps(self):
        gps = self.cfg.get("gps") or {}
        if not gps.get("enabled", True) or gps.get("source") == "off":
            return
        if gps.get("source") in ("auto", "usb") and HAVE_SERIAL:
            self.gps_reader = GpsReader(gps, self.gps_state)
            self.gps_reader.start()

    def _serial_disabled(self):
        s = self.store.get_settings().get("serial.enabled")
        return s is False

    def shutdown(self):
        if self.link:
            self.link.stop()
        if self.gps_reader:
            self.gps_reader.stop()

    def _on_status(self, st, port):
        self.link_status = (st, port)

    def _on_line(self, obj):
        with self.lock:
            self.raw = obj
            self.last_rx = time.monotonic()

    def _blank(self):
        return {
            "conn": "off",
            "ts": int(time.time() * 1000),
            "age_ms": 0,
            "board": None, "adc": None,
            "speed": 0, "rpm": 0, "coolant": 20, "iat": 20, "oilt": 20,
            "throttle": 0, "fuel": 50, "volt": 12.4, "oilp": 0.0, "batt": 12.4,
            "load": 0, "runtime": 0, "mil": 0, "obd": 0, "dtc_count": 0,
            "dtc": [],
            "lt": 0, "rt": 0, "hl": 0, "hb": 0, "hz": 0, "brk": 0,
            "sbl": 0, "door": 0, "ign": 0, "fan": 0, "ac": 0,
            "gear": "P", "rev": 0, "reverse": False, "range": 0.0, "odo": self.odo_base,
            "trip": {"km": 0.0, "s": 0.0, "avg": 0.0, "max": 0.0,
                     "fuel_l": 0.0, "cons": 0.0},
            "gps": self._blank_gps(),
            "alerts": [],
            "car": self.cfg["car"],
            "units": self.cfg["units"],
            "mode": {"sim": self.force_sim, "port": None, "gps": None,
                     "gps_src": "none"},
            "nav": {"active": False, "dest": None, "route_n": 0, "updated": 0},
            "radio": dict(self.radio),
        }

    @staticmethod
    def _blank_gps():
        return {"fix": 0, "lat": None, "lon": None, "alt": None, "sats": 0,
                "hdop": None, "speed": None, "heading": None, "utc": None,
                "age_ms": None, "has": False, "src": "none"}

    def _source(self, now_mono: float):
        age = now_mono - self.last_rx
        serial_alive = self.link is not None and age < 3.0
        if self.force_sim:
            return "sim", None
        if self.link is None:
            if not HAVE_SERIAL or not self.cfg["serial"].get("enabled"):
                return "sim", None
        if serial_alive:
            return "serial", age
        if self.raw is not None:
            return "off", age
        return "off", None

    def tick(self, now=None):
        now_mono = time.monotonic()
        dt = max(0.001, min(1.0, now_mono - self._last_tick))
        self._last_tick = now_mono
        with self.lock:
            conn, age = self._source(now_mono)
            if conn == "sim":
                raw = self.sim.tick(dt)
            elif conn == "serial":
                raw = self.raw
            else:
                raw = self.raw if self.raw is not None else self.sim.tick(0.0)
            if raw is None:
                raw = self._blank()

            ts = int(time.time() * 1000)
            st = dict(raw)
            st["conn"] = conn
            st["ts"] = ts
            st["age_ms"] = int(age * 1000) if age is not None else 0
            st["dtc"] = list(raw.get("dtc") or [])
            st["dtc_count"] = raw.get("dtc_count", len(st["dtc"]))
            st["fan"] = int(raw.get("fan", self.climate["fan"]))
            st["ac"] = int(raw.get("ac", self.climate["ac"]))
            ign = int(raw.get("ign", 0))

            self._trip_update(st, dt, ign)
            st["odo"] = round(self.odo_base + self.session_km, 1)
            rev = self._reverse(raw)
            st["gear"] = "R" if rev else self._gear(st, ign)
            st["rev"] = 1 if rev else 0
            st["reverse"] = rev
            st["range"] = self._range(st)
            st["trip"] = dict(self.trip) if self.trip else self._blank_trip()
            gps = self._merge_gps(raw, conn)
            st["gps"] = gps

            st["alerts"] = self.engine.update(st)
            st["car"] = self.cfg["car"]
            st["units"] = self.cfg["units"]
            st["mode"] = {
                "sim": self.force_sim,
                "port": self.link.port_name if self.link else None,
                "link": self.link_status[0] if self.link else None,
                "gps": self.gps_reader.port_name if self.gps_reader else None,
                "gps_src": gps.get("src", "none"),
            }
            st["climate"] = {"fan": st["fan"], "ac": st["ac"]}
            st["nav"] = self._nav_summary()
            st["radio"] = dict(self.radio)
            self.state = st
            self._maybe_track(gps, ts)

            if time.monotonic() - self._last_log >= 1.0 / float(self.cfg["rates"].get("log_hz", 1)):
                self._last_log = time.monotonic()
                if conn != "off":
                    self.store.log_sample(
                        ts, float(st["speed"]), float(st["rpm"]),
                        float(st["coolant"]), float(st["fuel"]),
                        float(st["trip"]["km"]),
                    )
                    self.store.sync_dtc(st["dtc"], ts)
            return st

    def _arduino_gps(self, raw, conn):
        if raw is None:
            return None
        lat, lon = raw.get("lat"), raw.get("lon")
        if lat is None or lon is None:
            return None
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return None
        fix = 1 if int(raw.get("fix") or 0) else 0
        return {
            "fix": fix,
            "lat": lat,
            "lon": lon,
            "alt": raw.get("alt"),
            "sats": int(raw.get("sats") or 0),
            "hdop": raw.get("hdop"),
            "speed": raw.get("gspd"),
            "heading": raw.get("hdg"),
            "utc": raw.get("utc"),
            "age_ms": None,
            "has": bool(fix),
            "src": "sim" if conn == "sim" else "arduino",
        }

    def _merge_gps(self, raw, conn):
        gps_cfg = self.cfg.get("gps") or {}
        if not gps_cfg.get("enabled", True) or gps_cfg.get("source") == "off":
            return self._blank_gps()
        pref = gps_cfg.get("source", "auto")

        arduino = self._arduino_gps(raw, conn)
        usb = None
        if self.gps_reader is not None and pref in ("auto", "usb"):
            snap = self.gps_state.snapshot()
            if snap.get("has"):
                snap["src"] = "usb"
                snap["age_ms"] = snap.get("age_ms")
                usb = snap

        order = {
            "arduino": [arduino],
            "usb": [usb],
        }.get(pref)
        if order is None:
            order = [arduino, usb] if conn == "sim" else [usb, arduino]

        for cand in order:
            if cand:
                return cand
        return self._blank_gps()

    def _maybe_track(self, gps, ts):
        if not gps or not gps.get("has") or gps.get("lat") is None:
            return
        now = time.monotonic()
        if now - self._last_track < 1.0:
            return
        self._last_track = now
        self.store.log_track(
            ts, float(gps["lat"]), float(gps["lon"]),
            float(gps.get("speed") or 0.0),
            float(gps.get("heading") or 0.0),
        )

    def _blank_trip(self):
        return {"km": 0.0, "s": 0.0, "avg": 0.0, "max": 0.0, "fuel_l": 0.0,
                "cons": 0.0, "start_ts": 0}

    def _trip_update(self, st, dt, ign):
        speed = float(st.get("speed") or 0)
        fuel = st.get("fuel")
        now_ms = st["ts"]

        if ign and self.trip is None:
            self.trip = dict(self._blank_trip())
            self.trip["start_ts"] = now_ms
            self.trip_start_wall = now_ms
            self._last_fuel = fuel

        if not ign and self.trip is not None:
            if self.trip["km"] > 0.05:
                self.store.save_trip(self.trip)
            self.odo_base = round(self.odo_base + self.trip["km"], 3)
            self.store.set_settings({"trip.odometer_km": self.odo_base})
            self.trip = None
            self._last_fuel = None
            self.session_km = 0.0
            return

        if self.trip is None:
            return

        dist = speed * dt / 3600.0
        self.trip["km"] += dist
        self.session_km += dist
        self.trip["s"] += dt
        if speed > self.trip["max"]:
            self.trip["max"] = speed
        hours = self.trip["s"] / 3600.0
        self.trip["avg"] = self.trip["km"] / hours if hours > 0.05 else 0.0

        if fuel is not None and self._last_fuel is not None:
            if fuel < self._last_fuel - 0.01:
                used = (self._last_fuel - fuel) / 100.0 * self.trip_cap
                self.trip["fuel_l"] += max(0.0, used)
            elif fuel > self._last_fuel + 2:
                pass
            self._last_fuel = fuel
        if self.trip["km"] > 0.2:
            self.trip["cons"] = self.trip["fuel_l"] / self.trip["km"] * 100.0

    @staticmethod
    def _gear(st, ign):
        if not ign:
            return "P"
        speed = st.get("speed") or 0
        if speed < 1:
            return "P" if st.get("brk") else "N"
        if st.get("throttle", 0) > 55 and speed > 40:
            return "S"
        return "D"

    @staticmethod
    def _reverse(raw):
        """Marcha à ré: campo 'rev' do Arduino ou alavanca 'gear' = R."""
        if not isinstance(raw, dict):
            return False
        lever = str(raw.get("gear") or raw.get("shifter") or "").strip().upper()
        val = raw.get("rev", 0)
        if isinstance(val, str):
            rev = val.strip().lower() in ("1", "true", "r", "on", "yes")
        else:
            try:
                rev = bool(int(val))
            except (TypeError, ValueError):
                rev = bool(val)
        return rev or lever == "R"

    def _range(self, st):
        fuel = float(st.get("fuel") or 0)
        cons = float(self.trip_cons or 8.5)
        km = (fuel / 100.0) * self.trip_cap / (cons / 100.0)
        trip_cons = (self.trip or {}).get("cons") or 0
        if trip_cons and self.trip and self.trip["km"] > 2:
            km = (fuel / 100.0) * self.trip_cap / (trip_cons / 100.0)
        return round(km, 1)

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.state))

    def _nav_summary(self):
        n = self.nav
        dest = n.get("dest")
        return {
            "active": bool(n.get("active")),
            "dest": dict(dest) if dest else None,
            "route_n": len(n.get("route") or []),
            "updated": n.get("updated", 0),
        }

    def nav_state(self):
        with self.lock:
            return json.loads(json.dumps(self.nav))

    def set_nav(self, obj):
        """Recebe o destino/rota traçados na Navegação (painel principal)."""
        with self.lock:
            now = int(time.time() * 1000)
            if obj.get("clear"):
                self.nav = {"dest": None, "route": [], "active": False, "updated": now}
            else:
                dest = obj.get("dest")
                if dest is not None:
                    try:
                        self.nav["dest"] = {
                            "lat": float(dest["lat"]),
                            "lon": float(dest["lon"]),
                            "name": str(dest.get("name") or "")[:200],
                        }
                    except (KeyError, TypeError, ValueError):
                        self.nav["dest"] = None
                route = obj.get("route")
                if route is not None:
                    pts = []
                    for p in route:
                        try:
                            pts.append([float(p[0]), float(p[1])])
                        except (IndexError, TypeError, ValueError):
                            continue
                    self.nav["route"] = pts
                self.nav["active"] = bool(self.nav["dest"])
                self.nav["updated"] = now
            if self.state is not None:
                self.state["nav"] = self._nav_summary()
            return {"ok": True, "active": bool(self.nav["active"]),
                    "route_n": len(self.nav["route"]), "updated": self.nav["updated"]}

    def set_radio(self, obj):
        """Estado do radio FM (Si4703) publicado pelo driver em background."""
        with self.lock:
            self.radio = dict(obj)
            if self.state is not None:
                self.state["radio"] = dict(self.radio)

    def command(self, obj: dict):
        if not isinstance(obj, dict):
            return {"ok": False, "error": "payload"}
        cmd = obj.get("cmd") or obj.get("type")
        with self.lock:
            if cmd == "ack":
                return {"ok": self.engine.ack(str(obj.get("id", "")))}
            if cmd == "ack_all":
                self.engine.ack_all()
                return {"ok": True}
            if cmd == "climate":
                fan = int(obj.get("fan", self.climate["fan"]))
                ac = int(obj.get("ac", self.climate["ac"]))
                self.climate = {"fan": max(0, min(4, fan)), "ac": 1 if ac else 0}
                self._forward({"cmd": "climate", **self.climate})
                if self.state:
                    self.state["fan"] = self.climate["fan"]
                    self.state["ac"] = self.climate["ac"]
                return {"ok": True, "climate": dict(self.climate)}
            if cmd == "beep":
                ms = int(obj.get("ms", 250))
                return {"ok": self._forward({"cmd": "beep", "ms": ms})}
            if cmd == "dtc_read":
                return {"ok": self._forward({"cmd": "dtc_read"})}
            if cmd == "dtc_clear":
                self.store.clear_dtcs(int(time.time() * 1000))
                if self.force_sim:
                    self.sim.dtc.clear()
                    self.sim.mil = 0
                    self.sim.injected = 0
                return {"ok": self._forward({"cmd": "dtc_clear"})}
            if cmd == "sim_dtc":
                if self.force_sim or self.link is None:
                    return {"ok": True, "result": self.sim.inject_dtc(obj.get("code"))}
                return {"ok": False, "error": "modo serial"}
            if cmd == "reverse":
                on = bool(obj.get("on", obj.get("rev", 1)))
                if hasattr(self.sim, "set_reverse"):
                    self.sim.set_reverse(on)
                if self.state is not None:
                    self.state["reverse"] = on
                    self.state["rev"] = 1 if on else 0
                    if on:
                        self.state["gear"] = "R"
                return {"ok": True, "reverse": on}
            if cmd == "set_mode":
                mode = obj.get("mode")
                if mode not in ("sim", "auto"):
                    return {"ok": False, "error": "mode"}
                self.force_sim = mode == "sim"
                self.store.set_settings({"simulation.enabled": self.force_sim})
                return {"ok": True, "mode": "sim" if self.force_sim else "auto"}
            if cmd == "dtc_list":
                return {"ok": True, "dtc": self.store.dtcs()}
            if cmd == "nav":
                return self.set_nav(obj)
        return {"ok": False, "error": "comando desconhecido"}

    def _forward(self, obj: dict) -> bool:
        if self.link is None:
            return False
        return self.link.write(obj)

    def apply_settings(self, values: dict):
        with self.lock:
            if "trip.fuel_capacity_l" in values:
                self.trip_cap = float(values["trip.fuel_capacity_l"])
            if "trip.consumption_l100" in values:
                self.trip_cons = float(values["trip.consumption_l100"])
            if "trip.odometer_km" in values:
                self.odo_base = float(values["trip.odometer_km"])
                self.session_km = 0.0
            if "simulation.enabled" in values:
                self.force_sim = bool(values["simulation.enabled"])
            if "car.name" in values:
                self.cfg["car"]["name"] = values["car.name"]
            if any(k in values for k in ("gps.enabled", "gps.source", "gps.port")):
                self._restart_gps()

    def _restart_gps(self):
        if self.gps_reader:
            self.gps_reader.stop()
            self.gps_reader = None
        self._start_gps()
