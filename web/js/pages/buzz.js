// Buzz quiz: a four player buzzer game show on Athena's own question banks.
// Runs full screen over the shell. Everything after opening is driven by the Buzz buzzers:
// the show moves on by itself, and any red buzzer skips ahead. Party answers never touch
// study progress; only a game history row is saved at the end.

import { api, qs } from "../api.js";
import { escapeHtml as esc, toast } from "../ui.js";

export const title = () => "Buzz quiz";

// ------------------------------------------------------------------ constants

const BUTTONS = ["red", "blue", "orange", "green", "yellow"];
const COLORS = ["blue", "orange", "green", "yellow"]; // answer buttons, top to bottom on a handset
// The receiver reports 20 buttons, 5 per handset, in HID order red, yellow, green, orange, blue.
const DEFAULT_LAYOUT = { stride: 5, red: 0, yellow: 1, green: 2, orange: 3, blue: 4 };
const PLAYER_COLORS = ["#ff5fa2", "#38d9f5", "#a3e635", "#b18cff"];
const SKIN = ["#f1c27d", "#c68642", "#e0ac69", "#8d5524"];
const LENGTHS = {
  short: { label: "Short", ff: 3, buzz: 6, snatch: 3, potatoes: 1, final: 3 },
  normal: { label: "Normal", ff: 5, buzz: 10, snatch: 5, potatoes: 2, final: 5 },
  long: { label: "Long", ff: 8, buzz: 16, snatch: 8, potatoes: 3, final: 8 },
};
const FOCI = [["all", "All topics"], ["pyq", "Past-paper topics"], ["exam", "Exam syllabus"]];
const ANSWER_TIMES = [5, 10, 15];
const BUZZ_WINDOWS = [1, 2, 3];
const POINTS = { base: 500, speed: 500, buzz: 500, penalty: 250, snatch: 300, pass: 100, boom: 500, ko: 500 };
const DAMAGE = { wrong: 20, boom: 50 };
const GUARD_MS = 1200; // a frantic buzz cannot skip the next screen by accident
const MIN_SUBJECT_QUESTIONS = 8;
const CAL_STEPS = [[0, "red"], [0, "blue"], [0, "orange"], [0, "green"], [0, "yellow"], [1, "red"]];

const LINES = {
  hello: ["Welcome to the Buzz quiz! I'm Bolt. Press your red buzzers to join.", "Hello, hello! Bolt here. Red buzzers to join, green to start."],
  join: ["{name} is in!", "{name} has entered the building.", "Here comes {name}. Act natural.", "{name}, ready to lose gracefully?"],
  needPlayers: ["Somebody press a red buzzer first!"],
  pick: ["{subject}! Good choice.", "{subject}. Let's see what you remember.", "Ooh, {subject}."],
  intro_fastest: ["Fastest Finger! Everyone answers. The quicker you are, the more you score.", "Round one, Fastest Finger. Speed is everything."],
  intro_buzz: ["Buzz In! Slam red first, then answer in {secs} seconds. Wrong answers hurt.", "Buzz In time. Fast fingers, brave hearts, questionable choices."],
  intro_snatch: ["Snatch! The fastest right answer steals {pts} points from the leader.", "Snatch round. Be quick and rob the leader blind."],
  intro_potato: ["Hot Potato! Only the holder answers. Right answer, pass it on. Don't be holding it when it blows!", "Hot Potato. Nobody knows when it goes off. Not even me."],
  intro_final: ["The final! Double points. Wrong answers cost you. Use your doubles wisely.", "Final round. Everything counts double. Good luck, you'll need it."],
  right: ["Correct!", "Nailed it!", "Look at that brain go!", "Somebody actually studied!", "Beautiful."],
  nobody: ["Ouch. Nobody got that one.", "Silence. Beautiful, terrible silence.", "Not one of you. Wow.", "I'm not angry. Just disappointed."],
  buzzed: ["{name}!", "{name} buzzes in!", "Go on, {name}!"],
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

// ------------------------------------------------------------------ art (original characters)

const HOST_SVG = `<svg viewBox="0 0 120 130" aria-hidden="true">
  <line x1="60" y1="20" x2="60" y2="8" stroke="#ffd21f" stroke-width="4"/>
  <circle class="bz-bulb" cx="60" cy="7" r="6"/>
  <rect x="16" y="20" width="88" height="76" rx="30" fill="#ffd21f"/>
  <rect x="25" y="31" width="70" height="46" rx="20" fill="#14183c"/>
  <g class="bz-eyes"><ellipse cx="46" cy="48" rx="7" ry="9" fill="#7df9ff"/><ellipse cx="74" cy="48" rx="7" ry="9" fill="#7df9ff"/></g>
  <ellipse class="bz-mouth" cx="60" cy="64" rx="11" ry="2.6" fill="#7df9ff"/>
  <circle cx="18" cy="58" r="6" fill="#e0b400"/><circle cx="102" cy="58" r="6" fill="#e0b400"/>
  <rect x="50" y="96" width="20" height="9" fill="#c9a400"/>
  <path d="M42 105 L60 114 L42 123 Z M78 105 L60 114 L78 123 Z" fill="#ff2e4d"/><circle cx="60" cy="114" r="5" fill="#ff2e4d"/>
</svg>`;

const HAIR = [
  '<path d="M14 36 Q14 8 40 8 Q66 8 66 36 Q58 20 40 21 Q22 20 14 36Z" fill="#3b2a1a"/>',
  '<path d="M12 44 Q9 6 40 6 Q71 6 68 44 L66 64 Q62 30 40 23 Q18 30 14 64Z" fill="#1c1c1c"/>',
  '<circle cx="40" cy="11" r="11" fill="#5a3a22"/><path d="M14 36 Q15 13 40 15 Q65 13 66 36 Q56 22 40 23 Q24 22 14 36Z" fill="#5a3a22"/>',
  '<path d="M14 32 L20 10 L28 22 L36 5 L44 22 L52 8 L58 22 L66 32 Q60 19 40 19 Q20 19 14 32Z" fill="#c0392b"/>',
];

function avatar(i, mood) {
  const eyes = {
    idle: '<circle cx="31" cy="42" r="3.4" fill="#222"/><circle cx="49" cy="42" r="3.4" fill="#222"/>',
    happy: '<path d="M26 43 Q31 37 36 43 M44 43 Q49 37 54 43" stroke="#222" stroke-width="3" fill="none" stroke-linecap="round"/>',
    sad: '<circle cx="31" cy="44" r="3.2" fill="#222"/><circle cx="49" cy="44" r="3.2" fill="#222"/><path d="M25 37 L35 40 M55 37 L45 40" stroke="#222" stroke-width="2.5" stroke-linecap="round"/>',
    ko: '<path d="M27 38 L35 46 M35 38 L27 46 M45 38 L53 46 M53 38 L45 46" stroke="#222" stroke-width="3" stroke-linecap="round"/>',
    think: '<circle cx="32" cy="40" r="3.4" fill="#222"/><circle cx="50" cy="40" r="3.4" fill="#222"/>',
  }[mood];
  const mouth = {
    idle: '<path d="M33 56 L47 56" stroke="#222" stroke-width="3" stroke-linecap="round"/>',
    happy: '<path d="M28 52 Q40 66 52 52 Z" fill="#7a1f1f"/>',
    sad: '<path d="M31 60 Q40 52 49 60" stroke="#222" stroke-width="3" fill="none" stroke-linecap="round"/>',
    ko: '<path d="M30 58 Q34 54 38 58 T46 58 T52 57" stroke="#222" stroke-width="2.5" fill="none" stroke-linecap="round"/>',
    think: '<ellipse cx="44" cy="57" rx="4" ry="5" fill="#7a1f1f"/>',
  }[mood];
  return `<svg viewBox="0 0 80 80" aria-hidden="true"><circle cx="40" cy="44" r="27" fill="${SKIN[i]}"/>${HAIR[i]}${eyes}${mouth}
    <path d="M16 80 Q18 68 40 68 Q62 68 64 80Z" fill="${PLAYER_COLORS[i]}"/></svg>`;
}

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
    voice: typeof p.voice === "boolean" ? p.voice : true,
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
      voice: S.voice, prize: S.prize, focus: S.focus, subject: subject ? subject.id : "", layout: S.layout,
    }));
  } catch { /* private mode: settings just reset next time */ }
}

function buildLookup(L) {
  const map = new Map();
  for (let p = 0; p < 4; p++) for (const b of BUTTONS) map.set(L[b] + p * L.stride, { player: p, button: b });
  return map;
}

const now = () => performance.now();
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const shuffle = (arr) => { const a = [...arr]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const joined = () => S.players.map((p, i) => (p.joined ? i : -1)).filter((i) => i >= 0);
const fill = (text, vars = {}) => text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
const fmtDate = (iso) => { try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }); } catch { return iso; } };

// ------------------------------------------------------------------ sound

let actx = null;
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
const SFX = {
  join: (i) => { tone(440 + i * 110, 0.12, "triangle", 0.1); tone(660 + i * 165, 0.15, "triangle", 0.1, 0.1); },
  move: () => tone(900, 0.04, "square", 0.04),
  buzz: (i) => tone([300, 360, 420, 480][i], 0.45, "sawtooth", 0.12, 0, [600, 720, 840, 960][i]),
  lock: () => tone(1200, 0.06, "square", 0.05),
  double: () => [600, 800, 1200].forEach((f, k) => tone(f, 0.08, "square", 0.06, k * 0.06)),
  right: () => [523, 659, 784, 1047].forEach((f, k) => tone(f, 0.18, "triangle", 0.1, k * 0.09)),
  wrong: () => tone(220, 0.35, "sawtooth", 0.1, 0, 110),
  tick: () => tone(880, 0.05, "sine", 0.06),
  boom: () => { tone(140, 0.9, "sawtooth", 0.22, 0, 35); tone(90, 1.1, "square", 0.16, 0.04, 30); tone(60, 1.2, "triangle", 0.2, 0.08, 25); },
  ko: () => [400, 300, 200, 120].forEach((f, k) => tone(f, 0.18, "square", 0.08, k * 0.12)),
  fanfare: () => [523, 659, 784, 1047, 784, 1047].forEach((f, k) => tone(f, 0.25, "triangle", 0.1, k * 0.14)),
};

// ------------------------------------------------------------------ host voice

let hostVoice = null;
function chooseVoice() {
  if (!("speechSynthesis" in window)) return;
  const voices = speechSynthesis.getVoices();
  hostVoice = voices.find((v) => /^en-IN/i.test(v.lang)) || voices.find((v) => /^en-GB/i.test(v.lang)) || voices.find((v) => /^en/i.test(v.lang)) || null;
}

function setTalking(on) {
  const h = S && S.dom.host;
  if (h) h.classList.toggle("talking", on);
}

// The host says a line: it shows in the speech bubble and, with the voice on, is spoken.
function say(text, { bubble = true } = {}) {
  if (!S || !text) return;
  if (bubble) S.dom.bubble.textContent = text;
  const quietUntil = now() + Math.min(4500, 700 + text.length * 45);
  if (!S.voice || !("speechSynthesis" in window)) {
    S.speakingUntil = quietUntil;
    setTalking(true);
    return;
  }
  try {
    speechSynthesis.cancel(); // the newest line always wins, so the host never lags behind the game
    const u = new SpeechSynthesisUtterance(text);
    if (hostVoice) u.voice = hostVoice;
    u.rate = 1.08;
    u.pitch = 1.1;
    const done = () => { if (S && S.utter === u) { S.utter = null; S.speakingUntil = 0; setTalking(false); } };
    u.onend = done;
    u.onerror = done;
    S.utter = u;
    S.speakingUntil = now() + 15000; // safety net if the browser never reports the end
    setTalking(true);
    speechSynthesis.speak(u);
  } catch (err) {
    console.warn("Host voice failed", err);
    S.speakingUntil = quietUntil;
  }
}
const line = (kind, vars, extra = "") => say(fill(pick(LINES[kind]), vars) + (extra ? " " + extra : ""));
const speaking = () => S && now() < S.speakingUntil;
function shutUp() { if ("speechSynthesis" in window) speechSynthesis.cancel(); }

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
      S.lightsOff = true; // stop retrying every frame; the game plays fine without lights
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
  const target = b === "red" ? pod.querySelector(".bz-dome") : pod.querySelector(`.bz-keys i[data-b="${b}"]`);
  if (!target) return;
  target.classList.add(b === "red" ? "press" : "on");
  setTimeout(() => target.classList.remove("press", "on"), 220);
}

const settled = () => now() - S.phaseAt >= GUARD_MS;

function onButton(p, b) {
  const pl = S.players[p];
  switch (S.phase) {
    case "lobby": lobbyButton(p, b); return;
    case "final":
      if (pl.joined && settled()) { if (b === "red") startGame(); else if (b === "green") showLobby(); }
      return;
    case "intro": case "reveal": case "scores": case "boom":
      if (pl.joined && b === "red" && settled()) runAuto();
      return;
    case "question":
      if (pl.joined) questionButton(p, b);
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
  else if (b === "orange") cycleFocus();
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
}

// Move on by itself once the host has finished talking (or after maxMs at the latest).
function autoAdvance(fn, minMs, maxMs) { S.auto = { fn, at: now() + minMs, max: now() + maxMs }; }
function runAuto() { if (S.auto) { const fn = S.auto.fn; S.auto = null; fn(); } }

function tick() {
  if (!S) return;
  poll();
  const t = now();
  if (S.dom.host.classList.contains("talking") && !speaking()) setTalking(false);
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
    updateBar(t);
  } else if (["potato", "potatoJudging", "potatoPause"].includes(S.phase)) {
    const pot = S.game.potato;
    if (t >= pot.fuseEnd) boom();
    else if (t >= pot.nextTick) { SFX.tick(); pot.nextTick = t + Math.max(150, 800 - (t - pot.fuseStart) * 0.025); }
  }
  rafId = requestAnimationFrame(tick);
}

function updateBar(t) {
  const bar = S.dom.bar;
  const answering = S.buzz.holder !== null;
  S.dom.timer.classList.toggle("answering", answering);
  const frac = answering ? (S.buzz.deadline - t) / (S.buzzWindow * 1000) : (S.timer.end - t) / S.timer.total;
  bar.style.width = (Math.max(0, Math.min(1, frac)) * 100).toFixed(2) + "%";
}

// ------------------------------------------------------------------ lobby

function moveSubject(dir) {
  const n = S.subjects.length;
  for (let k = 1; k <= n; k++) {
    const i = (S.sel + dir * k + n * k) % n;
    if (subjectCount(S.subjects[i]) >= MIN_SUBJECT_QUESTIONS) { S.sel = i; break; }
  }
  SFX.move();
  savePrefs();
  renderMain();
  clearTimeout(S.pickTimer);
  S.pickTimer = setTimeout(() => { if (S && S.phase === "lobby") line("pick", { subject: S.subjects[S.sel].name }); }, 700);
}

function cycleFocus() {
  const i = FOCI.findIndex(([k]) => k === S.focus);
  S.focus = FOCI[(i + 1) % FOCI.length][0];
  SFX.move();
  savePrefs();
  renderMain();
  say(FOCI.find(([k]) => k === S.focus)[1] + ".");
}

function subjectCount(s) {
  if (!s) return 0;
  return S.focus === "pyq" && s.pyq_questions ? s.pyq_questions : S.focus === "exam" && s.exam_questions ? s.exam_questions : s.questions;
}

function showLobby() {
  shutUp();
  setPhase("lobby");
  S.game = null;
  S.dom.bubble.textContent = "";
  renderTop();
  renderMain();
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
  const L = LENGTHS[S.length];
  const main = L.ff + L.buzz + L.snatch + L.final;
  let data;
  try {
    data = await api.get(`/buzz/questions${qs({ subject_id: subject.id, focus: S.focus, count: Math.min(120, main + L.potatoes * 12) })}`);
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
  S.game = { subject, focus: data.focus, rounds, r: -1, qi: 0, spare: pool, used: [], potato: null };
  S.players.forEach((p) => Object.assign(p, { score: 0, hp: 100, doubles: 2, throws: 1, stats: { fastest: 0, damage: 0, snatched: 0, kos: 0 } }));
  if (data.focus !== S.focus) toast(`No ${FOCI.find(([k]) => k === S.focus)[1].toLowerCase()} questions in ${subject.short_name} yet, so this show uses all topics.`);
  savePrefs();
  nextRound();
}

function nextRound() {
  const g = S.game;
  g.r += 1;
  g.qi = 0;
  if (g.r >= g.rounds.length) { showFinal(); return; }
  const round = g.rounds[g.r];
  if (round.mode === "potato") g.potato = { left: round.potatoes, holder: null, fuseStart: 0, fuseEnd: 0, nextTick: 0, answered: null, passTo: null };
  setPhase("intro");
  setLights([false, false, false, false]);
  renderTop();
  renderMain(true);
  renderPods();
  line("intro_" + round.mode, { secs: S.buzzWindow, pts: POINTS.snatch });
  autoAdvance(round.mode === "potato" ? startPotato : startQuestion, 3000, 11000);
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
  g.used.push(S.q);
  answerFor(S.q);
  S.answers = [null, null, null, null];
  S.doubled = [false, false, false, false];
  S.pending = [0, 0, 0, 0];
  S.results = null;
  S.buzz = { holder: null, locked: new Set(), deadline: 0, judging: false };
  S.timer = { total: S.answerTime * 1000, end: now() + S.answerTime * 1000, remaining: 0 };
  S.lastTick = -1;
  setPhase("question");
  setLights(round.mode === "buzz" ? S.players.map((p) => p.joined) : [false, false, false, false]);
  renderTop();
  renderMain(true);
  renderPods();
  say(S.q.stem, { bubble: false });
  S.dom.bubble.textContent = round.mode === "buzz" ? "Red buzzer to answer!" : (round.mode === "final" ? "Double points! Red doubles again." : "Lock in your answer! Red to double up.");
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

async function buzzAnswer(p, choice) {
  if (S.buzz.holder !== p || S.buzz.judging || choice >= S.q.options.length) return;
  S.buzz.judging = true;
  S.answers[p] = { choice, at: now() };
  let ans;
  try { ans = await answerFor(S.q); } catch (err) { ans = { index: -1 }; toast(err.message); }
  if (!S || S.phase !== "question" || S.buzz.holder !== p) return;
  S.buzz.judging = false;
  if (choice === ans.index) {
    S.pending[p] += POINTS.buzz * S.game.rounds[S.game.r].mult;
    reveal();
  } else {
    wrongBuzz(p, false);
  }
}

function wrongBuzz(p, timedOut) {
  S.pending[p] -= POINTS.penalty;
  damage(p, DAMAGE.wrong);
  S.buzz.locked.add(p);
  S.buzz.holder = null;
  S.buzz.judging = false;
  SFX.wrong();
  if (joined().every((i) => S.buzz.locked.has(i))) { reveal(); return; }
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

async function reveal() {
  if (S.phase !== "question") return;
  setPhase("revealing");
  let ans;
  try { ans = await answerFor(S.q); } catch (err) { toast(err.message); ans = { index: -1, explanation: "" }; }
  if (!S || S.phase !== "revealing") return;
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
      damage(i, DAMAGE.wrong * (S.doubled[i] ? 2 : 1));
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
  setPhase("reveal");
  const winners = joined().filter((i) => S.results[i] && S.results[i].delta > 0);
  if (winners.length) { SFX.right(); blink(winners); } else { SFX.wrong(); setLights([false, false, false, false]); }
  if (kos.length) setTimeout(() => SFX.ko(), 500);
  renderMain();
  renderPods(true);
  const pyq = S.q.pyq && S.q.pyq[0];
  if (kos.length) line("ko", { name: S.players[kos[0]].name, pts: POINTS.ko });
  else if (S.snatch && S.snatch.amount) line("snatch", { name: S.players[S.snatch.thief].name, victim: S.players[S.snatch.victim].name, pts: S.snatch.amount });
  else line(winners.length ? "right" : "nobody", {}, pyq ? fill(LINES.pyq[0], pyq) : "");
  autoAdvance(nextQuestion, 3200 + (ans.explanation ? 1800 : 0), 9000);
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
  pot.holder = pick(joined());
  pot.fuseStart = t;
  pot.fuseEnd = t + 20000 + Math.random() * 15000; // nobody knows when
  pot.nextTick = t;
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
  let ans;
  try { ans = await answerFor(S.q); } catch (err) { ans = { index: -1 }; toast(err.message); }
  if (!S || S.phase !== "potatoJudging") return; // it blew up while we were checking
  const correct = choice === ans.index;
  pot.answered = { choice, correct, index: ans.index };
  if (correct) { S.players[pot.holder].score += POINTS.pass; pot.passTo = nextHolder(pot.holder); SFX.right(); }
  else { pot.passTo = pot.holder; SFX.wrong(); }
  potatoPause();
}

function throwPotato(p) {
  const pot = S.game.potato;
  const pl = S.players[p];
  if (pl.throws <= 0 || joined().length < 2) return;
  pl.throws -= 1;
  pot.answered = { thrown: true };
  pot.passTo = nextHolder(p);
  SFX.double();
  line("throwIt", { name: pl.name });
  potatoPause();
}

function potatoPause() {
  const pot = S.game.potato;
  setPhase("potatoPause");
  renderMain();
  renderPods();
  setTimeout(() => {
    if (!S || S.phase !== "potatoPause") return;
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
  pot.left -= 1;
  const victim = pot.holder;
  S.players[victim].score -= POINTS.boom;
  damage(victim, DAMAGE.boom);
  const kos = checkKOs();
  S.results = S.players.map((pl, i) => (pl.joined ? { delta: i === victim ? -POINTS.boom - (kos.includes(i) ? POINTS.ko : 0) : 0, ko: kos.includes(i) } : null));
  SFX.boom();
  blink([0, 1, 2, 3], 1600);
  renderMain();
  renderPods(true);
  line(kos.length ? "ko" : "boom", { name: S.players[victim].name, pts: POINTS.ko });
  autoAdvance(pot.left > 0 ? startPotato : showScores, 3800, 9000);
}

// ------------------------------------------------------------------ scores and final

const ranked = () => joined().sort((a, b) => S.players[b].score - S.players[a].score);

function showScores() {
  setPhase("scores");
  setLights([false, false, false, false]);
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
    out.push({ p: tank, name: "Iron wall", why: `took the least damage (${S.players[tank].stats.damage})` });
  }
  return out;
}

function showFinal() {
  setPhase("final");
  const order = ranked();
  const top = S.players[order[0]].score;
  S.winners = order.filter((i) => S.players[i].score === top);
  S.badges = badges();
  renderTop();
  renderMain(true);
  renderPods();
  SFX.fanfare();
  confetti();
  blink(S.winners);
  if (S.winners.length > 1) line("tie");
  else line("winner", { name: S.players[S.winners[0]].name });
  const winnerNames = S.winners.map((i) => S.players[i].name).join(" and ");
  api.post("/buzz/games", {
    subject_id: S.game.subject.id, focus: S.game.focus,
    players: order.map((i) => ({ name: S.players[i].name, score: S.players[i].score })),
    winner: winnerNames.slice(0, 60), prize: S.prize.slice(0, 80),
  }).catch((err) => toast("Could not save this game to the history: " + err.message));
}

function confetti(ms = 4500) {
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "bz-confetti";
  document.body.append(c);
  const ctx = c.getContext("2d");
  const W = (c.width = innerWidth);
  const H = (c.height = innerHeight);
  const colors = ["#2f7bff", "#ff8a1f", "#22c55e", "#ffd21f", "#ff2e4d", "#ff5fa2"];
  const bits = Array.from({ length: 200 }, () => ({
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
    const count = round.mode === "potato" ? `Potato ${Math.min(round.potatoes, round.potatoes - g.potato.left + 1)} of ${round.potatoes}`
      : `Question ${Math.min(g.qi + 1, round.questions.length)} of ${round.questions.length}`;
    meta = `<span class="bz-tag">Round ${g.r + 1}: ${esc(round.name)}${round.mult > 1 ? " (x2)" : ""}</span>
      <span class="bz-small">${esc(g.subject.short_name)} · ${S.phase === "intro" || S.phase === "scores" ? `${g.rounds.length} rounds` : count}</span>`;
  } else if (S.phase === "lobby") {
    meta = '<span class="bz-tag">Buzz quiz</span>';
  }
  const inShow = S.phase !== "lobby" && S.phase !== "calibrate";
  S.dom.meta.innerHTML = `${meta}<span class="bz-actions">
    <button class="bz-btn tiny" data-act="fullscreen">Full screen</button>
    <button class="bz-btn tiny" data-act="${inShow ? "lobby" : "exit"}">${inShow ? "End show" : "Exit"}</button></span>`;
}

function renderMain(enter = false) {
  const m = S.dom.main;
  m.className = "bz-main" + (enter ? " bz-enter" : "");
  m.innerHTML = {
    lobby: lobbyHTML, calibrate: calibrateHTML, intro: introHTML, question: questionHTML, revealing: questionHTML,
    reveal: questionHTML, potato: potatoHTML, potatoJudging: potatoHTML, potatoPause: potatoHTML, boom: boomHTML,
    scores: scoresHTML, final: finalHTML,
  }[S.phase]();
  if (S.phase !== "question" && S.phase !== "revealing") S.dom.bar.style.width = "0";
  if (S.phase === "lobby") {
    const prize = m.querySelector("#bzPrize");
    if (prize) prize.addEventListener("input", () => { S.prize = prize.value.slice(0, 80); savePrefs(); });
  }
}

function lobbyHTML() {
  const pad = findPad();
  const subj = S.subjects.map((s, i) => {
    const n = subjectCount(s);
    const exam = s.next_exam ? `<span class="x">${esc(s.next_exam.type || "Exam")} in ${s.next_exam.days_left} day${s.next_exam.days_left === 1 ? "" : "s"}</span>` : "";
    return `<button class="bz-subj ${i === S.sel ? "sel" : ""}" style="--sc:${esc(s.color || "#2f7bff")}" data-act="subject" data-i="${i}" ${n < MIN_SUBJECT_QUESTIONS ? "disabled" : ""}>
      <div class="s">${esc(s.short_name)}</div><div class="n">${esc(s.name)}</div><div class="c">${n} questions</div>${exam}</button>`;
  }).join("");
  const chips = (list, cur, act, label = (x) => x) => list.map((x) => `<button class="bz-pick ${x === cur ? "on" : ""}" data-act="${act}" data-v="${x}">${esc(label(x))}</button>`).join("");
  const hist = S.history.length ? S.history.map((h) => `<li>${esc(fmtDate(h.played_at))} · ${esc(h.short_name)} · <span class="w">${esc(h.winner || "?")}</span> won${h.players[0] ? ` (${h.players[0].score})` : ""}${h.prize ? ` · ${esc(h.prize)}` : ""}</li>`).join("")
    : '<li class="bz-small">No shows yet. The first winner goes here.</li>';
  return `
  <p class="bz-legend">Any joined buzzer: <b class="c-red">Red</b> join · <b class="c-blue">Blue</b> / <b class="c-yellow">Yellow</b> choose subject · <b class="c-orange">Orange</b> topics · <b class="c-green">Green</b> start the show
    ${pad ? "" : '<br>No buzzers seen yet: press any button on a handset to wake them up.'}</p>
  <div class="bz-lobby">
    <section class="bz-panel"><h2>Subject (soonest exam first)</h2><div class="bz-subjects">${subj}</div></section>
    <section class="bz-panel">
      <h2>Show settings</h2>
      <div class="bz-opts-row"><span>Topics</span>${chips(FOCI.map(([k]) => k), S.focus, "focus", (k) => FOCI.find(([x]) => x === k)[1])}</div>
      <div class="bz-opts-row"><span>Length</span>${chips(Object.keys(LENGTHS), S.length, "length", (k) => LENGTHS[k].label)}</div>
      <div class="bz-opts-row"><span>Answer time</span>${chips(ANSWER_TIMES, S.answerTime, "answerTime", (x) => x + "s")}</div>
      <div class="bz-opts-row"><span>After a buzz</span>${chips(BUZZ_WINDOWS, S.buzzWindow, "buzzWindow", (x) => x + "s to answer")}</div>
      <div class="bz-opts-row"><span>Host voice</span>${chips(["on", "off"], S.voice ? "on" : "off", "voice")}</div>
      <div class="bz-opts-row"><span>Prize</span><input id="bzPrize" class="bz-prize" maxlength="80" value="${esc(S.prize)}" aria-label="Prize for the winner"></div>
      <div class="bz-opts-row"><button class="bz-btn go" data-act="start">Start the show</button><button class="bz-btn tiny" data-act="calibrate">Fix buzzer buttons</button></div>
      <h2>Last shows</h2><ul class="bz-hist">${hist}</ul>
    </section>
  </div>`;
}

function calibrateHTML() {
  const [p, color] = CAL_STEPS[S.cal.length];
  return `<div class="bz-center"><div class="bz-eyebrow">Fix buzzer buttons · step ${S.cal.length + 1} of ${CAL_STEPS.length}</div>
    <div class="bz-title sm">Handset ${p + 1}: press <span class="c-${color}">${color}</span></div>
    <p class="bz-rules">Only needed if a button lights the wrong colour or player.</p>
    <div class="bz-opts-row" style="justify-content:center"><button class="bz-btn" data-act="calReset">Reset to default</button><button class="bz-btn" data-act="lobby">Cancel</button></div></div>`;
}

function introHTML() {
  const g = S.game;
  const round = g.rounds[g.r];
  const rules = {
    fastest: `Everyone answers with blue, orange, green or yellow. Faster right answers score more. Red uses a <b>x2</b> lifeline.`,
    buzz: `Hit <b class="c-red">red</b> first, then answer within <b>${S.buzzWindow} second${S.buzzWindow === 1 ? "" : "s"}</b>. Right: +${POINTS.buzz}. Wrong or too slow: -${POINTS.penalty} and damage.`,
    snatch: `Everyone answers. The fastest right answer snatches <b>${POINTS.snatch}</b> points from the leader.`,
    potato: `Only the holder answers. Right: +${POINTS.pass} and pass it on. When it blows, the holder loses <b>${POINTS.boom}</b>. Red throws it away (once per game).`,
    final: `Double points. Wrong answers cost ${POINTS.penalty * 2} and hurt. Red doubles again if you still have a x2.`,
  }[round.mode];
  return `<div class="bz-center"><div class="bz-eyebrow">Round ${g.r + 1} of ${g.rounds.length}</div>
    <div class="bz-title">${esc(round.name)}</div><p class="bz-rules">${rules}</p></div>`;
}

function optionsHTML(marks, pickers = []) {
  return S.q.options.map((o, j) => `<li class="bz-opt ${COLORS[j]} ${marks(j)}" style="--i:${j}">
    <span class="dot" aria-hidden="true"></span><span class="txt">${esc(o)}</span>
    <span class="bz-chips">${(pickers[j] || []).map((i) => `<span class="bz-chip" style="--pc:${PLAYER_COLORS[i]}">${esc(S.players[i].name)}</span>`).join("")}</span></li>`).join("");
}

function questionHTML() {
  const revealed = S.phase === "reveal";
  const round = S.game.rounds[S.game.r];
  const pickers = COLORS.map(() => []);
  if (revealed) S.players.forEach((pl, i) => { if (pl.joined && S.answers[i]) pickers[S.answers[i].choice].push(i); });
  const marks = (j) => (revealed ? (j === S.answer.index ? "correct" : "dim") : "");
  let prompt = "";
  if (!revealed && round.mode === "buzz") {
    prompt = S.buzz.holder === null ? (S.buzz.locked.size ? "Still open! Hit red to have a go" : "Hit your red buzzer to answer")
      : `${esc(S.players[S.buzz.holder].name)}, answer now!`;
  } else if (!revealed) prompt = "Lock in with blue, orange, green or yellow";
  let info = "";
  if (revealed) {
    if (S.snatch) {
      info += `<div class="bz-note snatch">${S.snatch.amount ? `${esc(S.players[S.snatch.thief].name)} snatched ${S.snatch.amount} points from ${esc(S.players[S.snatch.victim].name)}!`
        : `${esc(S.players[S.snatch.thief].name)} was fastest, but there was nothing to snatch.`}</div>`;
    }
    const pyq = S.q.pyq && S.q.pyq[0];
    if (pyq) info += `<div class="bz-note pyq">Examined in ${esc(pyq.exam)} ${esc(pyq.year)}, Q${esc(pyq.q_no)}${pyq.marks ? ` (${esc(pyq.marks)} marks)` : ""}</div>`;
    if (S.answer.explanation) info += `<div class="bz-note">${esc(S.answer.explanation)}</div>`;
  }
  return `<div class="bz-qcard" data-qid="${esc(S.q.id)}"><p class="bz-q">${esc(S.q.stem)}</p></div>
    <ol class="bz-opts">${optionsHTML(marks, pickers)}</ol>
    ${info ? `<div class="bz-info">${info}</div>` : ""}
    <div class="bz-prompt">${prompt}</div>`;
}

function potatoHTML() {
  const pot = S.game.potato;
  const a = pot.answered;
  const marks = (j) => (!a || a.thrown ? "" : j === a.index ? "correct" : j === a.choice ? "wrongpick" : "dim");
  const holder = S.players[pot.holder];
  const prompt = !a ? (S.phase === "potatoJudging" ? "Checking..." : `Only ${esc(holder.name)} can answer. Quick!${holder.throws ? " Red throws it away." : ""}`)
    : a.thrown ? "Thrown!" : a.correct ? "Right! Pass it on!" : "Wrong! Still holding it...";
  return `<div class="bz-center" style="flex:0;flex-direction:row;gap:2vw"><span class="bz-potato" aria-hidden="true">\u{1F954}</span>
      <span class="bz-holder" style="--pc:${PLAYER_COLORS[pot.holder]}">${esc(holder.name)} has the potato!</span></div>
    <div class="bz-qcard" data-qid="${esc(S.q.id)}"><p class="bz-q">${esc(S.q.stem)}</p></div>
    <ol class="bz-opts">${optionsHTML(marks)}</ol>
    <div class="bz-prompt">${prompt}</div>`;
}

function boomHTML() {
  const pot = S.game.potato;
  return `<div class="bz-center bz-shake"><div class="bz-boom">BOOM!</div>
    <p class="bz-rules">${esc(S.players[pot.holder].name)} was holding it and loses ${POINTS.boom} points.${pot.left > 0 ? " Another potato is coming..." : ""}</p></div>`;
}

function scoresHTML() {
  const order = ranked();
  const max = Math.max(1, ...order.map((i) => S.players[i].score));
  return `<div class="bz-center"><div class="bz-eyebrow">After round ${S.game.r + 1}</div><div class="bz-title sm">Scoreboard</div>
    <div class="bz-board">${order.map((i) => `<div class="bz-brow" style="--pc:${PLAYER_COLORS[i]}"><span>${esc(S.players[i].name)}</span>
      <div class="bz-track"><div class="bz-fill" style="width:${Math.max(0, S.players[i].score) / max * 100}%"></div></div><span>${S.players[i].score}</span></div>`).join("")}</div></div>`;
}

function finalHTML() {
  const names = S.winners.map((i) => esc(S.players[i].name)).join(" and ");
  return `<div class="bz-center"><div class="bz-trophy" aria-hidden="true">\u{1F3C6}</div>
    <div class="bz-title">${S.winners.length > 1 ? "It's a tie!" : `${names} wins!`}</div>
    ${S.prize ? `<div class="bz-prizeline">Prize: ${esc(S.prize)}${S.winners.length > 1 ? ` (shared by ${names})` : ""}</div>` : ""}
    <div class="bz-badges">${S.badges.map((b) => `<div class="bz-badge" style="--pc:${PLAYER_COLORS[b.p]}">${esc(b.name)}: ${esc(S.players[b.p].name)}<small>${esc(b.why)}</small></div>`).join("")}</div>
    <p class="bz-rules"><b class="c-red">Red</b>: play again · <b class="c-green">Green</b>: back to the lobby</p></div>`;
}

function podState(i) {
  const pl = S.players[i];
  if (!pl.joined) return { cls: "empty", mood: "idle", status: "" };
  const ph = S.phase;
  const r = S.results && S.results[i];
  if (ph === "lobby") return { cls: "", mood: "happy", status: "Ready!" };
  if (ph === "final") return S.winners.includes(i) ? { cls: "winner", mood: "happy", status: "Winner!" } : { cls: "", mood: "sad", status: "" };
  if ((ph === "reveal" || ph === "boom") && r) {
    if (r.ko) return { cls: "out", mood: "ko", status: "Knocked out!", ko: true };
    if (ph === "boom" && i === S.game.potato.holder) return { cls: "out", mood: "ko", status: "Boom!" };
    if (r.delta > 0) return { cls: "", mood: "happy", status: "" };
    if (r.delta < 0) return { cls: "", mood: "sad", status: "" };
    return { cls: "", mood: "idle", status: ph === "reveal" ? "No points" : "" };
  }
  if (ph === "question" || ph === "revealing") {
    const mode = S.game.rounds[S.game.r].mode;
    const dbl = S.doubled[i] ? " x2!" : "";
    if (mode === "buzz") {
      if (S.buzz.holder === i) return { cls: "buzzed", mood: "think", status: "Answer!" };
      if (S.buzz.locked.has(i)) return { cls: "out", mood: "sad", status: "Locked out" };
      return { cls: "", mood: "idle", status: S.buzz.holder === null ? "Ready to buzz" : "Wait..." };
    }
    return S.answers[i] ? { cls: "locked", mood: "think", status: "Locked in" + dbl } : { cls: "", mood: "idle", status: "Thinking..." + dbl };
  }
  if (["potato", "potatoJudging", "potatoPause"].includes(ph) && i === S.game.potato.holder) return { cls: "hot", mood: "think", status: "Hot potato!" };
  return { cls: "", mood: "idle", status: "" };
}

function renderPods(animate = false) {
  const inGame = S.phase !== "lobby" && S.phase !== "calibrate";
  S.dom.pods.innerHTML = S.players.map((pl, i) => {
    const st = podState(i);
    const from = animate && S.before ? S.before[i] : pl.score;
    const tokens = inGame && pl.joined
      ? `${[0, 1].map((k) => `<span class="bz-tok x2 ${k < pl.doubles ? "" : "used"}">x2</span>`).join("")}<span class="bz-tok throw ${pl.throws ? "" : "used"}">Throw</span>` : "";
    return `<div class="bz-pod ${st.cls}" style="--pc:${PLAYER_COLORS[i]}" data-act="pod" data-p="${i}">
      <div class="bz-delta" data-p="${i}"></div>
      ${st.ko ? '<div class="bz-ko">K.O.</div>' : ""}
      <div class="bz-avatar">${avatar(i, st.mood)}</div>
      <div class="bz-name">${esc(pl.name)}</div>
      ${pl.joined
        ? `<div><div class="bz-score" data-from="${from}" data-to="${pl.score}">${inGame ? from : "Ready"}</div>${inGame ? `<div class="bz-hp" title="Health ${pl.hp}"><i style="width:${pl.hp}%"></i></div><div class="bz-tokens">${tokens}</div>` : ""}</div>`
        : '<div class="bz-join">Press <b class="c-red">red</b> to join</div>'}
      <div class="bz-desk"><span class="bz-dome ${S.lights[i] ? "lit" : ""}"></span>
        <span class="bz-keys">${COLORS.map((c) => `<i data-b="${c}" style="background:var(--${c});color:var(--${c})"></i>`).join("")}</span></div>
      <div class="bz-status">${esc(st.status)}</div>
    </div>`;
  }).join("");
  if (!animate || !S.results) return;
  S.results.forEach((r, i) => {
    if (!r || !r.delta) return;
    const d = S.dom.pods.querySelector(`.bz-delta[data-p="${i}"]`);
    d.textContent = (r.delta > 0 ? "+" : "") + r.delta;
    d.classList.add("show", r.delta > 0 ? "plus" : "minus");
  });
  countUp();
}

function countUp() {
  S.dom.pods.querySelectorAll(".bz-score[data-to]").forEach((el) => {
    const from = +el.dataset.from;
    const to = +el.dataset.to;
    if (from === to) return;
    const start = now();
    const step = () => {
      const k = Math.min(1, (now() - start) / 900);
      el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
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
  else if (act === "length") { S.length = v; savePrefs(); renderMain(); }
  else if (act === "answerTime") { S.answerTime = +v; savePrefs(); renderMain(); }
  else if (act === "buzzWindow") { S.buzzWindow = +v; savePrefs(); renderMain(); }
  else if (act === "voice") { S.voice = v === "on"; if (!S.voice) shutUp(); savePrefs(); renderMain(); if (S.voice) say("Bolt here. I'm back!"); }
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
  stage.innerHTML = `<header class="bz-top"><div class="bz-host">${HOST_SVG}</div><div class="bz-bubble" aria-live="polite"></div><div class="bz-meta"></div></header>
    <div class="bz-timer"><i></i></div><main class="bz-main"></main><footer class="bz-pods"></footer>`;
  document.body.append(stage);
  const subjects = setup.subjects;
  const savedSel = subjects.findIndex((s) => s.id === prefs.subject);
  S = {
    dom: { stage, host: stage.querySelector(".bz-host"), bubble: stage.querySelector(".bz-bubble"), meta: stage.querySelector(".bz-meta"),
      timer: stage.querySelector(".bz-timer"), bar: stage.querySelector(".bz-timer i"), main: stage.querySelector(".bz-main"), pods: stage.querySelector(".bz-pods") },
    subjects, history: setup.history, sel: Math.max(0, savedSel >= 0 ? savedSel : subjects.findIndex((s) => s.questions >= MIN_SUBJECT_QUESTIONS)),
    focus: prefs.focus, length: prefs.length, answerTime: prefs.answerTime, buzzWindow: prefs.buzzWindow, voice: prefs.voice, prize: prefs.prize,
    layout: prefs.layout, lookup: buildLookup(prefs.layout),
    players: [0, 1, 2, 3].map((i) => ({ name: (typeof prefs.names[i] === "string" && prefs.names[i].trim()) ? prefs.names[i].trim().slice(0, 20) : `Player ${i + 1}`,
      joined: false, score: 0, hp: 100, doubles: 2, throws: 1, stats: { fastest: 0, damage: 0, snatched: 0, kos: 0 } })),
    lights: [false, false, false, false], phase: "lobby", phaseAt: now(), auto: null, speakingUntil: 0, padId: undefined, prev: [], game: null,
  };
  stage.addEventListener("click", onClick);
  if (!subjects.length) { S.dom.main.innerHTML = '<div class="bz-center"><div class="bz-title sm">No questions yet</div><p class="bz-rules">Import a subject first.</p></div>'; return; }
  if ("speechSynthesis" in window) { chooseVoice(); speechSynthesis.onvoiceschanged = chooseVoice; }
  showLobby();
  rafId = requestAnimationFrame(tick);
}

export function cleanup() {
  cancelAnimationFrame(rafId);
  if (!S) return;
  stopBlink();
  shutUp();
  clearTimeout(S.pickTimer);
  const lightsWereOn = !S.lightsOff;
  S.dom.stage.remove();
  document.querySelectorAll(".bz-confetti").forEach((c) => c.remove());
  if (document.fullscreenElement) document.exitFullscreen().catch(() => { /* already gone */ });
  S = null;
  if (lightsWereOn) api.post("/buzz/lights", { on: [false, false, false, false] }).catch(() => { /* receiver unplugged: nothing to switch off */ });
}
