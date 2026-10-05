// Review: FSRS flashcards. Space or Enter flips; 1 Again, 2 Hard, 3 Good, 4 Easy.

import { api } from "../api.js";
import { startTracking } from "../components.js";
import { refreshBadge } from "../app.js";
import { clear, el, empty, md, pill, subjectDot, toast } from "../ui.js";

export const title = () => "Review";

let state = null;
const RATINGS = [[1, "Again", "bad"], [2, "Hard", "warn"], [3, "Good", "accent"], [4, "Easy", "good"]];

function draw() {
  const { root, cards } = state;
  clear(root);
  const page = el("div", { class: "page narrow" });
  root.append(page);
  page.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Review"), el("div", { class: "sub" }, state.done
      ? `${state.done} reviewed this session`
      : "Cards come back just before you would forget them.")),
    el("div", { class: "stat", style: { textAlign: "right" } }, el("span", { class: "label" }, "Left"),
      el("div", { class: "num" }, String(Math.max(0, state.due - state.done))))));

  if (!cards.length || state.index >= cards.length) {
    page.append(empty(state.done ? "All caught up" : "Nothing to review right now",
      state.done ? "Great session. New cards arrive as you finish topics and as old ones come due."
        : "Cards join this queue when you finish a topic or miss a question.",
      el("div", { class: "row" }, el("a", { class: "btn primary", href: "#/today" }, "Back to today"),
        el("a", { class: "btn", href: "#/practice" }, "Quick quiz"))));
    state.keys = null;
    return;
  }
  const card = cards[state.index];
  const face = el("div", { class: "card flash", role: "button", tabindex: "0", "aria-label": "Flashcard. Press space to flip." });
  function paint() {
    clear(face);
    if (!state.flipped) {
      face.append(el("div", {}, el("div", { class: "lesson", html: md(card.front), style: { fontSize: "inherit", maxWidth: "none" } }),
        el("div", { class: "small faint", style: { marginTop: "18px" } }, "Think of the answer, then flip")));
    } else {
      face.append(el("div", {}, el("div", { class: "front-small" }, card.front.split("\n")[0]),
        el("div", { class: "back lesson", html: md(card.back), style: { fontSize: "inherit", maxWidth: "none" } })));
    }
  }
  paint();
  face.addEventListener("click", () => { if (!state.flipped) { state.flipped = true; draw(); } });

  page.append(el("div", { class: "row between", style: { marginBottom: "10px" } },
    el("div", { class: "row" }, subjectDot(card.color), el("span", { class: "small muted ellipsis" }, `${card.subject_name} · ${card.topic_title}`)),
    card.origin === "wrong" ? pill("From a missed question", "warn") : pill(card.reps ? `Seen ${card.reps}x` : "New")));
  page.append(face);

  const controls = el("div", { class: "section" });
  if (!state.flipped) {
    controls.append(el("button", { class: "btn primary big block", onclick: () => { state.flipped = true; draw(); } },
      "Show answer ", el("span", { class: "kbd" }, "Space")));
  } else {
    controls.append(el("div", { class: "ratings" }, ...RATINGS.map(([v, label]) =>
      el("button", { class: `btn ${v === 3 ? "primary" : ""}`, onclick: () => rate(v) }, el("span", {}, label), el("span", { class: "kbd" }, String(v))))));
  }
  page.append(controls);
  state.keys = (e) => {
    if (!state.flipped && (e.key === " " || e.key === "Enter")) { e.preventDefault(); state.flipped = true; draw(); return; }
    if (state.flipped && ["1", "2", "3", "4"].includes(e.key)) { e.preventDefault(); rate(Number(e.key)); }
  };
}

async function rate(value) {
  if (state.busy) return;
  state.busy = true;
  const card = state.cards[state.index];
  try {
    await api.post(`/review/${encodeURIComponent(card.card_id)}`, { rating: value });
    state.done += 1;
    state.index += 1;
    state.flipped = false;
    if (state.index >= state.cards.length) {
      const more = await api.get("/review?limit=30");
      state.cards = more.cards;
      state.due = state.done + more.due;
      state.index = 0;
    }
    refreshBadge();
    draw();
  } catch (err) {
    toast(err.message);
  } finally {
    state.busy = false;
  }
}

export function onKey(e) {
  if (state && state.keys) state.keys(e);
}

export async function render(root, { query }) {
  const subject = query.get("subject") || "";
  const q = await api.get(`/review?limit=30${subject ? `&subject_id=${encodeURIComponent(subject)}` : ""}`);
  state = { root, cards: q.cards, due: q.due, index: 0, flipped: false, done: 0, busy: false, keys: null };
  startTracking("review");
  draw();
}

export function cleanup() {
  state = null;
}
