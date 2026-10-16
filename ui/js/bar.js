(function () {
  if (new URLSearchParams(location.search).get("screen") === "full") {
    location.replace("./");
    return;
  }

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const MI = 0.621371;
  const GAL = 0.264172;

  const app = $("#app");
  const boot = $("#boot");
  const bootSub = $("#bootSub");

  const ctx = {
    data: null,
    units: { speed: "kmh", temp: "c", volume: "l" },
    settings: null,
    ws: null,
    wsRetry: 0,
    lastMsg: 0,
    alertsShown: new Map(),
    turn: { next: 0, phase: 1 },
    disp: { speed: 0, rpm: 0, coolant: 20, fuel: 50, throttle: 0, load: 0, volt: 12.4, oilp: 0 },
  };

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
      case "v1": return n(v, 1);
      case "v2": return n(v, 2);
      case "pct": return n(v) + "%";
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

  function send(obj) {
    if (ctx.ws && ctx.ws.readyState === WebSocket.OPEN) {
      ctx.ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  async function api(path) {
    const res = await fetch(path);
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
      if (msg.type === "state") applyState(msg.data);
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
        if (node) node.remove();
        toasts.querySelectorAll(`[data-alert="${id}"]`).forEach((t) => t.remove());
      }
    });
  }

  document.addEventListener("click", (ev) => {
    const alert = ev.target.closest(".warn, .toast");
    if (alert && alert.dataset.alert) send({ type: "cmd", cmd: "ack", id: alert.dataset.alert });
  });

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
    const cap = ctx.settings ? ctx.settings["trip.fuel_capacity_l"] : 55;
    $("#fuelL").textContent = U.vol(fuel / 100 * cap, 1) + " " + U.volUnit();
    $("#barFuelL").textContent = U.vol(fuel / 100 * cap, 1);
    $("#rangeTxt").textContent = U.dist(d.range) + " " + U.distUnit();
    $("#odoRange").textContent = U.dist(d.range) + " " + U.distUnit();
    $("#odoTotal").textContent = U.dist(d.odo) + " " + U.distUnit();
    $("#odoTrip").textContent = U.dist(d.trip ? d.trip.km : 0, 1) + " " + U.distUnit();
    const t = d.trip || {};
    $("#barCons").textContent = t.cons ? n(t.cons, 1) : (Number(d.speed) > 1 ? "--" : "0.0");

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

  async function startup() {
    connect();
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
      }, bootAnim ? 1500 : 150);
    } catch (e) {
      bootSub.textContent = "servidor indisponível";
      setTimeout(() => {
        boot.classList.add("is-done");
        app.classList.remove("is-hidden");
        requestAnimationFrame(frame);
      }, 1000);
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  startup();
})();
