import base64
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "https://gateway.apilib.prefeitura.sp.gov.br/sptrans/olhovivo/v2.1"
DEFAULT_TOKEN_URL = "https://gateway.apilib.prefeitura.sp.gov.br/token"


def _hz(a, b):
    return math.radians(float(b) - float(a))


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    h = (
        math.sin(_hz(lat1, lat2) / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(_hz(lon1, lon2) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, h))))


class Traffic:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.cache_at = 0.0
        self.cache_hr = ""
        self.cache = []
        self.cache_full = False
        self.last_ok = 0.0
        self.last_error = ""
        self._tok = ""
        self._tok_at = 0.0

    def section(self):
        return self.cfg.get("traffic") or {}

    def base_url(self):
        return str(self.section().get("base_url") or DEFAULT_BASE_URL).rstrip("/")

    def token_url(self):
        return str(self.section().get("token_url") or DEFAULT_TOKEN_URL).strip()

    def enabled(self):
        s = self.section()
        if not s.get("enabled"):
            return False
        return bool(self._static_token() or (s.get("client_id") and s.get("client_secret")))

    def _static_token(self):
        s = self.section()
        tok = str(s.get("token") or "").strip()
        if not tok:
            env = str(s.get("token_env") or "").strip()
            if env:
                tok = str(__import__("os").environ.get(env) or "").strip()
        return tok

    def _token(self, force=False):
        s = self.section()
        if not force:
            static = self._static_token()
            if static:
                return static
            if self._tok and time.time() - self._tok_at < 480:
                return self._tok
        cid = str(s.get("client_id") or "").strip()
        sec = str(s.get("client_secret") or "").strip()
        if not cid or not sec:
            return self._tok if self._tok else ""
        url = self.token_url()
        if not url:
            return self._tok if self._tok else ""
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": "Basic "
                + base64.b64encode(f"{cid}:{sec}".encode()).decode(),
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        tok = str(body.get("access_token") or "").strip()
        if tok:
            self._tok = tok
            self._tok_at = time.time()
        return tok

    def _get(self, path, params=None, retry=True):
        tok = self._token()
        if not tok:
            raise RuntimeError("token nao configurado")
        url = self.base_url() + "/" + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "Authorization": "Bearer " + tok}
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and retry:
                self._tok = ""
                if self._token(force=True):
                    return self._get(path, params, retry=False)
            raise

    def _load(self):
        s = self.section()
        ttl = float(s.get("refresh_s") or 25) or 25
        with self.lock:
            if self.cache and time.time() - self.cache_at < ttl:
                return self.cache
            try:
                raw = self._get("Posicao")
            except Exception as exc:
                self.last_error = str(exc)[:200]
                if self.cache:
                    return self.cache
                return []
            now = time.time()
            out = []
            for ln in raw.get("l") or []:
                code = ln.get("cl")
                letreiro = ln.get("c") or ""
                lt0 = ln.get("lt0") or ""
                lt1 = ln.get("lt1") or ""
                sl = ln.get("sl")
                for v in ln.get("vs") or []:
                    py, px = v.get("py"), v.get("px")
                    if py is None or px is None:
                        continue
                    out.append({
                        "p": v.get("p"),
                        "lat": float(py),
                        "lon": float(px),
                        "cl": code,
                        "c": letreiro,
                        "lt0": lt0,
                        "lt1": lt1,
                        "sl": sl,
                        "a": bool(v.get("a")),
                        "ts": v.get("ta") or "",
                    })
            out.sort(key=lambda x: x.get("p") or 0)
            self.cache = out
            self.cache_at = now
            self.cache_hr = raw.get("hr") or ""
            self.cache_full = True
            self.last_ok = now
            self.last_error = ""
            return self.cache

    def status(self):
        s = self.section()
        with self.lock:
            return {
                "provider": "olhovivo",
                "enabled": s.get("enabled"),
                "configured": self.enabled(),
                "gateway": self.base_url(),
                "refresh_s": s.get("refresh_s"),
                "radius_km": s.get("radius_km"),
                "hr": self.cache_hr,
                "cached": len(self.cache) if self.cache_full else 0,
                "age_s": round(time.time() - self.cache_at) if self.cache_at else None,
                "last_ok": self.last_ok,
                "last_error": self.last_error,
            }

    def buses(self, lat=None, lon=None, radius=None):
        s = self.section()
        radius = radius if radius is not None else s.get("radius_km")
        data = self._load()
        with self.lock:
            hr = self.cache_hr
            updated = self.cache_at
        if data and lat is not None and lon is not None and radius:
            r = float(radius)
            scored = []
            for v in data:
                d = haversine_km(lat, lon, v["lat"], v["lon"])
                if d <= r:
                    scored.append((d, v))
            scored.sort(key=lambda x: x[0])
            data = [v for _, v in scored]
        cap = int(s.get("max_vehicles") or 1500) or 1500
        if len(data) > cap:
            data = data[:cap]
        return {
            "hr": hr,
            "updated": int(updated) if updated else 0,
            "count": len(data),
            "vehicles": data,
            "status": self.status(),
        }

    def lines(self, query):
        q = str(query or "").strip()
        if not q:
            return {"lines": [], "query": q}
        raw = self._get("Linha/Buscar", {"termosBusca": q})
        out = []
        if isinstance(raw, list):
            for ln in raw:
                out.append({
                    "cl": ln.get("cl"),
                    "c": ln.get("c") or "",
                    "lt0": ln.get("lt0") or "",
                    "lt1": ln.get("lt1") or "",
                    "sl": ln.get("sl"),
                    "lc": bool(ln.get("lc")),
                })
        return {"lines": out[:50], "query": q}

    def line_vehicles(self, codigo):
        try:
            cl = int(codigo)
        except (TypeError, ValueError):
            return {"vehicles": [], "line": None}
        raw = self._get("Posicao/Linha", {"codigoLinha": cl})
        vs = raw.get("vs") if isinstance(raw, dict) else None
        out = []
        for v in vs or []:
            py, px = v.get("py"), v.get("px")
            if py is None or px is None:
                continue
            out.append({
                "p": v.get("p"),
                "lat": float(py),
                "lon": float(px),
                "a": bool(v.get("a")),
                "ts": v.get("ta") or "",
            })
        return {
            "line": cl,
            "hr": raw.get("hr") if isinstance(raw, dict) else "",
            "count": len(out),
            "vehicles": out,
        }
