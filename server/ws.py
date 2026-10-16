import base64
import contextlib
import hashlib
import struct
import threading

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def accept_key(key: str) -> str:
    digest = hashlib.sha1((key + GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


class WSConn:
    def __init__(self, rfile, wfile, addr=""):
        self.rfile = rfile
        self.wfile = wfile
        self.addr = addr
        self.lock = threading.Lock()
        self.closed = False
        self._frag = b""

    def _read(self, n: int) -> bytes:
        data = self.rfile.read(n)
        if not data or len(data) < n:
            raise ConnectionError("eof")
        return data

    def recv(self):
        while True:
            hdr = self._read(2)
            b0, b1 = hdr[0], hdr[1]
            fin = b0 & 0x80
            opcode = b0 & 0x0F
            masked = b1 & 0x80
            length = b1 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if masked else b"\x00\x00\x00\x00"
            payload = self._read(length) if length else b""
            if masked and payload:
                payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
            if opcode == 0x8:
                raise ConnectionError("close")
            if opcode == 0x9:
                self._send_frame(payload, 0xA)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                self._frag = payload
            elif opcode == 0x0:
                self._frag += payload
            else:
                continue
            if fin:
                text = self._frag.decode("utf-8", "ignore")
                self._frag = b""
                return text

    def _send_frame(self, data: bytes, opcode: int = 0x1):
        header = bytearray([0x80 | opcode])
        n = len(data)
        if n < 126:
            header.append(n)
        elif n < 65536:
            header.append(126)
            header += struct.pack(">H", n)
        else:
            header.append(127)
            header += struct.pack(">Q", n)
        frame = bytes(header) + data
        with self.lock:
            if self.closed:
                raise ConnectionError("closed")
            self.wfile.write(frame)
            self._flush()

    def _flush(self):
        fn = getattr(self.wfile, "flush", None)
        if callable(fn):
            with contextlib.suppress(Exception):
                fn()

    def send_text(self, text: str):
        self._send_frame(text.encode("utf-8"), 0x1)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            try:
                self.wfile.write(b"\x88\x00")
                self._flush()
            except OSError:
                pass
