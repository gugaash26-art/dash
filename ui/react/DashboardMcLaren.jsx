import React from "react";
import { motion } from "framer-motion";

/* ------------------------------------------------------------------ config */

const RPM_MAX = 10000;
const START_ANGLE = 135; // 0 rpm — bottom-left
const SWEEP = 270; // clockwise to 10k — bottom-right

const clamp = (value, min, max) => Math.min(Math.max(Number(value) || 0, min), max);

function polar(cx, cy, r, angleDeg) {
  const a = (angleDeg * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

/* ------------------------------------------------------------------- icons */

function Icon({ children, className = "" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const HeadlightIcon = (p) => (
  <Icon {...p}>
    <path d="M3 12a7 7 0 0 1 7-7h3v14h-3a7 7 0 0 1-7-7Z" />
    <path d="M16.5 9H20M16.5 12H21M16.5 15H20" />
  </Icon>
);

const AutoIcon = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.2 15.4 12 7.8l3.8 7.6M9.4 12.6h5.2" />
  </Icon>
);

const BeltIcon = (p) => (
  <Icon {...p}>
    <circle cx="10.5" cy="5" r="2.1" />
    <path d="M8 21l1.4-6.6 5.3-4" />
    <path d="M9.4 14.4H16l2.2 6.6" />
    <path d="M6.2 9.2l10.6 8.4" />
  </Icon>
);

const FuelIcon = (p) => (
  <Icon {...p}>
    <path d="M5 21V5a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v16" />
    <path d="M4 21h11" />
    <path d="M14 8h3l3 3v7a2 2 0 0 1-4 0v-4h-2" />
    <path d="M7.5 7h4v4h-4z" />
  </Icon>
);

const TireIcon = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="3.1" />
    <path d="M12 4v1.8M12 18.2V20M4 12h1.8M18.2 12H20" />
  </Icon>
);

const SnowIcon = (p) => (
  <Icon {...p}>
    <path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5 4.2 16.5" />
    <path d="M9 4.4 12 7l3-2.6M9 19.6 12 17l3 2.6" />
  </Icon>
);

const CarIcon = (p) => (
  <Icon {...p}>
    <path d="M4 16v-2.6L6.2 8h11.6L20 13.4V16" />
    <path d="M3 16h18v3.2h-2.6L17.4 17H6.6l-1 2.2H3z" />
    <circle cx="7.6" cy="16.4" r="1.2" />
    <circle cx="16.4" cy="16.4" r="1.2" />
  </Icon>
);

const BrakeIcon = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M10 17V7h3a3 3 0 0 1 0 6h-3" />
  </Icon>
);

const RadarIcon = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="1.8" />
    <path d="M12 3a9 9 0 0 1 9 9M12 6.5A5.5 5.5 0 0 1 17.5 12M3 12h3M18 12h3M12 18v3" />
  </Icon>
);

const RadioIcon = (p) => (
  <Icon {...p}>
    <path d="M4 20V8l16-3v12" />
    <circle cx="7.5" cy="17" r="2.6" />
    <circle cx="17" cy="15.5" r="2.6" />
    <path d="M10.1 17V9.8l6.9-1.3" />
  </Icon>
);

const WetIcon = (p) => (
  <Icon {...p}>
    <path d="M12 3.5c2.4 3 4.5 5.6 4.5 8.2A4.5 4.5 0 0 1 12 16.2a4.5 4.5 0 0 1-4.5-4.5c0-2.6 2.1-5.2 4.5-8.2Z" />
    <path d="M9.6 12.1c.2 1.2 1.1 2 2.4 2" />
  </Icon>
);

/* -------------------------------------------------------------- tachometer */

function Tachometer({ rpm, gear, mode }) {
  const needleAngle = START_ANGLE + (clamp(rpm, 0, RPM_MAX) / RPM_MAX) * SWEEP - 270;

  const ticks = React.useMemo(
    () =>
      Array.from({ length: 101 }, (_, i) => {
        const major = i % 10 === 0;
        const [x1, y1] = polar(200, 200, major ? 160 : 171, START_ANGLE + (i / 100) * SWEEP);
        const [x2, y2] = polar(200, 200, 181, START_ANGLE + (i / 100) * SWEEP);
        return { x1, y1, x2, y2, major, red: i >= 80 };
      }),
    []
  );

  const numbers = React.useMemo(
    () =>
      Array.from({ length: 11 }, (_, n) => {
        const [x, y] = polar(200, 200, 138, START_ANGLE + (n / 10) * SWEEP);
        return { n, x, y, red: n >= 8 };
      }),
    []
  );

  const [arcX1, arcY1] = polar(200, 200, 186, START_ANGLE + 0.8 * SWEEP);
  const [arcX2, arcY2] = polar(200, 200, 186, START_ANGLE + SWEEP);

  return (
    <div className="relative" style={{ width: "35.5cqw", height: "35.5cqw" }}>
      {/* cyan halo */}
      <div
        className="absolute -inset-[7%] rounded-full opacity-70 blur-2xl"
        style={{
          background:
            "radial-gradient(circle, rgba(70,230,255,.32) 0%, rgba(20,120,160,.14) 44%, rgba(0,0,0,0) 70%)",
        }}
      />

      <svg viewBox="0 0 400 400" className="absolute inset-0 h-full w-full overflow-visible">
        <defs>
          <radialGradient id="mclDial" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#f2feff" />
            <stop offset="12%" stopColor="#c8fbff" />
            <stop offset="30%" stopColor="#59e6ff" stopOpacity=".82" />
            <stop offset="48%" stopColor="#1287a8" stopOpacity=".55" />
            <stop offset="66%" stopColor="#062430" stopOpacity=".92" />
            <stop offset="83%" stopColor="#010a0e" />
            <stop offset="100%" stopColor="#000000" />
          </radialGradient>
          <radialGradient id="mclCore" cx="50%" cy="45%" r="42%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity=".9" />
            <stop offset="45%" stopColor="#8ff5ff" stopOpacity=".45" />
            <stop offset="100%" stopColor="#38f8ff" stopOpacity="0" />
          </radialGradient>
          <filter id="mclNum" x="-60%" y="-60%" width="220%" height="220%">
            <feDropShadow dx="0" dy="2.5" stdDeviation="1.2" floodColor="#000" floodOpacity=".95" />
            <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#7ef2ff" floodOpacity=".3" />
          </filter>
          <filter id="mclRedGlow" x="-60%" y="-60%" width="220%" height="220%">
            <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#ff2020" floodOpacity=".85" />
          </filter>
        </defs>

        {/* black outer ring */}
        <circle cx="200" cy="200" r="188" fill="#030607" stroke="#0a0f13" strokeWidth="1.5" />
        <circle cx="200" cy="200" r="181" fill="none" stroke="#13202a" strokeWidth="2" />

        {/* dial face */}
        <circle cx="200" cy="200" r="175" fill="url(#mclDial)" />
        <circle cx="200" cy="200" r="150" fill="url(#mclCore)" opacity=".55" />
        <circle cx="200" cy="200" r="156" fill="none" stroke="#8ff4ff" strokeOpacity=".1" />
        <circle cx="200" cy="200" r="120" fill="none" stroke="#8ff4ff" strokeOpacity=".07" />

        {/* red zone 8k–10k */}
        <path
          d={`M ${arcX1} ${arcY1} A 186 186 0 0 1 ${arcX2} ${arcY2}`}
          fill="none"
          stroke="#ff2323"
          strokeWidth="5"
          strokeLinecap="round"
          opacity=".9"
          filter="url(#mclRedGlow)"
        />

        {/* ticks */}
        {ticks.map((t, i) => (
          <line
            key={i}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke={t.red ? "#ff3b3b" : t.major ? "#eafcff" : "#5d8b99"}
            strokeOpacity={t.major ? 0.95 : 0.55}
            strokeWidth={t.major ? 2.2 : 1}
          />
        ))}

        {/* 0–10 with floating 3D numbers; 8–10 neon red */}
        {numbers.map(({ n, x, y, red }) => (
          <g key={n} filter="url(#mclNum)">
            <text
              x={x}
              y={y + 2.5}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="27"
              fontWeight="800"
              fill="#000"
              opacity=".6"
              style={{ fontFamily: "Orbitron, sans-serif" }}
            >
              {n}
            </text>
            <text
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="27"
              fontWeight="800"
              fill={red ? "#ff2f2f" : "#f2feff"}
              style={{
                fontFamily: "Orbitron, sans-serif",
                filter: red
                  ? "drop-shadow(0 0 7px rgba(255,40,40,.85))"
                  : "drop-shadow(0 0 7px rgba(150,245,255,.45))",
              }}
            >
              {n}
            </text>
          </g>
        ))}

        <text
          x="200"
          y="255"
          textAnchor="middle"
          fontSize="10"
          letterSpacing="3"
          fill="#8fd8e6"
          fillOpacity=".4"
          style={{ fontFamily: "Rajdhani, sans-serif" }}
        >
          x1000 r/min
        </text>
      </svg>

      {/* needle */}
      <motion.div
        className="absolute z-20 rounded-full"
        style={{
          left: "calc(50% - 0.085cqw)",
          bottom: "50%",
          width: "0.17cqw",
          height: "41%",
          transformOrigin: "50% 100%",
          background: "linear-gradient(to top, #5a0000 0%, #ff1f1f 40%, #ff8a8a 82%, #fff 100%)",
          boxShadow: "0 0 12px rgba(255,30,30,.9), 0 0 34px rgba(255,30,30,.4)",
        }}
        initial={false}
        animate={{ rotate: needleAngle }}
        transition={{ type: "spring", stiffness: 42, damping: 12, mass: 0.7 }}
      />

      {/* hollow red hub */}
      <div className="absolute left-1/2 top-1/2 z-30 h-[4.6%] w-[4.6%] -translate-x-1/2 -translate-y-1/2 rounded-full border-[0.16cqw] border-red-500 bg-black shadow-[0_0_18px_rgba(255,30,30,.75)]">
        <div className="absolute inset-[24%] rounded-full bg-red-500/25" />
      </div>

      {/* P / AUTO badge */}
      <div
        className="absolute z-20 flex flex-col items-center justify-center rounded-[0.8cqw] border border-white/10 bg-black/75 px-[1.05cqw] py-[0.5cqw] shadow-[0_0_30px_rgba(0,0,0,.9),inset_0_0_20px_rgba(0,220,255,.05)]"
        style={{ left: "50%", bottom: "11%" }}
      >
        <span className="font-display text-[3.05cqw] font-bold leading-[0.95] text-white drop-shadow-[0_0_10px_rgba(255,255,255,.35)]">
          {gear}
        </span>
        <span className="font-body text-[0.66cqw] font-semibold leading-none tracking-[0.32em] text-white/55">
          {mode}
        </span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- waveform */

function Waveform() {
  const bars = React.useMemo(
    () =>
      Array.from({ length: 24 }, (_, i) => ({
        height: 26 + Math.abs(Math.sin(i * 1.7)) * 74,
        duration: 0.9 + ((i * 7) % 9) * 0.11,
        delay: (i % 7) * 0.06,
      })),
    []
  );

  return (
    <div className="mt-[0.7cqw] flex h-[2.7cqw] w-full items-center justify-end gap-[0.14cqw]">
      {bars.map((bar, i) => (
        <motion.span
          key={i}
          className="w-[0.26cqw] rounded-full bg-gradient-to-t from-cyan-500/30 via-cyan-300 to-white"
          style={{
            height: `${bar.height}%`,
            transformOrigin: "bottom",
            boxShadow: "0 0 6px rgba(56,248,255,.55)",
          }}
          animate={{ scaleY: [0.28, 1, 0.4, 0.86, 0.32] }}
          transition={{
            repeat: Infinity,
            duration: bar.duration,
            delay: bar.delay,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------- panel */

/**
 * DashboardMcLaren
 * Ultra-wide 21:9 supercar cluster (McLaren GT / Artura inspired).
 *
 * @param {number} rpm     0..10000  — drives the tachometer needle
 * @param {number} speed   km/h
 * @param {string} gear    big letter in the P badge (default "P")
 * @param {number} odo     odometer in km
 * @param {string} time    clock string, e.g. "10:22"
 * @param {number} temp    ambient temperature in °C
 * @param {number} fuel    0..1 tank level (dotted bar)
 * @param {number} fmFreq  FM frequency, e.g. 91.1
 * @param {string} mode    small label under the gear (default "AUTO")
 */
export default function DashboardMcLaren({
  rpm = 500,
  speed = 0,
  gear = "P",
  odo = 1612,
  time = "10:22",
  temp = 27,
  fuel = 0.62,
  fmFreq = 91.1,
  mode = "AUTO",
}) {
  const fuelPct = clamp(fuel, 0, 1);
  const litres = Number(fmFreq).toFixed(2);
  const dots = Math.round(fuelPct * 16);

  return (
    <div
      className="relative w-full select-none overflow-hidden bg-black text-white"
      style={{ aspectRatio: "21 / 9", containerType: "inline-size" }}
    >
      {/* ambient carbon + glow */}
      <div className="absolute inset-0 mcl-carbon" />
      <div className="absolute inset-0 mcl-scan" />
      <div className="absolute left-1/2 top-[50%] h-[78%] w-[48%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-400/10 blur-[90px]" />
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 100% at 50% 45%, transparent 28%, rgba(0,0,0,.55) 72%, #000 100%)",
        }}
      />

      {/* cluster shell — arched top edge */}
      <div
        className="mcl-bevel absolute inset-[1.8%] overflow-hidden bg-[#010406]/85"
        style={{
          borderTopLeftRadius: "50% 8%",
          borderTopRightRadius: "50% 8%",
          borderBottomLeftRadius: "6% 8%",
          borderBottomRightRadius: "6% 8%",
        }}
      >
        {/* thin cyan inner rim */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            borderRadius: "inherit",
            boxShadow:
              "inset 0 0 0 1px rgba(120,235,255,.10), inset 0 2px 24px rgba(80,230,255,.05)",
          }}
        />
        <div className="absolute left-1/2 top-[1.2%] h-px w-[62%] -translate-x-1/2 bg-gradient-to-r from-transparent via-cyan-300/40 to-transparent" />

        {/* bottom bar backing */}
        <div className="pointer-events-none absolute inset-x-[2%] bottom-[0.9%] h-[8%] rounded-b-[2cqw] bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
        <div className="pointer-events-none absolute inset-x-[7%] bottom-[9.4%] h-px bg-gradient-to-r from-transparent via-cyan-300/15 to-transparent" />

        {/* top bar */}
        <div className="absolute inset-x-[5.2%] top-[5.2%] z-20 flex items-center justify-between font-body">
          <div className="flex items-center gap-[0.8cqw]">
            <span className="h-[0.5cqw] w-[0.5cqw] rounded-full bg-cyan-300 shadow-[0_0_8px_rgba(56,248,255,.9)]" />
            <span className="font-display text-[1.12cqw] tracking-[0.28em] text-white/90">
              {time}
            </span>
          </div>

          <div className="flex items-center gap-[1.3cqw]">
            <span className="font-display text-[1.12cqw] tracking-[0.1em] text-white/90">
              {Math.round(Number(temp) || 0)}°C
            </span>
            <div className="flex items-center gap-[0.45cqw]">
              <WetIcon className="h-[1.35cqw] w-[1.35cqw] text-lime-300 drop-shadow-[0_0_6px_rgba(198,255,58,.7)]" />
              <span className="text-[1cqw] font-semibold tracking-[0.22em] text-lime-200/85">
                S WET
              </span>
            </div>
          </div>
        </div>

        {/* giant tachometer */}
        <div className="absolute left-1/2 top-[49.5%] z-10 -translate-x-1/2 -translate-y-1/2">
          <Tachometer rpm={rpm} gear={gear} mode={mode} />
        </div>

        {/* speed — left */}
        <div className="absolute left-[4.6%] top-[43%] z-20">
          <div className="flex items-end gap-[1cqw]">
            <span className="font-display text-[7.2cqw] font-extrabold leading-none text-[#eafcff] mcl-glow-cyan">
              {Math.round(Number(speed) || 0)}
            </span>
            <span className="mb-[1.1cqw] font-body text-[1.25cqw] font-semibold tracking-[0.22em] text-white/55">
              km/h
            </span>
          </div>
          <div className="mt-[0.55cqw] h-[0.16cqw] w-[10.5cqw] bg-gradient-to-r from-red-500 via-red-500/70 to-transparent shadow-[0_0_10px_rgba(255,40,40,.7)]" />
        </div>

        {/* FM / media — right */}
        <div className="absolute right-[4%] top-[33%] z-20 flex w-[14.5cqw] flex-col items-end">
          <div className="flex items-center gap-[0.55cqw]">
            <RadioIcon className="h-[1.35cqw] w-[1.35cqw] text-cyan-300" />
            <span className="font-display text-[1.15cqw] tracking-[0.3em] text-cyan-200/90">
              FM
            </span>
          </div>

          <Waveform />

          <div className="mt-[0.8cqw] flex w-full items-center gap-[0.7cqw] rounded-[0.7cqw] border border-cyan-300/15 bg-white/[0.035] px-[0.9cqw] py-[0.6cqw]">
            <RadarIcon className="h-[1.35cqw] w-[1.35cqw] text-cyan-300/90" />
            <span className="font-display text-[1.25cqw] tracking-[0.06em] text-[#eafcff]">
              {litres}
            </span>
            <span className="font-body text-[0.95cqw] tracking-[0.1em] text-white/35">
              / {litres}
            </span>
          </div>
        </div>

        {/* bottom bar */}
        <div className="absolute inset-x-[3%] bottom-[2.4%] z-20 flex items-center justify-between font-body">
          {/* left: odo + lights + belt */}
          <div className="flex items-center gap-[0.9cqw]">
            <span className="text-[1.05cqw] tracking-[0.14em] text-white/80">
              odo <span className="font-display text-[1.05cqw] text-white">{Math.round(Number(odo) || 0)}</span>km
            </span>
            <span className="h-[1.6cqw] w-px bg-white/15" />
            <HeadlightIcon className="h-[1.45cqw] w-[1.45cqw] text-lime-300 mcl-glow-lime" />
            <AutoIcon className="h-[1.45cqw] w-[1.45cqw] text-lime-300 mcl-glow-lime" />
            <BeltIcon className="h-[1.5cqw] w-[1.5cqw] text-red-500 drop-shadow-[0_0_7px_rgba(255,40,40,.75)]" />
          </div>

          {/* center: fuel */}
          <div className="flex items-center gap-[0.8cqw]">
            <FuelIcon className="h-[1.45cqw] w-[1.45cqw] text-white/85" />
            <div className="flex items-center gap-[0.22cqw]">
              {Array.from({ length: 16 }, (_, i) => (
                <span
                  key={i}
                  className="h-[0.28cqw] w-[0.28cqw] rounded-full"
                  style={{
                    background: i < dots ? "#8ff5ff" : "rgba(255,255,255,.16)",
                    boxShadow: i < dots ? "0 0 6px rgba(56,248,255,.7)" : "none",
                  }}
                />
              ))}
            </div>
            <span className="ml-[0.3cqw] text-[0.95cqw] tracking-[0.16em] text-white/55">
              --- km
            </span>
          </div>

          {/* right: tire + climate + car */}
          <div className="flex items-center gap-[0.95cqw] text-white/80">
            <div className="flex items-center gap-[0.35cqw]">
              <TireIcon className="h-[1.4cqw] w-[1.4cqw] text-sky-400" />
              <span className="text-[0.95cqw] font-semibold tracking-[0.12em] text-sky-300/90">
                SE
              </span>
            </div>
            <div className="flex items-center gap-[0.35cqw]">
              <SnowIcon className="h-[1.35cqw] w-[1.35cqw] text-cyan-200/80" />
              <span className="text-[0.95cqw] tracking-[0.08em]">19.0°C</span>
            </div>
            <CarIcon className="h-[1.55cqw] w-[1.55cqw] text-white/85" />
          </div>
        </div>
      </div>

      {/* blurred steering wheel in the foreground */}
      <div className="pointer-events-none absolute inset-0 z-40 overflow-hidden">
        {/* soft rim mass */}
        <div className="absolute left-1/2 top-[88%] h-[84%] w-[58%] -translate-x-1/2 rounded-full border-[3.4cqw] border-[#050608] opacity-75 blur-[20px]" />
        {/* rim highlight */}
        <div className="absolute left-1/2 top-[88.5%] h-[84%] w-[58%] -translate-x-1/2 rounded-full border-[0.26cqw] border-[#454b55]/80 opacity-75 blur-[7px]" />
        {/* spokes */}
        <div className="absolute left-[21%] top-[90%] h-[30%] w-[11%] rotate-[42deg] rounded-full bg-[#0a0b0d] opacity-85 blur-[16px]" />
        <div className="absolute right-[21%] top-[90%] h-[30%] w-[11%] -rotate-[42deg] rounded-full bg-[#0a0b0d] opacity-85 blur-[16px]" />
        <div className="absolute left-1/2 top-[99%] h-[18%] w-[8%] -translate-x-1/2 rounded-t-[45%] bg-[#08090b] opacity-90 blur-[10px]" />
      </div>

      {/* handbrake light — outside the cluster, bottom-right */}
      <div className="absolute bottom-[1%] right-[0.9%] z-50">
        <div className="grid h-[2.7cqw] w-[2.7cqw] place-items-center rounded-full border-[0.14cqw] border-red-500 bg-black/85 shadow-[0_0_20px_rgba(255,30,30,.8)]">
          <BrakeIcon className="h-[1.7cqw] w-[1.7cqw] text-red-500 drop-shadow-[0_0_7px_rgba(255,40,40,.9)]" />
        </div>
      </div>
    </div>
  );
}
