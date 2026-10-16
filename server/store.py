import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS samples(
  ts INTEGER PRIMARY KEY,
  speed REAL, rpm REAL, coolant REAL, fuel REAL, trip_km REAL
);
CREATE TABLE IF NOT EXISTS trips(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  start_ts INTEGER, end_ts INTEGER,
  distance_km REAL, duration_s REAL,
  avg_kmh REAL, max_kmh REAL, fuel_used_l REAL
);
CREATE TABLE IF NOT EXISTS dtc(
  code TEXT PRIMARY KEY,
  first_seen INTEGER, last_seen INTEGER, cleared INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS apps(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  icon TEXT DEFAULT 'globe',
  color TEXT DEFAULT '#4aa8ff',
  kind TEXT DEFAULT 'web',
  sort INTEGER DEFAULT 0,
  created_ts INTEGER
);
CREATE TABLE IF NOT EXISTS track(
  ts INTEGER PRIMARY KEY,
  lat REAL, lon REAL, speed REAL, heading REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
CREATE INDEX IF NOT EXISTS idx_track_ts ON track(ts);
"""

DEFAULT_APPS = [
    {"id": "nav", "name": "Navegação", "url": "nav", "icon": "nav",
     "color": "#4aa8ff", "kind": "nav", "sort": 0},
    {"id": "youtube", "name": "YouTube",
     "url": "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ",
     "icon": "play", "color": "#ff0033", "kind": "embed", "sort": 1},
    {"id": "spotify", "name": "Spotify",
     "url": "https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M",
     "icon": "music", "color": "#1db954", "kind": "embed", "sort": 2},
    {"id": "maps", "name": "Mapas",
     "url": "https://maps.google.com/maps?q=-23.5613,-46.6565&z=15&output=embed",
     "icon": "map", "color": "#34a853", "kind": "embed", "sort": 3},
    {"id": "web", "name": "Navegador", "url": "https://duckduckgo.com/",
     "icon": "compass", "color": "#35d6e6", "kind": "browser", "sort": 4},
    {"id": "gnome-maps", "name": "GNOME Maps",
     "url": "gnome-maps", "icon": "map", "color": "#5b9e4a",
     "kind": "native", "sort": 5},
]

# Apps de sistema que sempre existem (nao podem ser removidos pelo painel).
BUILTIN_APP_IDS = {"nav", "gnome-maps"}


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._db:
            self._db.executescript(SCHEMA)

    def get_settings(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT key, value FROM settings").fetchall()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except json.JSONDecodeError:
                out[r["key"]] = r["value"]
        return out

    def set_settings(self, values: dict):
        with self._lock, self._db:
            for k, v in values.items():
                self._db.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, json.dumps(v)),
                )

    def log_sample(self, ts: int, speed: float, rpm: float, coolant: float,
                   fuel: float, trip_km: float):
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO samples(ts, speed, rpm, coolant, fuel, trip_km) "
                "VALUES(?,?,?,?,?,?)",
                (ts, speed, rpm, coolant, fuel, trip_km),
            )
            self._db.execute("DELETE FROM samples WHERE ts < ?", (ts - 86400_000,))

    def history(self, minutes: int = 15) -> dict:
        since = int(time.time() * 1000) - minutes * 60_000
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, speed, rpm, coolant, fuel, trip_km FROM samples "
                "WHERE ts >= ? ORDER BY ts",
                (since,),
            ).fetchall()
        return {
            "ts": [r["ts"] for r in rows],
            "speed": [r["speed"] for r in rows],
            "rpm": [r["rpm"] for r in rows],
            "coolant": [r["coolant"] for r in rows],
            "fuel": [r["fuel"] for r in rows],
            "trip_km": [r["trip_km"] for r in rows],
        }

    def save_trip(self, trip: dict):
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO trips(start_ts, end_ts, distance_km, duration_s, "
                "avg_kmh, max_kmh, fuel_used_l) VALUES(?,?,?,?,?,?,?)",
                (
                    trip.get("start_ts"),
                    int(time.time() * 1000),
                    trip.get("km", 0.0),
                    trip.get("s", 0.0),
                    trip.get("avg", 0.0),
                    trip.get("max", 0.0),
                    trip.get("fuel_l", 0.0),
                ),
            )
            self._db.execute(
                "DELETE FROM trips WHERE id NOT IN "
                "(SELECT id FROM trips ORDER BY end_ts DESC LIMIT 400)"
            )

    def trips(self, limit: int = 20) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM trips ORDER BY end_ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def sync_dtc(self, codes: list, now_ms: int):
        with self._lock, self._db:
            active = set(codes)
            known = {
                r["code"]
                for r in self._db.execute("SELECT code FROM dtc WHERE cleared=0").fetchall()
            }
            for code in active:
                self._db.execute(
                    "INSERT INTO dtc(code, first_seen, last_seen, cleared) "
                    "VALUES(?,?,?,0) ON CONFLICT(code) DO UPDATE SET "
                    "last_seen=excluded.last_seen, cleared=0",
                    (code, now_ms, now_ms),
                )
            for gone in known - active:
                self._db.execute(
                    "UPDATE dtc SET cleared=1, last_seen=? WHERE code=?",
                    (now_ms, gone),
                )

    def dtcs(self) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM dtc WHERE cleared=0 ORDER BY last_seen DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_dtcs(self, now_ms: int):
        with self._lock, self._db:
            self._db.execute("UPDATE dtc SET cleared=1, last_seen=?", (now_ms,))

    def apps(self) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM apps ORDER BY sort, name COLLATE NOCASE"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_app(self, app: dict):
        now_ms = int(time.time() * 1000)
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO apps(id, name, url, icon, color, kind, sort, created_ts) "
                "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "name=excluded.name, url=excluded.url, icon=excluded.icon, "
                "color=excluded.color, kind=excluded.kind, sort=excluded.sort",
                (
                    app["id"], app["name"], app["url"],
                    app.get("icon") or "globe", app.get("color") or "#4aa8ff",
                    app.get("kind") or "web", int(app.get("sort") or 0), now_ms,
                ),
            )
        return self.app(app["id"])

    def app(self, app_id: str):
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM apps WHERE id=?", (app_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_app(self, app_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM apps WHERE id=?", (app_id,))
        return cur.rowcount > 0

    def seed_apps(self, defaults: list):
        with self._lock, self._db:
            n = self._db.execute("SELECT COUNT(*) AS c FROM apps").fetchone()["c"]
            if n:
                return
            now_ms = int(time.time() * 1000)
            for a in defaults:
                self._db.execute(
                    "INSERT OR IGNORE INTO apps(id, name, url, icon, color, kind, "
                    "sort, created_ts) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        a["id"], a["name"], a["url"], a.get("icon", "globe"),
                        a.get("color", "#4aa8ff"), a.get("kind", "web"),
                        int(a.get("sort", 0)), now_ms,
                    ),
                )

    def ensure_apps(self, defaults: list):
        with self._lock, self._db:
            now_ms = int(time.time() * 1000)
            for a in defaults:
                self._db.execute(
                    "INSERT OR IGNORE INTO apps(id, name, url, icon, color, kind, "
                    "sort, created_ts) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        a["id"], a["name"], a["url"], a.get("icon", "globe"),
                        a.get("color", "#4aa8ff"), a.get("kind", "web"),
                        int(a.get("sort", 0)), now_ms,
                    ),
                )

    def log_track(self, ts: int, lat: float, lon: float,
                  speed: float, heading: float):
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO track(ts, lat, lon, speed, heading) "
                "VALUES(?,?,?,?,?)",
                (ts, lat, lon, speed, heading),
            )
            self._db.execute("DELETE FROM track WHERE ts < ?", (ts - 86400_000,))

    def track(self, minutes: int = 180) -> list:
        since = int(time.time() * 1000) - minutes * 60_000
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, lat, lon, speed, heading FROM track "
                "WHERE ts >= ? ORDER BY ts",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]
