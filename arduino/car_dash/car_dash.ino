#include <SPI.h>
#include <mcp_can.h>
#include "config.h"

struct Vehicle {
  uint8_t obd_ok = 0;
  uint8_t mil = 0;
  uint8_t dtc_count = 0;
  uint16_t speed = 0;
  uint16_t rpm = 0;
  int16_t coolant = 20;
  int16_t iat = 20;
  int16_t oilt = 20;
  uint8_t throttle = 0;
  uint8_t fuel = 50;
  uint8_t load = 0;
  float volt = 12.6f;
  float oilp = 0.0f;
  float batt = 12.6f;
  uint32_t runtime = 0;
  uint8_t hl = 0, hb = 0, lt = 0, rt = 0, hz = 0, brk = 0;
  uint8_t sbl = 0, sbr = 0, door = 0, ign = 1;
  uint8_t rev = 0;
  uint8_t fan = 0, ac = 0;
};

static mcp_can CAN(PIN_CS_CAN);

static char dtcList[16][6];
static uint8_t dtcN = 0;
static uint8_t wantDtcRead = 0;
static uint8_t wantDtcClear = 0;

static uint8_t inputPin[] = {PIN_LEFT, PIN_RIGHT, PIN_HEADLIGHT, PIN_HIGHBEAM,
                             PIN_HANDBRAKE, PIN_SEATBELT, PIN_DOOR, PIN_HAZARD,
                             PIN_IGNITION};
static uint8_t inputVal[9];
static uint32_t inputLast[9];

static uint8_t revVal = 0;
static uint32_t revLast = 0;

static uint32_t lastJson = 0;
static uint32_t lastAnalog = 0;
static uint32_t lastSlot = 0;
static uint32_t beepUntil = 0;

static const uint8_t obdPids[] = {0x0C, 0x0D, 0x05, 0x0F, 0x11, 0x2F,
                                  0x42, 0x04, 0x1F, 0x01, 0x5C, 0x21};
static const uint8_t obdPidN = sizeof(obdPids);
static uint8_t pidIdx = 0;
static uint8_t phase = 0;
static uint8_t retries = 0;
static uint32_t reqAt = 0;
static uint8_t reqMode = 0x01;
static uint8_t reqPid = 0;

static uint8_t rxData[64];
static uint8_t rxLen = 0;
static uint8_t isoActive = 0;
static uint16_t isoExpect = 0;
static uint16_t isoGot = 0;
static uint8_t isoSeq = 0;

static char lineBuf[RX_BUF_SIZE];
static uint16_t lineLen = 0;

static uint32_t demoSpeedT = 0;
static float demoCoolant = 20.0f;
static float demoFuel = 61.0f;

static char gpsLine[GPS_BUF_SIZE];
static uint8_t gpsLen = 0;
static float gpsLat = 0.0f;
static float gpsLon = 0.0f;
static float gpsAlt = 0.0f;
static float gpsHdop = 0.0f;
static float gpsSpeed = 0.0f;
static float gpsHeading = 0.0f;
static uint8_t gpsSats = 0;
static uint8_t gpsFix = 0;
static char gpsUtc[8] = "000000";
static uint32_t gpsLast = 0;

class Jw {
  char buf[STATE_SIZE];
  uint16_t n = 0;
  bool first = true;
 public:
  void begin() {
    n = 0;
    first = true;
    buf[0] = '{';
    n = 1;
  }
  bool key(const char* k) {
    uint16_t need = (uint16_t)strlen(k) + 4;
    if (n + need >= STATE_SIZE) return false;
    if (!first) buf[n++] = ',';
    first = false;
    buf[n++] = '"';
    memcpy(buf + n, k, strlen(k));
    n += strlen(k);
    buf[n++] = '"';
    buf[n++] = ':';
    return true;
  }
  void putInt(long v) {
    if (n + 16 >= STATE_SIZE) return;
    n += sprintf(buf + n, "%ld", v);
  }
  void putUInt(unsigned long v) {
    if (n + 16 >= STATE_SIZE) return;
    n += sprintf(buf + n, "%lu", v);
  }
  void putFloat(float v, uint8_t dec) {
    if (n + 24 >= STATE_SIZE) return;
    unsigned long scale = 1;
    for (uint8_t i = 0; i < dec; i++) scale *= 10;
    float x = v;
    if (x < 0) {
      buf[n++] = '-';
      x = -x;
    }
    long whole = (long)x;
    long frac = (long)((x - (float)whole) * scale + 0.5f);
    if (frac >= (long)scale) {
      whole += 1;
      frac = 0;
    }
    if (dec == 0) {
      n += sprintf(buf + n, "%ld", whole);
      return;
    }
    char fmt[12];
    snprintf(fmt, sizeof(fmt), "%%ld.%%0%dlu", dec);
    n += sprintf(buf + n, fmt, whole, frac);
  }
  void i(const char* k, long v) {
    if (key(k)) putInt(v);
  }
  void u(const char* k, unsigned long v) {
    if (key(k)) putUInt(v);
  }
  void f(const char* k, float v, uint8_t dec) {
    if (key(k)) putFloat(v, dec);
  }
  void s(const char* k, const char* v) {
    if (!key(k)) return;
    uint16_t l = (uint16_t)strlen(v);
    if (n + l + 3 >= STATE_SIZE) return;
    buf[n++] = '"';
    memcpy(buf + n, v, l);
    n += l;
    buf[n++] = '"';
  }
  void arr(const char* k) {
    if (key(k)) {
      buf[n++] = '[';
    }
  }
  void arrStr(const char* s) {
    if (n + 10 >= STATE_SIZE) return;
    if (buf[n - 1] != '[') buf[n++] = ',';
    buf[n++] = '"';
    memcpy(buf + n, s, strlen(s));
    n += strlen(s);
    buf[n++] = '"';
  }
  void arrEnd() {
    buf[n++] = ']';
  }
  const char* done() {
    buf[n++] = '}';
    buf[n] = 0;
    return buf;
  }
  uint16_t len() { return n; }
};

static Jw jw;

static void fmtDtc(char* dst, uint16_t v) {
  const char* letters = "PCBU";
  dst[0] = letters[(v >> 14) & 0x03];
  dst[1] = "0123"[(v >> 12) & 0x03];
  dst[2] = "0123456789ABCDEF"[(v >> 8) & 0x0F];
  dst[3] = "0123456789ABCDEF"[(v >> 4) & 0x0F];
  dst[4] = "0123456789ABCDEF"[v & 0x0F];
  dst[5] = 0;
}

static int dtcFind(const char* code) {
  for (uint8_t i = 0; i < dtcN; i++) {
    if (strcmp(dtcList[i], code) == 0) return (int)i;
  }
  return -1;
}

static void dtcAdd(uint16_t v) {
  char code[6];
  fmtDtc(code, v);
  if (dtcFind(code) >= 0) return;
  if (dtcN >= 16) return;
  memcpy(dtcList[dtcN], code, 6);
  dtcN++;
}

static void dtcClearAll() { dtcN = 0; }

static bool jsonGetStr(const char* body, const char* key, char* out, uint8_t max) {
  char pat[32];
  snprintf(pat, sizeof(pat), "\"%s\"", key);
  const char* p = strstr(body, pat);
  if (!p) return false;
  p = strchr(p + strlen(pat), ':');
  if (!p) return false;
  p++;
  while (*p == ' ' || *p == '\t') p++;
  if (*p != '"') return false;
  p++;
  uint8_t i = 0;
  while (*p && *p != '"' && i < max - 1) out[i++] = *p++;
  out[i] = 0;
  return i > 0;
}

static bool jsonGetInt(const char* body, const char* key, long* out) {
  char pat[32];
  snprintf(pat, sizeof(pat), "\"%s\"", key);
  const char* p = strstr(body, pat);
  if (!p) return false;
  p = strchr(p + strlen(pat), ':');
  if (!p) return false;
  p++;
  while (*p == ' ' || *p == '\t') p++;
  bool neg = false;
  if (*p == '-') {
    neg = true;
    p++;
  }
  if (*p < '0' || *p > '9') return false;
  long v = 0;
  while (*p >= '0' && *p <= '9') {
    v = v * 10 + (*p - '0');
    p++;
  }
  *out = neg ? -v : v;
  return true;
}

static void applyClimate() {
  digitalWrite(PIN_RELAY_FAN, veh.fan > 0 ? HIGH : LOW);
  digitalWrite(PIN_RELAY_AC, (veh.ac && veh.fan > 0) ? HIGH : LOW);
}

static void handleLine(char* body) {
  char cmd[24];
  if (!jsonGetStr(body, "cmd", cmd, sizeof(cmd))) return;
  if (strcmp(cmd, "dtc_read") == 0) {
    wantDtcRead = 1;
  } else if (strcmp(cmd, "dtc_clear") == 0) {
    wantDtcClear = 1;
  } else if (strcmp(cmd, "beep") == 0) {
    long ms = 200;
    jsonGetInt(body, "ms", &ms);
    if (ms < 20) ms = 20;
    if (ms > 3000) ms = 3000;
    beepUntil = millis() + (uint32_t)ms;
    digitalWrite(PIN_BUZZER, HIGH);
  } else if (strcmp(cmd, "climate") == 0) {
    long v;
    if (jsonGetInt(body, "fan", &v)) veh.fan = constrain(v, 0, 4);
    if (jsonGetInt(body, "ac", &v)) veh.ac = v ? 1 : 0;
    applyClimate();
  } else if (strcmp(cmd, "reset") == 0) {
    void (*rebootFn)(void) = 0;
    rebootFn();
  }
}

static void pollSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      lineBuf[lineLen] = 0;
      if (lineLen > 2) handleLine(lineBuf);
      lineLen = 0;
    } else if (c != '\r') {
      if (lineLen < RX_BUF_SIZE - 1) lineBuf[lineLen++] = c;
    }
  }
}

static const char* nmeaField(const char* s, uint8_t idx, char* out, uint8_t outMax) {
  uint8_t n = 0;
  const char* p = s;
  while (n < idx) {
    p = strchr(p, ',');
    if (!p) return NULL;
    p++;
    n++;
  }
  uint8_t i = 0;
  while (*p && *p != ',' && *p != '*' && i < outMax - 1) out[i++] = *p++;
  out[i] = 0;
  return out;
}

static float nmeaCoord(const char* dm, const char* hemi) {
  float v = atof(dm);
  int deg = (int)(v / 100.0f);
  float min = v - (float)deg * 100.0f;
  float d = (float)deg + min / 60.0f;
  if (hemi && (hemi[0] == 'S' || hemi[0] == 'W')) d = -d;
  return d;
}

static void parseGpsLine(char* line) {
  if (line[0] != '$') return;
  const char* tag = line + 1;
  char f[24];
  if (strstr(tag, "RMC")) {
    nmeaField(line, 2, f, sizeof(f));
    gpsFix = (f[0] == 'A') ? 1 : 0;
    if (nmeaField(line, 1, f, sizeof(f)) && strlen(f) >= 6) {
      memcpy(gpsUtc, f, 6);
      gpsUtc[6] = 0;
    }
    char lat[16], ns[4], lon[16], ew[4];
    if (nmeaField(line, 3, lat, sizeof(lat)) && nmeaField(line, 4, ns, sizeof(ns)) && lat[0])
      gpsLat = nmeaCoord(lat, ns);
    if (nmeaField(line, 5, lon, sizeof(lon)) && nmeaField(line, 6, ew, sizeof(ew)) && lon[0])
      gpsLon = nmeaCoord(lon, ew);
    if (nmeaField(line, 7, f, sizeof(f)) && f[0]) gpsSpeed = atof(f) * 1.852f;
    if (nmeaField(line, 8, f, sizeof(f)) && f[0]) gpsHeading = atof(f);
    gpsLast = millis();
  } else if (strstr(tag, "GGA")) {
    char lat[16], ns[4], lon[16], ew[4];
    if (nmeaField(line, 2, lat, sizeof(lat)) && nmeaField(line, 3, ns, sizeof(ns)) && lat[0]) {
      gpsLat = nmeaCoord(lat, ns);
      gpsFix = 1;
    }
    if (nmeaField(line, 4, lon, sizeof(lon)) && nmeaField(line, 5, ew, sizeof(ew)) && lon[0])
      gpsLon = nmeaCoord(lon, ew);
    if (nmeaField(line, 6, f, sizeof(f)) && f[0]) gpsFix = (f[0] == '0') ? 0 : 1;
    if (nmeaField(line, 7, f, sizeof(f)) && f[0]) gpsSats = (uint8_t)atoi(f);
    if (nmeaField(line, 8, f, sizeof(f)) && f[0]) gpsHdop = atof(f);
    if (nmeaField(line, 9, f, sizeof(f)) && f[0]) gpsAlt = atof(f);
    gpsLast = millis();
  }
}

static void pollGps() {
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    if (c == '\n') {
      gpsLine[gpsLen] = 0;
      if (gpsLen > 6) parseGpsLine(gpsLine);
      gpsLen = 0;
    } else if (c != '\r') {
      if (gpsLen < GPS_BUF_SIZE - 1) gpsLine[gpsLen++] = c;
      else gpsLen = 0;
    }
  }
  if (gpsLast && millis() - gpsLast > GPS_TIMEOUT_MS) gpsFix = 0;
}

static void pollInputs() {
  for (uint8_t i = 0; i < sizeof(inputPin); i++) {
    uint8_t raw = digitalRead(inputPin[i]);
#if INPUT_ACTIVE_LOW
    raw = raw ? 0 : 1;
#endif
    if (raw != inputVal[i] && millis() - inputLast[i] > DEBOUNCE_MS) {
      inputVal[i] = raw;
      inputLast[i] = millis();
    }
  }
  veh.lt = inputVal[0];
  veh.rt = inputVal[1];
  veh.hl = inputVal[2];
  veh.hb = inputVal[3];
  veh.brk = inputVal[4];
  veh.sbl = inputVal[5];
  veh.door = inputVal[6];
  veh.hz = inputVal[7];
  veh.ign = inputVal[8];

  uint8_t rawRev = digitalRead(PIN_REVERSE);
#if INPUT_ACTIVE_LOW
  rawRev = rawRev ? 0 : 1;
#endif
  if (rawRev != revVal && millis() - revLast > DEBOUNCE_MS) {
    revVal = rawRev;
    revLast = millis();
  }
  veh.rev = revVal;
}

static void pollAnalog() {
  float v;
  v = ADC_VREF * analogRead(PIN_BATT_SENSE) / 1023.0f;
  veh.batt = v * BATT_DIVIDER;
  v = ADC_VREF * analogRead(PIN_OIL_PRESS) / 1023.0f;
  veh.oilp = ((v - OIL_PSI_MIN_V) / (OIL_PSI_MAX_V - OIL_PSI_MIN_V)) * OIL_PSI_MAX;
  if (veh.oilp < 0) veh.oilp = 0;
  if (veh.oilp > OIL_PSI_MAX) veh.oilp = OIL_PSI_MAX;
  long adc = analogRead(PIN_FUEL_LEVEL);
  float pct = 100.0f * (adc - FUEL_ADC_EMPTY) / (FUEL_ADC_FULL - FUEL_ADC_EMPTY);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  if (!veh.obd_ok) veh.fuel = (uint8_t)pct;
  v = ADC_VREF * analogRead(PIN_OIL_TEMP) / 1023.0f;
  veh.oilt = (int16_t)(v * OILT_SCALE - 40.0f);
}

static void obdRequest(uint8_t mode, uint8_t pid, uint16_t id) {
  uint8_t tx[8] = {0x02, mode, pid, 0, 0, 0, 0, 0};
  if (mode == 0x03 || mode == 0x04) {
    tx[0] = 0x01;
    tx[2] = 0;
  }
  CAN.sendMsgBuf(id, 0, 8, tx);
}

static void parsePid(uint8_t pid, const uint8_t* d, uint8_t n) {
  if (n < 1) return;
  switch (pid) {
    case 0x0C:
      if (n >= 2) veh.rpm = (uint16_t)(((uint16_t)d[0] << 8) | d[1]) / 4;
      break;
    case 0x0D:
      veh.speed = d[0];
      break;
    case 0x05:
      veh.coolant = (int16_t)d[0] - 40;
      break;
    case 0x0F:
      veh.iat = (int16_t)d[0] - 40;
      break;
    case 0x11:
      veh.throttle = (uint8_t)(((uint16_t)d[0] * 100) / 255);
      break;
    case 0x2F:
      veh.fuel = (uint8_t)(((uint16_t)d[0] * 100) / 255);
      break;
    case 0x42:
      if (n >= 2) veh.volt = (((uint16_t)d[0] << 8) | d[1]) / 1000.0f;
      break;
    case 0x04:
      veh.load = (uint8_t)(((uint16_t)d[0] * 100) / 255);
      break;
    case 0x1F:
      if (n >= 2) veh.runtime = ((uint16_t)d[0] << 8) | d[1];
      break;
    case 0x01:
      veh.mil = (d[0] & 0x80) ? 1 : 0;
      veh.dtc_count = d[0] & 0x7F;
      break;
    case 0x5C:
      veh.oilt = (int16_t)d[0] - 40;
      break;
    case 0x21:
      break;
    default:
      break;
  }
}

static void processResponse() {
  if (rxLen < 2) return;
  uint8_t mode = rxData[0];
  if (mode == 0x7F) {
    phase = 0;
    return;
  }
  if (mode == 0x41) {
    if (rxLen >= 3 && rxData[1] == reqPid) {
      parsePid(reqPid, &rxData[2], rxLen - 2);
      phase = 0;
      retries = 0;
    }
    return;
  }
  if (mode == 0x43) {
    if (wantDtcClear) {
      phase = 0;
      return;
    }
    dtcClearAll();
    for (uint8_t i = 1; i + 1 < rxLen; i += 2) {
      uint16_t v = ((uint16_t)rxData[i] << 8) | rxData[i + 1];
      if (v) dtcAdd(v);
    }
    wantDtcRead = 0;
    phase = 0;
    retries = 0;
    return;
  }
  if (mode == 0x44) {
    dtcClearAll();
    veh.mil = 0;
    veh.dtc_count = 0;
    wantDtcClear = 0;
    wantDtcRead = 1;
    phase = 0;
    retries = 0;
    return;
  }
}

static void feedFrame(uint32_t id, const uint8_t* b, uint8_t len) {
  if (id < 0x7E8 || id > 0x7EF || len < 1) return;
  uint8_t pci = b[0];
  if ((pci & 0xF0) == 0x00) {
    uint8_t n = pci & 0x0F;
    if (n + 1 > len) return;
    memcpy(rxData, b + 1, n);
    rxLen = n;
    isoActive = 0;
    processResponse();
  } else if ((pci & 0xF0) == 0x10) {
    isoExpect = (((uint16_t)(pci & 0x0F)) << 8) | b[1];
    if (isoExpect > sizeof(rxData)) isoExpect = sizeof(rxData);
    isoGot = 0;
    isoSeq = 1;
    isoActive = 1;
    memcpy(rxData, b + 3, 5);
    isoGot = 5;
    uint8_t fc[8] = {0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    CAN.sendMsgBuf(id, 0, 8, fc);
  } else if ((pci & 0xF0) == 0x20) {
    if (!isoActive) return;
    if ((pci & 0x0F) != isoSeq) {
      isoActive = 0;
      return;
    }
    isoSeq++;
    uint8_t space = isoExpect - isoGot;
    uint8_t take = len - 1;
    if (take > space) take = space;
    memcpy(rxData + isoGot, b + 1, take);
    isoGot += take;
    if (isoGot >= isoExpect) {
      rxLen = isoExpect;
      isoActive = 0;
      processResponse();
    }
  }
}

static void obdTick() {
  if (!veh.obd_ok) return;
  while (CAN.checkReceive() == CAN_MSGAVAIL) {
      uint32_t id;
      uint8_t len;
      uint8_t b[8];
      CAN.readMsgBuf(&len, b, &id);
      feedFrame(id, b, len);
  }
  if (phase == 1) {
    if (millis() - reqAt > OBD_TIMEOUT_MS) {
      retries++;
      if (retries >= OBD_RETRY_MAX) {
        phase = 0;
        retries = 0;
        pidIdx = (pidIdx + 1) % obdPidN;
      } else {
        obdRequest(reqMode, reqPid, 0x7DF);
        reqAt = millis();
      }
    }
    return;
  }
  if (millis() - lastSlot < OBD_SLOT_MS) return;
  lastSlot = millis();
  if (wantDtcClear) {
    reqMode = 0x04;
    reqPid = 0;
  } else if (wantDtcRead) {
    reqMode = 0x03;
    reqPid = 0;
  } else {
    reqMode = 0x01;
    reqPid = obdPids[pidIdx];
    pidIdx = (pidIdx + 1) % obdPidN;
  }
  retries = 1;
  phase = 1;
  obdRequest(reqMode, reqPid, 0x7DF);
  reqAt = millis();
}

static void demoTick() {
  if (veh.obd_ok) return;
  if (millis() - demoSpeedT > 400) {
    demoSpeedT = millis();
    static uint8_t phaseN = 0;
    phaseN = (phaseN + 1) % 12;
    if (veh.ign) {
      static int16_t target = 0;
      if (phaseN == 0) target = 40 + random(80);
      if (phaseN == 6) target = random(20);
      veh.speed += (target - veh.speed) / 4;
      if (abs(veh.speed - target) < 2) veh.speed = target;
      veh.rpm = 850 + veh.speed * 38 + random(60);
      if (veh.rpm > 6200) veh.rpm = 6200;
      veh.throttle = veh.speed > 0 ? 12 + random(30) : 3;
      veh.load = veh.speed > 0 ? 25 + random(35) : 12;
      veh.volt = 14.1f + random(3) * 0.1f;
      veh.oilp = veh.speed > 0 ? 35 + veh.speed / 4 + random(6) : 8;
      veh.runtime += 1;
      if (demoCoolant < 88) demoCoolant += 0.15f;
      if (veh.speed > 0 && demoFuel > 4) demoFuel -= 0.004f;
      veh.fuel = (uint8_t)demoFuel;
      veh.coolant = (int16_t)demoCoolant;
      veh.oilt = (int16_t)(demoCoolant - 4);
      veh.iat = 28 + random(4);
      veh.mil = (dtcN > 0) ? 1 : 0;
      veh.dtc_count = dtcN;
    } else {
      veh.speed = 0;
      veh.rpm = 0;
      veh.throttle = 0;
      veh.load = 0;
      veh.volt = 12.4f;
      veh.oilp = 0;
    }
  }
}

static void sendJson() {
  jw.begin();
  jw.i("v", FW_VERSION);
  jw.u("ms", millis());
  jw.i("obd", veh.obd_ok);
  jw.i("mil", veh.mil);
  jw.i("dtcn", veh.dtc_count);
  jw.i("speed", veh.speed);
  jw.i("rpm", veh.rpm);
  jw.i("coolant", veh.coolant);
  jw.i("iat", veh.iat);
  jw.i("oilt", veh.oilt);
  jw.i("throttle", veh.throttle);
  jw.i("fuel", veh.fuel);
  jw.f("volt", veh.volt, 2);
  jw.f("oilp", veh.oilp, 1);
  jw.f("batt", veh.batt, 2);
  jw.u("runtime", veh.runtime);
  jw.i("load", veh.load);
  jw.i("hl", veh.hl);
  jw.i("hb", veh.hb);
  jw.i("lt", veh.lt);
  jw.i("rt", veh.rt);
  jw.i("hz", veh.hz);
  jw.i("brk", veh.brk);
  jw.i("rev", veh.rev);
  jw.i("sbl", veh.sbl);
  jw.i("door", veh.door);
  jw.i("ign", veh.ign);
  jw.i("fan", veh.fan);
  jw.i("ac", veh.ac);
  jw.i("fix", gpsFix);
  jw.f("lat", gpsLat, 6);
  jw.f("lon", gpsLon, 6);
  jw.f("alt", gpsAlt, 1);
  jw.i("sats", gpsSats);
  jw.f("hdop", gpsHdop, 2);
  jw.f("gspd", gpsSpeed, 1);
  jw.f("hdg", gpsHeading, 1);
  jw.s("utc", gpsUtc);
  jw.arr("dtc");
  for (uint8_t i = 0; i < dtcN; i++) jw.arrStr(dtcList[i]);
  jw.arrEnd();
  const char* out = jw.done();
  Serial.write((const uint8_t*)out, jw.len());
  Serial.write('\n');
}

static void initCan() {
  veh.obd_ok = 0;
#if CAN_CLOCK_16MHZ
  if (CAN.begin(MCP_ANY, CAN_SPEED_500K ? CAN_500KBPS : CAN_250KBPS, MCP_16MHZ) == CAN_OK) {
    veh.obd_ok = 1;
  } else if (CAN.begin(MCP_ANY, CAN_SPEED_500K ? CAN_500KBPS : CAN_250KBPS, MCP_8MHZ) == CAN_OK) {
    veh.obd_ok = 1;
  }
#else
  if (CAN.begin(MCP_ANY, CAN_SPEED_500K ? CAN_500KBPS : CAN_250KBPS, MCP_8MHZ) == CAN_OK) {
    veh.obd_ok = 1;
  }
#endif
  if (veh.obd_ok) {
    CAN.setMode(MCP_NORMAL);
    wantDtcRead = 1;
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
#if GPS_ENABLED
  Serial1.begin(GPS_BAUD);
#endif
  for (uint8_t i = 0; i < sizeof(inputPin); i++) {
    pinMode(inputPin[i], INPUT_PULLUP);
    inputVal[i] = 0;
    inputLast[i] = 0;
  }
  pinMode(PIN_REVERSE, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_RELAY_FAN, OUTPUT);
  pinMode(PIN_RELAY_AC, OUTPUT);
  applyClimate();
  SPI.begin();
  initCan();
  randomSeed(analogRead(A7));
  digitalWrite(PIN_LED, HIGH);
}

void loop() {
  uint32_t now = millis();
  if (beepUntil && now > beepUntil) {
    beepUntil = 0;
    digitalWrite(PIN_BUZZER, LOW);
  }
  pollSerial();
#if GPS_ENABLED
  pollGps();
#endif
  pollInputs();
  if (now - lastAnalog >= ANALOG_INTERVAL_MS) {
    lastAnalog = now;
    pollAnalog();
  }
  obdTick();
  demoTick();
  if (now - lastJson >= JSON_INTERVAL_MS) {
    lastJson = now;
    sendJson();
    digitalWrite(PIN_LED, veh.obd_ok ? ((now / 250) & 1) : LOW);
  }
}
