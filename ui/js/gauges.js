(function () {
  const NS = "http://www.w3.org/2000/svg";
  const START = 135;
  const SWEEP = 270;

  function el(name, attrs) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function polar(cx, cy, r, deg) {
    const a = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  }

  function arcPath(cx, cy, r, a0, a1) {
    const [x0, y0] = polar(cx, cy, r, a0);
    const [x1, y1] = polar(cx, cy, r, a1);
    const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
    const sweep = a1 > a0 ? 1 : 0;
    return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} ${sweep} ${x1.toFixed(2)} ${y1.toFixed(2)}`;
  }

  function arcLen(r, deg) {
    return (Math.PI * r * deg) / 180;
  }

  const COLOR = {
    amber: "#ffb020",
    blue: "#4aa8ff",
    green: "#2ee6a8",
    cyan: "#35d6e6",
    red: "#e82127",
  };

  function mainGauge(svg) {
    svg.innerHTML = "";
    const cx = 160, cy = 160, r = 124;
    const rs = r - 4;
    const max0 = 220;

    // trilho do velocimetro
    svg.appendChild(el("path", {
      d: arcPath(cx, cy, rs, START, START + SWEEP),
      fill: "none", "stroke-width": 13, "stroke-linecap": "round",
      class: "g-track",
    }));
    // zona vermelha (ultimos 18%)
    const rz0 = START + SWEEP * 0.82;
    svg.appendChild(el("path", {
      d: arcPath(cx, cy, rs, rz0, START + SWEEP),
      fill: "none", stroke: "rgba(232,33,39,0.38)", "stroke-width": 13, "stroke-linecap": "round",
    }));
    // progresso: halo + nucleo
    const total = arcLen(rs, SWEEP);
    const glow = el("path", {
      d: arcPath(cx, cy, rs, START, START + SWEEP),
      fill: "none", "stroke-width": 20, "stroke-linecap": "round",
      class: "g-glow",
      "stroke-dasharray": total, "stroke-dashoffset": total,
    });
    svg.appendChild(glow);
    const progress = el("path", {
      d: arcPath(cx, cy, rs, START, START + SWEEP),
      fill: "none", "stroke-width": 9, "stroke-linecap": "round",
      class: "g-core",
      "stroke-dasharray": total, "stroke-dashoffset": total,
    });
    svg.appendChild(progress);

    // marcas + rotulos do velocimetro
    const ticks = el("g", { class: "g-ticks" });
    const nums = el("g", { class: "g-nums" });
    for (let i = 0; i <= 10; i++) {
      const a = START + (SWEEP * i) / 10;
      const major = i % 2 === 0;
      const [x0, y0] = polar(cx, cy, r - 20, a);
      const [x1, y1] = polar(cx, cy, r - (major ? 36 : 30), a);
      const red = i >= 9;
      ticks.appendChild(el("line", {
        x1: x0, y1: y0, x2: x1, y2: y1,
        "stroke-width": major ? 3 : 1.6, "stroke-linecap": "round",
        class: red ? "g-tick-red" : "g-tick",
      }));
      if (major) {
        const [tx, ty] = polar(cx, cy, r - 50, a);
        const t = el("text", { x: tx, y: ty, "text-anchor": "middle", "dominant-baseline": "middle" });
        t.textContent = Math.round(max0 * (i / 10));
        if (red) t.setAttribute("class", "g-red");
        nums.appendChild(t);
      }
    }
    svg.appendChild(ticks);
    svg.appendChild(nums);

    // ponteiro do velocimetro (agulha)
    const needle = el("line", {
      x1: cx, y1: cy, x2: cx, y2: cy - (r - 30),
      class: "g-needle",
    });
    needle.setAttribute("transform", `rotate(${START} ${cx} ${cy})`);
    svg.appendChild(needle);
    const nHub = el("circle", { cx, cy, r: 7, class: "g-needle-hub", fill: "var(--accent)" });
    svg.appendChild(nHub);

    // counterno interno: taquimetro (rpm x1000)
    const rr = r - 66;
    const rt0 = START + (SWEEP - 250) / 2, rsweep = 250;
    const rtotal = arcLen(rr, rsweep);
    svg.appendChild(el("path", {
      d: arcPath(cx, cy, rr, rt0, rt0 + rsweep),
      fill: "none", "stroke-width": 7, "stroke-linecap": "round",
      class: "g-rpm-track",
    }));
    svg.appendChild(el("path", {
      d: arcPath(cx, cy, rr, rt0 + rsweep * 0.85, rt0 + rsweep),
      fill: "none", stroke: "rgba(232,33,39,0.45)", "stroke-width": 7, "stroke-linecap": "round",
    }));
    const rglow = el("path", {
      d: arcPath(cx, cy, rr, rt0, rt0 + rsweep),
      fill: "none", "stroke-width": 14, "stroke-linecap": "round",
      class: "g-glow g-glow-rpm",
      "stroke-dasharray": rtotal, "stroke-dashoffset": rtotal,
    });
    svg.appendChild(rglow);
    const rprog = el("path", {
      d: arcPath(cx, cy, rr, rt0, rt0 + rsweep),
      fill: "none", "stroke-width": 5, "stroke-linecap": "round",
      class: "g-core g-core-rpm",
      "stroke-dasharray": rtotal, "stroke-dashoffset": rtotal,
    });
    svg.appendChild(rprog);

    let max = 220;
    return {
      set(value, newMax) {
        if (newMax && newMax !== max) {
          max = newMax;
          nums.querySelectorAll("text").forEach((t, i) => {
            t.textContent = Math.round((max * ((i * 2) / 10)) * 10) / 10;
          });
        }
        const frac = Math.max(0, Math.min(1, value / max));
        const off = (total * (1 - frac)).toFixed(2);
        glow.setAttribute("stroke-dashoffset", off);
        progress.setAttribute("stroke-dashoffset", off);
        const deg = START + SWEEP * frac;
        needle.setAttribute("transform", `rotate(${deg.toFixed(2)} ${cx} ${cy})`);
      },
      setRpm(frac) {
        frac = Math.max(0, Math.min(1, frac || 0));
        const off = (rtotal * (1 - frac)).toFixed(2);
        rglow.setAttribute("stroke-dashoffset", off);
        rprog.setAttribute("stroke-dashoffset", off);
      },
    };
  }

  function miniGauge(svg) {
    const min = parseFloat(svg.dataset.min || "0");
    const max = parseFloat(svg.dataset.max || "100");
    const color = COLOR[svg.dataset.color] || "#4aa8ff";
    svg.innerHTML = "";
    const cx = 32, cy = 32, r = 26;
    svg.appendChild(el("path", {
      d: arcPath(cx, cy, r, START, START + SWEEP),
      fill: "none", stroke: "rgba(255,255,255,0.09)", "stroke-width": 6, "stroke-linecap": "round",
    }));
    const progress = el("path", {
      d: arcPath(cx, cy, r, START, START + SWEEP),
      fill: "none", stroke: color, "stroke-width": 6, "stroke-linecap": "round",
      "stroke-dasharray": arcLen(r, SWEEP), "stroke-dashoffset": arcLen(r, SWEEP),
    });
    svg.appendChild(progress);
    const total = arcLen(r, SWEEP);
    return {
      set(value) {
        const frac = Math.max(0, Math.min(1, (value - min) / (max - min || 1)));
        progress.setAttribute("stroke-dashoffset", (total * (1 - frac)).toFixed(2));
        progress.setAttribute("stroke", frac > 0.92 ? COLOR.red : frac > 0.78 ? COLOR.amber : color);
      },
    };
  }

  function segments(container, count) {
    container.innerHTML = "";
    const segs = [];
    for (let i = 0; i < count; i++) {
      const d = document.createElement("div");
      d.className = "seg";
      container.appendChild(d);
      segs.push(d);
    }
    return {
      set(frac) {
        const active = Math.round(Math.max(0, Math.min(1, frac)) * count);
        segs.forEach((s, i) => {
          const on = i < active;
          s.classList.toggle("on", on);
          s.classList.toggle("warn", on && i >= count * 0.7 && i < count * 0.85);
          s.classList.toggle("red", on && i >= count * 0.85);
        });
      },
    };
  }

  function chart(canvas) {
    const ctx = canvas.getContext("2d");
    let data = null;
    let dashed = 0;
    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, rect.width * dpr);
      canvas.height = Math.max(1, rect.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }
    function line(values, color, minV, maxV, width, fill) {
      const rect = canvas.getBoundingClientRect();
      const w = rect.width, h = rect.height;
      if (!values.length) return;
      ctx.beginPath();
      values.forEach((v, i) => {
        const x = (i / Math.max(1, values.length - 1)) * w;
        const y = h - ((v - minV) / (maxV - minV || 1)) * h;
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineJoin = "round";
      ctx.stroke();
      if (fill) {
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();
      }
    }
    function draw() {
      const rect = canvas.getBoundingClientRect();
      const w = rect.width, h = rect.height;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = "rgba(255,255,255,0.06)";
      ctx.lineWidth = 1;
      for (let i = 1; i < 4; i++) {
        const y = (h / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
      if (!data || !data.speed || data.speed.length < 2) {
        ctx.fillStyle = "rgba(255,255,255,0.25)";
        ctx.font = "13px " + getComputedStyle(document.body).fontFamily;
        ctx.fillText("coletando dados...", 10, h / 2);
        return;
      }
      line(data.fuel, "#2ee6a8", 0, 100, 1.6, "rgba(46,230,168,0.07)");
      line(data.coolant, "#ffb020", 40, 130, 1.6, null);
      line(data.speed, "#4aa8ff", 0, Math.max(120, ...data.speed) * 1.15, 2.2, "rgba(74,168,255,0.12)");
    }
    window.addEventListener("resize", resize);
    resize();
    return {
      set(history) {
        data = history;
        draw();
      },
    };
  }

  window.Gauges = { main: mainGauge, mini: miniGauge, segments, chart, COLOR, polar, arcPath };
})();
