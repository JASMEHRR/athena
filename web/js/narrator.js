// The lesson voice: reads a part aloud one block at a time and highlights the block it is reading,
// so the words on screen and the voice always line up. Each block is its own utterance, which
// is what keeps them in sync (one long utterance drifts from any highlight driven by timers).

const KEY = "athena-voice";
let voices = [];
let run = null; // { blocks, i, playing, onState }

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
}
function save(prefs) {
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* private window */ }
}

export const supported = () => "speechSynthesis" in window;
export const autoOn = () => load().auto !== false;
export function setAuto(on) { save({ ...load(), auto: on }); }

function rank() {
  const score = (v) => (/natural/i.test(v.name) ? 100 : 0) + (/online/i.test(v.name) ? 20 : 0) + (/^google/i.test(v.name) ? 40 : 0)
    + (/^en-IN/i.test(v.lang) ? 15 : /^en-GB/i.test(v.lang) ? 10 : 5);
  voices = speechSynthesis.getVoices().filter((v) => /^en/i.test(v.lang)).sort((a, b) => score(b) - score(a));
}
if (supported()) { rank(); speechSynthesis.addEventListener?.("voiceschanged", rank); }

// Turn lesson text into something a voice reads like a teacher would say it.
export function speakable(text) {
  return String(text)
    .replace(/\s+/g, " ")
    .replace(/(\w)\u00b2/g, "$1 squared")
    .replace(/(\d)\s*x\s*(?=[\d(A-Z])/g, "$1 times ")
    .replace(/\s[x\u00d7]\s/g, " times ")
    .replace(/\s-\s/g, " minus ")
    .replace(/\s\+\s/g, " plus ")
    .replace(/\s=\s/g, " equals ")
    .replace(/\u2265/g, " is at least ")
    .replace(/</g, " is less than ")
    .replace(/>/g, " is greater than ")
    .replace(/\bP\*/g, "P star").replace(/\bQ\*/g, "Q star").replace(/(\w)\*/g, "$1 star")
    .replace(/(\w)\s*\/\s*(\w)/g, "$1 over $2")
    .replace(/\bMC\b/g, "M C").replace(/\bMR\b/g, "M R").replace(/\bATC\b/g, "A T C").replace(/\bAVC\b/g, "A V C")
    .replace(/[|#`_]/g, " ")
    .trim();
}

function setReading(node) {
  document.querySelectorAll(".reading").forEach((n) => n.classList.remove("reading"));
  if (!node) return;
  node.classList.add("reading");
  const r = node.getBoundingClientRect();
  if (r.top < 70 || r.bottom > window.innerHeight - 40) node.scrollIntoView({ behavior: "smooth", block: "center" });
}

function speakNext() {
  if (!run || !run.playing) return;
  if (run.i >= run.blocks.length) { finish(); return; }
  const block = run.blocks[run.i];
  setReading(block.node);
  const u = new SpeechSynthesisUtterance(block.say);
  if (voices[0]) u.voice = voices[0];
  u.rate = 1;
  const mine = run;
  u.onend = () => { if (run === mine && mine.playing) { mine.i += 1; speakNext(); } };
  u.onerror = u.onend;
  speechSynthesis.speak(u);
}

function finish() {
  const r = run;
  setReading(null);
  if (r) { r.playing = false; r.i = 0; r.onState?.("done"); }
}

/** Start reading these blocks: [{ node, say }]. Stops anything already playing. */
export function play(blocks, onState) {
  stop();
  if (!supported() || !blocks.length) return;
  run = { blocks, i: 0, playing: true, onState };
  onState?.("playing");
  speakNext();
}
export function pause() {
  if (!run) return;
  run.playing = false;
  speechSynthesis.cancel();
  run.onState?.("paused");
}
export function resume() {
  if (!run) return;
  run.playing = true;
  run.onState?.("playing");
  speakNext();
}
export function stop() {
  if (supported()) speechSynthesis.cancel();
  if (run) { run.playing = false; run = null; }
  setReading(null);
}
export const playing = () => !!(run && run.playing);
