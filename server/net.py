"""Conectividade do OpenDash: Wi-Fi (NetworkManager/nmcli) e Bluetooth (bluez).

Tudo degrada com educacao quando as ferramentas nao existem (ex.: rodando em
PRoot/Termux), devolvendo ``available: False`` em vez de estourar erro.
"""
import re
import shutil
import subprocess

# Endereco MAC no formato AA:BB:CC:DD:EE:FF
_MAC = re.compile(r"Device ([0-9A-Fa-f:]{17})\s*(.*)")


def _run(cmd, timeout=15):
    """Executa um comando e devolve (rc, stdout, stderr) sem levantar excecoes."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", "comando ausente"
    except subprocess.TimeoutExpired:
        return 124, "", "tempo esgotado"
    except Exception as exc:  # pragma: no cover - defensivo
        return 1, "", str(exc)


def _split_terse(line):
    """Divide uma linha do ``nmcli -t`` respeitando ':' escapado com '\\'."""
    out, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


class Net:
    def __init__(self, cfg):
        self.cfg = cfg
        self.wifi_cache = []
        self.bt_cache = []

    # ------------------------------------------------------------- capacidades
    @property
    def has_nmcli(self):
        return shutil.which("nmcli") is not None

    @property
    def has_bt(self):
        return shutil.which("bluetoothctl") is not None

    def tools(self):
        return {
            "nmcli": self.has_nmcli,
            "bluetoothctl": self.has_bt,
        }

    def status(self):
        return {"wifi": self.wifi_status(), "bluetooth": self.bt_status(),
                "tools": self.tools()}

    # -------------------------------------------------------------------- Wi-Fi
    def _wifi_device(self):
        rc, out, _ = _run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"])
        for line in out.splitlines():
            parts = _split_terse(line)
            if len(parts) >= 2 and parts[1] == "wifi":
                return parts[0]
        return None

    def wifi_status(self):
        if not self.has_nmcli:
            return {"available": False, "reason": "nmcli ausente (instale network-manager)"}
        rc, out, _ = _run(["nmcli", "-t", "-f", "WIFI", "general", "status"])
        enabled = out.strip().endswith("enabled")
        device = self._wifi_device()
        ssid = signal = ip = None
        if device:
            rc, wl, _ = _run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL",
                              "device", "wifi", "list"])
            for line in wl.splitlines():
                parts = _split_terse(line)
                if parts and parts[0] == "yes":
                    ssid = parts[1] if len(parts) > 1 else None
                    signal = parts[2] if len(parts) > 2 else None
            rc, addr, _ = _run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", device])
            for line in addr.splitlines():
                if ":" in line:
                    ip = line.split(":", 1)[1].split("/")[0].strip()
                    break
        return {"available": True, "enabled": enabled, "device": device,
                "ssid": ssid or None, "signal": signal, "ip": ip}

    def wifi_scan(self, rescan=True):
        if not self.has_nmcli:
            return {"available": False, "networks": [], "reason": "nmcli ausente"}
        if rescan:
            _run(["nmcli", "device", "wifi", "rescan"], timeout=15)
        rc, out, err = _run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                             "device", "wifi", "list"], timeout=25)
        if rc != 0 and not out.strip():
            return {"available": True, "networks": [], "error": (err or "").strip()[:160]}
        seen = {}
        for line in out.splitlines():
            parts = _split_terse(line)
            if len(parts) < 4:
                continue
            in_use, ssid, signal, sec = parts[0], parts[1], parts[2], parts[3]
            if not ssid:
                continue
            try:
                sig = int(signal)
            except ValueError:
                sig = 0
            entry = {"ssid": ssid, "signal": sig,
                     "security": sec or "aberta", "active": in_use.strip() == "*"}
            old = seen.get(ssid)
            if old is None or entry["signal"] > old["signal"] or entry["active"]:
                seen[ssid] = entry
        nets = sorted(seen.values(), key=lambda n: (not n["active"], -n["signal"]))
        self.wifi_cache = nets
        return {"available": True, "networks": nets}

    def wifi_action(self, action, ssid=None, password=None):
        if not self.has_nmcli:
            return {"ok": False, "error": "nmcli ausente (instale network-manager)"}
        if action in ("enable", "disable"):
            _run(["nmcli", "radio", "wifi", "on" if action == "enable" else "off"])
            return {"ok": True, "status": self.wifi_status()}
        if action == "scan":
            return self.wifi_scan()
        if action == "disconnect":
            device = self._wifi_device()
            if not device:
                return {"ok": False, "error": "nenhum adaptador Wi-Fi"}
            rc, out, err = _run(["nmcli", "device", "disconnect", device])
            return {"ok": rc == 0, "error": None if rc == 0 else (err or out).strip()[:160]}
        if not ssid:
            return {"ok": False, "error": "ssid obrigatorio"}
        if action == "connect":
            cmd = ["nmcli", "device", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]
            rc, out, err = _run(cmd, timeout=45)
            return {"ok": rc == 0,
                    "error": None if rc == 0 else (err or out).strip()[:200],
                    "status": self.wifi_status()}
        if action == "forget":
            rc, out, err = _run(["nmcli", "connection", "delete", "id", ssid])
            return {"ok": rc == 0, "error": None if rc == 0 else (err or out).strip()[:160]}
        return {"ok": False, "error": "acao invalida"}

    # --------------------------------------------------------------- Bluetooth
    def bt_status(self):
        if not self.has_bt:
            return {"available": False, "reason": "bluetoothctl ausente (instale bluez)"}
        rc, out, err = _run(["bluetoothctl", "show"], timeout=10)
        if rc != 0:
            return {"available": True, "powered": False,
                    "error": (err or out).strip()[:160]}
        name = re.search(r"Name:\s*(.+)", out)
        return {"available": True, "powered": "Powered: yes" in out,
                "discoverable": "Discoverable: yes" in out,
                "name": name.group(1).strip() if name else None}

    def _bt_list(self, filter_=None):
        cmd = ["bluetoothctl", "devices"]
        if filter_:
            cmd.append(filter_)
        rc, out, _ = _run(cmd, timeout=10)
        devs = []
        for line in out.splitlines():
            m = _MAC.match(line)
            if m:
                mac, name = m.group(1), m.group(2).strip()
                devs.append({"mac": mac.upper(), "name": name or mac.upper()})
        return devs

    def bt_devices(self):
        if not self.has_bt:
            return {"available": False, "devices": [], "reason": "bluetoothctl ausente"}
        found = {d["mac"]: d for d in self._bt_list()}
        paired = {d["mac"] for d in self._bt_list("Paired")}
        connected = {d["mac"] for d in self._bt_list("Connected")}
        for mac, dev in found.items():
            dev["paired"] = mac in paired
            dev["connected"] = mac in connected
        devs = sorted(found.values(),
                      key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
        self.bt_cache = devs
        return {"available": True, "devices": devs}

    def bt_action(self, action, mac=None):
        if not self.has_bt:
            return {"ok": False, "error": "bluetoothctl ausente (instale bluez)"}
        if action in ("enable", "disable"):
            rc, out, err = _run(["bluetoothctl", "power",
                                 "on" if action == "enable" else "off"], timeout=10)
            return {"ok": rc == 0, "status": self.bt_status()}
        if action == "scan":
            _run(["bluetoothctl", "--timeout", "8", "scan", "on"], timeout=14)
            return self.bt_devices()
        if not mac:
            return {"ok": False, "error": "mac obrigatorio"}
        steps = {
            "pair": [["pair", mac], ["trust", mac], ["connect", mac]],
            "connect": [["connect", mac]],
            "disconnect": [["disconnect", mac]],
            "remove": [["remove", mac]],
        }.get(action)
        if not steps:
            return {"ok": False, "error": "acao invalida"}
        logs, ok = [], True
        for args in steps:
            rc, out, err = _run(["bluetoothctl", *args], timeout=20)
            logs.append((out or err).strip()[:160])
            if rc != 0:
                ok = False
        return {"ok": ok, "log": " | ".join(x for x in logs if x)[:300],
                "devices": self.bt_devices().get("devices", [])}
