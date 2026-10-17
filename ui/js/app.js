(function () {
  const SCREEN = new URLSearchParams(location.search).get("screen") || "";
  if (SCREEN === "bar") {
    location.replace("bar.html");
    return;
  }
  // ?screen=cluster -> só o painel de velocidade (velocímetro redondo), sem menus.
  const CLUSTER = SCREEN === "cluster";
  if (CLUSTER) document.body.classList.add("is-cluster");
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const PAGES = ["drive", "energy", "nav", "media", "apps", "climate", "diag", "settings"];
  const MI = 0.621371;
  const GAL = 0.264172;

  const app = $("#app");
  const boot = $("#boot");
  const bootSub = $("#bootSub");

  const ctx = {
    data: null,
    units: { speed: "kmh", temp: "c", volume: "l" },
    settings: null,
    page: "drive",
    ws: null,
    wsRetry: 0,
    lastMsg: 0,
    chart: null,
    chartAt: 0,
    tripsAt: 0,
    settingsReady: false,
    alertsShown: new Map(),
    turn: { lt: 0, rt: 0, next: 0, phase: 1 },
    climate: { fan: 0, ac: 0, defrost: 0, recirc: 0, temp: 22 },
    media: { playing: false, pos: 0, source: "Rádio FM", t: 0 },
    disp: { speed: 0, rpm: 0, coolant: 20, fuel: 50, throttle: 0, load: 0, volt: 12.4, oilp: 0, batt: 12.4 },
  };

  const savedClimate = (() => {
    try { return JSON.parse(localStorage.getItem("cardash.climate") || "null"); } catch (e) { return null; }
  })();
  if (savedClimate) Object.assign(ctx.climate, savedClimate);

  const sound = {
    ctx: null,
    enabled: true,
    init() {
      if (this.ctx) return;
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        this.ctx = new AC();
      } catch (e) { this.enabled = false; }
    },
    tone(freq, dur, gain, type) {
      if (!this.enabled || !this.ctx) return;
      const t = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const g = this.ctx.createGain();
      osc.type = type || "sine";
      osc.frequency.value = freq;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(gain || 0.05, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      osc.connect(g).connect(this.ctx.destination);
      osc.start(t);
      osc.stop(t + dur + 0.02);
    },
    click(freq) { this.tone(freq || 1200, 0.045, 0.03, "square"); },
    alert(level) {
      if (level === "crit") {
        this.tone(880, 0.18, 0.09, "square");
        setTimeout(() => this.tone(660, 0.22, 0.09, "square"), 190);
      } else {
        this.tone(990, 0.12, 0.05, "sine");
      }
    },
  };
  const resumeAudio = () => { sound.init(); if (sound.ctx && sound.ctx.state === "suspended") sound.ctx.resume(); };
  document.addEventListener("pointerdown", resumeAudio, { once: true });

  function n(v, dec) {
    const x = Number(v);
    if (!isFinite(x)) return "--";
    return dec ? x.toFixed(dec) : Math.round(x).toString();
  }
  const U = {
    speed(v) { return ctx.units.speed === "mph" ? n(v * MI) : n(v); },
    speedUnit() { return ctx.units.speed === "mph" ? "mph" : "km/h"; },
    temp(v) { return ctx.units.temp === "f" ? n(v * 9 / 5 + 32) : n(v); },
    tempUnit() { return ctx.units.temp === "f" ? "°F" : "°C"; },
    dist(v, dec) {
      const x = ctx.units.speed === "mph" ? v * MI : v;
      return dec ? n(x, dec) : n(x);
    },
    distUnit() { return ctx.units.speed === "mph" ? "mi" : "km"; },
    vol(v, dec) { return ctx.units.volume === "gal" ? n(v * GAL, dec || 1) : n(v, dec || 1); },
    volUnit() { return ctx.units.volume === "gal" ? "gal" : "L"; },
  };

  function fmtBy(kind, v) {
    switch (kind) {
      case "speed": return U.speed(v);
      case "temp": return U.temp(v) + "°";
      case "dist": return U.dist(v) + " " + U.distUnit();
      case "dist1": return U.dist(v, 1) + " " + U.distUnit();
      case "v1": return n(v, 1);
      case "v2": return n(v, 2);
      case "pct": return n(v) + "%";
      case "int": return n(v);
      default: return n(v);
    }
  }

  const bindings = $$("[data-bind]").map((elm) => ({
    el: elm, path: elm.dataset.bind, fmt: elm.dataset.fmt, last: null,
  }));

  const speedGauge = Gauges.main($("#speedGauge"));
  const rpmSegs = Gauges.segments($("#rpmSegs"), 26);
  const miniGauges = $$(".mini-svg").map((s) => ({ key: s.dataset.gauge, g: Gauges.mini(s) }));

  function pick(path, src) {
    let cur = src;
    for (const part of path.split(".")) {
      if (cur == null) return null;
      cur = cur[part];
    }
    return cur;
  }

  function setPage(name) {
    if (!PAGES.includes(name)) return;
    ctx.page = name;
    $$(".page").forEach((p) => p.classList.toggle("is-active", p.dataset.page === name));
    $$(".tab").forEach((t) => t.classList.toggle("is-active", t.dataset.pageGo === name));
    if (name === "energy") { loadTrips(); loadChart(true); }
    if (name === "settings") { loadSettings(); loadSystem(); loadNetwork(); loadUpdate(); loadScreens(); }
    if (name === "media") { loadWallpaper(); }
    if (name === "diag") { loadDtcs(); }
    if (name === "nav") { initNav(); loadNative(); }
    if (name === "apps") loadApps();
    const page = $(`.page[data-page="${name}"]`);
    if (page) page.scrollTop = 0;
  }

  document.addEventListener("click", (ev) => {
    const go = ev.target.closest("[data-page-go]");
    if (go && !CLUSTER) { setPage(go.dataset.pageGo); return; }
    const alert = ev.target.closest(".warn, .toast");
    if (alert && alert.dataset.alert) {
      send({ type: "cmd", cmd: "ack", id: alert.dataset.alert });
    }
  });

  let touchX = 0, touchY = 0, touchT = 0;
  $(".pages").addEventListener("touchstart", (e) => {
    touchX = e.touches[0].clientX;
    touchY = e.touches[0].clientY;
    touchT = Date.now();
  }, { passive: true });
  $(".pages").addEventListener("touchend", (e) => {
    if (CLUSTER) return;
    const dx = e.changedTouches[0].clientX - touchX;
    const dy = e.changedTouches[0].clientY - touchY;
    if (Date.now() - touchT < 700 && Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.6) {
      const i = PAGES.indexOf(ctx.page);
      setPage(PAGES[Math.max(0, Math.min(PAGES.length - 1, i + (dx < 0 ? 1 : -1)))]);
    }
  }, { passive: true });

  function send(obj) {
    if (ctx.ws && ctx.ws.readyState === WebSocket.OPEN) {
      ctx.ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(path + " " + res.status);
    return res.json();
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ctx.ws = ws;
    ws.onopen = () => { ctx.wsRetry = 0; };
    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.type === "state") { applyState(msg.data); }
      else if (msg.type === "agent") { agentEvent(msg.data); }
      else if (msg.type === "update") { renderUpdate(msg.data); toast("Atualização disponível"); }
    };
    ws.onclose = () => {
      ctx.wsRetry = Math.min(ctx.wsRetry + 1, 8);
      setTimeout(connect, 400 * ctx.wsRetry);
    };
    ws.onerror = () => ws.close();
  }

  function applyState(data) {
    ctx.data = data;
    ctx.lastMsg = Date.now();
    if (data.units) ctx.units = data.units;
    if (data.climate && !ctx.climateLocal) {
      ctx.climate.fan = data.climate.fan;
      ctx.climate.ac = data.climate.ac;
    }
    updateAlerts(data.alerts || []);
    updateConn(data);
  }

  function updateConn(data) {
    const pill = $("#linkPill");
    const txt = $("#linkText");
    pill.classList.remove("ok", "sim", "off");
    let label = "sem sinal";
    let cls = "off";
    if (data.conn === "serial") { cls = "ok"; label = data.mode && data.mode.port ? data.mode.port.replace("/dev/", "") : "OBD online"; }
    else if (data.conn === "sim") { cls = "sim"; label = "simulação"; }
    pill.classList.add(cls);
    if (txt.textContent !== label) txt.textContent = label;
  }

  function updateAlerts(alerts) {
    const strip = $("#warnStrip");
    const toasts = $("#toasts");
    const seen = new Set();
    alerts.forEach((a) => {
      seen.add(a.id);
      if (ctx.alertsShown.has(a.id)) {
        const existing = ctx.alertsShown.get(a.id);
        if (existing.level !== a.level || existing.text !== a.text) {
          const node = strip.querySelector(`[data-alert="${a.id}"]`);
          if (node) node.innerHTML = `<b>${a.title}</b> · ${a.text}`;
          existing.level = a.level;
          existing.text = a.text;
        }
        return;
      }
      const el = document.createElement("div");
      el.className = "warn " + a.level;
      el.dataset.alert = a.id;
      el.innerHTML = `<b>${a.title}</b> · ${a.text} <span class="x">✕</span>`;
      strip.appendChild(el);

      const toast = document.createElement("div");
      toast.className = "toast " + a.level;
      toast.dataset.alert = a.id;
      toast.innerHTML = `<b>${a.title}</b><small>${a.text}</small>`;
      toasts.appendChild(toast);
      setTimeout(() => {
        toast.classList.add("gone");
        setTimeout(() => toast.remove(), 400);
      }, a.level === "crit" ? 9000 : 5000);

      ctx.alertsShown.set(a.id, { level: a.level, text: a.text });
      sound.alert(a.level);
    });
    ctx.alertsShown.forEach((_, id) => {
      if (!seen.has(id)) {
        ctx.alertsShown.delete(id);
        const node = strip.querySelector(`[data-alert="${id}"]`);
        if (node) { node.remove(); }
        toasts.querySelectorAll(`[data-alert="${id}"]`).forEach((t) => t.remove());
      }
    });
  }

  function updateClock() {
    const d = new Date();
    $("#clock").textContent = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    $("#date").textContent = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
    if (ctx.settings && ctx.settings["ui.theme"] === "auto") applyTheme("auto");
  }

  function applyTheme(theme) {
    let t = theme;
    if (t === "auto") {
      const h = new Date().getHours();
      t = h >= 7 && h < 19 ? "light" : "dark";
    }
    document.documentElement.dataset.theme = t;
  }

  function applyBrightness(v) {
    let dim = $("#dim");
    if (!dim) {
      dim = document.createElement("div");
      dim.id = "dim";
      dim.style.cssText = "position:fixed;inset:0;background:#000;pointer-events:none;z-index:90;transition:opacity .4s";
      document.body.appendChild(dim);
    }
    dim.style.opacity = String(Math.max(0, Math.min(0.65, (100 - v) / 100 * 0.65)));
  }

  function ease(cur, target, k) { return cur + (target - cur) * k; }

  let lastFrame = performance.now();
  function frame(now) {
    const dt = Math.min(0.1, (now - lastFrame) / 1000);
    lastFrame = now;
    const d = ctx.data;
    if (d) {
      const k = 1 - Math.pow(0.001, dt);
      const dp = ctx.disp;
      dp.speed = ease(dp.speed, Number(d.speed) || 0, k);
      dp.rpm = ease(dp.rpm, Number(d.rpm) || 0, k);
      dp.throttle = ease(dp.throttle, Number(d.throttle) || 0, k);
      dp.load = ease(dp.load, Number(d.load) || 0, k);
      dp.coolant = ease(dp.coolant, Number(d.coolant) || 0, k * 0.5);
      dp.fuel = ease(dp.fuel, Number(d.fuel) || 0, k * 0.5);
      dp.volt = ease(dp.volt, Number(d.volt) || 0, k);
      dp.oilp = ease(dp.oilp, Number(d.oilp) || 0, k);

      renderCluster(d, dp);
      bindings.forEach((b) => {
        const v = pick(b.path, d);
        if (v === null || v === undefined) return;
        const out = b.fmt ? fmtBy(b.fmt, v) : String(v);
        if (out !== b.last) { b.last = out; b.el.textContent = out; }
      });
      if (ctx.page === "energy") renderEnergy(d);
      if (ctx.page === "diag") renderLive(d);
      if (ctx.page === "nav") renderNav(d);
    }
    tickTurnSignals(dt);
    requestAnimationFrame(frame);
  }

  function renderCluster(d, dp) {
    const maxSpeed = ctx.units.speed === "mph" ? 140 : 220;
    speedGauge.set(U.speed(dp.speed), maxSpeed);
    rpmSegs.set(dp.rpm / 7000);
    $("#speedUnit").textContent = U.speedUnit();
    $("#speedValue").textContent = U.speed(dp.speed);
    $("#throttleBar").style.width = Math.max(0, Math.min(100, dp.throttle)) + "%";
    $("#rpmValue").textContent = n(dp.rpm);

    const gear = d.gear || "P";
    const gEl = $("#gear");
    if (gEl.textContent !== gear) gEl.textContent = gear;
    gEl.classList.toggle("rev", gear === "R");

    const fuel = Number(d.fuel) || 0;
    const fill = $("#fuelFill");
    fill.style.height = Math.max(2, Math.min(100, dp.fuel)) + "%";
    fill.classList.toggle("low", fuel <= 20 && fuel > 10);
    fill.classList.toggle("crit", fuel <= 10);
    $("#fuelPct").textContent = n(fuel);
    $("#fuelL").textContent = U.vol(fuel / 100 * (ctx.settings ? ctx.settings["trip.fuel_capacity_l"] : 55), 1) + " " + U.volUnit();
    $("#rangeTxt").textContent = U.dist(d.range) + " " + U.distUnit();
    $("#odoRange").textContent = fmtBy("dist", d.range);
    $("#odoTotal").textContent = U.dist(d.odo) + " " + U.distUnit();
    $("#odoTrip").textContent = U.dist(d.trip ? d.trip.km : 0, 1) + " " + U.distUnit();

    const tEl = $("#turnLeft"), trEl = $("#turnRight");
    const lt = d.lt || d.hz, rt = d.rt || d.hz;
    const blink = ctx.turn.phase === 1;
    tEl.classList.toggle("on", !!(lt && blink));
    trEl.classList.toggle("on", !!(rt && blink));

    $$(".chip").forEach((chip) => {
      const key = chip.dataset.flag;
      const on = key === "mil" ? !!d.mil : !!d[key];
      chip.classList.toggle("on", on);
    });

    miniGauges.forEach(({ key, g }) => {
      const val = key === "batt" ? dp.volt : dp[key];
      g.set(Number(val) || 0);
    });
    $("#oilVal").textContent = n(dp.oilp, 0);
  }

  function tickTurnSignals(dt) {
    const d = ctx.data;
    if (!d) return;
    const active = (d.lt || d.hz) || (d.rt || d.hz);
    if (!active) { ctx.turn.next = 0; ctx.turn.phase = 1; return; }
    ctx.turn.next -= dt;
    if (ctx.turn.next <= 0) {
      ctx.turn.next = 0.42;
      ctx.turn.phase = ctx.turn.phase ? 0 : 1;
      if (ctx.turn.phase) sound.click(1350);
    }
  }

  function renderEnergy(d) {
    const fuel = Number(d.fuel) || 0;
    const cap = ctx.settings ? ctx.settings["trip.fuel_capacity_l"] : 55;
    $("#tankFill").style.height = Math.max(2, fuel) + "%";
    $("#energyPct").textContent = n(fuel);
    $("#energyLiters").textContent = U.vol(fuel / 100 * cap, 1) + " " + U.volUnit();
    $("#energyRange").textContent = U.dist(d.range) + " " + U.distUnit() + " de autonomia";
    const t = d.trip || {};
    const cons = t.cons || 0;
    $("#consNow").textContent = cons ? n(cons, 1) : (Number(d.speed) > 1 ? "--" : "0.0");
    $("#consTrip").textContent = cons ? n(cons, 1) + " L/100km" : "--";
    $("#consLiters").textContent = U.vol(t.fuel_l || 0, 2) + " " + U.volUnit();
    $("#tDist").textContent = U.dist(t.km || 0, 1) + " " + U.distUnit();
    $("#tTime").textContent = fmtDuration(t.s || 0);
    $("#tAvg").textContent = fmtBy("speed", t.avg || 0) + " " + U.speedUnit();
    $("#tMax").textContent = fmtBy("speed", t.max || 0) + " " + U.speedUnit();
    const now = Date.now();
    if (now - ctx.chartAt > 5000) loadChart();
  }

  function fmtDuration(s) {
    s = Math.round(s);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return (h ? h + "h " : "") + m + "min";
  }

  function loadChart(force) {
    if (!force && Date.now() - ctx.chartAt < 5000) return;
    ctx.chartAt = Date.now();
    if (!ctx.chart) ctx.chart = Gauges.chart($("#historyChart"));
    api("/api/history?minutes=15").then((h) => ctx.chart.set(h)).catch(() => {});
  }

  function loadTrips(force) {
    if (!force && Date.now() - ctx.tripsAt < 15000) return;
    ctx.tripsAt = Date.now();
    api("/api/trips?limit=12").then(({ trips }) => {
      const box = $("#tripList");
      if (!trips.length) { box.innerHTML = '<div class="empty">sem viagens registradas</div>'; return; }
      box.innerHTML = trips.map((t) => {
        const date = new Date(t.end_ts || t.start_ts);
        return `<div class="trip-item">
          <span>${date.toLocaleDateString("pt-BR")} <small>${date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</small></span>
          <b>${U.dist(t.distance_km, 1)} ${U.distUnit()}</b>
          <small>${fmtDuration(t.duration_s || 0)}</small>
          <small>${n(t.avg_kmh, 0)} km/h</small>
        </div>`;
      }).join("");
    }).catch(() => {});
  }

  const PID_ROWS = [
    ["speed", "Velocidade", "speed"], ["rpm", "Rotação", "int"],
    ["coolant", "Água", "temp"], ["iat", "Admissão", "temp"],
    ["oilt", "Óleo motor", "temp"], ["oilp", "Pressão óleo", "v1"],
    ["throttle", "Acelerador", "pct"], ["load", "Carga motor", "pct"],
    ["fuel", "Combustível", "pct"], ["volt", "Tensão", "v2"],
    ["batt", "Bateria", "v2"], ["runtime", "Tempo motor", "runtime"],
  ];

  function buildPidGrid() {
    const grid = $("#pidGrid");
    if (grid.dataset.built) return;
    grid.dataset.built = "1";
    grid.innerHTML = PID_ROWS.map(([k, label]) => `<div class="pid"><small>${label}</small><b data-pid="${k}">--</b></div>`).join("");
  }

  function renderLive(d) {
    buildPidGrid();
    $$("[data-pid]").forEach((elm) => {
      const key = elm.dataset.pid;
      const v = d[key];
      let out = "--";
      if (key === "runtime") out = fmtDuration(v || 0);
      else if (v !== undefined && v !== null) {
        const row = PID_ROWS.find((r) => r[0] === key);
        out = fmtBy(row ? row[2] : "int", v);
      }
      if (elm.textContent !== out) elm.textContent = out;
    });
    const mil = $("#milBadge");
    mil.classList.toggle("bad", !!d.mil);
    mil.textContent = d.mil ? "FALHA" : "OK";
    $("#diagConn").textContent = d.conn === "serial" ? "Conectado via serial" : d.conn === "sim" ? "Simulação ativa" : "Sem comunicação";
    $("#diagPort").textContent = (d.mode && d.mode.port) || (d.conn === "sim" ? "modo bancada" : "verifique o cabo USB");
    const list = $("#dtcList");
    const codes = d.dtc || [];
    if (!codes.length && !list.dataset.filled) {
      list.innerHTML = '<div class="empty">nenhum código ativo</div>';
    } else if (codes.length) {
      list.dataset.filled = "1";
      list.innerHTML = codes.map((c) => `<div class="dtc-item"><code>${c}</code><small>${describeDtc(c)}</small></div>`).join("");
    } else {
      list.dataset.filled = "";
    }
  }

  const DTC_DESC = {
    P0300: "Falha de ignição aleatória", P0301: "Falha de ignição cilindro 1",
    P0302: "Falha de ignição cilindro 2", P0303: "Falha de ignição cilindro 3",
    P0304: "Falha de ignição cilindro 4", P0420: "Eficiência do catalisador",
    P0171: "Mistura pobre (banco 1)", P0172: "Mistura rica (banco 1)",
    P0128: "Termostato / temperatura", P0113: "Sensor de ar de admissão",
    P0135: "Sonda lambda aquecimento", P0325: "Sensor de detonação",
    P0340: "Sensor de fase", P0505: "Controle de marcha lenta",
    P0442: "Vazamento pequeno EVAP", P0455: "Vazamento grande EVAP",
  };
  function describeDtc(code) { return DTC_DESC[code] || "código de falha registrado pela ECU"; }

  function loadDtcs() {
    api("/api/dtc").then((d) => {
      const list = $("#dtcList");
      list.dataset.filled = d.dtc.length ? "1" : "";
      list.innerHTML = d.dtc.length
        ? d.dtc.map((x) => `<div class="dtc-item"><code>${x.code}</code><small>${describeDtc(x.code)} · visto ${new Date(x.last_seen).toLocaleString("pt-BR")}</small></div>`).join("")
        : '<div class="empty">nenhum código ativo</div>';
    }).catch(() => {});
  }

  function loadSettings() {
    api("/api/settings").then(({ settings }) => {
      ctx.settings = settings;
      ctx.settingsReady = true;
      $$("[data-setting]").forEach((elm) => {
        const key = elm.dataset.setting;
        const val = settings[key];
        if (val === undefined) return;
        if (elm.type === "checkbox") elm.checked = !!val;
        else elm.value = val;
      });
      applyTheme(settings["ui.theme"] || "auto");
      applyBrightness(Number(settings["ui.brightness"]) || 100);
    }).catch(() => {});
  }

  function loadSystem() {
    api("/api/system").then((s) => {
      const rows = [
        ["Conexão", s.conn === "serial" ? "Arduino serial" : s.conn === "sim" ? "Simulação" : "Offline"],
        ["Porta", s.port || "—"],
        ["Host", s.hostname || "—"],
        ["Python", s.python],
        ["Arquitetura", s.machine],
        ["Uptime", fmtDuration(s.uptime_s)],
      ];
      $("#sysGrid").innerHTML = rows.map(([k, v]) => `<div><small>${k}</small><b>${v}</b></div>`).join("");
    }).catch(() => {});
  }

  let saveTimer = null;
  function saveSetting(key, value) {
    const payload = { settings: {} };
    payload.settings[key] = value;
    api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(({ settings }) => {
      ctx.settings = Object.assign({}, ctx.settings, settings);
      const info = $("#saveInfo");
      info.textContent = "ajustes salvos";
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => { info.textContent = ""; }, 2200);
      if (key === "ui.theme") applyTheme(value);
      if (key === "ui.brightness") applyBrightness(Number(value));
    }).catch(() => {});
  }

  $$("[data-setting]").forEach((elm) => {
    const key = elm.dataset.setting;
    const ev = elm.tagName === "SELECT" || elm.type === "checkbox" ? "change" : "change";
    elm.addEventListener(ev, () => {
      let value;
      if (elm.type === "checkbox") value = elm.checked;
      else if (elm.type === "number" || elm.type === "range") value = Number(elm.value);
      else value = elm.value;
      saveSetting(key, value);
    });
    if (elm.type === "range") {
      elm.addEventListener("input", () => {
        if (key === "ui.brightness") applyBrightness(Number(elm.value));
      });
    }
  });

  $("#btnSave").addEventListener("click", loadSettings);
  $("#btnReboot").addEventListener("click", () => power("reboot"));
  $("#btnShutdown").addEventListener("click", () => power("shutdown"));
  function power(action) {
    api("/api/system/power", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    }).catch(() => {
      const info = $("#saveInfo");
      info.textContent = "recurso desabilitado (CARDASH_ALLOW_POWER=1)";
      setTimeout(() => { info.textContent = ""; }, 3000);
    });
  }

  // ---------------------------------------------------------- Wi-Fi e Bluetooth
  function netPost(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function signalBars(sig) {
    const lvl = sig >= 75 ? 4 : sig >= 50 ? 3 : sig >= 25 ? 2 : 1;
    return '<span class="net-bars">' +
      [1, 2, 3, 4].map((i) => `<i class="${i <= lvl ? "on" : ""}"></i>`).join("") +
      "</span>";
  }

  function loadNetwork() {
    api("/api/network").then((s) => {
      ctx.net = s;
      renderWifiStatus(s.wifi);
      renderBtStatus(s.bluetooth);
    }).catch(() => {});
    api("/api/bluetooth").then((b) => {
      if (b && b.available) renderBtList(b.devices || []);
    }).catch(() => {});
  }

  function renderWifiStatus(w) {
    const el = $("#wifiStatus");
    if (!el) return;
    const chk = $("#wifiEnabled");
    const scan = $("#wifiScan");
    if (!w || !w.available) {
      el.textContent = (w && w.reason) || "indisponível";
      el.className = "net-status warn";
      if (chk) { chk.checked = false; chk.disabled = true; }
      if (scan) scan.disabled = true;
      const list = $("#wifiList");
      if (list && !list.dataset.loaded) list.innerHTML = `<div class="empty">${esc((w && w.reason) || "Wi-Fi indisponível")}</div>`;
      return;
    }
    if (chk) { chk.disabled = false; chk.checked = !!w.enabled; }
    if (scan) scan.disabled = !w.enabled;
    if (w.ssid) {
      el.textContent = "conectado a " + w.ssid + (w.ip ? " · " + w.ip : "");
      el.className = "net-status ok";
    } else {
      el.textContent = w.enabled ? "desconectado" : "desligado";
      el.className = "net-status";
    }
  }

  function renderWifiList(networks) {
    const list = $("#wifiList");
    if (!list) return;
    list.dataset.loaded = "1";
    if (!networks || !networks.length) {
      list.innerHTML = '<div class="empty">nenhuma rede encontrada</div>';
      return;
    }
    list.innerHTML = networks.map((n) => {
      const lock = n.security && n.security !== "aberta" && n.security !== "--";
      return `<div class="net-item ${n.active ? "active" : ""}">
        <span class="net-ico">${lock ? "🔒" : "📶"}</span>
        <span class="info"><b>${esc(n.ssid)}</b><small>${esc(n.security)}${n.active ? " · conectada" : ""}</small></span>
        ${signalBars(Number(n.signal) || 0)}
        <span class="actions">${n.active
          ? '<button class="btn btn-ghost" data-wifi-action="disconnect">Desconectar</button>'
          : `<button class="btn" data-wifi-connect="${esc(n.ssid)}">Conectar</button>`}</span>
      </div>`;
    }).join("");
  }

  function renderBtStatus(b) {
    const el = $("#btStatus");
    if (!el) return;
    const chk = $("#btEnabled");
    const scan = $("#btScan");
    if (!b || !b.available) {
      el.textContent = (b && b.reason) || "indisponível";
      el.className = "net-status warn";
      if (chk) { chk.checked = false; chk.disabled = true; }
      if (scan) scan.disabled = true;
      return;
    }
    if (chk) { chk.disabled = false; chk.checked = !!b.powered; }
    if (scan) scan.disabled = !b.powered;
    el.textContent = b.powered ? ("ligado" + (b.name ? " · " + b.name : "")) : "desligado";
    el.className = "net-status" + (b.powered ? " ok" : "");
  }

  function renderBtList(devices) {
    const list = $("#btList");
    if (!list) return;
    if (!devices || !devices.length) {
      list.innerHTML = '<div class="empty">nenhum aparelho encontrado — pareie pelo celular</div>';
      return;
    }
    list.innerHTML = devices.map((d) => {
      let btn;
      if (d.connected) btn = `<button class="btn btn-ghost" data-bt-action="disconnect" data-mac="${d.mac}">Desconectar</button>`;
      else if (d.paired) btn = `<button class="btn" data-bt-action="connect" data-mac="${d.mac}">Conectar</button>`;
      else btn = `<button class="btn" data-bt-action="pair" data-mac="${d.mac}">Parear</button>`;
      const badge = d.connected ? '<span class="net-badge on">conectado</span>'
        : d.paired ? '<span class="net-badge">pareado</span>' : "";
      return `<div class="net-item ${d.connected ? "active" : ""}">
        <span class="net-ico">🎧</span>
        <span class="info"><b>${esc(d.name)}</b><small>${esc(d.mac)}</small></span>
        ${badge}<span class="actions">${btn}</span>
      </div>`;
    }).join("");
  }

  async function wifiScan() {
    const b = $("#wifiScan");
    if (b) { b.disabled = true; b.textContent = "escanear..."; }
    try {
      const r = await netPost("/api/wifi", { action: "scan" });
      if (r.available === false) toast(r.reason || "Wi-Fi indisponível");
      renderWifiList(r.networks || []);
      loadNetwork();
    } catch (e) { toast("falha ao escanear redes"); }
    if (b) { b.disabled = false; b.textContent = "Escanear"; }
  }

  async function btScan() {
    const b = $("#btScan");
    if (b) { b.disabled = true; b.textContent = "escanear..."; }
    try {
      const r = await netPost("/api/bluetooth", { action: "scan" });
      renderBtList(r.devices || []);
      loadNetwork();
    } catch (e) { toast("falha ao escanear bluetooth"); }
    if (b) { b.disabled = false; b.textContent = "Escanear"; }
  }

  async function btAction(action, mac) {
    try {
      const r = await netPost("/api/bluetooth", { action, mac });
      if (r.devices) renderBtList(r.devices);
      if (!r.ok && r.error) toast(r.error);
      else toast(action === "pair" ? "pareado" : action === "connect" ? "conectado" : "desconectado");
      loadNetwork();
    } catch (e) { toast("falha no bluetooth"); }
  }

  let wifiPending = null;
  function openWifiModal(ssid) {
    wifiPending = ssid;
    $("#wifiModalSsid").textContent = ssid;
    $("#wifiPassword").value = "";
    $("#wifiFormInfo").textContent = "";
    $("#wifiModal").hidden = false;
    setTimeout(() => $("#wifiPassword").focus(), 60);
  }
  async function wifiConnectNow() {
    if (!wifiPending) return;
    const info = $("#wifiFormInfo");
    const btn = $("#wifiConnect");
    info.textContent = "conectando...";
    btn.disabled = true;
    try {
      const r = await netPost("/api/wifi", {
        action: "connect", ssid: wifiPending, password: $("#wifiPassword").value,
      });
      if (r.ok) { $("#wifiModal").hidden = true; toast("conectado a " + wifiPending); wifiScan(); }
      else info.textContent = r.error || "não foi possível conectar";
    } catch (e) { info.textContent = "erro ao conectar"; }
    btn.disabled = false;
  }

  if ($("#wifiScan")) $("#wifiScan").addEventListener("click", wifiScan);
  if ($("#btScan")) $("#btScan").addEventListener("click", btScan);
  if ($("#wifiEnabled")) $("#wifiEnabled").addEventListener("change", (e) => {
    netPost("/api/wifi", { action: e.target.checked ? "enable" : "disable" })
      .then(() => setTimeout(loadNetwork, 1500)).catch(() => {});
  });
  if ($("#btEnabled")) $("#btEnabled").addEventListener("change", (e) => {
    netPost("/api/bluetooth", { action: e.target.checked ? "enable" : "disable" })
      .then(() => setTimeout(loadNetwork, 1500)).catch(() => {});
  });
  if ($("#wifiConnect")) $("#wifiConnect").addEventListener("click", wifiConnectNow);
  if ($("#wifiCancel")) $("#wifiCancel").addEventListener("click", () => { $("#wifiModal").hidden = true; });
  if ($("#wifiPassword")) $("#wifiPassword").addEventListener("keydown", (e) => { if (e.key === "Enter") wifiConnectNow(); });
  if ($("#wifiModal")) $("#wifiModal").addEventListener("click", (e) => { if (e.target.id === "wifiModal") e.target.hidden = true; });

  document.addEventListener("click", (ev) => {
    const wc = ev.target.closest("[data-wifi-connect]");
    if (wc) { openWifiModal(wc.dataset.wifiConnect); return; }
    const wa = ev.target.closest("[data-wifi-action]");
    if (wa) {
      netPost("/api/wifi", { action: wa.dataset.wifiAction })
        .then(() => { toast("Wi-Fi desconectado"); wifiScan(); }).catch(() => {});
      return;
    }
    const ba = ev.target.closest("[data-bt-action]");
    if (ba) btAction(ba.dataset.btAction, ba.dataset.mac);
  });

  // -------------------------------------------------------------- Atualizações
  function renderUpdate(u) {
    const st = $("#updateStatus");
    const info = $("#updateInfo");
    const btn = $("#updateInstall");
    if (!st) return;
    if (u && u.available) {
      if (u.available_update) {
        st.textContent = `atualização disponível (${u.behind} commit${u.behind > 1 ? "s" : ""})`;
        st.className = "net-status warn";
        if (btn) btn.disabled = false;
      } else {
        st.textContent = "sistema atualizado";
        st.className = "net-status ok";
        if (btn) btn.disabled = true;
      }
      const rows = [
        ["Versão atual", (u.current || "—") + (u.dirty ? " · alterações locais" : "")],
        ["Descrição", u.subject || "—"],
        ["Branch", u.branch || "—"],
        ["Repositório", u.remote_url || "—"],
      ];
      if (u.behind) rows.push(["Novidade", `${u.latest || ""}`]);
      if (u.fetch_error) rows.push(["Erro", u.fetch_error]);
      info.innerHTML = rows.map(([k, v]) => `<div><small>${esc(k)}</small><b>${esc(v)}</b></div>`).join("");
    } else {
      st.textContent = (u && u.reason) || "indisponível";
      st.className = "net-status warn";
      if (btn) btn.disabled = true;
      if (info) info.innerHTML = "";
    }
  }

  function loadUpdate() { api("/api/update").then(renderUpdate).catch(() => {}); }

  async function updateCheck() {
    const b = $("#updateCheck");
    b.disabled = true; b.textContent = "verificando...";
    try { renderUpdate(await netPost("/api/update", { action: "check" })); }
    catch (e) { toast("falha ao verificar atualizações"); }
    b.disabled = false; b.textContent = "Verificar";
  }

  async function updateInstall() {
    const b = $("#updateInstall");
    const log = $("#updateLog");
    b.disabled = true; b.textContent = "atualizando...";
    if (log) { log.hidden = false; log.textContent = "baixando e instalando..."; }
    try {
      const r = await netPost("/api/update", { action: "install", restart: true });
      if (log) log.textContent = (r.log || []).join("\n") || (r.error || r.message || "concluído");
      if (r.ok && r.updated) { toast("Atualizado! reiniciando o painel..."); setTimeout(() => location.reload(), 7000); return; }
      if (r.ok) { toast(r.message || "já está atualizado"); loadUpdate(); }
      else toast(r.error || "falha na atualização");
    } catch (e) { if (log) log.textContent = "erro na atualização"; }
    b.disabled = false; b.textContent = "Atualizar agora";
  }

  if ($("#updateCheck")) $("#updateCheck").addEventListener("click", updateCheck);
  if ($("#updateInstall")) $("#updateInstall").addEventListener("click", updateInstall);

  // ---------------------------------------------------------- Telas (HDMI)
  async function netPostSafe(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    if (!res.ok) return Object.assign({ ok: false, error: data.error || ("erro " + res.status) }, data);
    return data;
  }

  function fillScreensSelect(sel, outputs, chosen) {
    if (!sel) return;
    const opts = ['<option value="">— automático —</option>'];
    outputs.forEach((o) => {
      opts.push(`<option value="${esc(o.name)}">${esc(o.name)} · ${esc(o.resolution)}</option>`);
    });
    sel.innerHTML = opts.join("");
    sel.value = chosen || "";
    if (sel.value !== (chosen || "")) sel.value = "";
  }

  function loadScreens() {
    api("/api/screens").then(renderScreens).catch(() => {});
  }

  function renderScreens(s) {
    const st = $("#screensStatus");
    const list = $("#screensList");
    if (!st || !list) return;
    ctx.screens = s;
    const apply = $("#screensApply");
    if (!s || !s.available) {
      st.textContent = (s && s.reason) || "indisponível";
      st.className = "net-status warn";
      list.innerHTML = `<div class="empty">${esc((s && s.reason) || "não foi possível detectar monitores")}</div>`;
      if (apply) apply.disabled = true;
      return;
    }
    if (apply) apply.disabled = false;
    const outputs = (s.outputs || []).filter((o) => o.connected);
    st.textContent = outputs.length ? outputs.length + " monitor(es) detectado(s)" : "nenhum monitor";
    st.className = "net-status" + (outputs.length ? " ok" : "");
    const a = s.assignment || {};
    fillScreensSelect($("#screenMain"), outputs, a.main);
    fillScreensSelect($("#screenBar"), outputs, a.bar);
    const arrange = $("#screensArrange");
    if (arrange) arrange.checked = !!a.arrange;
    if (!outputs.length) {
      list.innerHTML = '<div class="empty">nenhum monitor conectado</div>';
      return;
    }
    list.innerHTML = outputs.map((o) => {
      const role = o.name === a.main ? "painel" : o.name === a.bar ? "cluster" : "";
      const pos = o.geometry ? " · " + o.geometry.x + "," + o.geometry.y : "";
      return `<div class="scr-row">
        <span class="net-ico">🖥</span>
        <span class="info"><b>${esc(o.name)}</b><small>${esc(o.resolution)}${pos}</small></span>
        ${o.primary ? '<span class="net-badge on">principal</span>' : ""}
        ${role ? `<span class="net-badge on">${role}</span>` : ""}
      </div>`;
    }).join("");
  }

  async function screensApply() {
    const b = $("#screensApply");
    if (b) { b.disabled = true; b.textContent = "aplicando..."; }
    try {
      const r = await netPostSafe("/api/screens", {
        main: ($("#screenMain") || {}).value || "",
        bar: ($("#screenBar") || {}).value || "",
        arrange: !!($("#screensArrange") && $("#screensArrange").checked),
        enabled: true,
      });
      if (r.ok) {
        const msgs = r.messages || [];
        if (msgs.length) msgs.forEach((m, i) => setTimeout(() => toast(m), i * 400));
        else toast("telas atualizadas");
        renderScreens(r);
      } else {
        toast(r.error || "falha ao aplicar telas");
      }
    } catch (e) { toast("falha ao aplicar telas"); }
    if (b) { b.disabled = false; b.textContent = "Aplicar e reiniciar"; }
  }

  if ($("#screensDetect")) $("#screensDetect").addEventListener("click", loadScreens);
  if ($("#screensApply")) $("#screensApply").addEventListener("click", screensApply);

  // ---------------------------------------------------------- Papel de parede
  const WP_HINT = "A imagem vira o fundo da página Mídia. Formatos: PNG, JPG, WEBP, GIF, BMP (até 8 MB).";

  function loadWallpaper() {
    api("/api/media").then((m) => {
      ctx.wallpaper = m.wallpaper || "";
      applyWallpaper(ctx.wallpaper, m.fit);
      renderWallpaperPreview(ctx.wallpaper);
    }).catch(() => {});
  }

  function applyWallpaper(url, fit) {
    const page = document.querySelector('.page[data-page="media"]');
    if (!page) return;
    if (url) {
      page.style.setProperty("--wp", `url("${url}")`);
      page.style.setProperty("--wp-fit", fit || "cover");
    } else {
      page.style.removeProperty("--wp");
      page.style.removeProperty("--wp-fit");
    }
  }

  function renderWallpaperPreview(url) {
    const p = $("#wpPreview");
    const input = $("#wpUrl");
    if (input) input.value = (url && url.indexOf("http") === 0) ? url : "";
    if (!p) return;
    if (url) { p.style.backgroundImage = `url("${url}")`; p.classList.add("has-image"); }
    else { p.style.backgroundImage = ""; p.classList.remove("has-image"); }
  }

  async function wallpaperUseUrl() {
    const info = $("#wpInfo");
    const url = (($("#wpUrl") || {}).value || "").trim();
    if (info) info.textContent = "aplicando...";
    const r = await netPostSafe("/api/media/wallpaper", { url });
    if (r.ok) {
      applyWallpaper(r.wallpaper, r.fit);
      renderWallpaperPreview(r.wallpaper);
      toast(r.wallpaper ? "papel de parede aplicado" : "papel de parede removido");
      if (info) info.textContent = WP_HINT;
    } else {
      toast(r.error || "falha ao aplicar papel de parede");
      if (info) info.textContent = r.error || "";
    }
  }

  async function wallpaperUpload(file) {
    const info = $("#wpInfo");
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) { toast("imagem muito grande (máx 8 MB)"); return; }
    if (info) info.textContent = "enviando imagem...";
    const reader = new FileReader();
    reader.onload = async () => {
      const r = await netPostSafe("/api/media/wallpaper", { data: reader.result });
      if (r.ok) {
        const bust = r.wallpaper + (r.wallpaper.indexOf("http") === 0 ? "" : "?t=" + Date.now());
        applyWallpaper(bust, r.fit);
        renderWallpaperPreview(bust);
        toast("papel de parede aplicado");
        if (info) info.textContent = WP_HINT;
      } else {
        toast(r.error || "falha ao enviar imagem");
        if (info) info.textContent = r.error || "";
      }
    };
    reader.onerror = () => toast("falha ao ler a imagem");
    reader.readAsDataURL(file);
  }

  async function wallpaperClear() {
    const r = await netPostSafe("/api/media/wallpaper", { clear: true });
    if (r.ok) { applyWallpaper(""); renderWallpaperPreview(""); toast("papel de parede removido"); }
    else toast(r.error || "falha ao remover papel de parede");
  }

  if ($("#wpUse")) $("#wpUse").addEventListener("click", wallpaperUseUrl);
  if ($("#wpClear")) $("#wpClear").addEventListener("click", wallpaperClear);
  if ($("#wpFile")) $("#wpFile").addEventListener("change", (e) => {
    wallpaperUpload(e.target.files && e.target.files[0]);
    e.target.value = "";
  });

  $("#btnDtcRead").addEventListener("click", () => send({ type: "cmd", cmd: "dtc_read" }));
  $("#btnDtcClear").addEventListener("click", () => {
    send({ type: "cmd", cmd: "dtc_clear" });
    loadDtcs();
  });
  $("#btnSimDtc").addEventListener("click", () => {
    send({ type: "cmd", cmd: "sim_dtc", code: "P0301" });
  });

  $$("#fanSteps button").forEach((b) => b.addEventListener("click", () => {
    ctx.climate.fan = Number(b.dataset.fan);
    ctx.climateLocal = true;
    sendClimate();
    renderClimate();
  }));
  $("#acToggle").addEventListener("click", () => {
    ctx.climate.ac = ctx.climate.ac ? 0 : 1;
    ctx.climateLocal = true;
    sendClimate();
    renderClimate();
  });
  $("#defrostToggle").addEventListener("click", () => { ctx.climate.defrost = ctx.climate.defrost ? 0 : 1; renderClimate(); });
  $("#recircToggle").addEventListener("click", () => { ctx.climate.recirc = ctx.climate.recirc ? 0 : 1; renderClimate(); });
  $("#tempUp").addEventListener("click", () => { ctx.climate.temp = Math.min(30, ctx.climate.temp + 1); renderClimate(); });
  $("#tempDown").addEventListener("click", () => { ctx.climate.temp = Math.max(16, ctx.climate.temp - 1); renderClimate(); });

  function sendClimate() {
    localStorage.setItem("cardash.climate", JSON.stringify(ctx.climate));
    send({ type: "cmd", cmd: "climate", fan: ctx.climate.fan, ac: ctx.climate.ac });
  }

  function renderClimate() {
    $("#climateTemp").textContent = ctx.climate.temp;
    $("#acToggle").classList.toggle("on", !!ctx.climate.ac);
    $("#acToggle").querySelector("b").textContent = ctx.climate.ac ? "ON" : "OFF";
    $("#defrostToggle").classList.toggle("on", !!ctx.climate.defrost);
    $("#defrostToggle").querySelector("b").textContent = ctx.climate.defrost ? "ON" : "OFF";
    $("#recircToggle").classList.toggle("on", !!ctx.climate.recirc);
    $("#recircToggle").querySelector("b").textContent = ctx.climate.recirc ? "ON" : "OFF";
    $$("#fanSteps button").forEach((b) => b.classList.toggle("on", Number(b.dataset.fan) === ctx.climate.fan));
  }

  const MEDIA = [
    { title: "Rádio FM 89.1", artist: "OpenDash Player" },
    { title: "Bluetooth · Celular", artist: "Playlist da estrada" },
    { title: "USB · MP3", artist: "Coletânea" },
    { title: "Auxiliar", artist: "Entrada externa" },
  ];
  $$(".source").forEach((b, i) => b.addEventListener("click", () => {
    $$(".source").forEach((x) => x.classList.remove("is-active"));
    b.classList.add("is-active");
    ctx.media.source = b.dataset.source;
    const meta = MEDIA[i] || { title: b.dataset.source, artist: "OpenDash" };
    $("#mediaTitle").textContent = meta.title;
    $("#mediaArtist").textContent = meta.artist;
    $("#miniTitle").textContent = meta.title;
    $("#miniArtist").textContent = meta.artist;
  }));

  function togglePlay() {
    ctx.media.playing = !ctx.media.playing;
    const path = ctx.media.playing ? "M6 5h4v14H6zm8 0h4v14h-4z" : "M8 5v14l11-7z";
    $("#playPath").setAttribute("d", path);
    $("#miniPlayPath").setAttribute("d", path);
  }
  $("#btnPlay").addEventListener("click", togglePlay);
  $("#miniPlay").addEventListener("click", (e) => { e.stopPropagation(); togglePlay(); });
  $("#btnNext").addEventListener("click", () => { ctx.media.pos = 0; });
  $("#btnPrev").addEventListener("click", () => { ctx.media.pos = 0; });
  $("#volume").addEventListener("input", (e) => {
    $("#volVal").textContent = e.target.value;
    ctx.media.volume = Number(e.target.value);
  });
  setInterval(() => {
    if (ctx.media.playing) {
      ctx.media.pos = (ctx.media.pos + 0.5) % 100;
      $("#mediaProgress").style.width = ctx.media.pos + "%";
    }
  }, 500);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }
  function hostOf(u) {
    try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; }
  }

  const nav = {
    map: null, marker: null, trackLine: null, routeLine: null, destMarker: null,
    dest: null, follow: true, ready: false, trackAt: 0, tries: 0,
  };

  function initNav() {
    if (typeof L === "undefined") return;
    if (!nav.map) {
      try {
        nav.map = L.map("map", { zoomControl: false, attributionControl: true })
          .setView([-23.5613, -46.6565], 14);
        L.control.zoom({ position: "bottomright" }).addTo(nav.map);
        nav.map.on("dragstart", () => { nav.follow = false; });
      } catch (e) { nav.map = null; }
      loadApps();
    }
    setTimeout(() => { if (nav.map) nav.map.invalidateSize(); }, 60);
    loadTrack(true);
  }

  function tileLayer(cfg) {
    if (cfg && cfg.provider === "google") {
      return L.tileLayer("https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", {
        subdomains: ["mt0", "mt1", "mt2", "mt3"], maxZoom: 20,
        attribution: "© Google",
      });
    }
    const url = (cfg && cfg.tile_url) || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    return L.tileLayer(url, { maxZoom: 19, attribution: "© OpenStreetMap" });
  }

  function carIcon(heading) {
    return L.divIcon({
      className: "car-marker",
      html: `<svg viewBox="0 0 24 24" style="transform:rotate(${Number(heading) || 0}deg)">`
        + `<path d="M12 2 19 21 12 17 5 21 12 2z" fill="#4aa8ff" stroke="#fff" `
        + `stroke-width="1.3" stroke-linejoin="round"/></svg>`,
      iconSize: [34, 34], iconAnchor: [17, 17],
    });
  }

  function renderNav(d) {
    const g = (d && d.gps) || {};
    const has = !!g.has && g.lat != null && g.lon != null;
    $("#navFix").classList.toggle("ok", has);
    $("#navFixText").textContent = has ? (g.fix ? "sinal GPS" : "sem fix") : "sem sinal";
    $("#navLat").textContent = has ? Number(g.lat).toFixed(5) : "--";
    $("#navLon").textContent = has ? Number(g.lon).toFixed(5) : "--";
    $("#navSpeed").textContent = g.speed != null ? n(g.speed) + " km/h" : "--";
    $("#navHeading").textContent = g.heading != null ? n(g.heading) + "°" : "--";
    $("#navSats").textContent = g.sats != null ? String(g.sats) : "--";
    $("#navAlt").textContent = g.alt != null ? n(g.alt) + " m" : "--";
    $("#navHdop").textContent = g.hdop != null ? Number(g.hdop).toFixed(1) : "--";
    $("#navSrc").textContent = { usb: "USB", arduino: "Arduino", sim: "Simulação" }[g.src] || "—";
    if (has && nav.map) {
      const pos = [Number(g.lat), Number(g.lon)];
      if (!nav.marker) {
        nav.marker = L.marker(pos, { icon: carIcon(g.heading) }).addTo(nav.map);
      } else {
        nav.marker.setLatLng(pos);
        nav.marker.setIcon(carIcon(g.heading));
      }
      if (!nav.ready) { nav.map.setView(pos, 15); nav.ready = true; }
      else if (nav.follow) nav.map.panTo(pos, { animate: true, duration: 0.4 });
    }
  }

  function loadTrack(force) {
    if (!nav.map) return;
    if (!force && Date.now() - nav.trackAt < 10000) return;
    nav.trackAt = Date.now();
    api("/api/gps/track?minutes=180").then(({ track }) => {
      const pts = (track || []).filter((p) => p.lat != null).map((p) => [p.lat, p.lon]);
      if (!pts.length) return;
      if (nav.trackLine) { nav.trackLine.setLatLngs(pts); return; }
      nav.trackLine = L.polyline(pts, { color: "#4aa8ff", weight: 4, opacity: 0.75 }).addTo(nav.map);
    }).catch(() => {});
  }

  function navInfo(text) { $("#navRouteInfo").textContent = text; }

  async function navSearch() {
    const q = $("#navSearch").value.trim();
    if (!q) return null;
    const m = q.match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
    let dest = null;
    if (m) {
      dest = { lat: Number(m[1]), lon: Number(m[2]), name: q };
    } else {
      navInfo("buscar...");
      try {
        const r = await fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(q));
        const arr = await r.json();
        if (arr && arr[0]) dest = { lat: Number(arr[0].lat), lon: Number(arr[0].lon), name: arr[0].display_name };
      } catch (e) { /* offline */ }
    }
    if (!dest) { navInfo("destino não encontrado (precisa de internet)"); return null; }
    nav.dest = dest;
    if (nav.map) {
      const ll = [dest.lat, dest.lon];
      if (nav.destMarker) nav.destMarker.setLatLng(ll);
      else nav.destMarker = L.marker(ll).addTo(nav.map);
      nav.follow = false;
      nav.map.fitBounds([ll, nav.marker ? nav.marker.getLatLng() : ll], { padding: [60, 60], maxZoom: 15 });
    }
    navInfo(dest.name);
    return dest;
  }

  async function navRoute() {
    if (typeof L === "undefined") return;
    if (!nav.dest) { if (!(await navSearch())) return; }
    if (!nav.marker) { navInfo("sem posição GPS"); return; }
    const a = nav.marker.getLatLng();
    navInfo("calculando rota...");
    const url = `https://router.project-osrm.org/route/v1/driving/${a.lng},${a.lat};`
      + `${nav.dest.lon},${nav.dest.lat}?overview=full&geometries=geojson`;
    try {
      const r = await fetch(url);
      const j = await r.json();
      if (!j.routes || !j.routes[0]) throw new Error("sem rota");
      const route = j.routes[0];
      const latlngs = route.geometry.coordinates.map((c) => [c[1], c[0]]);
      if (nav.routeLine) nav.map.removeLayer(nav.routeLine);
      nav.routeLine = L.polyline(latlngs, { color: "#e82127", weight: 6, opacity: 0.9 }).addTo(nav.map);
      nav.map.fitBounds(nav.routeLine.getBounds(), { padding: [60, 60] });
      nav.follow = false;
      const km = route.distance / 1000;
      const min = Math.round(route.duration / 60);
      navInfo(`${km.toFixed(1)} km · ${min} min · via ${(route.legs[0].summary) || "rota"}`);
    } catch (e) {
      navInfo("não foi possível calcular a rota (precisa de internet)");
    }
  }

  // ---------------------------------------------- GNOME Maps (app nativo)
  const nativeState = { apps: [] };

  function nativeInfo(text) { const el = $("#nativeInfo"); if (el) el.textContent = text; }

  function renderNative(st) {
    nativeState.apps = (st && st.apps) || [];
    const el = $("#nativeStatus");
    if (!el) return;
    const maps = nativeState.apps.find((a) => a.key === "gnome-maps");
    const parts = [];
    if (maps && maps.installed) {
      parts.push(`GNOME Maps instalado${maps.running ? " · em execução" : ""}`);
    } else if (maps) {
      parts.push("GNOME Maps não instalado");
    } else {
      parts.push("indisponível");
    }
    if (st && !st.allowed) parts.push("lancamento desativado (CARDASH_ALLOW_NATIVE=1)");
    else if (st && !st.enabled) parts.push("desativado nas configurações");
    el.textContent = parts.join(" · ");
    el.classList.toggle("ok", !!(st && st.allowed && st.enabled && maps && maps.installed));
    if (nativeState.apps.length && $("#appsGrid")) loadApps();
  }

  function loadNative() {
    api("/api/native").then(renderNative).catch(() => renderNative(null));
  }

  function nativeSpec(key) {
    return (nativeState.apps || []).find((a) => a.key === key) || null;
  }

  function nativeOpen(app, altName) {
    const key = app || "gnome-maps";
    const name = altName || (nativeSpec(key) && nativeSpec(key).name) || key;
    const body = { app: key };
    if (nav.dest) {
      body.lat = nav.dest.lat;
      body.lon = nav.dest.lon;
    } else {
      const q = ($("#navSearch") && $("#navSearch").value.trim()) || "";
      if (q && key === "gnome-maps") body.query = q;
    }
    nativeInfo(`abrindo ${name}…`);
    netPostSafe("/api/native/launch", body).then((r) => {
      if (r.ok) {
        nativeInfo(`aberto${r.uri ? " em " + r.uri : ""}`);
        toast(name + ": " + (r.uri || r.name));
      } else {
        nativeInfo(r.error || "falha ao abrir");
        toast(r.error || `não foi possível abrir ${name}`);
      }
      loadNative();
    }).catch(() => { nativeInfo("falha ao abrir"); });
  }

  function nativeClose() {
    netPostSafe("/api/native/close", { app: "gnome-maps" }).then((r) => {
      nativeInfo(r.ok ? "GNOME Maps fechado" : (r.error || "falha ao fechar"));
      loadNative();
    }).catch(() => {});
  }

  const BUILTIN = new Set(["nav", "gnome-maps"]);
  const ICON_SVG = {
    nav: '<path d="M12 2 4 21l8-4 8 4z" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>',
    play: '<path d="M8 5v14l11-7z" fill="#fff"/>',
    music: '<path d="M9 18V6l10-2v12" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round"/><circle cx="7" cy="18" r="2.4" fill="#fff"/><circle cx="17" cy="16" r="2.4" fill="#fff"/>',
    map: '<path d="M9 3 3 5v16l6-2 6 2 6-2V3l-6 2-6-2z" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round"/><path d="M9 3v16M15 5v16" stroke="#fff" stroke-width="2"/>',
    compass: '<circle cx="12" cy="12" r="9" fill="none" stroke="#fff" stroke-width="2"/><path d="m15 9-2 6-4 2 2-6z" fill="#fff"/>',
    globe: '<circle cx="12" cy="12" r="9" fill="none" stroke="#fff" stroke-width="2"/><path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" fill="none" stroke="#fff" stroke-width="2"/>',
  };
  function appIcon(v) {
    const svg = ICON_SVG[v];
    if (svg) return `<svg viewBox="0 0 24 24" width="30" height="30">${svg}</svg>`;
    return esc((v && v.length <= 3) ? v : "🌐");
  }

  function loadApps() {
    api("/api/apps").then((data) => {
      if (data.maps) applyMapConfig(data.maps);
      ctx.appsCache = data.apps || [];
      renderApps(ctx.appsCache);
    }).catch(() => {});
  }

  let mapCfgLoaded = false;
  function applyMapConfig(cfg) {
    ctx.mapsCfg = cfg;
    if (!nav.map || mapCfgLoaded) return;
    mapCfgLoaded = true;
    tileLayer(cfg).addTo(nav.map);
  }

  function renderApps(list) {
    const grid = $("#appsGrid");
    const tiles = list.map((a) => {
      const nat = a.kind === "native" ? nativeSpec(a.url) : null;
      let sub;
      if (a.kind === "nav") sub = "mapa e GPS";
      else if (a.kind === "browser") sub = "navegador embutido";
      else if (a.kind === "native") sub = (nat && nat.installed === false)
        ? "não instalado"
        : "app nativo do sistema";
      else sub = hostOf(a.url);
      const del = BUILTIN.has(a.id) ? "" :
        `<button class="app-del" data-del="${esc(a.id)}" title="remover">✕</button>`;
      return `<div class="app-tile${nat && nat.installed === false ? " is-off" : ""}" data-app="${esc(a.id)}">
        <div class="app-icon" style="background:${esc(a.color || "#4aa8ff")}">${appIcon(a.icon)}</div>
        <b>${esc(a.name)}</b><small>${esc(sub)}</small>${del}
      </div>`;
    }).join("");
    grid.innerHTML = tiles || '<div class="empty">nenhum aplicativo cadastrado</div>';
  }

  function showOverlay(title, url) {
    $("#appTitle").textContent = title || "App";
    const frame = $("#appFrame");
    frame.src = url;
    $("#appOverlay").hidden = false;
    nav.follow = false;
    clearTimeout(openApp._t);
    openApp._t = setTimeout(() => {
      if (!$("#appOverlay").hidden) toast("Se o app não aparecer, use ↗ para abrir em outra aba");
    }, 3500);
  }
  function openApp(a) {
    if (!a) return;
    if (a.kind === "nav" || a.url === "nav") { setPage("nav"); return; }
    if (a.kind === "native") {
      const key = a.url || "gnome-maps";
      if (key === "gnome-maps") setPage("nav");
      nativeOpen(key, a.name);
      return;
    }
    if (a.kind === "web") {
      try { window.open(a.url, "_blank", "noopener"); } catch (e) { window.location.href = a.url; }
      return;
    }
    showOverlay(a.name, a.url);
  }
  function closeOverlay() {
    const frame = $("#appFrame");
    $("#appOverlay").hidden = true;
    frame.src = "about:blank";
    clearTimeout(openApp._t);
  }
  function toast(text) {
    const t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = `<b>${esc(text)}</b>`;
    $("#toasts").appendChild(t);
    setTimeout(() => { t.classList.add("gone"); setTimeout(() => t.remove(), 400); }, 4500);
  }

  // --------------------------------------------------------- Assistente de IA
  const agentState = { recording: false, speaking: localStorage.getItem("cardash.agent.speak") !== "0" };

  function agentSetStatus(text, cls) {
    const el = $("#agentStatus");
    if (!el) return;
    el.classList.remove("ok", "rec", "think");
    if (cls) el.classList.add(cls);
    $("#agentStatusText").textContent = text;
  }

  function agentPost(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function refreshAgentStatus() {
    return api("/api/agent").then((s) => {
      ctx.agent = s;
      if (!s.enabled) agentSetStatus("desligado", "think");
      else if (!s.llm_ready) agentSetStatus("sem chave de IA", "think");
      else if (!s.arecord) agentSetStatus("sem microfone", "think");
      else if (!s.stt_ready) agentSetStatus("falta o Whisper", "think");
      else agentSetStatus("pronto", "ok");
      const box = $("#agentSys");
      if (box) {
        box.innerHTML = [
          ["Voz→texto", s.stt_ready ? "pronto" : "instalar"],
          ["Microfone", s.arecord ? "ok" : "sem arecord"],
          ["IA", s.llm_ready ? "pronta" : "falta chave"],
          ["Voz (TTS)", s.tts === "edge" ? "edge-tts" : (s.tts || "—")],
        ].map(([k, v]) => `<div><small>${k}</small><b>${esc(v)}</b></div>`).join("");
      }
    }).catch(() => agentSetStatus("indisponível", "think"));
  }

  function agentEvent(data) {
    if (!data) return;
    if (data.phase === "listening") { agentSetStatus("ouvindo…", "rec"); return; }
    if (data.phase === "transcribing") { agentSetStatus("transcrevendo…", "think"); return; }
    if (data.phase === "thinking") {
      agentSetStatus("pensando…", "think");
      if (data.transcript) $("#agentYou").textContent = data.transcript;
      return;
    }
    if (data.done) {
      agentSetStatus(data.ok ? "pronto" : "erro", data.ok ? "ok" : "think");
      $("#agentYou").textContent = data.transcript || "—";
      $("#agentReply").textContent = data.reply || "—";
      agentRunActions(data.actions || []);
      if (agentState.speaking && data.audio) agentPlayAudio(data.audio);
    }
  }

  function agentPlayAudio(b64) {
    try {
      const a = new Audio("data:audio/mpeg;base64," + b64);
      a.play().catch(() => {});
    } catch (e) { /* ignora */ }
  }

  function agentFindApp(name) {
    if (!name || !ctx.appsCache) return null;
    const q = String(name).toLowerCase();
    return ctx.appsCache.find((a) => a.id.toLowerCase() === q)
      || ctx.appsCache.find((a) => a.name.toLowerCase() === q)
      || ctx.appsCache.find((a) => a.name.toLowerCase().includes(q) || a.id.toLowerCase().includes(q));
  }

  function agentMedia(act) {
    if (act.provider === "spotube") {
      const spotube = agentFindApp("spotube") || agentFindApp("Spotube");
      if (spotube) { openApp(spotube); setPage("apps"); }
      else toast("Spotube não está na grade de aplicativos");
      return;
    }
    setPage("media");
    if (act.provider === "youtube") {
      const q = encodeURIComponent(act.query || "");
      showOverlay("YouTube", `https://www.youtube-nocookie.com/embed?listType=search&list=${q}`);
    } else if (act.provider === "spotify") {
      if (act.uri && act.uri.indexOf("spotify:") === 0) {
        const parts = act.uri.split(":");
        showOverlay("Spotify", `https://open.spotify.com/embed/${parts[1]}/${parts[2]}`);
      } else {
        showOverlay("Spotify", `https://open.spotify.com/search/${encodeURIComponent(act.query || "")}`);
      }
    }
  }

  function agentMediaControl(action) {
    if (action === "play" && !ctx.media.playing) togglePlay();
    else if (action === "pause" && ctx.media.playing) togglePlay();
    else if (action === "proxima" || action === "anterior") {
      ctx.media.pos = 0;
      const p = $("#mediaProgress");
      if (p) p.style.width = "0%";
    }
  }

  function agentRunActions(actions) {
    actions.forEach((act) => {
      if (!act || !act.type) return;
      if (act.type === "open_app") {
        const app = agentFindApp(act.name);
        if (app) openApp(app);
        else { setPage("apps"); toast("Não achei o app: " + act.name); }
      } else if (act.type === "media") {
        agentMedia(act);
      } else if (act.type === "media_control") {
        agentMediaControl(act.action);
      } else if (act.type === "navigate") {
        setPage("nav");
        setTimeout(() => {
          const inp = $("#navSearch");
          if (inp) { inp.value = act.destination || ""; if (navSearch && navRoute) navSearch().then(() => navRoute()); }
        }, 400);
      } else if (act.type === "climate") {
        if (act.fan !== null && act.fan !== undefined) ctx.climate.fan = Number(act.fan);
        if (act.ac !== null && act.ac !== undefined) ctx.climate.ac = act.ac ? 1 : 0;
        if (act.temp) ctx.climate.temp = Number(act.temp);
        ctx.climateLocal = true;
        renderClimate();
        setPage("climate");
      } else if (act.type === "page") {
        setPage(act.page);
      } else if (act.type === "open_url") {
        showOverlay("Web", act.url);
      }
    });
  }

  function agentAskText() {
    const inp = $("#agentText");
    const text = (inp.value || "").trim();
    if (!text) return;
    inp.value = "";
    $("#agentYou").textContent = text;
    agentSetStatus("pensando…", "think");
    agentPost("/api/agent/ask", { text })
      .then((r) => agentEvent(r))
      .catch(() => agentSetStatus("erro", "think"));
  }

  const micBtn = $("#agentMic");
  function agentListenStart() {
    if (agentState.recording) return;
    agentState.recording = true;
    if (micBtn) micBtn.classList.add("rec");
    agentSetStatus("ouvindo…", "rec");
    agentPost("/api/agent/listen/start").then((r) => {
      if (!r.ok) {
        agentState.recording = false;
        if (micBtn) micBtn.classList.remove("rec");
        toast(r.error || "microfone indisponível");
        refreshAgentStatus();
      }
    }).catch(() => { agentState.recording = false; if (micBtn) micBtn.classList.remove("rec"); });
  }
  function agentListenStop() {
    if (!agentState.recording) return;
    agentState.recording = false;
    if (micBtn) micBtn.classList.remove("rec");
    agentSetStatus("processando…", "think");
    agentPost("/api/agent/listen/stop").catch(() => {});
  }

  if (micBtn) {
    micBtn.addEventListener("pointerdown", (e) => { e.preventDefault(); agentListenStart(); });
    ["pointerup", "pointerleave", "pointercancel"].forEach((ev) =>
      micBtn.addEventListener(ev, agentListenStop));
    document.addEventListener("pointerup", agentListenStop);
  }
  if ($("#agentSend")) $("#agentSend").addEventListener("click", agentAskText);
  if ($("#agentText")) $("#agentText").addEventListener("keydown", (e) => { if (e.key === "Enter") agentAskText(); });
  if ($("#agentSpeak")) {
    $("#agentSpeak").checked = agentState.speaking;
    $("#agentSpeak").addEventListener("change", (e) => {
      agentState.speaking = e.target.checked;
      localStorage.setItem("cardash.agent.speak", e.target.checked ? "1" : "0");
    });
  }

  function openAppModal() {
    $("#appName").value = "";
    $("#appUrl").value = "";
    $("#appIcon").value = "";
    $("#appColor").value = "#4aa8ff";
    $("#appKind").value = "embed";
    $("#appFormInfo").textContent = "";
    $("#appModal").hidden = false;
    $("#appName").focus();
  }
  function closeAppModal() { $("#appModal").hidden = true; }

  function saveApp() {
    const name = $("#appName").value.trim();
    const url = $("#appUrl").value.trim();
    if (!name || !url) { $("#appFormInfo").textContent = "informe nome e URL"; return; }
    api("/api/apps", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name, url,
        icon: $("#appIcon").value.trim() || "🌐",
        color: $("#appColor").value || "#4aa8ff",
        kind: $("#appKind").value,
      }),
    }).then(() => { closeAppModal(); loadApps(); })
      .catch(() => { $("#appFormInfo").textContent = "falha ao salvar"; });
  }

  $("#appsGrid").addEventListener("click", (ev) => {
    const del = ev.target.closest("[data-del]");
    if (del) {
      const id = del.dataset.del;
      api("/api/apps/" + encodeURIComponent(id), { method: "DELETE" })
        .then(() => loadApps()).catch(() => {});
      return;
    }
    const tile = ev.target.closest("[data-app]");
    if (tile && ctx.appsCache) openApp(ctx.appsCache.find((a) => a.id === tile.dataset.app));
  });

  $("#btnAddApp").addEventListener("click", openAppModal);
  $("#appSave").addEventListener("click", saveApp);
  $("#appCancel").addEventListener("click", closeAppModal);
  $("#appClose").addEventListener("click", closeOverlay);
  $("#appReload").addEventListener("click", () => {
    const frame = $("#appFrame");
    frame.src = frame.src;
  });
  $("#appExt").addEventListener("click", () => {
    try { window.open($("#appFrame").src, "_blank", "noopener"); } catch (e) {}
  });
  $("#navSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") navSearch(); });
  $("#btnNavRoute").addEventListener("click", navRoute);
  const btnNativeOpen = $("#btnNativeOpen");
  if (btnNativeOpen) btnNativeOpen.addEventListener("click", () => nativeOpen("gnome-maps"));
  const btnNativeClose = $("#btnNativeClose");
  if (btnNativeClose) btnNativeClose.addEventListener("click", nativeClose);
  $("#btnNavCenter").addEventListener("click", () => {
    nav.follow = true;
    if (nav.marker && nav.map) nav.map.setView(nav.marker.getLatLng(), 16);
  });

  async function startup() {
    connect();
    renderClimate();
    loadApps();
    loadNative();
    refreshAgentStatus();
    loadWallpaper();
    try {
      const { settings } = await api("/api/settings");
      ctx.settings = settings;
      applyTheme(settings["ui.theme"] || "auto");
      applyBrightness(Number(settings["ui.brightness"]) || 100);
      const bootAnim = settings["ui.boot_animation"] !== false;
      bootSub.textContent = "verificando sensores";
      setTimeout(() => {
        boot.classList.add("is-done");
        app.classList.remove("is-hidden");
        requestAnimationFrame(frame);
      }, bootAnim ? 1900 : 200);
    } catch (e) {
      bootSub.textContent = "servidor indisponível";
      setTimeout(() => {
        boot.classList.add("is-done");
        app.classList.remove("is-hidden");
        requestAnimationFrame(frame);
      }, 1200);
    }
    updateClock();
    setInterval(updateClock, 1000);
    setInterval(() => { if (ctx.page === "energy") loadChart(); }, 5000);
  }

  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (e.key === "Escape") { closeOverlay(); closeAppModal(); return; }
    if (CLUSTER) return;
    const i = PAGES.indexOf(ctx.page);
    if (e.key === "ArrowRight") setPage(PAGES[Math.min(PAGES.length - 1, i + 1)]);
    if (e.key === "ArrowLeft") setPage(PAGES[Math.max(0, i - 1)]);
    if (e.key === "d" && ctx.data) send({ type: "cmd", cmd: "ack_all" });
  });

  startup();
})();
