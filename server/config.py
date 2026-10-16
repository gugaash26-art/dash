import copy
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("CARDASH_CONFIG", ROOT / "config.yaml"))

DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 8080},
    "serial": {
        "enabled": True,
        "auto_detect": True,
        "port": "/dev/ttyUSB0",
        "baud": 115200,
        "candidates": ["/dev/ttyUSB0", "/dev/ttyACM0"],
        "reconnect_s": 2.0,
    },
    "simulation": {"enabled": False, "drive": True},
    "rates": {"broadcast_hz": 10, "log_hz": 1},
    "units": {"speed": "kmh", "temp": "c", "pressure": "psi", "volume": "l"},
    "thresholds": {
        "coolant_warn_c": 100,
        "coolant_crit_c": 106,
        "volt_warn_v": 12.2,
        "volt_crit_v": 11.8,
        "fuel_warn_pct": 12,
        "oil_warn_psi": 25,
        "oil_crit_psi": 15,
        "rpm_warn": 5800,
        "speed_warn": 0,
    },
    "trip": {
        "fuel_capacity_l": 55,
        "consumption_l100": 8.5,
        "odometer_km": 0,
        "idle_lh": 0.9,
    },
    "car": {"name": "OpenDash", "model": "Projetor", "engine": "2.0"},
    "gps": {
        "enabled": True,
        "source": "auto",
        "port": "",
        "baud": 9600,
        "candidates": [
            "/dev/ttyACM0", "/dev/ttyACM1",
            "/dev/ttyUSB1", "/dev/gps", "/dev/serial0",
        ],
        "reconnect_s": 3.0,
        "track_minutes": 180,
    },
    "maps": {
        "provider": "osm",
        "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "google_key": "",
        "zoom": 16,
    },
    "apps": {"seed_defaults": True},
    "paths": {"data_dir": str(ROOT / "data"), "db": str(ROOT / "data" / "cardash.db")},
    "ui": {"boot_animation": True, "theme": "auto", "brightness": 100},
}

EDITABLE = [
    ("units.speed", ["kmh", "mph"]),
    ("units.temp", ["c", "f"]),
    ("units.volume", ["l", "gal"]),
    ("ui.theme", ["auto", "dark", "light"]),
    ("ui.brightness", None),
    ("ui.boot_animation", None),
    ("trip.fuel_capacity_l", None),
    ("trip.consumption_l100", None),
    ("trip.odometer_km", None),
    ("car.name", None),
    ("simulation.enabled", None),
    ("serial.enabled", None),
    ("serial.port", None),
    ("serial.baud", None),
    ("gps.enabled", None),
    ("gps.source", ["auto", "arduino", "usb", "off"]),
    ("gps.port", None),
    ("gps.baud", None),
    ("maps.provider", ["osm", "google"]),
    ("maps.tile_url", None),
    ("maps.google_key", None),
]


def _merge(base: dict, other: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (other or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        cur = cur.get(part)
    return cur


def _set(d: dict, dotted: str, value):
    parts = dotted.split(".")
    cur = d
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def load_config() -> dict:
    raw = {}
    if CONFIG_PATH.exists():
        if yaml is None:
            print(f"[cardash] PyYAML ausente: usando padroes, nao foi possivel ler {CONFIG_PATH}")
        else:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
    cfg = _merge(DEFAULTS, raw)
    Path(cfg["paths"]["data_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg


cfg = load_config()


def validate_setting(key: str, value):
    spec = next((s for s in EDITABLE if s[0] == key), None)
    if spec is None:
        raise KeyError(key)
    choices = spec[1]
    if choices and value not in choices:
        raise ValueError(f"{key} deve ser um de {choices}")
    if key in ("ui.brightness",):
        value = max(10, min(100, int(value)))
    if key in ("trip.fuel_capacity_l", "trip.consumption_l100"):
        value = float(value)
        if value <= 0:
            raise ValueError(key)
    if key == "trip.odometer_km":
        value = max(0.0, float(value))
    if key in ("ui.boot_animation", "simulation.enabled", "serial.enabled",
               "gps.enabled"):
        value = bool(value)
    if key in ("serial.baud", "gps.baud"):
        value = int(value)
    if key in ("car.name", "serial.port", "gps.port"):
        value = str(value)[:64]
    if key in ("maps.tile_url", "maps.google_key"):
        value = str(value)[:256]
    return value
