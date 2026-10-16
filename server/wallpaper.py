import base64
import binascii
import re
from pathlib import Path

DATA_URL_RE = re.compile(r"^data:(image/[a-z0-9.+-]+);base64,(.+)$", re.IGNORECASE | re.DOTALL)
EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}
MIME = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp"}
MAX_BYTES = 8 * 1024 * 1024
ROUTE = "/media/wallpaper"


class Wallpaper:
    """Store a wallpaper as an external URL or an uploaded image kept in
    data/wallpapers/current.* and served at /media/wallpaper."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.dir = Path(cfg["paths"]["data_dir"]) / "wallpapers"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _stored_files(self):
        return [self.dir / ("current" + ext) for ext in sorted(set(EXT.values()))]

    def value(self):
        return str((self.cfg.get("media") or {}).get("wallpaper") or "")

    def get(self):
        return {"wallpaper": self.value(),
                "fit": (self.cfg.get("media") or {}).get("fit") or "cover"}

    def save_url(self, url):
        url = (url or "").strip()[:512]
        if url and not (url.startswith("http://") or url.startswith("https://")
                        or url.startswith("/")):
            raise ValueError("URL invalida (use http://, https:// ou um caminho local)")
        self._clear_files()
        return url

    def save_data(self, data_url):
        m = DATA_URL_RE.match((data_url or "").strip())
        if not m:
            raise ValueError("imagem invalida (esperado data:image/...;base64,...)")
        ext = EXT.get(m.group(1).lower())
        if not ext:
            raise ValueError("formato de imagem nao suportado (use PNG, JPG, WEBP, GIF ou BMP)")
        try:
            raw = base64.b64decode(m.group(2), validate=False)
        except (binascii.Error, ValueError):
            raise ValueError("nao foi possivel decodificar a imagem")
        if len(raw) > MAX_BYTES:
            raise ValueError("imagem muito grande (limite de 8 MB)")
        self._clear_files()
        (self.dir / ("current" + ext)).write_bytes(raw)
        return ROUTE

    def clear(self):
        self._clear_files()
        return ""

    def read(self):
        for f in self._stored_files():
            if f.is_file():
                return f.read_bytes(), MIME.get(f.suffix, "application/octet-stream")
        return None, None

    def _clear_files(self):
        for f in self._stored_files():
            try:
                f.unlink()
            except FileNotFoundError:
                pass
