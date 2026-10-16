THRESH_ORDER = {"info": 0, "warn": 1, "crit": 2}


class AlertEngine:
    def __init__(self, thresholds: dict, capacity_l: float, consumption: float):
        self.t = thresholds
        self.capacity = capacity_l
        self.consumption = consumption
        self.hold = {}
        self.active = {}
        self.acked = set()
        self.rules = [
            ("comm", self._comm, 6, "warn"),
            ("coolant", self._coolant, 3, None),
            ("volt", self._volt, 4, None),
            ("fuel", self._fuel, 4, "warn"),
            ("oil", self._oil, 4, None),
            ("mil", self._mil, 3, None),
            ("rpm", self._rpm, 4, "warn"),
            ("handbrake", self._handbrake, 3, "crit"),
            ("seatbelt", self._seatbelt, 8, "warn"),
            ("door", self._door, 5, "warn"),
        ]

    @staticmethod
    def _comm(s, _):
        if s.get("conn") == "off":
            return ("warn", "Sem comunicação", "Verifique o Arduino e o cabo USB")
        return None

    @staticmethod
    def _coolant(s, t):
        v = s.get("coolant")
        if v is None:
            return None
        if v >= t["coolant_crit_c"]:
            return ("crit", "Superaquecimento", f"Água do motor a {v:.0f} °C")
        if v >= t["coolant_warn_c"]:
            return ("warn", "Motor quente", f"Água do motor a {v:.0f} °C")
        return None

    @staticmethod
    def _volt(s, t):
        v = s.get("volt") or s.get("batt") or 0
        if v and v <= t["volt_crit_v"]:
            return ("crit", "Bateria fraca", f"Tensão {v:.1f} V")
        if v and v <= t["volt_warn_v"]:
            return ("warn", "Bateria baixa", f"Tensão {v:.1f} V")
        return None

    def _fuel(self, s, _):
        f = s.get("fuel")
        if f is None:
            return None
        if f <= self.t["fuel_warn_pct"]:
            km = (f / 100.0) * self.capacity / (self.consumption / 100.0)
            return ("warn", "Combustível baixo", f"{f:.0f}% · ~{km:.0f} km restantes")
        return None

    @staticmethod
    def _oil(s, t):
        p, rpm = s.get("oilp"), s.get("rpm") or 0
        if p is None or rpm < 900:
            return None
        if p <= t["oil_crit_psi"]:
            return ("crit", "Pressão do óleo", f"{p:.0f} psi")
        if p <= t["oil_warn_psi"]:
            return ("warn", "Óleo baixo", f"{p:.0f} psi")
        return None

    @staticmethod
    def _mil(s, _):
        if s.get("mil"):
            n = s.get("dtc_count") or len(s.get("dtc") or [])
            return ("warn", "Injeção eletrônica", f"{n} código(s) de falha")
        return None

    @staticmethod
    def _rpm(s, t):
        r = s.get("rpm") or 0
        if t["rpm_warn"] and r >= t["rpm_warn"]:
            return ("warn", "Alta rotação", f"{r:.0f} rpm")
        return None

    @staticmethod
    def _handbrake(s, _):
        if s.get("brk") and (s.get("speed") or 0) > 5:
            return ("crit", "Freio de mão", "Veículo em movimento")
        return None

    @staticmethod
    def _seatbelt(s, _):
        if s.get("sbl") and (s.get("speed") or 0) > 10:
            return ("warn", "Cinto desabotoado", "Abotoe o cinto")
        return None

    @staticmethod
    def _door(s, _):
        if s.get("door") and (s.get("speed") or 0) > 3:
            return ("warn", "Porta aberta", "Veículo em movimento")
        return None

    def update(self, state: dict) -> list:
        out = []
        for aid, fn, need, fixed_level in self.rules:
            res = fn(state, self.t)
            if res is None:
                self.hold[aid] = 0
                self.active.pop(aid, None)
                self.acked.discard(aid)
                continue
            level, title, text = res
            if fixed_level:
                level = fixed_level
            self.hold[aid] = self.hold.get(aid, 0) + 1
            if self.hold[aid] < need:
                continue
            prev = self.active.get(aid)
            if prev and prev["level"] == level and prev["text"] == text:
                continue
            self.active[aid] = {
                "id": aid,
                "level": level,
                "title": title,
                "text": text,
                "ts": state.get("ts"),
            }
        for aid in list(self.acked):
            if aid not in self.active:
                self.acked.discard(aid)
        return [
            a for aid, a in sorted(
                self.active.items(),
                key=lambda kv: -THRESH_ORDER[kv[1]["level"]],
            )
            if aid not in self.acked
        ]

    def ack(self, alert_id: str):
        if alert_id in self.active:
            self.acked.add(alert_id)
            return True
        return False

    def ack_all(self):
        self.acked |= set(self.active)
