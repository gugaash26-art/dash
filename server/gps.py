import json
import os
import threading
import time

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


KNOTS_TO_KMH = 1.852


def _dm_to_deg(dm: str, hemi: str):
    if not dm:
        return None
    try:
        dot = dm.index(".")
        deg_len = dot - 2
        if deg_len < 1:
            deg_len = 1
        deg = float(dm[:deg_len])
        minutes = float(dm[deg_len:])
    except (ValueError, IndexError):
        return None
    val = deg + minutes / 60.0
    if hemi in ("S", "W"):
        val = -val
    return val


def _f(s, default=None):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def parse_nmea(line: str):
    if not isinstance(line, str):
        return None
    line = line.strip()
    if not line.startswith("$"):
        return None
    body = line[1:]
    if "*" in body:
        body = body.split("*", 1)[0]
    parts = body.split(",")
    if not parts:
        return None
    tag = parts[0]
    if tag.endswith(("RMC", "RMZ")):
        return _parse_rmc(parts)
    if tag.endswith("GGA"):
        return _parse_gga(parts)
    if tag.endswith("VTG"):
        return _parse_vtg(parts)
    if tag.endswith("GSA"):
        return _parse_gsa(parts)
    return None


def _parse_rmc(p):
    if len(p) < 10:
        return None
    status = p[2]
    out = {"utc": p[1], "fix": 1 if status == "A" else 0}
    lat = _dm_to_deg(p[3], p[4]) if p[3] else None
    lon = _dm_to_deg(p[5], p[6]) if p[5] else None
    if lat is not None:
        out["lat"] = lat
    if lon is not None:
        out["lon"] = lon
    spd = _f(p[7])
    if spd is not None:
        out["speed"] = round(spd * KNOTS_TO_KMH, 2)
    hdg = _f(p[8])
    if hdg is not None:
        out["heading"] = round(hdg, 1)
    return out


def _parse_gga(p):
    if len(p) < 10:
        return None
    fixq = _f(p[6], 0) or 0
    out = {"fix": 1 if fixq else 0}
    lat = _dm_to_deg(p[2], p[3]) if p[2] else None
    lon = _dm_to_deg(p[4], p[5]) if p[4] else None
    if lat is not None:
        out["lat"] = lat
    if lon is not None:
        out["lon"] = lon
    sats = _f(p[7])
    if sats is not None:
        out["sats"] = int(sats)
    hdop = _f(p[8])
    if hdop is not None:
        out["hdop"] = round(hdop, 2)
    alt = _f(p[9])
    if alt is not None:
        out["alt"] = round(alt, 1)
    return out


def _parse_vtg(p):
    if len(p) < 8:
        return None
    out = {}
    hdg = _f(p[1])
    if hdg is not None:
        out["heading"] = round(hdg, 1)
    kmh = _f(p[7])
    if kmh is not None:
        out["speed"] = round(kmh, 2)
    return out or None


def _parse_gsa(p):
    if len(p) < 18:
        return None
    out = {}
    fix = p[2]
    if fix:
        out["fix"] = 0 if fix == "1" else (1 if fix in ("2", "3") else 0)
    hdop = _f(p[16])
    if hdop is not None:
        out["hdop"] = round(hdop, 2)
    return out or None


class GpsState:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {
            "fix": 0, "lat": None, "lon": None, "alt": None,
            "sats": 0, "hdop": None, "speed": None, "heading": None,
            "utc": None,
        }
        self.last_update = 0.0

    def feed(self, parsed: dict):
        if not parsed:
            return
        with self.lock:
            self.data.update(parsed)
            self.last_update = time.monotonic()

    def snapshot(self, max_age=5.0):
        with self.lock:
            d = dict(self.data)
            age = time.monotonic() - self.last_update if self.last_update else None
        age_ms = int(age * 1000) if age is not None else None
        fresh = age is not None and age <= max_age
        has = fresh and d.get("lat") is not None and d.get("lon") is not None
        return {
            "fix": int(bool(d.get("fix")) and has),
            "lat": d.get("lat"),
            "lon": d.get("lon"),
            "alt": d.get("alt"),
            "sats": int(d.get("sats") or 0),
            "hdop": d.get("hdop"),
            "speed": d.get("speed"),
            "heading": d.get("heading"),
            "utc": d.get("utc"),
            "age_ms": age_ms,
            "has": bool(has),
        }


class GpsReader(threading.Thread):
    def __init__(self, cfg, state):
        super().__init__(daemon=True, name="gps-usb")
        self.cfg = cfg
        self.state = state
        self._stop = threading.Event()
        self._dev = None
        self.port_name = None
        self.status = "down"

    def _candidates(self):
        if self.cfg.get("port"):
            yield self.cfg["port"]
        if list_ports is not None:
            seen = set()
            for p in list_ports.comports():
                desc = (p.description or "").lower()
                dev = p.device
                if dev in seen:
                    continue
                seen.add(dev)
                if "gps" in desc or "gnss" in desc or "nmea" in desc:
                    yield dev
            for cand in self.cfg.get("candidates") or []:
                if cand not in seen:
                    yield cand

    def _open(self):
        if serial is None:
            return None
        baud = int(self.cfg.get("baud", 9600))
        for cand in self._candidates():
            if self._stop.is_set():
                return None
            if not os.path.exists(cand):
                continue
            try:
                dev = serial.Serial(cand, baud, timeout=0.5, write_timeout=0.5)
                time.sleep(0.3)
                dev.reset_input_buffer()
                self.port_name = cand
                self.status = "open"
                return dev
            except (serial.SerialException, OSError):
                continue
        return None

    def run(self):
        while not self._stop.is_set():
            dev = self._open()
            if dev is None:
                self.status = "down"
                self.port_name = None
                self._stop.wait(float(self.cfg.get("reconnect_s", 3.0)))
                continue
            buf = b""
            while not self._stop.is_set():
                try:
                    chunk = dev.read(256)
                except (serial.SerialException, OSError):
                    break
                if not chunk:
                    continue
                buf += chunk
                if len(buf) > 4096:
                    buf = buf[-1024:]
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("ascii", "ignore").strip()
                    if line.startswith("$"):
                        self.state.feed(parse_nmea(line))
            try:
                dev.close()
            except Exception:
                pass
            self._dev = None
            self.status = "down"
            self.port_name = None
            self._stop.wait(float(self.cfg.get("reconnect_s", 3.0)))

    def stop(self):
        self._stop.set()
