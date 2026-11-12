// Buzz quiz: a four player buzzer game show on Athena's own question banks.
// Runs full screen over the shell. Everything after opening is driven by the Buzz buzzers:
// the show moves on by itself, and any red buzzer skips ahead. Party answers never touch
// study progress; only a game history row is saved at the end.
// Look and feel follow Ascend (glass, cyan accent, mono labels); the host is an original
// particle orb and all sound is synthesised, so nothing is borrowed from any real show.

import { api, qs } from "../api.js";
import { escapeHtml as esc, toast } from "../ui.js";

export const title = () => "Buzz quiz";

// ------------------------------------------------------------------ constants

const BUTTONS = ["red", "blue", "orange", "green", "yellow"];
const COLORS = ["blue", "orange", "green", "yellow"]; // answer buttons, top to bottom on a handset
// The receiver reports 20 buttons, 5 per handset, in HID order red, yellow, green, orange, blue.
const DEFAULT_LAYOUT = { stride: 5, red: 0, yellow: 1, green: 2, orange: 3, blue: 4 };
const PLAYER_COLORS = ["#22d3ee", "#f17a11", "#a78bfa", "#facc15"];
const LENGTHS = {
  short: { label: "Short", ff: 3, buzz: 6, snatch: 3, potatoes: 1, final: 3 },
  normal: { label: "Normal", ff: 5, buzz: 10, snatch: 5, potatoes: 2, final: 5 },
  long: { label: "Long", ff: 8, buzz: 16, snatch: 8, potatoes: 3, final: 8 },
};
const FOCI = [["all", "Whole syllabus"], ["pyq", "Past-paper topics"]];
// MST: the decks on the mid-semester syllabus. EST: the whole course, leaning on what came after the MST.
const EXAMS = { EST: { label: "EST", long: "End-semester", blurb: "Whole course, weighted to what came after the MST" },
  MST: { label: "MST", long: "Mid-semester", blurb: "Only the decks on the MST syllabus" } };
const ANSWER_TIMES = [5, 10, 15];
const BUZZ_WINDOWS = [1, 2, 3];
const POINTS = { base: 500, speed: 500, buzz: 500, penalty: 250, snatch: 300, pass: 100, boom: 500, ko: 500 };
const DAMAGE = { wrong: 20, boom: 50 };
const GUARD_MS = 1200; // a frantic buzz cannot skip the next screen by accident
const RED_GRACE_MS = 700; // red is ignored this long after a question appears
const MIN_SUBJECT_QUESTIONS = 8;
const CAL_STEPS = [[0, "red"], [0, "blue"], [0, "orange"], [0, "green"], [0, "yellow"], [1, "red"]];
const CIRC = 2 * Math.PI * 42; // timer ring circumference (r = 42 in a 100 box)
// Text sizes step down with length so long slide wording still fits its panel.
const sizeClass = (text, m, l, xl) => (text.length > xl ? "xl" : text.length > l ? "l" : text.length > m ? "m" : "");

const LINES = {
  hello: ["Welcome to the Buzz quiz! I'm Bolt. Press your red buzzers to join.", "Hello, hello! Bolt here. Red buzzers to join, green to start the show."],
  join: ["{name} is in!", "{name} has entered the studio.", "Here comes {name}. Act natural.", "{name}, ready to lose gracefully?"],
  needPlayers: ["Somebody press a red buzzer first!"],
  pick: ["{subject}! Good choice.", "{subject}. Let's see what you remember.", "Ooh, {subject}."],
  intro_fastest: ["Fastest Finger! Everyone answers. The quicker you are, the more you score.", "Round one, Fastest Finger. Speed is everything."],
  intro_buzz: ["Buzz In! Slam red first, then you have {secs} seconds. Wrong answers hurt.", "Buzz In time. Fast fingers, brave hearts, questionable choices."],
  intro_snatch: ["Snatch! The fastest right answer steals {pts} points from the leader.", "Snatch round. Be quick and rob the leader blind."],
  intro_potato: ["Hot Potato! Only the holder answers. Right answer, pass it on. Don't be holding it when it blows!", "Hot Potato. Nobody knows when it goes off. Not even me."],
  intro_final: ["The final! Double points. Wrong answers cost you. Use your doubles wisely.", "Final round. Everything counts double. Good luck, you'll need it."],
  lockedIn: ["Answers are locked. Let's see...", "Everyone's in. The answer is...", "Locked. Drumroll please..."],
  right: ["Correct!", "Nailed it!", "Look at that brain go!", "Somebody actually studied!", "Beautiful."],
  nobody: ["Ouch. Nobody got that one.", "Silence. Beautiful, terrible silence.", "Not one of you. Wow.", "I'm not angry. Just disappointed."],
  buzzed: ["{name}!", "{name} buzzes in!", "Go on, {name}!"],
  finalAnswer: ["Is that your final answer?", "Bold choice...", "Let's see..."],
  buzzWrong: ["Nope!", "Swing and a miss, {name}.", "That's a no from me."],
  double: ["{name} doubles up! Brave.", "Double or nothing, {name}!"],
  snatch: ["{name} snatches {pts} points from {victim}! Daylight robbery!", "Thief! {name} grabs {pts} from {victim}!"],
  potatoStart: ["{name} gets the potato first. Tick tock.", "Potato goes to {name}. Good luck with that."],
  pass: ["Pass it to {name}!", "{name}, catch!", "Over to {name}!"],
  throwIt: ["{name} throws it away! Cheeky.", "{name} uses a throw! Hot hands!"],
  boom: ["Boom! {name} was holding it.", "Kaboom! Sorry, {name}. Well, not that sorry."],
  ko: ["{name} is knocked out! That costs {pts} points.", "K.O.! {name} needs a lie down."],
  leader: ["{name} leads with {score} points. Next up, {next}.", "{name} is on top with {score}. {next} is next."],
  winner: ["And the winner is {name}! Take a bow.", "{name} wins! Everyone else, there's always next time."],
  tie: ["It's a tie! You're all equally brilliant. Or equally not."],
  pyq: ["Fun fact: this topic was in your {exam} {year} paper."],
};

// ------------------------------------------------------------------ contestants: neutral faces in the player's colour
// No hair, skin tone or other identity cues, so anyone can be any player.

function avatar(i, mood) {
  const eyes = {
    idle: '<circle cx="31" cy="42" r="3.4" fill="#111"/><circle cx="49" cy="42" r="3.4" fill="#111"/>',
    happy: '<path d="M26 43 Q31 37 36 43 M44 43 Q49 37 54 43" stroke="#111" stroke-width="3" fill="none" stroke-linecap="round"/>',
    sad: '<circle cx="31" cy="44" r="3.2" fill="#111"/><circle cx="49" cy="44" r="3.2" fill="#111"/><path d="M25 37 L35 40 M55 37 L45 40" stroke="#111" stroke-width="2.5" stroke-linecap="round"/>',
    ko: '<path d="M27 38 L35 46 M35 38 L27 46 M45 38 L53 46 M53 38 L45 46" stroke="#111" stroke-width="3" stroke-linecap="round"/>',
    think: '<circle cx="32" cy="40" r="3.4" fill="#111"/><circle cx="50" cy="40" r="3.4" fill="#111"/>',
  }[mood];
  const mouth = {
    idle: '<path d="M33 56 L47 56" stroke="#111" stroke-width="3" stroke-linecap="round"/>',
    happy: '<path d="M28 52 Q40 66 52 52 Z" fill="#7a1f1f"/>',
    sad: '<path d="M31 60 Q40 52 49 60" stroke="#111" stroke-width="3" fill="none" stroke-linecap="round"/>',
    ko: '<path d="M30 58 Q34 54 38 58 T46 58 T52 57" stroke="#111" stroke-width="2.5" fill="none" stroke-linecap="round"/>',
    think: '<ellipse cx="44" cy="57" rx="4" ry="5" fill="#7a1f1f"/>',
  }[mood];
  const c = PLAYER_COLORS[i];
  return `<svg viewBox="0 0 80 80" aria-hidden="true"><circle cx="40" cy="44" r="30" fill="${c}"/>
    <circle cx="40" cy="44" r="30" fill="url(#bz-shade)"/><g transform="translate(0 2)">${eyes}${mouth}</g>
    <defs><radialGradient id="bz-shade" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#000" stop-opacity=".18"/></radialGradient></defs></svg>`;
}

// ------------------------------------------------------------------ the host: a particle orb

const ORB_STATES = {
  idle: { tint: [34, 211, 238], spin: 0.25, glow: 0.45, jitter: 0, link: 0.22 },
  speaking: { tint: [103, 232, 249], spin: 0.5, glow: 0.95, jitter: 0.015, link: 0.4 },
  thinking: { tint: [139, 92, 246], spin: 0.95, glow: 0.7, jitter: 0.03, link: 0.34 },
  win: { tint: [250, 204, 21], spin: 1.3, glow: 1, jitter: 0.02, link: 0.5 },
  alarm: { tint: [244, 63, 94], spin: 1.6, glow: 1, jitter: 0.07, link: 0.45 },
};

function makeOrb(canvas) {
  const N = 110;
  const golden = Math.PI * (3 - Math.sqrt(5));
  const pts = [];
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    pts.push([Math.cos(golden * i) * r, y, Math.sin(golden * i) * r]);
  }
  const links = [];
  for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
    const d = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2 + (pts[i][2] - pts[j][2]) ** 2;
    if (d < 0.11) links.push([i, j]);
  }
  const ctx = canvas.getContext("2d");
  const reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cur = { ...ORB_STATES.idle, tint: [...ORB_STATES.idle.tint] };
  let target = "idle";
  let angle = 0;
  let last = performance.now();
  return {
    set(state) { if (ORB_STATES[state]) target = state; },
    draw(t) {
      const dt = Math.min(0.1, (t - last) / 1000);
      last = t;
      const want = ORB_STATES[target];
      const k = 1 - Math.exp(-dt * 5); // smooth blend between moods
      for (const key of ["spin", "glow", "jitter", "link"]) cur[key] += (want[key] - cur[key]) * k;
      for (let c = 0; c < 3; c++) cur.tint[c] += (want.tint[c] - cur.tint[c]) * k;
      const dpr = window.devicePixelRatio || 1;
      const size = canvas.clientWidth * dpr;
      if (!size) return;
      if (canvas.width !== size) { canvas.width = size; canvas.height = size; }
      angle += (reduced ? 0.15 : cur.spin) * dt;
      const pulse = target === "speaking" ? 1 + 0.06 * Math.sin(t * 0.018) + 0.035 * Math.sin(t * 0.041)
        : 1 + 0.025 * Math.sin(t * 0.0016);
      const R = size * 0.33 * (reduced ? 1 : pulse);
      const cx = size / 2;
      const [r, g, b] = cur.tint.map(Math.round);
      ctx.clearRect(0, 0, size, size);
      const halo = ctx.createRadialGradient(cx, cx, R * 0.1, cx, cx, R * 1.5);
      halo.addColorStop(0, `rgba(${r},${g},${b},${0.35 * cur.glow})`);
      halo.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = halo;
      ctx.fillRect(0, 0, size, size);
      const ca = Math.cos(angle);
      const sa = Math.sin(angle);
      const tilt = 0.38;
      const ct = Math.cos(tilt);
      const st = Math.sin(tilt);
      const jit = reduced ? 0 : cur.jitter;
      const proj = pts.map(([x, y, z], i) => {
        const jx = jit ? Math.sin(t * 0.013 + i) * jit : 0;
        const x1 = (x + jx) * ca - z * sa;
        const z1 = (x + jx) * sa + z * ca;
        const y1 = y * ct - z1 * st;
        const z2 = y * st + z1 * ct;
        const s = 1 / (1.9 - z2 * 0.6);
        return [cx + x1 * R * s * 1.4, cx + y1 * R * s * 1.4, z2];
      });
      ctx.lineWidth = Math.max(1, dpr * 0.8);
      for (const [i, j] of links) {
        const depth = (proj[i][2] + proj[j][2] + 2) / 4;
        ctx.strokeStyle = `rgba(${r},${g},${b},${(cur.link * depth).toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(proj[i][0], proj[i][1]);
        ctx.lineTo(proj[j][0], proj[j][1]);
        ctx.stroke();
      }
      for (const [x, y, z] of proj) {
        const depth = (z + 1) / 2;
        ctx.fillStyle = `rgba(${Math.min(255, r + 60)},${Math.min(255, g + 40)},${Math.min(255, b + 20)},${0.35 + 0.65 * depth})`;
        ctx.beginPath();
        ctx.arc(x, y, (1 + depth * 2.2) * dpr, 0, Math.PI * 2);
        ctx.fill();
      }
      const core = ctx.createRadialGradient(cx, cx, 0, cx, cx, R * 0.45);
      core.addColorStop(0, `rgba(255,255,255,${0.5 * cur.glow})`);
      core.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = core;
      ctx.beginPath();
      ctx.arc(cx, cx, R * 0.45, 0, Math.PI * 2);
      ctx.fill();
    },
  };
}

// ------------------------------------------------------------------ scenery: a calm, still landscape per question
// Drawn as SVG in code (no image files): sky, sun or moon, stars, aurora, layered land, mist, water.

const SCENES = [
  { kind: "peaks", sky: ["#131a3a", "#3b2f63", "#b4687a", "#f3b48a"], glow: "#ffe2c2", body: { y: 0.6, r: 70, c: "#fff1dc" }, land: ["#4a3a66", "#352a52", "#251d3d", "#15112a"] },
  { kind: "sea", sky: ["#0b1d2a", "#164557", "#3f8790", "#a8d5c9"], glow: "#d8fff4", body: { y: 0.5, r: 58, c: "#f4fffb" }, land: ["#245a5c", "#1b4547", "#123335", "#0a2224"] },
  { kind: "forest", sky: ["#0d1a14", "#1f3b30", "#4f7a63", "#b9d3b8"], glow: "#eaf6e4", body: null, land: ["#365e4a", "#28493a", "#1b3529", "#10231b"], mist: true },
  { kind: "lake", sky: ["#070b1f", "#121a3f", "#24306b", "#3c4a8f"], glow: "#cfd8ff", body: { y: 0.28, r: 44, c: "#eef2ff" }, land: ["#1e2752", "#171f44", "#111735", "#0a0f25"], stars: true },
  { kind: "dunes", sky: ["#1e1410", "#5a3121", "#c0703d", "#f2c38f"], glow: "#ffe9c8", body: { y: 0.6, r: 80, c: "#fff3dd" }, land: ["#8a4b2c", "#6e3a22", "#52291a", "#371a10"] },
  { kind: "peaks", sky: ["#050a18", "#0c1830", "#123a40", "#16263d"], glow: "#b8fff0", body: null, land: ["#122434", "#0e1c2a", "#0a1520", "#060d16"], stars: true, aurora: true },
  { kind: "peaks", sky: ["#1c2133", "#3d4763", "#8a98b8", "#dfe6f2"], glow: "#ffffff", body: { y: 0.38, r: 52, c: "#ffffff" }, land: ["#7d8aa8", "#5f6b88", "#434d68", "#2b3248"], mist: true },
  { kind: "hills", sky: ["#2a1630", "#5e2f5b", "#c76b8f", "#f7c1c7"], glow: "#ffe5ea", body: { y: 0.56, r: 62, c: "#fff0f2" }, land: ["#6b3a63", "#53304f", "#3c233b", "#261626"] },
];
const RIDGE = { peaks: 140, hills: 70, dunes: 50, forest: 55 };

function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function sceneURL(n) {
  const P = SCENES[((n % SCENES.length) + SCENES.length) % SCENES.length];
  const r = seeded(n * 7919 + 13);
  const W = 1600;
  const H = 900;
  const water = P.kind === "sea" || P.kind === "lake";
  const waterTop = H * (P.kind === "sea" ? 0.6 : 0.68);
  const out = [`<defs>
    <linearGradient id="s" x1="0" y1="0" x2="0" y2="1">${P.sky.map((c, i) => `<stop offset="${(i / (P.sky.length - 1)).toFixed(2)}" stop-color="${c}"/>`).join("")}</linearGradient>
    <radialGradient id="g"><stop offset="0" stop-color="${P.glow}" stop-opacity=".5"/><stop offset="1" stop-color="${P.glow}" stop-opacity="0"/></radialGradient>
    <linearGradient id="m" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <linearGradient id="w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${P.sky[2]}" stop-opacity=".85"/><stop offset="1" stop-color="${P.land[3]}"/></linearGradient>
    <filter id="b" x="-20%" y="-150%" width="140%" height="400%"><feGaussianBlur stdDeviation="28"/></filter></defs>`,
  `<rect width="${W}" height="${H}" fill="url(#s)"/>`];
  if (P.stars) {
    for (let i = 0; i < 110; i++) out.push(`<circle cx="${(r() * W).toFixed(0)}" cy="${(r() * H * 0.55).toFixed(0)}" r="${(r() * 1.5 + 0.4).toFixed(1)}" fill="#fff" opacity="${(r() * 0.55 + 0.2).toFixed(2)}"/>`);
  }
  if (P.aurora) {
    for (let k = 0; k < 2; k++) {
      const y0 = H * (0.2 + k * 0.1);
      let d = `M-50 ${y0.toFixed(0)}`;
      for (let x = -50; x <= W; x += 150) d += ` Q${x + 75} ${(y0 + (r() - 0.5) * 140).toFixed(0)} ${x + 150} ${(y0 + (r() - 0.5) * 70).toFixed(0)}`;
      out.push(`<path d="${d}" stroke="${k ? "#7dd3fc" : "#5eead4"}" stroke-width="${80 - k * 30}" fill="none" opacity=".3" filter="url(#b)"/>`);
    }
  }
  const bx = W * (0.25 + r() * 0.5);
  if (P.body) {
    const by = H * P.body.y;
    out.push(`<circle cx="${bx.toFixed(0)}" cy="${by.toFixed(0)}" r="${P.body.r * 4}" fill="url(#g)"/><circle cx="${bx.toFixed(0)}" cy="${by.toFixed(0)}" r="${P.body.r}" fill="${P.body.c}" opacity=".92"/>`);
  }
  const layers = water ? P.land.slice(0, 2) : P.land;
  layers.forEach((c, li) => {
    const base = water ? waterTop + 4 - (1 - li) * 12 : H * (0.55 + li * 0.1);
    const amp = (water ? (P.kind === "sea" ? 26 : 120) : RIDGE[P.kind]) * (1 - li * 0.22);
    const f1 = 0.002 + r() * 0.003;
    const f2 = f1 * (2 + r());
    const p1 = r() * 6.28;
    const p2 = r() * 6.28;
    let d = `M0 ${H}`;
    for (let x = 0; x <= W; x += 16) {
      let y = base - amp * (0.6 * Math.sin(x * f1 + p1) + 0.4 * Math.sin(x * f2 + p2) + 0.5);
      if (P.kind === "peaks" || P.kind === "lake") y -= amp * 0.45 * Math.abs(Math.sin(x * f1 * 3 + p2));
      if (P.kind === "forest") y -= r() * 26 * (1 - li * 0.2); // a soft treeline
      d += ` L${x} ${Math.min(water ? waterTop : H, y).toFixed(0)}`;
    }
    d += ` L${W} ${H} Z`;
    out.push(`<path d="${d}" fill="${c}"/>`);
    if (P.mist && li < layers.length - 1) out.push(`<rect y="${(base - 30).toFixed(0)}" width="${W}" height="110" fill="url(#m)"/>`);
  });
  if (water) {
    out.push(`<rect y="${waterTop.toFixed(0)}" width="${W}" height="${(H - waterTop).toFixed(0)}" fill="url(#w)"/>`);
    if (P.body) {
      for (let i = 0; i < 9; i++) {
        const ww = P.body.r * (2.3 - i * 0.17);
        out.push(`<rect x="${(bx - ww / 2).toFixed(0)}" y="${(waterTop + 18 + i * 24).toFixed(0)}" width="${ww.toFixed(0)}" height="3" rx="1.5" fill="${P.body.c}" opacity="${(0.32 - i * 0.03).toFixed(2)}"/>`);
      }
    }
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice">${out.join("")}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

// Cross-fade to a new scene: the two layers take turns.
function setScene(n) {
  if (!S) return;
  const [a, b] = S.dom.scenes;
  const next = S.sceneFlip ? a : b;
  const prev = S.sceneFlip ? b : a;
  next.style.backgroundImage = sceneURL(n);
  next.classList.add("on");
  prev.classList.remove("on");
  S.sceneFlip = !S.sceneFlip;
}
function nextScene() { S.sceneN += 1; setScene(S.sceneBase + S.sceneN); }

// ------------------------------------------------------------------ state and storage

let S = null;
let rafId = 0;

function loadPrefs() {
  let p = {};
  try { p = JSON.parse(localStorage.getItem("athena-buzz") || "{}") || {}; } catch { p = {}; }
  const layoutOk = (L) => L && Number.isInteger(L.stride) && BUTTONS.every((b) => Number.isInteger(L[b]) && L[b] >= 0) && buildLookup(L).size === 20;
  return {
    names: Array.isArray(p.names) ? p.names : [],
    length: LENGTHS[p.length] ? p.length : "normal",
    answerTime: ANSWER_TIMES.includes(p.answerTime) ? p.answerTime : 10,
    buzzWindow: BUZZ_WINDOWS.includes(p.buzzWindow) ? p.buzzWindow : 2,
    // Until someone picks a voice, it stays off unless a natural-sounding one is available (see rankVoices).
    voice: typeof p.voice === "boolean" ? p.voice : false,
    voiceChosen: p.voiceChosen === true,
    voiceName: typeof p.voiceName === "string" ? p.voiceName : "",
    exam: EXAMS[p.exam] ? p.exam : "EST",
    play: p.play === "learn" ? "learn" : "show",
    music: typeof p.music === "boolean" ? p.music : true,
    prize: typeof p.prize === "string" ? p.prize.slice(0, 80) : "Bragging rights",
    focus: FOCI.some(([k]) => k === p.focus) ? p.focus : "all",
    subject: typeof p.subject === "string" ? p.subject : "",
    layout: layoutOk(p.layout) ? p.layout : { ...DEFAULT_LAYOUT },
  };
}

function savePrefs() {
  if (!S) return;
  const subject = S.subjects[S.sel];
  try {
    localStorage.setItem("athena-buzz", JSON.stringify({
      names: S.players.map((p) => p.name), length: S.length, answerTime: S.answerTime, buzzWindow: S.buzzWindow,
      voice: S.voice, voiceChosen: S.voiceChosen, voiceName: S.voiceName, exam: S.exam, play: S.play,
      music: S.music, prize: S.prize, focus: S.focus, subject: subject ? subject.id : "", layout: S.layout,
    }));
  } catch { /* private mode: settings just reset next time */ }
}

function buildLookup(L) {
  const map = new Map();
  for (let p = 0; p < 4; p++) for (const b of BUTTONS) map.set(L[b] + p * L.stride, { player: p, button: b });
  return map;
}

const now = () => performance.now();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const shuffle = (arr) => { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const joined = () => S.players.map((p, i) => (p.joined ? i : -1)).filter((i) => i >= 0);
const fill = (text, vars = {}) => text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
const fmtDate = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }); } catch { return iso; } };
const fmtNum = (n) => Number(n).toLocaleString("en-IN");

// ------------------------------------------------------------------ sound (all synthesised)

let actx = null;
let noiseBuf = null;
function audio() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  if (!actx) actx = new Ctx();
  if (actx.state === "suspended") actx.resume().catch(() => { /* needs a click first; sounds stay off */ });
  return actx;
}
function tone(freq, dur = 0.15, type = "square", vol = 0.08, delay = 0, slideTo = null) {
  const ctx = audio();
  if (!ctx) return;
  const t = ctx.currentTime + delay;
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
  g.gain.setValueAtTime(vol, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g);
  g.connect(ctx.destination);
  o.start(t);
  o.stop(t + dur + 0.05);
}
// A short burst of filtered noise: claps, snare hits, whooshes.
function hiss(dur, { freq = 1800, q = 0.8, vol = 0.12, delay = 0, sweepTo = null, attack = 0.005 } = {}) {
  const ctx = audio();
  if (!ctx) return;
  if (!noiseBuf) {
    noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  const t = ctx.currentTime + delay;
  const src = ctx.createBufferSource();
  src.buffer = noiseBuf;
  src.loop = true;
  const f = ctx.createBiquadFilter();
  f.type = "bandpass";
  f.frequency.setValueAtTime(freq, t);
  if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, t + dur);
  f.Q.value = q;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(f);
  f.connect(g);
  g.connect(ctx.destination);
  src.start(t, Math.random() * 0.5);
  src.stop(t + dur + 0.05);
}
const SFX = {
  join: (i) => { tone(440 + i * 110, 0.12, "triangle", 0.1); tone(660 + i * 165, 0.15, "triangle", 0.1, 0.1); },
  move: () => tone(900, 0.04, "square", 0.04),
  buzz: (i) => tone([300, 360, 420, 480][i], 0.45, "sawtooth", 0.12, 0, [600, 720, 840, 960][i]),
  lock: () => tone(1200, 0.06, "square", 0.05),
  double: () => [600, 800, 1200].forEach((f, k) => tone(f, 0.08, "square", 0.06, k * 0.06)),
  right: () => [523, 659, 784, 1047].forEach((f, k) => tone(f, 0.18, "triangle", 0.1, k * 0.09)),
  wrong: () => { tone(196, 0.5, "sawtooth", 0.11, 0, 98); tone(185, 0.5, "square", 0.05, 0.02, 92); },
  tick: () => tone(880, 0.05, "sine", 0.06),
  whoosh: () => hiss(0.45, { freq: 300, sweepTo: 4000, q: 0.6, vol: 0.1, attack: 0.15 }),
  drumroll: (secs = 1.1) => {
    const hits = Math.floor(secs / 0.045);
    for (let i = 0; i < hits; i++) hiss(0.06, { freq: 2600, q: 0.9, vol: 0.03 + (0.09 * i) / hits, delay: i * 0.045 });
    hiss(0.35, { freq: 1800, q: 0.6, vol: 0.22, delay: secs });
    tone(70, 0.4, "sine", 0.25, secs, 45);
  },
  applause: (secs = 2.4, big = false) => {
    const claps = Math.floor(secs * (big ? 70 : 45));
    for (let i = 0; i < claps; i++) {
      const at = Math.random() * secs;
      const fade = 1 - at / (secs * 1.15);
      hiss(0.05 + Math.random() * 0.04, { freq: 900 + Math.random() * 1800, q: 1.2, vol: (0.03 + Math.random() * 0.05) * fade, delay: at });
    }
    hiss(secs, { freq: 1500, q: 0.4, vol: 0.05, attack: 0.25 });
  },
  boom: () => { hiss(1.4, { freq: 180, sweepTo: 60, q: 0.5, vol: 0.5, attack: 0.01 }); tone(80, 1.2, "sine", 0.4, 0, 30); },
  ko: () => [400, 300, 200, 120].forEach((f, k) => tone(f, 0.18, "square", 0.08, k * 0.12)),
  fanfare: () => [523, 659, 784, 1047, 784, 1047, 1319].forEach((f, k) => tone(f, 0.28, "triangle", 0.11, k * 0.14)),
};

// A quiet suspense bed while a question is open: a low pulse and soft ticks.
function musicStart(fast = false) {
  musicStop();
  if (!S || !S.music) return;
  const beat = fast ? 0.28 : 0.42;
  let n = 0;
  S.musicTimer = setInterval(() => {
    const low = n % 4 === 0;
    tone(low ? 55 : 62, beat * 0.9, "sine", low ? 0.16 : 0.09);
    if (n % 2 === 1) hiss(0.04, { freq: 7000, q: 1, vol: 0.02 });
    if (n % 8 === 6) tone(110, beat * 0.6, "triangle", 0.05);
    n += 1;
  }, beat * 1000);
}
function musicStop() { if (S && S.musicTimer) { clearInterval(S.musicTimer); S.musicTimer = null; } }

// ------------------------------------------------------------------ host voice

// English voices, most natural first: Edge's "Natural" voices, then Chrome's Google voices, then the rest.
let voices = [];
function rankVoices() {
  if (!("speechSynthesis" in window)) return;
  const score = (v) => (/natural/i.test(v.name) ? 100 : 0) + (/online/i.test(v.name) ? 20 : 0) + (/^google/i.test(v.name) ? 50 : 0)
    + (/^en-IN/i.test(v.lang) ? 15 : /^en-GB/i.test(v.lang) ? 10 : 5);
  voices = speechSynthesis.getVoices().filter((v) => /^en/i.test(v.lang)).sort((a, b) => score(b) - score(a));
  if (!S) return;
  // Robotic voices made the host feel cheap, so the voice starts on only when a natural one exists.
  if (!S.voiceChosen) S.voice = voices.some(isNatural);
  if (S.phase === "lobby") renderMain();
}
const isNatural = (v) => /natural/i.test(v.name);
const voiceLabel = (v) => v.name.replace(/^(Microsoft|Google)\s+/i, "").replace(/\s*\(Natural\)|\s+Online|\s+-\s+.*$/gi, "").trim();
const currentVoice = () => voices.find((v) => v.name === S.voiceName) || voices[0] || null;

// The host says a line: it shows in the speech bubble and, with the voice on, is spoken.
function say(text, { bubble = true } = {}) {
  if (!S || !text) return;
  if (bubble) {
    S.dom.say.textContent = text;
    S.dom.bubble.classList.remove("pop");
    void S.dom.bubble.offsetWidth; // restart the pop animation
    S.dom.bubble.classList.add("pop");
  }
  const quietUntil = now() + Math.min(4500, 700 + text.length * 45);
  if (!S.voice || !("speechSynthesis" in window)) { S.speakingUntil = quietUntil; return; }
  try {
    speechSynthesis.cancel(); // the newest line always wins, so the host never lags behind the game
    const u = new SpeechSynthesisUtterance(text);
    const voice = currentVoice();
    if (voice) u.voice = voice;
    u.rate = 1; // natural pace and pitch: speeding up or raising the pitch is what makes it sound robotic
    u.pitch = 1;
    const done = () => { if (S && S.utter === u) { S.utter = null; S.speakingUntil = 0; } };
    u.onend = done;
    u.onerror = done;
    S.utter = u;
    S.speakingUntil = now() + 15000; // safety net if the browser never reports the end
    speechSynthesis.speak(u);
  } catch (err) {
    console.warn("Host voice failed", err);
    S.speakingUntil = quietUntil;
  }
}
const line = (kind, vars, extra = "") => say(fill(pick(LINES[kind]), vars) + (extra ? " " + extra : ""));
const speaking = () => S && now() < S.speakingUntil;
function shutUp() { if ("speechSynthesis" in window) speechSynthesis.cancel(); }

// ------------------------------------------------------------------ stage effects

function orbFlash(state, ms = 1800) { S.orbFlash = { state, until: now() + ms }; }
function orbMood() {
  if (S.orbFlash && now() < S.orbFlash.until) return S.orbFlash.state;
  if (S.phase === "final") return "win";
  if (speaking()) return "speaking";
  if (["question", "revealing", "potato", "potatoJudging", "countdown"].includes(S.phase)) return "thinking";
  return "idle";
}
function dim(on) { S.dom.stage.classList.toggle("dim", on); }
function strike() {
  const s = S.dom.strike;
  s.hidden = false;
  s.innerHTML = '<div class="x"></div>'; // a fresh element restarts the stamp animation
  clearTimeout(S.strikeTimer);
  S.strikeTimer = setTimeout(() => { if (S) S.dom.strike.hidden = true; }, 950);
}

// ------------------------------------------------------------------ lights (Athena server drives the receiver)

function setLights(on) {
  if (!S) return;
  S.lights = on.map(Boolean);
  S.dom.pods.querySelectorAll(".bz-dome").forEach((d, i) => d.classList.toggle("lit", S.lights[i]));
  pushLights();
}
async function pushLights() {
  if (!S || S.lightsOff) return;
  if (S.lightsBusy) { S.lightsDirty = true; return; }
  S.lightsBusy = true;
  try {
    do {
      S.lightsDirty = false;
      await api.post("/buzz/lights", { on: S.lights });
    } while (S && S.lightsDirty);
  } catch (err) {
    if (S) {
      S.lightsOff = true; // stop retrying; the game plays fine without lights
      if (err.status === 503) toast("Buzzer lights not found. Is the receiver plugged in? The game works without them.");
      else console.warn("Buzzer lights failed", err);
    }
  } finally {
    if (S) S.lightsBusy = false;
  }
}
function stopBlink() { if (S && S.blink) { clearInterval(S.blink); S.blink = null; } }
function blink(players, ms = 0) {
  stopBlink();
  let on = true;
  setLights([0, 1, 2, 3].map((i) => players.includes(i)));
  S.blink = setInterval(() => { on = !on; setLights([0, 1, 2, 3].map((i) => on && players.includes(i))); }, ms ? 110 : 400);
  if (ms) {
    const mine = S.blink;
    setTimeout(() => { if (S && S.blink === mine) { stopBlink(); setLights([false, false, false, false]); } }, ms);
  }
}

// ------------------------------------------------------------------ input

function findPad() {
  if (!navigator.getGamepads) return null;
  const pads = [...navigator.getGamepads()].filter(Boolean);
  return pads.find((p) => /054c|buzz/i.test(p.id)) || pads.find((p) => p.buttons.length >= 20) || null;
}

function poll() {
  const pad = findPad();
  const id = pad ? pad.id : null;
  if (id !== S.padId) { S.padId = id; S.prev = []; if (S.phase === "lobby") renderMain(); }
  if (!pad) return;
  pad.buttons.forEach((b, i) => {
    if (b.pressed && !S.prev[i]) onRaw(i);
    S.prev[i] = b.pressed;
  });
}

function onRaw(i) {
  audio();
  if (S.phase === "calibrate") { calibrateRaw(i); return; }
  const hit = S.lookup.get(i);
  if (!hit) return;
  flashKey(hit.player, hit.button);
  onButton(hit.player, hit.button);
}

function flashKey(p, b) {
  const pod = S.dom.pods.children[p];
  if (!pod) return;
  const target = b === "red" ? pod.querySelector(".bz-dome") : null; // only the buzzer dome reacts on screen
  if (!target) return;
  target.classList.add(b === "red" ? "press" : "on");
  setTimeout(() => target.classList.remove("press", "on"), 220);
}

const settled = () => now() - S.phaseAt >= GUARD_MS;

function onButton(p, b) {
  const pl = S.players[p];
  switch (S.phase) {
    case "lobby": lobbyButton(p, b); return;
    case "final": case "recap":
      if (!pl.joined || !settled()) return;
      if (b === "red") startGame();
      else if (b === "green") showLobby();
      else if (b === "blue") { if (S.phase === "final") showRecap(); else backToFinal(); }
      return;
    case "intro": case "teach": case "reveal": case "scores": case "boom":
      if (pl.joined && b === "red" && settled()) runAuto();
      return;
    case "question":
      // A red press meant to skip the previous screen must not buzz in or spend a x2 by accident.
      if (pl.joined && !(b === "red" && now() - S.phaseAt < RED_GRACE_MS)) questionButton(p, b);
      return;
    case "potato":
      if (pl.joined && p === S.game.potato.holder) {
        if (b === "red") throwPotato(p);
        else { const c = COLORS.indexOf(b); if (c >= 0 && c < S.q.options.length) potatoAnswer(c); }
      }
      return;
    default:
  }
}

function lobbyButton(p, b) {
  const pl = S.players[p];
  if (b === "red") {
    if (!pl.joined) { pl.joined = true; SFX.join(p); line("join", { name: pl.name }); setLights(S.players.map((x) => x.joined)); renderPods(); }
    return;
  }
  if (!pl.joined) return;
  if (b === "blue" || b === "yellow") moveSubject(b === "blue" ? -1 : 1);
  else if (b === "orange") cycleMode();
  else if (b === "green") startGame();
}

function questionButton(p, b) {
  const round = S.game.rounds[S.game.r];
  const c = COLORS.indexOf(b);
  if (round.mode === "buzz") {
    if (b === "red") buzzIn(p);
    else if (c >= 0) buzzAnswer(p, c);
  } else if (b === "red") useDouble(p);
  else if (c >= 0) lockIn(p, c);
}

export function onKey(e) {
  if (!S) return;
  if (e.target && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
  if (e.key === "Escape") { e.preventDefault(); if (S.phase === "lobby") exitShow(); else if (S.phase === "calibrate" || confirm("End this show and go back to the lobby?")) showLobby(); }
  else if ((e.key === " " || e.key === "Enter") && ["intro", "reveal", "scores", "boom"].includes(S.phase)) { e.preventDefault(); runAuto(); }
}

// ------------------------------------------------------------------ phases and the automatic flow

function setPhase(p) {
  stopBlink();
  S.phase = p;
  S.phaseAt = now();
  S.auto = null;
  S.token = (S.token || 0) + 1; // lets timers notice that the show has moved on
}

// Move on by itself once the host has finished talking (or after maxMs at the latest).
function autoAdvance(fn, minMs, maxMs) { S.auto = { fn, at: now() + minMs, max: now() + maxMs }; }
function runAuto() { if (S.auto) { const fn = S.auto.fn; S.auto = null; fn(); } }

function tick(t) {
  if (!S) return;
  poll();
  S.orb.set(orbMood());
  S.orb.draw(t);
  if (S.auto && t >= S.auto.at && (!speaking() || t >= S.auto.max)) runAuto();
  if (S.phase === "question") {
    if (S.buzz.holder !== null && !S.buzz.judging) {
      if (t >= S.buzz.deadline) wrongBuzz(S.buzz.holder, true);
    } else if (S.buzz.holder === null && t >= S.timer.end) {
      reveal();
    } else if (S.buzz.holder === null) {
      const secs = Math.ceil((S.timer.end - t) / 1000);
      if (secs <= 3 && secs !== S.lastTick) { S.lastTick = secs; SFX.tick(); }
    }
    if (S.phase === "question") updateClock(t);
  } else if (["potato", "potatoJudging", "potatoPause"].includes(S.phase)) {
    const pot = S.game.potato;
    if (t >= pot.fuseEnd) boom();
    else if (t >= pot.nextTick) { SFX.tick(); pot.nextTick = t + Math.max(150, 800 - (t - pot.fuseStart) * 0.025); }
  }
  rafId = requestAnimationFrame(tick);
}

function updateClock(t) {
  const c = S.dom.clock;
  if (!c || !c.isConnected) return;
  const answering = S.buzz.holder !== null;
  const total = answering ? S.buzzWindow * 1000 : S.timer.total;
  const left = Math.max(0, answering ? S.buzz.deadline - t : S.timer.end - t);
  const frac = left / total;
  c.querySelector(".fg").style.strokeDashoffset = (CIRC * (1 - frac)).toFixed(1);
  const n = String(Math.ceil(left / 1000));
  const label = c.querySelector(".n");
  if (label.textContent !== n) label.textContent = n;
  c.classList.toggle("hot", answering || frac < 0.25);
  c.classList.toggle("warn", !answering && frac >= 0.25 && frac < 0.5);
}

// A 3, 2, 1 before the first question of each round.
function countdown(then) {
  setPhase("countdown");
  const token = S.token;
  let n = 3;
  const step = () => {
    if (!S || S.token !== token) return;
    if (n === 0) { SFX.whoosh(); then(); return; }
    S.countN = n;
    renderMain();
    SFX.tick();
    n -= 1;
    setTimeout(step, 750);
  };
  step();
}

// ------------------------------------------------------------------ lobby

// Subjects in board order for the chosen exam: soonest exam first, then the rest by name.
function boardOrder() {
  const days = (s) => (s.exams[S.exam] ? s.exams[S.exam].days_left : 9999);
  return S.subjects.map((s, i) => i).sort((a, b) => days(S.subjects[a]) - days(S.subjects[b])
    || S.subjects[a].short_name.localeCompare(S.subjects[b].short_name));
}

function moveSubject(dir) {
  const order = boardOrder();
  const n = order.length;
  const at = Math.max(0, order.indexOf(S.sel));
  for (let k = 1; k <= n; k++) {
    const i = order[(((at + dir * k) % n) + n) % n];
    if (subjectCount(S.subjects[i]) >= MIN_SUBJECT_QUESTIONS) { S.sel = i; break; }
  }
  SFX.move();
  savePrefs();
  renderMain();
  clearTimeout(S.pickTimer);
  S.pickTimer = setTimeout(() => { if (S && S.phase === "lobby") line("pick", { subject: S.subjects[S.sel].name }); }, 700);
}

// Orange steps through the four ways to play: EST whole course, EST past papers, MST, MST past papers.
function cycleMode() {
  const modes = [["EST", "all"], ["EST", "pyq"], ["MST", "all"], ["MST", "pyq"]];
  const i = modes.findIndex(([e, f]) => e === S.exam && f === S.focus);
  [S.exam, S.focus] = modes[(i + 1) % modes.length];
  applyExamTheme();
  SFX.move();
  savePrefs();
  renderMain();
  say(`${EXAMS[S.exam].long} prep. ${FOCI.find(([k]) => k === S.focus)[1]}.`);
}

function setExam(exam) {
  S.exam = exam;
  applyExamTheme();
  savePrefs();
  renderMain();
}

// EST shows run in gold, MST shows in cyan, so it is obvious at a glance which exam you are revising for.
function applyExamTheme() {
  S.dom.stage.classList.toggle("est", S.exam === "EST");
  S.dom.stage.classList.toggle("mst", S.exam === "MST");
}

function subjectCount(s) {
  if (!s) return 0;
  const c = s.counts[S.exam];
  return S.focus === "pyq" && c.pyq ? c.pyq : c.all;
}

function showLobby() {
  shutUp();
  musicStop();
  setPhase("lobby");
  setScene(S.sceneBase);
  applyExamTheme();
  S.game = null;
  dim(false);
  renderTop();
  renderMain(true);
  renderPods();
  setLights(S.players.map((p) => p.joined));
  line("hello");
  api.get("/buzz/setup").then((setup) => {
    if (!S) return;
    S.history = setup.history;
    if (S.phase === "lobby") renderMain();
  }).catch(() => { /* history is a nice extra */ });
}

// ------------------------------------------------------------------ game

async function startGame() {
  if (!joined().length) { line("needPlayers"); return; }
  const subject = S.subjects[S.sel];
  if (!subject || S.loading) return;
  S.loading = true;
  if (S.play === "learn") { startLearning(subject); return; }
  const L = LENGTHS[S.length];
  const main = L.ff + L.buzz + L.snatch + L.final;
  let data;
  try {
    data = await api.get(`/buzz/questions${qs({ subject_id: subject.id, exam: S.exam, focus: S.focus, count: Math.min(120, main + L.potatoes * 12) })}`);
  } catch (err) {
    if (S) { S.loading = false; toast(err.message); }
    return;
  }
  if (!S) return; // left the page while loading
  S.loading = false;
  const pool = data.questions.slice();
  if (pool.length < 5) { toast(`${subject.short_name} has too few multiple choice questions for a show yet.`); return; }
  const scale = Math.min(1, pool.length / (main + 4));
  const take = (n) => Math.max(1, Math.floor(n * scale));
  const rounds = [
    { mode: "fastest", name: "Fastest Finger", mult: 1, penalty: false, n: take(L.ff) },
    { mode: "buzz", name: "Buzz In", mult: 1, penalty: true, n: take(L.buzz) },
    { mode: "snatch", name: "Snatch", mult: 1, penalty: false, n: take(L.snatch) },
    { mode: "potato", name: "Hot Potato", potatoes: L.potatoes },
    { mode: "final", name: "Double Trouble", mult: 2, penalty: true, n: take(L.final) },
  ].map((r) => (r.n ? { ...r, questions: pool.splice(0, r.n) } : r)).filter((r) => r.mode === "potato" || r.questions.length);
  S.game = { subject, exam: data.exam || S.exam, focus: data.focus, rounds, r: -1, qi: 0, spare: pool, used: [], potato: null, misses: [] };
  S.players.forEach((p) => Object.assign(p, { score: 0, hp: 100, doubles: 2, throws: 1, stats: { fastest: 0, damage: 0, snatched: 0, kos: 0 } }));
  if (data.focus !== S.focus) toast(`No past-paper topics for the ${S.exam} in ${subject.short_name} yet, so this show uses the whole ${S.exam} syllabus.`);
  savePrefs();
  SFX.fanfare();
  nextRound();
}

// Learn mode: each round is one lesson part, taught on a card, then checked with its own questions.
async function startLearning(subject) {
  const count = { short: 4, normal: 6, long: 10 }[S.length];
  let data;
  try {
    data = await api.get(`/buzz/lessons${qs({ subject_id: subject.id, exam: S.exam, count })}`);
  } catch (err) {
    if (S) { S.loading = false; toast(err.message); }
    return;
  }
  if (!S) return;
  S.loading = false;
  if (!data.lessons.length) { toast(`${subject.short_name} has no lessons with quiz checks for the ${S.exam} yet.`); return; }
  const rounds = data.lessons.map((l) => ({ mode: "learn", name: l.heading, mult: 1, penalty: false, lesson: l, questions: l.questions }));
  S.game = { subject, exam: S.exam, focus: "learn", rounds, r: -1, qi: 0, spare: [], used: [], potato: null, misses: [] };
  S.players.forEach((p) => Object.assign(p, { score: 0, hp: 100, doubles: 2, throws: 1, stats: { fastest: 0, damage: 0, snatched: 0, kos: 0 } }));
  savePrefs();
  SFX.fanfare();
  nextRound();
}

function teach(round) {
  setPhase("teach");
  setLights([false, false, false, false]);
  SFX.whoosh();
  renderTop();
  renderMain(true);
  renderPods();
  const l = round.lesson;
  say(l.big_idea || l.exam_line || l.heading);
  autoAdvance(startQuestion, 7000, 25000);
}

function nextRound() {
  const g = S.game;
  g.r += 1;
  g.qi = 0;
  musicStop();
  if (g.r >= g.rounds.length) { showFinal(); return; }
  nextScene();
  const round = g.rounds[g.r];
  if (round.mode === "learn") { teach(round); return; }
  if (round.mode === "potato") g.potato = { left: round.potatoes, holder: null, fuseStart: 0, fuseEnd: 0, nextTick: 0, answered: null, passTo: null };
  setPhase("intro");
  setLights([false, false, false, false]);
  SFX.whoosh();
  renderTop();
  renderMain(true);
  renderPods();
  line("intro_" + round.mode, { secs: S.buzzWindow, pts: POINTS.snatch });
  autoAdvance(() => countdown(round.mode === "potato" ? startPotato : startQuestion), 3000, 11000);
}

function answerFor(q) {
  if (!q.answerP) {
    q.answerP = api.get(`/buzz/answer/${encodeURIComponent(q.id)}`)
      .then((r) => ({ index: q.options.indexOf(r.answer), explanation: r.explanation || "" }));
    q.answerP.catch(() => { /* handled where it is awaited */ });
  }
  return q.answerP;
}

function startQuestion() {
  const g = S.game;
  const round = g.rounds[g.r];
  S.q = round.questions[g.qi];
  if (g.qi > 0) nextScene(); // the round intro already brought a fresh scene for question one
  g.used.push(S.q);
  answerFor(S.q);
  S.answers = [null, null, null, null];
  S.doubled = [false, false, false, false];
  S.pending = [0, 0, 0, 0];
  S.results = null;
  S.buzz = { holder: null, locked: new Set(), deadline: 0, judging: false, picked: null };
  S.timer = { total: S.answerTime * 1000, end: now() + S.answerTime * 1000, remaining: 0 };
  S.lastTick = -1;
  setPhase("question");
  dim(false);
  setLights(round.mode === "buzz" ? S.players.map((p) => p.joined) : [false, false, false, false]);
  renderTop();
  renderMain(true);
  renderPods();
  musicStart();
  // Long questions read by a robotic voice sound worst, so they are only read aloud by a natural voice.
  if (S.voice && currentVoice() && isNatural(currentVoice())) say(S.q.stem, { bubble: false });
  S.dom.say.textContent = round.mode === "buzz" ? "Red buzzer to answer!" : (round.mode === "final" ? "Double points! Red doubles again." : "Lock in your answer! Red to double up.");
}

function lockIn(p, choice) {
  if (S.answers[p] || choice >= S.q.options.length) return;
  S.answers[p] = { choice, at: now() };
  SFX.lock();
  setLights(S.players.map((_, i) => !!S.answers[i]));
  if (joined().every((i) => S.answers[i])) { reveal(); return; }
  renderPods();
}

function useDouble(p) {
  const pl = S.players[p];
  if (S.doubled[p] || S.answers[p] || pl.doubles <= 0) return;
  S.doubled[p] = true;
  pl.doubles -= 1;
  SFX.double();
  line("double", { name: pl.name });
  renderPods();
}

function buzzIn(p) {
  if (S.buzz.holder !== null || S.buzz.locked.has(p)) return;
  const t = now();
  S.buzz.holder = p;
  S.buzz.deadline = t + S.buzzWindow * 1000;
  S.timer.remaining = Math.max(0, S.timer.end - t);
  SFX.buzz(p);
  line("buzzed", { name: S.players[p].name });
  setLights(S.players.map((_, i) => i === p));
  renderMain();
  renderPods();
}

// The buzzed-in player picks: their panel lights up, a short drumroll, then the verdict.
async function buzzAnswer(p, choice) {
  if (S.buzz.holder !== p || S.buzz.judging || choice >= S.q.options.length) return;
  S.buzz.judging = true;
  S.buzz.picked = choice;
  S.answers[p] = { choice, at: now() };
  SFX.lock();
  musicStop();
  line("finalAnswer");
  SFX.drumroll(0.85);
  renderMain();
  const ansP = answerFor(S.q);
  await sleep(950);
  let ans;
  try { ans = await ansP; } catch (err) { ans = { index: -1 }; toast(err.message); }
  if (!S || S.phase !== "question" || S.buzz.holder !== p) return;
  S.buzz.judging = false;
  S.buzz.picked = null;
  if (choice === ans.index) {
    S.pending[p] += POINTS.buzz * S.game.rounds[S.game.r].mult;
    reveal({ suspense: false });
  } else {
    wrongBuzz(p, false);
    musicStart();
  }
}

function wrongBuzz(p, timedOut) {
  S.pending[p] -= POINTS.penalty;
  damage(p, DAMAGE.wrong);
  S.buzz.locked.add(p);
  S.buzz.holder = null;
  S.buzz.judging = false;
  S.buzz.picked = null;
  SFX.wrong();
  strike();
  orbFlash("alarm", 1200);
  if (joined().every((i) => S.buzz.locked.has(i))) { reveal({ suspense: false }); return; }
  line("buzzWrong", { name: S.players[p].name }, timedOut ? "Too slow!" : "");
  S.timer.end = now() + Math.max(S.timer.remaining, 3000);
  setLights(S.players.map((pl, i) => pl.joined && !S.buzz.locked.has(i)));
  renderMain();
  renderPods();
}

function damage(p, amount) {
  const pl = S.players[p];
  pl.hp = Math.max(0, pl.hp - amount);
  pl.stats.damage += amount;
}

// A player at 0 health is knocked out: they lose points and get back up at full health.
function checkKOs() {
  const kos = [];
  S.players.forEach((pl, i) => {
    if (pl.joined && pl.hp <= 0) {
      pl.score -= POINTS.ko;
      pl.hp = 100;
      pl.stats.kos += 1;
      kos.push(i);
    }
  });
  return kos;
}

async function reveal({ suspense = true } = {}) {
  if (S.phase !== "question") return;
  setPhase("revealing");
  musicStop();
  const token = S.token;
  const ansP = answerFor(S.q);
  if (suspense) {
    dim(true);
    line("lockedIn");
    SFX.drumroll(1.1);
    renderMain();
    renderPods();
    await sleep(1200);
  }
  let ans;
  try { ans = await ansP; } catch (err) { toast(err.message); ans = { index: -1, explanation: "" }; }
  if (!S || S.token !== token) return;
  dim(false);
  const round = S.game.rounds[S.game.r];
  S.before = S.players.map((p) => p.score);
  S.results = S.players.map((pl, i) => {
    if (!pl.joined) return null;
    if (round.mode === "buzz") return { delta: S.pending[i] };
    const a = S.answers[i];
    const mult = round.mult * (S.doubled[i] ? 2 : 1);
    if (a && a.choice === ans.index) {
      const frac = Math.max(0, Math.min(1, (S.timer.end - a.at) / S.timer.total));
      return { delta: Math.round((POINTS.base + POINTS.speed * frac) / 10) * 10 * mult };
    }
    if (a) {
      if (round.mode !== "learn") damage(i, DAMAGE.wrong * (S.doubled[i] ? 2 : 1)); // learning should not hurt
      return { delta: round.penalty || S.doubled[i] ? -POINTS.penalty * (S.doubled[i] ? 2 : 1) : 0 };
    }
    return { delta: 0 };
  });
  S.results.forEach((r, i) => { if (r) S.players[i].score += r.delta; });
  const right = joined().filter((i) => S.answers[i] && S.answers[i].choice === ans.index).sort((a, b) => S.answers[a].at - S.answers[b].at);
  if (right.length && round.mode !== "buzz") S.players[right[0]].stats.fastest += 1;
  S.snatch = round.mode === "snatch" ? applySnatch(right) : null;
  const kos = checkKOs();
  kos.forEach((i) => { S.results[i].ko = true; });
  S.answer = ans;
  const missed = round.mode === "buzz" ? !joined().some((i) => S.pending[i] > 0)
    : joined().some((i) => !(S.answers[i] && S.answers[i].choice === ans.index));
  if (missed) addMiss(S.q, ans);
  setPhase("reveal");
  const winners = joined().filter((i) => S.results[i] && S.results[i].delta > 0);
  if (winners.length) {
    SFX.right();
    SFX.applause(winners.length > 1 ? 2.2 : 1.8);
    blink(winners);
    orbFlash("win");
  } else {
    SFX.wrong();
    if (round.mode !== "buzz") strike();
    setLights([false, false, false, false]);
    orbFlash("alarm", 1400);
  }
  if (kos.length) setTimeout(() => SFX.ko(), 500);
  renderMain();
  renderPods(true);
  const pyq = S.q.pyq && S.q.pyq[0];
  if (kos.length) line("ko", { name: S.players[kos[0]].name, pts: POINTS.ko });
  else if (S.snatch && S.snatch.amount) line("snatch", { name: S.players[S.snatch.thief].name, victim: S.players[S.snatch.victim].name, pts: S.snatch.amount });
  else line(winners.length ? "right" : "nobody", {}, pyq ? fill(LINES.pyq[0], pyq) : "");
  autoAdvance(nextQuestion, 3200 + (ans.explanation ? 1800 : 0), 9000);
}

// Remember a question someone got wrong or nobody answered, for the revision list at the end.
function addMiss(q, ans) {
  const g = S.game;
  if (!g || ans.index < 0 || g.misses.some((m) => m.id === q.id)) return;
  g.misses.push({ id: q.id, stem: q.stem, answer: q.options[ans.index], why: ans.explanation || "", pyq: (q.pyq && q.pyq[0]) || null });
}

function applySnatch(right) {
  if (!right.length) return null;
  const thief = right[0];
  const others = joined().filter((i) => i !== thief).sort((a, b) => S.players[b].score - S.players[a].score);
  if (!others.length) return null;
  const victim = others[0];
  const amount = Math.min(POINTS.snatch, Math.max(0, S.players[victim].score));
  S.players[victim].score -= amount;
  S.players[thief].score += amount;
  S.players[thief].stats.snatched += amount;
  S.results[victim].delta -= amount;
  S.results[thief].delta += amount;
  return { thief, victim, amount };
}

function nextQuestion() {
  const g = S.game;
  g.qi += 1;
  if (g.qi < g.rounds[g.r].questions.length) startQuestion();
  else if (g.rounds[g.r].mode === "learn") nextRound(); // straight to the next lesson, no scoreboard in between
  else showScores();
}

// ------------------------------------------------------------------ hot potato

function spareQuestion() {
  const g = S.game;
  if (!g.spare.length) g.spare = shuffle(g.used); // ran out: replay earlier questions in a new order
  return g.spare.pop();
}

function startPotato() {
  const pot = S.game.potato;
  const t = now();
  if (pot.left < S.game.rounds[S.game.r].potatoes) nextScene(); // a new potato, a new scene
  pot.holder = pick(joined());
  pot.fuseStart = t;
  pot.fuseEnd = t + 20000 + Math.random() * 15000; // nobody knows when
  pot.nextTick = t;
  musicStart(true);
  potatoQuestion();
  line("potatoStart", { name: S.players[pot.holder].name });
}

function potatoQuestion() {
  S.q = spareQuestion();
  answerFor(S.q);
  S.game.potato.answered = null;
  setPhase("potato");
  setLights(S.players.map((_, i) => i === S.game.potato.holder));
  renderTop();
  renderMain(true);
  renderPods();
}

function nextHolder(from) {
  const ids = joined();
  return ids[(ids.indexOf(from) + 1) % ids.length];
}

async function potatoAnswer(choice) {
  const pot = S.game.potato;
  setPhase("potatoJudging");
  const token = S.token;
  let ans;
  try { ans = await answerFor(S.q); } catch (err) { ans = { index: -1 }; toast(err.message); }
  if (!S || S.token !== token) return; // it blew up while we were checking
  const correct = choice === ans.index;
  pot.answered = { choice, correct, index: ans.index };
  if (correct) { S.players[pot.holder].score += POINTS.pass; pot.passTo = nextHolder(pot.holder); SFX.right(); }
  else { pot.passTo = pot.holder; SFX.wrong(); strike(); addMiss(S.q, ans); }
  potatoPause();
}

function throwPotato(p) {
  const pot = S.game.potato;
  const pl = S.players[p];
  if (pl.throws <= 0 || joined().length < 2) return;
  pl.throws -= 1;
  pot.answered = { thrown: true };
  pot.passTo = nextHolder(p);
  SFX.whoosh();
  line("throwIt", { name: pl.name });
  potatoPause();
}

function potatoPause() {
  const pot = S.game.potato;
  setPhase("potatoPause");
  const token = S.token;
  renderMain();
  renderPods();
  setTimeout(() => {
    if (!S || S.token !== token) return;
    const passed = pot.passTo !== pot.holder;
    pot.holder = pot.passTo;
    if (passed && !pot.answered.thrown) line("pass", { name: S.players[pot.holder].name });
    potatoQuestion();
  }, 1100);
}

function boom() {
  const pot = S.game.potato;
  S.before = S.players.map((p) => p.score);
  setPhase("boom");
  musicStop();
  pot.left -= 1;
  const victim = pot.holder;
  S.players[victim].score -= POINTS.boom;
  damage(victim, DAMAGE.boom);
  const kos = checkKOs();
  S.results = S.players.map((pl, i) => (pl.joined ? { delta: i === victim ? -POINTS.boom - (kos.includes(i) ? POINTS.ko : 0) : 0, ko: kos.includes(i) } : null));
  SFX.boom();
  blink([0, 1, 2, 3], 1600);
  orbFlash("alarm", 2200);
  renderMain();
  renderPods(true);
  line(kos.length ? "ko" : "boom", { name: S.players[victim].name, pts: POINTS.ko });
  autoAdvance(pot.left > 0 ? () => countdown(startPotato) : showScores, 3800, 9000);
}

// ------------------------------------------------------------------ scores and final

const ranked = () => joined().sort((a, b) => S.players[b].score - S.players[a].score);

function showScores() {
  setPhase("scores");
  nextScene();
  musicStop();
  setLights([false, false, false, false]);
  SFX.whoosh();
  renderTop();
  renderMain(true);
  renderPods();
  const order = ranked();
  const nextRoundObj = S.game.rounds[S.game.r + 1];
  const next = nextRoundObj ? nextRoundObj.name : "the final results";
  if (order.length > 1) line("leader", { name: S.players[order[0]].name, score: S.players[order[0]].score, next });
  else say(`${S.players[order[0]].name}, you have ${S.players[order[0]].score} points. Next up, ${next}.`);
  autoAdvance(nextRound, 3500, 10000);
}

function badges() {
  const ids = joined();
  const out = [];
  const best = (key, cmp) => ids.reduce((b, i) => (b === null || cmp(S.players[i].stats[key], S.players[b].stats[key]) ? i : b), null);
  const fast = best("fastest", (a, b) => a > b);
  if (fast !== null && S.players[fast].stats.fastest > 0) out.push({ p: fast, name: "Quickest fingers", why: `${S.players[fast].stats.fastest} fastest right answers` });
  const thief = best("snatched", (a, b) => a > b);
  if (thief !== null && S.players[thief].stats.snatched > 0) out.push({ p: thief, name: "Pickpocket", why: `snatched ${S.players[thief].stats.snatched} points` });
  if (ids.length > 1) {
    const tank = best("damage", (a, b) => a < b);
    out.push({ p: tank, name: "Iron wall", why: `least damage taken (${S.players[tank].stats.damage})` });
  }
  return out;
}

function showFinal() {
  setPhase("final");
  nextScene();
  musicStop();
  const order = ranked();
  const top = S.players[order[0]].score;
  S.winners = order.filter((i) => S.players[i].score === top);
  S.badges = badges();
  renderTop();
  renderMain(true);
  renderPods();
  SFX.fanfare();
  SFX.applause(4, true);
  confetti();
  blink(S.winners);
  if (S.winners.length > 1) line("tie");
  else line("winner", { name: S.players[S.winners[0]].name });
  const winnerNames = S.winners.map((i) => S.players[i].name).join(" and ");
  api.post("/buzz/games", {
    subject_id: S.game.subject.id, focus: `${S.game.exam.toLowerCase()}-${S.game.focus}`,
    players: order.map((i) => ({ name: S.players[i].name, score: S.players[i].score })),
    winner: winnerNames.slice(0, 60), prize: S.prize.slice(0, 80),
  }).catch((err) => toast("Could not save this game to the history: " + err.message));
}

// The revision list: every question that tripped someone up, with the answer and why.
function showRecap() {
  if (!S.game.misses.length) { say("Nobody missed a thing. Impressive."); return; }
  setPhase("recap");
  renderMain(true);
  renderPods();
  say(`${S.game.misses.length} to revise. Read the why, not just the answer.`);
}
function backToFinal() {
  setPhase("final");
  renderTop();
  renderMain(true);
  renderPods();
}

function confetti(ms = 5000) {
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "bz-confetti";
  document.body.append(c);
  const ctx = c.getContext("2d");
  const W = (c.width = innerWidth);
  const H = (c.height = innerHeight);
  const colors = ["#22d3ee", "#67e8f9", "#facc15", "#a78bfa", "#f17a11", "#ffffff"];
  const bits = Array.from({ length: 220 }, () => ({
    x: Math.random() * W, y: -20 - Math.random() * H * 0.6, vx: (Math.random() - 0.5) * 3, vy: 2 + Math.random() * 4,
    r: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.3, s: 6 + Math.random() * 8, c: pick(colors),
  }));
  const end = now() + ms;
  const frame = () => {
    ctx.clearRect(0, 0, W, H);
    for (const b of bits) {
      b.x += b.vx; b.y += b.vy; b.r += b.vr;
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.r); ctx.fillStyle = b.c; ctx.fillRect(-b.s / 2, -b.s / 4, b.s, b.s / 2); ctx.restore();
    }
    if (now() < end && c.isConnected) requestAnimationFrame(frame); else c.remove();
  };
  requestAnimationFrame(frame);
}

// ------------------------------------------------------------------ calibration

function startCalibrate() {
  if (!findPad()) { toast("No buzzers seen yet. Press any button on a handset, then try again."); return; }
  setPhase("calibrate");
  S.cal = [];
  renderMain();
}

function calibrateRaw(i) {
  if (S.cal.includes(i)) { toast("That button is already used. Press the one asked for."); return; }
  S.cal.push(i);
  SFX.lock();
  if (S.cal.length < CAL_STEPS.length) { renderMain(); return; }
  const [red, blue, orange, green, yellow, red2] = S.cal;
  const L = { stride: red2 - red, red, blue, orange, green, yellow };
  const map = buildLookup(L);
  if (L.stride <= 0 || map.size !== 20) { toast("That layout did not make sense. Let's try again."); S.cal = []; renderMain(); return; }
  S.layout = L;
  S.lookup = map;
  savePrefs();
  toast("Button layout saved.");
  showLobby();
}

// ------------------------------------------------------------------ rendering

function renderTop() {
  const g = S.game;
  let meta = "";
  if (g && g.r >= 0 && g.r < g.rounds.length && S.phase !== "final") {
    const round = g.rounds[g.r];
    meta = `<span class="bz-roundtag">${g.exam} prep · Round ${g.r + 1} · ${esc(round.name)}${round.mult > 1 ? " x2" : ""}</span>
      <span class="bz-eyebrow">${esc(g.subject.short_name)} · ${esc(g.focus === "learn" ? "Learn while playing" : FOCI.find(([k]) => k === g.focus)[1])}</span>`;
  } else if (S.phase === "final") {
    meta = '<span class="bz-roundtag">Final results</span>';
  } else {
    meta = '<span class="bz-roundtag">Buzz quiz · Lobby</span>';
  }
  const inShow = S.phase !== "lobby" && S.phase !== "calibrate";
  S.dom.meta.innerHTML = `${meta}<span class="bz-actions">
    <button class="bz-btn ghost" data-act="fullscreen">Full screen</button>
    <button class="bz-btn ghost" data-act="${inShow ? "lobby" : "exit"}">${inShow ? "End show" : "Exit"}</button></span>`;
}

function renderMain(enter = false) {
  const m = S.dom.main;
  m.className = "bz-main" + (enter ? " bz-enter" : "");
  m.innerHTML = {
    teach: teachHTML, lobby: lobbyHTML, calibrate: calibrateHTML, intro: introHTML, countdown: countdownHTML, question: questionHTML,
    revealing: questionHTML, reveal: questionHTML, potato: potatoHTML, potatoJudging: potatoHTML, potatoPause: potatoHTML,
    boom: boomHTML, scores: scoresHTML, final: finalHTML, recap: recapHTML,
  }[S.phase]();
  S.dom.clock = m.querySelector(".bz-clock");
  if (S.phase === "lobby") {
    const prize = m.querySelector("#bzPrize");
    if (prize) prize.addEventListener("input", () => { S.prize = prize.value.slice(0, 80); savePrefs(); });
  }
}

function lobbyHTML() {
  const pad = findPad();
  const tiles = boardOrder().map((i) => {
    const s = S.subjects[i];
    const n = subjectCount(s);
    const e = s.exams[S.exam];
    const when = e ? (e.days_left === 0 ? "today" : e.days_left === 1 ? "tomorrow" : `${e.days_left}d`) : "";
    const exam = e ? `<span class="exam">${S.exam} ${esc(fmtDate(e.date))} · ${when}</span>` : "";
    const count = n >= MIN_SUBJECT_QUESTIONS ? `${fmtNum(n)} Qs` : n ? `Only ${n} Qs` : "No quiz questions yet";
    return `<button class="bz-tile ${i === S.sel ? "sel" : ""} ${e ? "soon" : ""}" style="--sc:${esc(s.color || "#22d3ee")}" data-act="subject" data-i="${i}" ${n < MIN_SUBJECT_QUESTIONS ? "disabled" : ""}>
      <span class="code">${esc(s.short_name)}</span><span class="name">${esc(s.name)}</span>
      <span class="foot"><span class="count">${count}</span>${exam}</span></button>`;
  }).join("");
  const examSwitch = Object.keys(EXAMS).map((k) => `<button class="bz-exam ${k === S.exam ? "on" : ""} ${k.toLowerCase()}" data-act="exam" data-v="${k}">
    <span class="big">${EXAMS[k].label}</span><span class="sub">${EXAMS[k].long}</span><span class="ex-why">${EXAMS[k].blurb}</span></button>`).join("");
  const seg = (label, list, cur, act, show = (x) => x) => `<div class="bz-setting"><span class="bz-eyebrow">${label}</span><div class="bz-seg">${
    list.map((x) => `<button class="${String(x) === String(cur) ? "on" : ""}" data-act="${act}" data-v="${esc(String(x))}">${esc(show(x))}</button>`).join("")}</div></div>`;
  const voiceList = voices.slice(0, 4);
  const voicePicker = seg(`Host voice${voices.some((v) => /natural/i.test(v.name)) ? "" : " · Edge has the most natural voices"}`,
    ["off", ...voiceList.map((v) => v.name)], S.voice && currentVoice() ? currentVoice().name : "off", "voice",
    (x) => (x === "off" ? "Off" : voiceLabel(voiceList.find((v) => v.name === x))));
  const hist = S.history.length ? S.history.slice(0, 6).map((h) => `<li><span class="d">${esc(fmtDate(h.played_at))} · ${esc(h.short_name)}${/^(est|mst)-/.test(h.focus) ? ` · ${esc(h.focus.slice(0, 3).toUpperCase())}` : ""}</span>
      <span class="w">${esc(h.winner || "?")}</span><span class="s">${h.players[0] ? fmtNum(h.players[0].score) : ""}</span>${h.prize ? `<span class="p">${esc(h.prize)}</span>` : ""}</li>`).join("")
    : '<li><span class="d">No shows yet</span><span class="w">The first winner goes here</span><span></span></li>';
  return `
  <div class="bz-legend"><span><i style="--kc:var(--red)"></i>Red join</span>
    <span><i style="--kc:var(--k-blue)"></i><i style="--kc:var(--k-yellow)"></i>Blue / yellow subject</span>
    <span><i style="--kc:var(--k-orange)"></i>Orange EST / MST and topics</span><span><i style="--kc:var(--k-green)"></i>Green start</span>
    ${pad ? "" : "<span>Press any buzzer to wake them up</span>"}</div>
  <div class="bz-lobby">
    <section class="bz-holo bz-panel">
      <div class="bz-panelhead"><span class="bz-eyebrow cyan">${EXAMS[S.exam].long} revision · choose a subject</span><span class="bz-eyebrow">Next ${S.exam} first</span></div>
      <div class="bz-board">${tiles}</div>
      <div class="bz-setting"><span class="bz-eyebrow">Hall of fame</span><ul class="bz-hist">${hist}</ul></div>
    </section>
    <section class="bz-holo bz-panel">
      <div class="bz-examswitch">${examSwitch}</div>
      <div class="bz-cta" style="justify-content:space-between;align-items:center"><button class="bz-btn go" data-act="start">${S.play === "learn" ? `Start ${S.exam} lesson` : `Start ${S.exam} show`}</button><button class="bz-btn ghost" data-act="calibrate">Fix buttons</button></div>
      ${seg("Mode", ["learn", "show"], S.play, "play", (k) => (k === "learn" ? "Learn while playing" : "Game show"))}
      ${S.play === "show" ? seg("Topics", FOCI.map(([k]) => k), S.focus, "focus", (k) => FOCI.find(([x]) => x === k)[1]) : ""}
      <div class="bz-grid2">
        ${seg("Show length", Object.keys(LENGTHS), S.length, "length", (k) => LENGTHS[k].label)}
        ${seg("Answer time", ANSWER_TIMES, S.answerTime, "answerTime", (x) => x + "s")}
        ${seg("After a buzz", BUZZ_WINDOWS, S.buzzWindow, "buzzWindow", (x) => x + "s")}
        ${seg("Music", ["on", "off"], S.music ? "on" : "off", "music")}
      </div>
      ${voicePicker}
      <div class="bz-setting"><span class="bz-eyebrow">Prize for the winner</span><input id="bzPrize" class="bz-input" maxlength="80" value="${esc(S.prize)}" aria-label="Prize for the winner"></div>
    </section>
  </div>`;
}

function calibrateHTML() {
  const [p, color] = CAL_STEPS[S.cal.length];
  return `<div class="bz-center"><span class="bz-eyebrow cyan">Fix buzzer buttons · step ${S.cal.length + 1} of ${CAL_STEPS.length}</span>
    <div class="bz-word sm">Handset ${p + 1}: press <span class="k-${color}">${color}</span></div>
    <p class="bz-lead">Only needed if a button lights the wrong colour or player.</p>
    <div class="bz-cta"><button class="bz-btn" data-act="calReset">Reset to default</button><button class="bz-btn" data-act="lobby">Cancel</button></div></div>`;
}

function introHTML() {
  const g = S.game;
  const round = g.rounds[g.r];
  const rules = {
    fastest: `Everyone answers with <b>blue, orange, green or yellow</b>. Faster right answers score up to <b>1,000</b>. Red plays a <b>x2</b>: double the points, double the risk.`,
    buzz: `Hit <b>red</b> first, then answer within <b>${S.buzzWindow} second${S.buzzWindow === 1 ? "" : "s"}</b>. Right: <b>+${POINTS.buzz}</b>. Wrong or too slow: <b>-${POINTS.penalty}</b> and damage.`,
    snatch: `Everyone answers. The fastest right answer snatches <b>${POINTS.snatch}</b> points straight from the leader.`,
    potato: `Only the holder answers. Right: <b>+${POINTS.pass}</b> and pass it on. When it blows, the holder loses <b>${POINTS.boom}</b>. Red throws it away, once per game.`,
    final: `Everything counts <b>double</b>. Wrong answers cost <b>${POINTS.penalty * 2}</b> and hurt. Still got a x2? Red stacks it.`,
  }[round.mode];
  const count = round.mode === "potato" ? `${round.potatoes} potato${round.potatoes === 1 ? "" : "es"}` : `${round.questions.length} questions`;
  return `<div class="bz-center"><span class="bz-eyebrow cyan">Round ${g.r + 1} of ${g.rounds.length} · ${count}</span>
    <div class="bz-word">${esc(round.name)}</div>
    <div class="bz-card bz-holo"><p class="bz-lead">${rules}</p></div></div>`;
}

function teachHTML() {
  const g = S.game;
  const l = g.rounds[g.r].lesson;
  const terms = l.terms.map((k) => `<li><b>${esc(k.term)}</b><span>${esc(k.meaning)}</span></li>`).join("");
  return `<div class="bz-center"><span class="bz-eyebrow cyan">Lesson ${g.r + 1} of ${g.rounds.length} · ${esc(l.topic_title)}</span>
    <div class="bz-teach bz-holo"><h2>${esc(l.heading)}</h2>
      ${l.big_idea ? `<p class="big">${esc(l.big_idea)}</p>` : ""}
      ${terms ? `<ul class="terms">${terms}</ul>` : ""}
      ${l.exam_line ? `<p class="exam"><span class="bz-eyebrow cyan">For the exam</span>${esc(l.exam_line)}</p>` : ""}</div>
    <span class="bz-eyebrow">Questions on this in a moment · red to skip ahead</span></div>`;
}

function countdownHTML() {
  const round = S.game.rounds[S.game.r];
  return `<div class="bz-center"><span class="bz-eyebrow cyan">${esc(round.name)}</span>
    <div class="bz-count" data-n="${S.countN}">${S.countN}</div><span class="bz-eyebrow">Get ready</span></div>`;
}

function answersHTML(marks, pickers = []) {
  // Every option in a question gets the same text size (from the longest), so the grid stays even.
  const size = sizeClass(S.q.options.reduce((a, o) => (o.length > a.length ? o : a), ""), 36, 72, 115);
  return S.q.options.map((o, j) => `<div class="bz-opt ${size} ${marks(j)}" style="--i:${j};--kc:var(--k-${COLORS[j]})">
    <span class="orb" aria-label="${COLORS[j]} button"></span><span class="txt">${esc(o)}</span>
    <span class="who">${(pickers[j] || []).map((i) => `<span style="--pc:${PLAYER_COLORS[i]}">${esc(S.players[i].name)}</span>`).join("")}</span></div>`).join("");
}
const answersGrid = (inner) => `<div class="bz-answers">${inner}</div>`;
const questionPanel = () => `<div class="bz-holo bz-qpanel" data-qid="${esc(S.q.id)}"><p class="bz-q ${sizeClass(S.q.stem, 70, 120, 180)}">${esc(S.q.stem)}</p></div>`;

function questionHTML() {
  const revealed = S.phase === "reveal";
  const round = S.game.rounds[S.game.r];
  const pickers = COLORS.map(() => []);
  if (revealed) S.players.forEach((pl, i) => { if (pl.joined && S.answers[i]) pickers[S.answers[i].choice].push(i); });
  const marks = (j) => {
    if (revealed) {
      if (j === S.answer.index) return "correct";
      return pickers[j].length ? "wrongpick dim" : "dim";
    }
    return S.buzz.picked === j ? "picked" : "";
  };
  let prompt = "";
  if (S.phase === "revealing") prompt = "Locked in...";
  else if (!revealed && round.mode === "buzz") {
    prompt = S.buzz.picked !== null ? "Final answer..." : S.buzz.holder === null ? (S.buzz.locked.size ? "Still open! Hit red to have a go" : "Hit your red buzzer to answer")
      : `${S.players[S.buzz.holder].name}, answer now!`;
  } else if (!revealed) prompt = "Lock in with blue, orange, green or yellow";
  let info = "";
  if (revealed) {
    if (S.snatch) {
      info += `<div class="bz-chip snatch"><span class="bz-eyebrow">Snatch</span>${S.snatch.amount ? `${esc(S.players[S.snatch.thief].name)} took ${S.snatch.amount} from ${esc(S.players[S.snatch.victim].name)}`
        : `${esc(S.players[S.snatch.thief].name)} was fastest, but there was nothing to snatch`}</div>`;
    }
    const pyq = S.q.pyq && S.q.pyq[0];
    if (pyq) info += `<div class="bz-chip pyq"><span class="bz-eyebrow">Past paper</span>${esc(pyq.exam)} ${esc(pyq.year)}, Q${esc(pyq.q_no)}${pyq.marks ? ` · ${esc(pyq.marks)} marks` : ""}</div>`;
    if (S.answer.explanation) info += `<div class="bz-chip"><span class="bz-eyebrow">Why</span>${esc(S.answer.explanation)}</div>`;
  }
  const g = S.game;
  const modeCap = { learn: "Check what you just learned", fastest: "Everyone answers", buzz: "Buzz in to answer", snatch: "Fastest steals", final: "Double points" }[round.mode];
  return `<div class="bz-qcol">
      <div class="bz-qhead">
        <div class="bz-clock"><svg viewBox="0 0 100 100"><circle class="bg" cx="50" cy="50" r="42"/><circle class="fg" cx="50" cy="50" r="42" stroke-dasharray="${CIRC.toFixed(1)}" stroke-dashoffset="${revealed ? CIRC.toFixed(1) : 0}"/></svg><span class="n">${revealed ? "" : S.answerTime}</span></div>
        <div class="bz-qmeta"><span class="bz-eyebrow">Question ${g.qi + 1} of ${round.questions.length}</span><span class="v">${esc(modeCap)}</span></div>
      </div>
      ${questionPanel()}
      ${answersGrid(answersHTML(marks, pickers))}
      <div class="bz-info">${info}</div>
      <div class="bz-prompt">${esc(prompt)}</div>
    </div>`;
}

function potatoHTML() {
  const pot = S.game.potato;
  const a = pot.answered;
  const marks = (j) => (!a || a.thrown ? "" : j === a.index ? "correct" : j === a.choice ? "wrongpick dim" : "dim");
  const holder = S.players[pot.holder];
  const prompt = !a ? (S.phase === "potatoJudging" ? "Checking..." : `Only ${holder.name} can answer${holder.throws ? " · red throws it away" : ""}`)
    : a.thrown ? "Thrown!" : a.correct ? "Right! Pass it on!" : "Wrong! Still holding it...";
  const round = S.game.rounds[S.game.r];
  return `<div class="bz-qcol" style="flex:1">
    <div class="bz-potrow"><span class="bz-potato" aria-hidden="true">\u{1F954}</span>
      <span class="bz-holder" style="--pc:${PLAYER_COLORS[pot.holder]}"><b>${esc(holder.name)}</b> has the potato</span>
      <span class="bz-eyebrow">Potato ${round.potatoes - pot.left + 1} of ${round.potatoes}</span></div>
    ${questionPanel()}
    ${answersGrid(answersHTML(marks))}
    <div class="bz-info"></div>
    <div class="bz-prompt">${esc(prompt)}</div></div>`;
}

function boomHTML() {
  const pot = S.game.potato;
  return `<div class="bz-center bz-shake"><div class="bz-boom">BOOM!</div>
    <p class="bz-lead"><b>${esc(S.players[pot.holder].name)}</b> was holding it and loses <b>${POINTS.boom}</b>.${pot.left > 0 ? " Another potato is coming..." : ""}</p></div>`;
}

function scoresHTML() {
  const order = ranked();
  return `<div class="bz-center"><span class="bz-eyebrow cyan">After round ${S.game.r + 1}</span><div class="bz-word sm">Scoreboard</div>
    <div class="bz-scores">${order.map((i, k) => `<div class="bz-row bz-holo ${k === 0 ? "lead" : ""}" style="--pc:${PLAYER_COLORS[i]};--i:${k}">
      <span class="r">#${k + 1}</span><span class="nm"><i></i>${esc(S.players[i].name)}</span><span class="sc">${fmtNum(S.players[i].score)}</span></div>`).join("")}</div></div>`;
}

function finalHTML() {
  const names = S.winners.map((i) => esc(S.players[i].name)).join(" and ");
  return `<div class="bz-center"><div class="bz-trophy" aria-hidden="true">\u{1F3C6}</div>
    <div class="bz-word">${S.winners.length > 1 ? "It's a tie!" : `${names} wins!`}</div>
    <div class="bz-legend"><span><i style="--kc:var(--red)"></i>Red play again</span><span><i style="--kc:var(--k-green)"></i>Green back to the lobby</span>
      ${S.game.misses.length ? `<span><i style="--kc:var(--k-blue)"></i>Blue revise ${S.game.misses.length} missed</span>` : ""}</div>
    ${S.prize ?`<div class="bz-prize bz-holo"><span class="bz-eyebrow cyan">The prize</span><div class="v">${esc(S.prize)}</div>${S.winners.length > 1 ? `<span class="bz-eyebrow">Shared by ${names}</span>` : ""}</div>` : ""}
    <div class="bz-badges">${S.badges.map((b) => `<div class="bz-badge bz-holo" style="--pc:${PLAYER_COLORS[b.p]}"><span class="bz-eyebrow">${esc(b.name)}</span>
      <div class="bz-bwho">${esc(S.players[b.p].name)}</div><div class="bz-bwhy">${esc(b.why)}</div></div>`).join("")}</div></div>`;
}

function recapHTML() {
  const g = S.game;
  const items = g.misses.slice(0, 12).map((m, k) => `<li class="bz-miss bz-holo" style="--i:${k}">
    <p class="q">${esc(m.stem)}</p>
    <p class="a"><span class="bz-eyebrow cyan">Answer</span>${esc(m.answer)}</p>
    ${m.why ? `<p class="w">${esc(m.why)}</p>` : ""}
    ${m.pyq ? `<span class="bz-eyebrow">Past paper · ${esc(m.pyq.exam)} ${esc(m.pyq.year)}, Q${esc(m.pyq.q_no)}</span>` : ""}</li>`).join("");
  return `<div class="bz-recap"><div class="bz-recaphead"><span class="bz-eyebrow cyan">${g.exam} revision · ${esc(g.subject.short_name)}</span>
      <div class="bz-word sm">Revise these ${g.misses.length}</div></div>
    <ol class="bz-misses">${items}</ol>
    <div class="bz-legend"><span><i style="--kc:var(--k-blue)"></i>Blue back to results</span><span><i style="--kc:var(--red)"></i>Red play again</span><span><i style="--kc:var(--k-green)"></i>Green lobby</span></div></div>`;
}

function podState(i) {
  const pl = S.players[i];
  if (!pl.joined) return { cls: "empty", mood: "idle", status: "" };
  const ph = S.phase;
  const r = S.results && S.results[i];
  if (ph === "lobby") return { cls: "locked", mood: "happy", status: "Ready" };
  if (ph === "final" || ph === "recap") return S.winners.includes(i) ? { cls: "winner", mood: "happy", status: "Winner" } : { cls: "", mood: "sad", status: "" };
  if ((ph === "reveal" || ph === "boom") && r) {
    if (r.ko) return { cls: "out", mood: "ko", status: "Knocked out", ko: true };
    if (ph === "boom" && i === S.game.potato.holder) return { cls: "out", mood: "ko", status: "Boom" };
    if (r.delta > 0) return { cls: "locked", mood: "happy", status: "Correct" };
    if (r.delta < 0) return { cls: "", mood: "sad", status: "Ouch" };
    return { cls: "", mood: "idle", status: ph === "reveal" ? "No points" : "" };
  }
  if (ph === "question" || ph === "revealing") {
    const mode = S.game.rounds[S.game.r].mode;
    const dbl = S.doubled[i] ? " · x2" : "";
    if (mode === "buzz") {
      if (S.buzz.holder === i) return { cls: "buzzed", mood: "think", status: "Answer!" };
      if (S.buzz.locked.has(i)) return { cls: "out", mood: "sad", status: "Locked out" };
      return { cls: "", mood: "idle", status: S.buzz.holder === null ? "Ready to buzz" : "Wait" };
    }
    return S.answers[i] ? { cls: "locked", mood: "think", status: "Locked in" + dbl } : { cls: "", mood: "idle", status: "Thinking" + dbl };
  }
  if (["potato", "potatoJudging", "potatoPause"].includes(ph) && i === S.game.potato.holder) return { cls: "hot", mood: "think", status: "Hot potato" };
  return { cls: "", mood: "idle", status: "" };
}

function renderPods(animate = false) {
  const inGame = S.phase !== "lobby" && S.phase !== "calibrate";
  S.dom.pods.innerHTML = S.players.map((pl, i) => {
    const st = podState(i);
    const from = animate && S.before ? S.before[i] : pl.score;
    // Lifelines only show while some are left, so a card never carries crossed-out clutter.
    const tokens = inGame && pl.joined
      ? `${pl.doubles ? `<span class="bz-tok">x2${pl.doubles > 1 ? ` · ${pl.doubles}` : ""}</span>` : ""}${pl.throws ? '<span class="bz-tok">Throw</span>' : ""}` : "";
    const body = pl.joined
      ? `<div class="sc" data-from="${from}" data-to="${pl.score}">${inGame ? fmtNum(from) : "Ready"}</div>
         ${inGame ? `<div class="bz-hp ${pl.hp <= 30 ? "low" : ""}" title="Health ${pl.hp}"><i style="width:${pl.hp}%"></i></div>${tokens ? `<div class="bz-toks">${tokens}</div>` : ""}` : ""}`
      : '<div class="join">Press <span class="k-red">red</span> to join</div>';
    return `<div class="bz-pod ${st.cls}" style="--pc:${PLAYER_COLORS[i]}" data-act="pod" data-p="${i}">
      <div class="bz-delta" data-p="${i}"></div>${st.ko ? '<div class="bz-ko">K.O.</div>' : ""}
      <div class="row1"><div class="bz-face">${avatar(i, st.mood)}</div>
        <div class="bz-who"><div class="nm">${esc(pl.name)}</div>${body}</div>
        <span class="bz-dome ${S.lights[i] ? "lit" : ""}"></span></div>
      <div class="bz-status">${esc(st.status)}</div></div>`;
  }).join("");
  if (!animate || !S.results) return;
  S.results.forEach((r, i) => {
    if (!r || !r.delta) return;
    const d = S.dom.pods.querySelector(`.bz-delta[data-p="${i}"]`);
    d.textContent = (r.delta > 0 ? "+" : "") + fmtNum(r.delta);
    d.classList.add("show", r.delta > 0 ? "plus" : "minus");
  });
  countUp();
}

function countUp() {
  S.dom.pods.querySelectorAll(".sc[data-to]").forEach((el) => {
    const from = +el.dataset.from;
    const to = +el.dataset.to;
    if (from === to) return;
    const start = now();
    const step = () => {
      const k = Math.min(1, (now() - start) / 900);
      el.textContent = fmtNum(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1 && el.isConnected) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

// ------------------------------------------------------------------ clicks (optional: everything also works from the buzzers)

function onClick(e) {
  const el = e.target.closest("[data-act]");
  if (!el || !S) return;
  audio();
  const act = el.dataset.act;
  const v = el.dataset.v;
  if (act === "subject") { S.sel = +el.dataset.i; SFX.move(); savePrefs(); renderMain(); line("pick", { subject: S.subjects[S.sel].name }); }
  else if (act === "focus") { S.focus = v; savePrefs(); renderMain(); }
  else if (act === "play") { S.play = v === "learn" ? "learn" : "show"; savePrefs(); renderMain(); }
  else if (act === "exam" && EXAMS[v]) { setExam(v); say(`${EXAMS[v].long} prep.`); }
  else if (act === "length") { S.length = v; savePrefs(); renderMain(); }
  else if (act === "answerTime") { S.answerTime = +v; savePrefs(); renderMain(); }
  else if (act === "buzzWindow") { S.buzzWindow = +v; savePrefs(); renderMain(); }
  else if (act === "voice") {
    S.voice = v !== "off";
    S.voiceChosen = true;
    if (S.voice) S.voiceName = v; else shutUp();
    savePrefs();
    renderMain();
    if (S.voice) say("Hi, I'm Bolt. Ready when you are.");
  }
  else if (act === "music") { S.music = v === "on"; if (!S.music) musicStop(); savePrefs(); renderMain(); }
  else if (act === "start") startGame();
  else if (act === "calibrate") startCalibrate();
  else if (act === "calReset") { S.layout = { ...DEFAULT_LAYOUT }; S.lookup = buildLookup(S.layout); savePrefs(); toast("Default button layout restored."); showLobby(); }
  else if (act === "lobby") { if (S.phase === "calibrate" || S.phase === "final" || confirm("End this show and go back to the lobby?")) showLobby(); }
  else if (act === "exit") exitShow();
  else if (act === "fullscreen") { const st = S.dom.stage; if (document.fullscreenElement) document.exitFullscreen(); else if (st.requestFullscreen) st.requestFullscreen().catch(() => toast("Full screen is not available here.")); }
  else if (act === "pod" && S.phase === "lobby") {
    const p = +el.dataset.p;
    const pl = S.players[p];
    if (!pl.joined) { onButton(p, "red"); return; }
    const name = prompt("Name for this player", pl.name);
    if (name && name.trim()) { pl.name = name.trim().slice(0, 20); savePrefs(); renderPods(); }
  }
}

function exitShow() { location.hash = "#/practice"; }

// ------------------------------------------------------------------ page lifecycle

export async function render(root) {
  root.append(Object.assign(document.createElement("div"), { className: "page", textContent: "Opening the Buzz quiz..." }));
  if (!document.getElementById("buzz-css")) {
    document.head.append(Object.assign(document.createElement("link"), { id: "buzz-css", rel: "stylesheet", href: "/css/buzz.css" }));
  }
  const setup = await api.get("/buzz/setup");
  const prefs = loadPrefs();
  const stage = document.createElement("div");
  stage.className = "bz-stage";
  stage.innerHTML = `<div class="bz-world" aria-hidden="true"><div class="bz-scene"></div><div class="bz-scene"></div><div class="bz-scrim"></div></div>
    <header class="bz-top"><div class="bz-host"><canvas aria-hidden="true"></canvas></div>
      <div class="bz-bubble bz-holo" aria-live="polite"><span class="bz-eyebrow cyan">Bolt · host</span><span class="t"></span></div>
      <div class="bz-meta"></div></header>
    <main class="bz-main"></main><footer class="bz-pods"></footer><div class="bz-strike" hidden></div>`;
  document.body.append(stage);
  const subjects = setup.subjects;
  const savedSel = subjects.findIndex((s) => s.id === prefs.subject);
  S = {
    dom: { stage, bubble: stage.querySelector(".bz-bubble"), say: stage.querySelector(".bz-bubble .t"), meta: stage.querySelector(".bz-meta"),
      scenes: [...stage.querySelectorAll(".bz-scene")], main: stage.querySelector(".bz-main"), pods: stage.querySelector(".bz-pods"), strike: stage.querySelector(".bz-strike"), clock: null },
    orb: makeOrb(stage.querySelector(".bz-host canvas")),
    sceneBase: Math.floor(Math.random() * 1000), sceneN: 0, sceneFlip: false, voiceName: prefs.voiceName,
    subjects, history: setup.history, sel: Math.max(0, savedSel),
    exam: prefs.exam, play: prefs.play, focus: prefs.focus, length: prefs.length, answerTime: prefs.answerTime, buzzWindow: prefs.buzzWindow,
    voice: prefs.voice, voiceChosen: prefs.voiceChosen, music: prefs.music, prize: prefs.prize,
    layout: prefs.layout, lookup: buildLookup(prefs.layout),
    players: [0, 1, 2, 3].map((i) => ({ name: (typeof prefs.names[i] === "string" && prefs.names[i].trim()) ? prefs.names[i].trim().slice(0, 20) : `Player ${i + 1}`,
      joined: false, score: 0, hp: 100, doubles: 2, throws: 1, stats: { fastest: 0, damage: 0, snatched: 0, kos: 0 } })),
    lights: [false, false, false, false], phase: "lobby", phaseAt: now(), auto: null, speakingUntil: 0, padId: undefined, prev: [], game: null, token: 0,
  };
  stage.addEventListener("click", onClick);
  if (!subjects.some((s) => s.counts.EST.all >= MIN_SUBJECT_QUESTIONS)) {
    S.dom.main.innerHTML = '<div class="bz-center"><div class="bz-word sm">No questions yet</div><p class="bz-lead">Import a subject first.</p></div>';
    return;
  }
  // Start on the saved subject, or else the playable subject with the soonest exam.
  if (savedSel < 0 || subjectCount(S.subjects[S.sel]) < MIN_SUBJECT_QUESTIONS) {
    S.sel = boardOrder().find((i) => subjectCount(S.subjects[i]) >= MIN_SUBJECT_QUESTIONS) ?? 0;
  }
  if ("speechSynthesis" in window) { rankVoices(); speechSynthesis.onvoiceschanged = rankVoices; }
  showLobby();
  rafId = requestAnimationFrame(tick);
}

export function cleanup() {
  cancelAnimationFrame(rafId);
  if (!S) return;
  stopBlink();
  musicStop();
  shutUp();
  clearTimeout(S.pickTimer);
  clearTimeout(S.strikeTimer);
  const lightsWereOn = !S.lightsOff;
  S.dom.stage.remove();
  document.querySelectorAll(".bz-confetti").forEach((c) => c.remove());
  if (document.fullscreenElement) document.exitFullscreen().catch(() => { /* already gone */ });
  S = null;
  if (lightsWereOn) api.post("/buzz/lights", { on: [false, false, false, false] }).catch(() => { /* receiver unplugged: nothing to switch off */ });
}
