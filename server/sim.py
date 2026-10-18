import math
import random
import time


class Simulator:
    def __init__(self):
        self.t = 0.0
        self.speed = 0.0
        self.rpm = 800.0
        self.coolant = 18.0
        self.oilt = 18.0
        self.fuel = 64.0
        self.volt = 12.4
        self.oilp = 0.0
        self.ign = 1
        self.runtime = 0
        self.throttle = 0
        self.load = 10
        self.lt = 0
        self.rt = 0
        self.blk_t = 0.0
        self.next_blink = 12.0
        self.blink_side = "lt"
        self.target = 0.0
        self.next_target = 6.0
        self.brk = 0
        self.rev = 0
        self.dtc = []
        self.mil = 0
        self.injected = 0
        self._wall = time.time()
        self.lat = -23.5613
        self.lon = -46.6565
        self.alt = 760.0
        self.heading = 84.0
        self.hdg_target = 84.0
        self.sats = 0.0
        self.hdop = 0.9
        self.next_turn = 20.0

    def set_reverse(self, on):
        """Liga/desliga a marcha à ré simulada (para testar a câmera de ré)."""
        self.rev = 1 if on else 0
        return self.rev

    def inject_dtc(self, code="P0301"):
        if code in self.dtc:
            self.dtc.remove(code)
            self.injected -= 1
            if self.injected <= 0:
                self.mil = 0
            return "removed"
        self.dtc.append(code)
        self.injected += 1
        self.mil = 1
        return "added"

    def tick(self, dt: float) -> dict:
        dt = min(dt, 0.5)
        self.t += dt
        self.runtime += int(dt)

        if self.t >= self.next_target:
            self.next_target = self.t + random.uniform(7, 16)
            r = random.random()
            if r < 0.18:
                self.target = 0.0
            elif r < 0.32:
                self.target = random.uniform(30, 50)
            else:
                self.target = random.uniform(55, 105)

        diff = self.target - self.speed
        if diff > 0.5:
            accel = min(diff, 4.5)
            self.throttle = min(78, 18 + diff * 6)
            self.load = min(85, 25 + diff * 5)
        elif diff < -1.0:
            accel = max(diff, -7.5)
            self.throttle = 0
            self.load = 14
        else:
            accel = 0
            self.throttle = 6 + 3 * math.sin(self.t * 0.7)
            self.load = 22 + 6 * math.sin(self.t * 0.5)

        self.speed = max(0.0, self.speed + accel * dt)
        if self.speed < 0.4:
            self.speed = 0.0
        self.brk = 1 if self.speed < 0.5 else 0

        gear_target = 820 + self.speed * 42 + self.throttle * 4
        self.rpm += (gear_target - self.rpm) * min(1.0, dt * 3.2)
        self.rpm = max(750.0, min(6400.0, self.rpm))

        warm = 88.0 if self.ign else 16.0
        self.coolant += (warm - self.coolant) * dt * (0.045 if self.ign else 0.01)
        self.oilt += (self.coolant + 4 - self.oilt) * dt * 0.05

        if self.speed > 1:
            rate = 8.5 * self.speed / (3600.0 * 55.0)
            self.fuel = max(0.0, self.fuel - dt * rate)
        elif self.ign:
            self.fuel = max(0.0, self.fuel - dt * 0.00045)

        self.volt = 14.15 + 0.1 * math.sin(self.t * 1.7) if self.rpm > 600 else 12.35
        if self.speed > 1:
            self.oilp = 28 + self.speed * 0.28 + 4 * math.sin(self.t)
        else:
            self.oilp = 9 + (2 if self.rpm > 900 else 0)

        if self.t >= self.next_blink and (self.speed > 2 or random.random() < 0.3):
            self.blk_t = 3.4
            self.next_blink = self.t + random.uniform(25, 55)
            self.blink_side = "lt" if random.random() < 0.5 else "rt"
        if self.blk_t > 0:
            self.blk_t -= dt
            on = int(self.t * 2.0) % 2 == 0
            self.lt = on and self.blink_side == "lt"
            self.rt = on and self.blink_side == "rt"
        else:
            self.lt = 0
            self.rt = 0

        self._gps_tick(dt)

        return {
            "v": 1,
            "board": "sim",
            "adc": 10,
            "ms": int(self.t * 1000),
            "obd": 1,
            "mil": self.mil,
            "dtcn": len(self.dtc),
            "speed": int(round(self.speed)),
            "rpm": int(round(self.rpm)),
            "coolant": int(round(self.coolant)),
            "iat": int(round(26 + 4 * math.sin(self.t * 0.05))),
            "oilt": int(round(self.oilt)),
            "throttle": int(round(max(0, min(100, self.throttle)))),
            "fuel": int(round(self.fuel)),
            "volt": round(self.volt, 2),
            "oilp": round(self.oilp, 1),
            "batt": round(self.volt, 2),
            "runtime": self.runtime,
            "load": int(round(max(0, min(100, self.load)))),
            "hl": 1,
            "hb": 0,
            "lt": int(self.lt),
            "rt": int(self.rt),
            "hz": 0,
            "brk": int(self.brk),
            "rev": int(self.rev),
            "sbl": 0,
            "door": 0,
            "ign": self.ign,
            "fan": 0,
            "ac": 0,
            "dtc": list(self.dtc),
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "alt": round(self.alt, 1),
            "sats": int(round(self.sats)),
            "hdop": round(self.hdop, 2),
            "gspd": round(self.speed, 1),
            "hdg": round(self.heading, 1),
            "fix": 1 if self.sats >= 4 else 0,
            "utc": time.strftime("%H%M%S", time.gmtime()),
            "_src": "sim",
        }

    def _gps_tick(self, dt):
        if self.t >= self.next_turn:
            self.next_turn = self.t + random.uniform(8, 22)
            self.hdg_target = random.uniform(0, 360)
        delta = (self.hdg_target - self.heading + 540) % 360 - 180
        self.heading = (self.heading + delta * min(1.0, dt * 0.4)) % 360
        dist_km = self.speed * dt / 3600.0
        if dist_km > 0:
            rad = math.radians(self.heading)
            self.lat += (dist_km / 111.32) * math.cos(rad)
            denom = 111.32 * max(0.2, math.cos(math.radians(self.lat)))
            self.lon += (dist_km / denom) * math.sin(rad)
        target_sats = 0.0 if self.t < 2.5 else 9.0
        self.sats += (target_sats - self.sats) * min(1.0, dt * 0.6)
        self.hdop = 0.9 + 0.3 * math.sin(self.t * 0.3)

    @property
    def wall_age(self) -> float:
        return time.time() - self._wall
