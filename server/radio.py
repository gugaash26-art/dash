import os
import shutil
import struct
import threading
import time

try:
    import smbus2

    HAVE_SMBUS2 = True
except ImportError:
    smbus2 = None
    HAVE_SMBUS2 = False

try:
    import smbus

    HAVE_SMBUS = True
except ImportError:
    smbus = None
    HAVE_SMBUS = False

I2C_ADDR = 0x10  # endereco I2C do Si4703

# registradores Bank 1 (leitura/escrita)
REG_DEVICEID = 0x00
REG_CHIPID = 0x01
REG_POWERCFG = 0x02
REG_CHANNEL = 0x03
REG_SYSCONFIG1 = 0x04
REG_SYSCONFIG2 = 0x05
REG_SYSCONFIG3 = 0x06
REG_TEST1 = 0x07
REG_TEST2 = 0x08
REG_BOOTCONFIG = 0x09
REG_STATUSRSSI = 0x0A
REG_READCHAN = 0x0B
REG_RDSA = 0x0C
REG_RDSB = 0x0D
REG_RDSC = 0x0E
REG_RDSD = 0x0F

# registradores Bank 2 (alta frequencia)
REG_SEEKREF = 0x07
REG_SKAFCRL = 0x08
REG_SKSNR = 0x09
REG_SKCNT = 0x0A

# bits uteis
POWERCFG_ENABLE = 0x0001
POWERCFG_DMUTE = 0x4000
POWERCFG_MONO = 0x1000
POWERCFG_SEEKUP = 0x0200
POWERCFG_SEEK = 0x0100
POWERCFG_DISABLE = 0x0040
POWERCFG_SKMODE = 0x0080

SYSCONFIG1_RDS = 0x0001
SYSCONFIG1_DE = 0x0800

RDSR = 0x8000   # STATUSRSSI.15
STC = 0x4000    # STATUSRSSI.14
SF_BL = 0x2000  # STATUSRSSI.13
ST = 0x0100     # STATUSRSSI.8  (1 = estereo)
RSSI_MASK = 0x00FF  # STATUSRSSI.7:0

CHANNEL_TUNE = 0x8000
CHANNEL_MASK = 0x03FF
SPACING = {1: 200, 2: 100, 3: 50}
BAND = {0: 87500, 1: 76000, 2: 76000}


def freq_to_khz(freq):
    try:
        f = float(str(freq).replace(",", "."))
    except (TypeError, ValueError):
        return 0
    if f < 1000:
        f *= 1000.0
    return int(round(f))


def khz_to_mhz(khz):
    return round(khz / 1000.0, 1)


class Radio:
    """Radio FM Si4703 via I2C (Raspberry Pi 4).

    O Si4703 e um receptor FM com RDS endereçado em 0x10. Este modulo
    conversa com ele por `i2cget`/`i2cset` (i2c-tools), evitando dependencia
    obrigatoria de smbus. Sem hardware tudo degrada de forma graciosa.
    """

    def __init__(self, cfg, hub=None):
        self.cfg = cfg
        self.hub = hub
        self.lock = threading.Lock()
        self.thread = None
        self._stop = threading.Event()
        self.available = False
        self.reason = "nao iniciado"
        self.bus = int((cfg.get("radio") or {}).get("bus", 1))
        self.addr = I2C_ADDR
        self.power_on = False
        self.muted = False
        self.mono = False
        self.freq_khz = 89100
        self.freq = 89100
        self.stereo = False
        self.rssi = 0
        self.tuned = False
        self.rds_ps = ""
        self.rds_radio_text = ""
        self.rds_pi = ""
        self._ps = "        "
        self._rt = " " * 64
        self._ps_seg = None
        self.seeking = False
        self.source = "Rádio FM"
        self._bus = None
        self._api = ""

    # ------------------------------------------------------------------ config
    def _cfg(self):
        return self.cfg.get("radio") or {}

    def _tool(self, name):
        return shutil.which(name)

    # O Si4703 exige escrever os registradores 0x02..0x07 em sequencia, sem
    # byte de endereco, o que i2cset nao faz. Usamos smbus2 (ou smbus) quando
    # disponivel; sem eles o modulo apenas diagnostica e degrada.
    def _i2c_open(self):
        if self._bus is not None:
            return self._bus
        if HAVE_SMBUS2:
            self._bus = smbus2.SMBus(self.bus)
            self._api = "smbus2"
        elif HAVE_SMBUS:
            self._bus = smbus.SMBus(self.bus)
            self._api = "smbus"
        else:
            raise OSError("smbus2/smbus ausente (pip install smbus2)")
        return self._bus

    def _write_regs(self, start_reg, values):
        """Escreve registradores em sequencia a partir de start_reg (0x02..0x07).

        O Si4703 nao aceita byte de endereco no inicio da transacao; envia
        apenas as palavras na ordem, comecando em 0x02.
        """
        bus = self._i2c_open()
        data = bytearray()
        for v in values:
            data += struct.pack(">H", v & 0xFFFF)
        if self._api == "smbus2":
            msg = smbus2.i2c_msg.write(self.addr, list(data))
            bus.i2c_rdwr(msg)
        else:
            bus.write_i2c_block_data(self.addr, start_reg, list(data))

    def _read_regs_smbus(self):
        bus = self._i2c_open()
        if self._api == "smbus2":
            msg = smbus2.i2c_msg.read(self.addr, 32)
            bus.i2c_rdwr(msg)
            raw = bytes(msg)
        else:
            raw = bytes(bus.read_i2c_block_data(self.addr, REG_STATUSRSSI, 32))
        regs = [0] * 16
        # o primeiro byte recebido e 0x0A, depois 0x0B..0x0F, 0x00..0x09
        for i in range(16):
            hi = raw[i * 2]
            lo = raw[i * 2 + 1]
            regs[(REG_STATUSRSSI + i) % 16] = (hi << 8) | lo
        return regs

    def detect(self):
        reason = ""
        available = True
        if HAVE_SMBUS2 or HAVE_SMBUS:
            api = "smbus2" if HAVE_SMBUS2 else "smbus"
        elif self._tool("i2cget") and self._tool("i2cset"):
            api = "i2c-tools"
        else:
            api, available, reason = "", False, "smbus2/smbus ausente (pip install smbus2)"
        if available and not os.path.exists(f"/dev/i2c-{self.bus}"):
            available, reason = False, f"/dev/i2c-{self.bus} nao encontrado (ative o I2C)"
        return {
            "available": available,
            "reason": reason,
            "bus": self.bus,
            "address": f"0x{self.addr:02x}",
            "api": api,
            "smbus2": HAVE_SMBUS2,
            "smbus": HAVE_SMBUS,
            "i2cget": bool(self._tool("i2cget")),
            "i2cset": bool(self._tool("i2cset")),
        }

    # ----------------------------------------------------------------- hardware
    def _read_regs(self):
        if HAVE_SMBUS2 or HAVE_SMBUS:
            return self._read_regs_smbus()
        raise OSError("leitura I2C indisponivel (pip install smbus2)")

    def _control_regs(self, regs):
        """Monta as 6 palavras de controle (0x02..0x07) a partir de regs."""
        return [regs[r] for r in range(REG_POWERCFG, REG_TEST1 + 1)]

    def _write_control(self, regs):
        self._write_regs(REG_POWERCFG, self._control_regs(regs))

    def init_chip(self):
        """Configura o Si4703 na sequencia de power-up do datasheet.

        Ativa o oscilador (TEST1), zera ENABLE, aguarda o clock estabilizar e
        entao habilita o chip com RDS e o espacamento de canal desejado.
        """
        regs = self._read_regs()
        regs[REG_TEST1] = 0x8100  # XOSCEN
        regs[REG_POWERCFG] &= ~POWERCFG_ENABLE
        regs[REG_SYSCONFIG1] = 0x0000
        regs[REG_SYSCONFIG2] = 0x0000
        self._write_control(regs)
        time.sleep(0.5)

        regs = self._read_regs()
        powercfg = POWERCFG_ENABLE | POWERCFG_DMUTE
        if self._cfg().get("mono"):
            powercfg |= POWERCFG_MONO
        regs[REG_POWERCFG] = powercfg

        sys1 = regs[REG_SYSCONFIG1]
        if self._cfg().get("rds", True):
            sys1 |= SYSCONFIG1_RDS
        sys1 |= SYSCONFIG1_DE
        regs[REG_SYSCONFIG1] = sys1

        spacing = int(self._cfg().get("spacing", 2))
        band = int(self._cfg().get("band", 0))
        sys2 = regs[REG_SYSCONFIG2] & ~(0x3000 | 0x0030 | 0x000F)
        sys2 |= (band & 0x03) << 12
        sys2 |= (spacing & 0x03) << 4
        sys2 |= int(self._cfg().get("volume", 8)) & 0x0F
        regs[REG_SYSCONFIG2] = sys2
        self._write_control(regs)
        time.sleep(0.11)

        self.power_on = True
        self.available = True
        self.reason = ""
        self.set_frequency(self._cfg().get("frequency", 89.1))

    def power_off(self):
        try:
            regs = self._read_regs()
            regs[REG_POWERCFG] &= ~POWERCFG_ENABLE
            self._write_control(regs)
        except OSError:
            pass
        self.power_on = False

    def set_frequency(self, freq):
        khz = freq_to_khz(freq)
        if not khz:
            return False
        lo = int(self._cfg().get("min_khz", 87500))
        hi = int(self._cfg().get("max_khz", 108000))
        khz = max(lo, min(hi, khz))
        spacing = SPACING.get(int(self._cfg().get("spacing", 2)), 100)
        band = BAND.get(int(self._cfg().get("band", 0)), 87500)
        chan = int(round((khz - band) / spacing))
        with self.lock:
            self.freq_khz = band + chan * spacing
            self.freq = self.freq_khz
            self.tuned = False
        if not self.power_on:
            return True
        try:
            regs = self._read_regs()
            regs[REG_CHANNEL] = (chan & CHANNEL_MASK) | CHANNEL_TUNE
            self._write_control(regs)
        except OSError as exc:
            self.reason = str(exc)
            return False
        return True

    def seek(self, up=True):
        if not self.power_on:
            return False
        try:
            regs = self._read_regs()
            p = regs[REG_POWERCFG] & ~(POWERCFG_SEEK | POWERCFG_SEEKUP)
            if up:
                p |= POWERCFG_SEEKUP
            p |= POWERCFG_SEEK
            regs[REG_POWERCFG] = p
            self._write_control(regs)
            self.seeking = True
        except OSError as exc:
            self.reason = str(exc)
            return False
        return True

    def set_volume(self, level):
        level = max(0, min(15, int(level)))
        if not self.power_on:
            return level
        try:
            regs = self._read_regs()
            sys2 = (regs[REG_SYSCONFIG2] & ~0x000F) | level
            regs[REG_SYSCONFIG2] = sys2
            self._write_control(regs)
        except OSError:
            pass
        return level

    def set_muted(self, muted):
        self.muted = bool(muted)
        if not self.power_on:
            return self.muted
        try:
            regs = self._read_regs()
            p = regs[REG_POWERCFG]
            if self.muted:
                p &= ~POWERCFG_DMUTE
            else:
                p |= POWERCFG_DMUTE
            regs[REG_POWERCFG] = p
            self._write_control(regs)
        except OSError:
            pass
        return self.muted

    def set_mono(self, mono):
        self.mono = bool(mono)
        try:
            regs = self._read_regs()
            p = regs[REG_POWERCFG]
            if self.mono:
                p |= POWERCFG_MONO
            else:
                p &= ~POWERCFG_MONO
            regs[REG_POWERCFG] = p
            self._write_control(regs)
        except OSError:
            pass
        return self.mono

    # -------------------------------------------------------------------- loop
    def start(self):
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                return True
        self._stop.clear()
        self.available = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="radio")
        self.thread.start()
        return True

    def _run(self):
        info = self.detect()
        if not info["available"]:
            self.available = False
            self.reason = info["reason"]
            return
        try:
            self.init_chip()
        except OSError as exc:
            self.available = False
            self.reason = f"falha ao iniciar Si4703: {exc}"
            self.power_on = False
            return
        while not self._stop.is_set():
            try:
                self._poll()
            except OSError as exc:
                self.reason = str(exc)
                time.sleep(1.0)
                continue
            self._stop.wait(float(self._cfg().get("poll_s", 0.6)))

    def _poll(self):
        regs = self._read_regs()
        status = regs[REG_STATUSRSSI]
        chan = regs[REG_READCHAN] & CHANNEL_MASK
        spacing = SPACING.get(int(self._cfg().get("spacing", 2)), 100)
        band = BAND.get(int(self._cfg().get("band", 0)), 87500)
        with self.lock:
            self.rssi = status & RSSI_MASK
            self.stereo = bool(status & ST)  # ST bit: 1 = estereo
            self.tuned = bool(status & STC) and not bool(status & SF_BL)
            if chan:
                self.freq_khz = band + chan * spacing
                self.freq = self.freq_khz
            if self.seeking and (status & STC):
                self.seeking = False
            if status & RDSR:
                self._parse_rds(regs)
        self._publish()

    def _parse_rds(self, regs):
        pi = regs[REG_RDSA]
        if pi:
            self.rds_pi = f"{pi:04X}"
        block_b = regs[REG_RDSB]
        block_c = regs[REG_RDSC]
        block_d = regs[REG_RDSD]
        group = (block_b >> 12) & 0x0F
        if group == 0:
            seg = block_b & 0x03
            if self._ps_seg != (block_b, block_d):
                self._ps_seg = (block_b, block_d)
                pos = seg * 2
                chars = _ps_char(block_d >> 8) + _ps_char(block_d)
                self._ps = self._ps[:pos] + chars + self._ps[pos + 2:]
                self.rds_ps = self._ps.strip()
        elif group == 2 and (block_b & 0x0010):
            seg = block_b & 0x0F
            if seg <= 15:
                chars = _rt_char(block_c >> 8) + _rt_char(block_c) + \
                    _rt_char(block_d >> 8) + _rt_char(block_d)
                start = seg * 4
                text = self._rt[:start] + chars + self._rt[start + 4:]
                self._rt = text.ljust(64)[:64]
                self.rds_radio_text = self._rt.split("\r")[0].rstrip().strip()

    def _publish(self):
        if self.hub is None:
            return
        snap = {
            "power": self.power_on,
            "available": self.available,
            "freq": khz_to_mhz(self.freq_khz),
            "freq_khz": self.freq_khz,
            "stereo": self.stereo,
            "rssi": self.rssi,
            "tuned": self.tuned,
            "seeking": self.seeking,
            "muted": self.muted,
            "mono": self.mono,
            "ps": self.rds_ps,
            "rt": self.rds_radio_text,
            "pi": self.rds_pi,
            "station": (self.rds_ps or f"FM {khz_to_mhz(self.freq_khz)}"),
        }
        self.hub.set_radio(snap)

    def stop(self):
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        self.power_off()
        self._close_bus()

    def _close_bus(self):
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
            self._bus = None
            self._api = ""

    def shutdown(self):
        self.stop()

    def status(self):
        info = self.detect()
        return {
            "enabled": bool(self._cfg().get("enabled", True)),
            "available": self.available and info["available"],
            "reason": self.reason or info["reason"],
            "bus": self.bus,
            "address": f"0x{self.addr:02x}",
            "api": info["api"],
            "smbus2": info["smbus2"],
            "smbus": info["smbus"],
            "i2cget": info["i2cget"],
            "i2cset": info["i2cset"],
            "power": self.power_on,
            "seeking": self.seeking,
            "freq": khz_to_mhz(self.freq_khz),
            "freq_khz": self.freq_khz,
            "stereo": self.stereo,
            "rssi": self.rssi,
            "tuned": self.tuned,
            "muted": self.muted,
            "mono": self.mono,
            "ps": self.rds_ps,
            "rt": self.rds_radio_text,
            "pi": self.rds_pi,
            "station": (self.rds_ps or f"FM {khz_to_mhz(self.freq_khz)}"),
            "min_khz": int(self._cfg().get("min_khz", 87500)),
            "max_khz": int(self._cfg().get("max_khz", 108000)),
        }


def _ps_char(code):
    code &= 0xFF
    if code == 0:
        return " "
    if 32 <= code <= 126:
        return chr(code)
    return ""


def _rt_char(code):
    code &= 0xFF
    if code == 13:
        return ""
    if 32 <= code <= 126:
        return chr(code)
    return ""
