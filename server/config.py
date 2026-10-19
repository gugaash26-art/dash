import copy
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("CARDASH_CONFIG", ROOT / "config.yaml"))


def _load_env_file(path: Path):
    """Carrega um arquivo .env simples (KEY=valor) para o ambiente.

    Nao sobrescreve variaveis ja definidas. Ignora linhas vazias/comentarios.
    Usado para a chave da IA (GROQ_API_KEY) e outras credenciais, mantendo os
    segredos fora do git e fora do /api/settings.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass


_env_files = [ROOT / ".env", ROOT / "data" / "agent.env"]
_extra = os.environ.get("CARDASH_ENV_FILE")
if _extra:
    _env_files.insert(0, Path(_extra))
for _p in _env_files:
    _load_env_file(_p)


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
    "traffic": {
        "enabled": False,
        "token": "",
        "token_env": "APILIB_TOKEN",
        "client_id": "",
        "client_secret": "",
        "base_url": "https://gateway.apilib.prefeitura.sp.gov.br/sptrans/olhovivo/v2.1",
        "token_url": "https://gateway.apilib.prefeitura.sp.gov.br/token",
        "refresh_s": 25,
        "radius_km": 12,
        "max_vehicles": 1500,
    },
    "apps": {"seed_defaults": True},
    "agent": {
        "enabled": True,
        "stt": "whisper",
        "whisper_bin": "whisper-cli",
        "whisper_model": str(ROOT / "models" / "ggml-base.bin"),
        "stt_lang": "pt",
        "mic_device": "default",
        "record_seconds": 6,
        "llm_provider": "groq",
        "llm_base_url": "https://api.groq.com/openai/v1",
        "llm_model": "openai/gpt-oss-120b",
        "llm_key_env": "GROQ_API_KEY",
        "llm_key": "",
        "tts": "edge",
        "tts_voice": "pt-BR-ThalitaMultilingualNeural",
        "speak": True,
        "play_local": False,
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "max_turns": 8,
    },
    "update": {
        "enabled": True,
        "remote": "origin",
        "branch": "main",
        "auto_check": True,
        "check_hours": 6,
        "install_deps": True,
        "restart_command": "",
    },
    "media": {"wallpaper": "", "fit": "cover"},
    "native": {
        "enabled": True,
        "display": ":0",
        "maps_app": "gnome-maps",
    },
    "screens": {
        "enabled": False,
        "main": "",
        "bar": "",
        "arrange": False,
        "display": ":0",
    },
    "display": {
        "scale": "auto",
        "inches": 0.0,
        "orientation": "auto",
        "width": 0,
        "height": 0,
    },
    "camera": {
        "enabled": True,
        "trigger": "gear",
        "device": "auto",
        "backend": "auto",
        "width": 0,
        "height": 0,
        "fps": 25,
        "guidelines": True,
        "flip_h": False,
        "flip_v": False,
        "extra_args": "",
    },
    "paths": {"data_dir": str(ROOT / "data"), "db": str(ROOT / "data" / "cardash.db")},
    "temas": {"ativo": "auto"},
    "ui": {"boot_animation": True, "theme": "auto", "brightness": 100},
}

PANEL_THEMES = [
    "auto", "dark", "light", "ferrari", "porsche", "bmw", "amg",
    "lambo", "audi", "tesla", "gr", "mustang", "corvette",
]

EDITABLE = [
    ("units.speed", ["kmh", "mph"]),
    ("units.temp", ["c", "f"]),
    ("units.volume", ["l", "gal"]),
    ("ui.theme", ["auto", "dark", "light"]),
    ("temas.ativo", PANEL_THEMES),
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
    ("traffic.enabled", None),
    ("traffic.token", None),
    ("traffic.token_env", None),
    ("traffic.client_id", None),
    ("traffic.client_secret", None),
    ("traffic.base_url", None),
    ("traffic.token_url", None),
    ("traffic.refresh_s", None),
    ("traffic.radius_km", None),
    ("traffic.max_vehicles", None),
    ("agent.enabled", None),
    ("agent.mic_device", None),
    ("agent.record_seconds", None),
    ("agent.stt_lang", None),
    ("agent.whisper_bin", None),
    ("agent.whisper_model", None),
    ("agent.llm_base_url", None),
    ("agent.llm_model", None),
    ("agent.llm_key_env", None),
    ("agent.llm_key", None),
    ("agent.tts_voice", None),
    ("agent.speak", None),
    ("agent.play_local", None),
    ("agent.spotify_client_id", None),
    ("agent.spotify_client_secret", None),
    ("media.wallpaper", None),
    ("media.fit", ["cover", "contain", "fill"]),
    ("native.enabled", None),
    ("native.display", None),
    ("native.maps_app", None),
    ("screens.enabled", None),
    ("screens.main", None),
    ("screens.bar", None),
    ("screens.arrange", None),
    ("display.scale", None),
    ("display.inches", None),
    ("display.orientation", ["auto", "landscape", "portrait"]),
    ("display.width", None),
    ("display.height", None),
    ("camera.enabled", None),
    ("camera.trigger", ["gear", "manual", "always", "off"]),
    ("camera.device", None),
    ("camera.backend", ["auto", "v4l2", "rpicam"]),
    ("camera.width", None),
    ("camera.height", None),
    ("camera.fps", None),
    ("camera.guidelines", None),
    ("camera.flip_h", None),
    ("camera.flip_v", None),
    ("camera.extra_args", None),
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
    if key == "traffic.enabled":
        value = bool(value)
    if key in ("traffic.token", "traffic.token_env", "traffic.client_id",
               "traffic.client_secret", "traffic.base_url", "traffic.token_url"):
        value = str(value or "")[:256]
    if key == "traffic.refresh_s":
        value = max(10, min(300, int(value)))
    if key in ("traffic.radius_km",):
        value = max(1.0, min(60.0, float(value)))
    if key == "traffic.max_vehicles":
        value = max(50, min(8000, int(value)))
    if key in ("agent.enabled", "agent.speak", "agent.play_local"):
        value = bool(value)
    if key == "agent.record_seconds":
        value = max(1, min(20, int(value)))
    if key in ("agent.mic_device", "agent.stt_lang", "agent.whisper_bin"):
        value = str(value)[:64]
    if key in ("agent.whisper_model", "agent.llm_base_url", "agent.llm_model",
               "agent.llm_key_env", "agent.llm_key", "agent.tts_voice",
               "agent.spotify_client_id", "agent.spotify_client_secret"):
        value = str(value)[:256]
    if key == "media.wallpaper":
        value = str(value)[:512]
    if key == "native.enabled":
        value = bool(value)
    if key in ("native.display", "native.maps_app"):
        value = str(value)[:64]
    if key == "screens.enabled" or key == "screens.arrange":
        value = bool(value)
    if key in ("screens.main", "screens.bar"):
        value = str(value)[:64]
    if key == "display.scale":
        if value in (None, "", "auto"):
            value = "auto"
        else:
            value = max(0.5, min(3.0, float(value)))
    if key == "display.inches":
        value = max(0.0, min(120.0, float(value)))
    if key == "display.orientation":
        value = str(value)
    if key in ("display.width", "display.height"):
        value = max(0, min(16000, int(value)))
    if key in ("camera.enabled", "camera.guidelines", "camera.flip_h", "camera.flip_v"):
        value = bool(value)
    if key in ("camera.device", "camera.extra_args"):
        value = str(value)[:128]
    if key in ("camera.width", "camera.height"):
        value = max(0, min(8000, int(value)))
    if key == "camera.fps":
        value = max(1, min(60, int(value)))
    return value
