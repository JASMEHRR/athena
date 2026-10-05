// Shared widgets: slide viewer, question card, activity tracker.

import { api } from "./api.js";
import { add, el, clear, icon, md, refLabel, toast } from "./ui.js";

// ------------------------------------------------------------- slide viewer

export async function renderSlide(container, ref) {
  clear(container);
  const [deckId, n] = String(ref).split("#");
  container.append(el("div", { class: "loading" }, "Loading slide"));
  try {
    const s = await api.get(`/slides/${encodeURIComponent(deckId)}/${encodeURIComponent(n)}`);
    clear(container);
    add(container,
      el("div", { class: "row between" },
        el("div", {}, el("div", { class: "label" }, `${refLabel(ref)} of ${s.total}`),
          el("div", { class: "small muted ellipsis", title: s.file_name }, s.deck_title)),
        el("div", { class: "row" },
          Number(n) > 1 ? el("button", { class: "icon-btn", title: "Previous slide", onclick: () => renderSlide(container, `${deckId}#${Number(n) - 1}`) }, icon("back")) : null,
          Number(n) < s.total ? el("button", { class: "icon-btn", title: "Next slide", onclick: () => renderSlide(container, `${deckId}#${Number(n) + 1}`) }, icon("arrow")) : null)),
      el("div", { style: { height: "12px" } }),
      s.image ? el("img", { src: s.image, alt: `Slide ${n}: ${s.title || "slide picture"}`, loading: "lazy" })
        : el("div", { class: "small faint" }, "No picture for this slide."),
      s.title ? el("h3", { style: { marginTop: "14px" } }, s.title) : null,
      s.text ? el("div", { class: "slide-text" }, s.text.replace(s.title, "").trim()) : null,
      s.visual_text ? el("div", { class: "small", style: { marginTop: "10px" } },
        el("span", { class: "label" }, "What the picture shows"), el("div", { class: "muted" }, s.visual_text)) : null,
      s.notes ? el("div", { class: "small", style: { marginTop: "10px" } },
        el("span", { class: "label" }, "Speaker notes"), el("div", { class: "muted" }, s.notes)) : null,
    );
  } catch (err) {
    clear(container);
    container.append(el("div", { class: "small muted" }, `Could not load this slide: ${err.message}`));
  }
}

export function openSlideModal(ref) {
  const body = el("div", {});
  const back = el("div", { class: "modal-back", onclick: (e) => { if (e.target === back) close(); } },
    el("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": "Slide" },
      el("div", { class: "row between", style: { marginBottom: "8px" } }, el("span", { class: "label" }, "From your professor's slides"),
        el("button", { class: "icon-btn", title: "Close", onclick: () => close() }, icon("close"))),
      body));
  function close() {
    back.remove();
    document.removeEventListener("keydown", onKey);
  }
  function onKey(e) { if (e.key === "Escape") close(); }
  document.addEventListener("keydown", onKey);
  document.body.append(back);
  renderSlide(body, ref);
}

export function refChips(refs, onOpen = openSlideModal) {
  return el("div", { class: "row wrap" }, ...(refs || []).map((r) =>
    el("button", { class: "ref-chip", title: "Open this slide", onclick: () => onOpen(r) }, icon("slide"), refLabel(r))));
}

// ------------------------------------------------------------- question card

/**
 * Renders an objective question. Calls onDone({correct, result}) after grading.
 * Number keys 1-4 pick options; Enter submits typed answers.
 */
export function questionCard(q, { context = "quiz", onDone, onOpenRef } = {}) {
  const box = el("div", { class: "q" });
  const feedback = el("div", {});
  let answered = false;

  async function submit(answer, buttons = []) {
    if (answered || !String(answer).trim()) return;
    answered = true;
    buttons.forEach((b) => (b.disabled = true));
    try {
      const res = await api.post("/answer", { question_id: q.id, answer: String(answer), context });
      buttons.forEach((b) => {
        if (b.dataset.value === res.answer) b.classList.add("right");
        else if (b.dataset.value === String(answer) && !res.correct) b.classList.add("wrong");
      });
      clear(feedback);
      feedback.append(el("div", { class: `feedback ${res.correct ? "good" : "bad"}` },
        el("b", {}, res.correct ? "Correct. " : `Not quite. Answer: ${res.answer}. `),
        res.explanation ? el("span", {}, res.explanation) : null,
        !res.correct && res.card_added ? el("div", { class: "small muted", style: { marginTop: "6px" } }, "Added to your review cards so it comes back.") : null,
        res.source_refs?.length ? el("div", { style: { marginTop: "8px" } }, refChips(res.source_refs, onOpenRef)) : null));
      onDone && onDone({ correct: res.correct, result: res });
    } catch (err) {
      answered = false;
      buttons.forEach((b) => (b.disabled = false));
      toast(err.message);
    }
  }

  box.append(el("div", { class: "q-stem" }, q.stem));
  if (q.type === "mcq" || q.type === "true_false") {
    const buttons = q.options.map((opt, i) => el("button", { class: "option", "data-value": opt },
      el("span", { class: "key" }, String(i + 1)), el("span", {}, opt)));
    buttons.forEach((b) => b.addEventListener("click", () => submit(b.dataset.value, buttons)));
    box.append(el("div", { class: "options" }, buttons));
    box._keys = (e) => {
      const idx = Number(e.key) - 1;
      if (!answered && idx >= 0 && idx < buttons.length) { e.preventDefault(); submit(buttons[idx].dataset.value, buttons); }
    };
  } else {
    const input = el("input", { type: "text", placeholder: "Type your answer", autocomplete: "off", "aria-label": "Your answer" });
    const go = el("button", { class: "btn primary" }, "Check");
    go.addEventListener("click", () => submit(input.value, [go]));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submit(input.value, [go]); } });
    box.append(el("div", { class: "row" }, input, go));
    setTimeout(() => input.focus(), 30);
  }
  box.append(feedback);
  box.isAnswered = () => answered;
  return box;
}

// ------------------------------------------------------------- activity tracker

const IDLE_MS = 2 * 60 * 1000;
const BEAT_MS = 30 * 1000;
let tracker = null;

export function startTracking(kind, subjectId = "", topicId = "") {
  stopTracking();
  let lastInput = Date.now();
  const bump = () => { lastInput = Date.now(); };
  const events = ["keydown", "pointerdown", "scroll", "pointermove"];
  events.forEach((ev) => window.addEventListener(ev, bump, { passive: true }));
  const timer = setInterval(() => {
    if (document.visibilityState !== "visible") return;
    if (Date.now() - lastInput > IDLE_MS) return;
    api.post("/activity", { kind, seconds: BEAT_MS / 1000, subject_id: subjectId, topic_id: topicId }).catch(() => {});
  }, BEAT_MS);
  tracker = { stop() { clearInterval(timer); events.forEach((ev) => window.removeEventListener(ev, bump)); } };
}

export function stopTracking() {
  if (tracker) tracker.stop();
  tracker = null;
}

export { md };
