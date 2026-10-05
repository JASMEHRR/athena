// Learn: teach one chunk, check it, move on; then explain it back and rate confidence.

import { api } from "../api.js";
import { openSlideModal, questionCard, refChips, renderSlide, startTracking } from "../components.js";
import { add, banner, clear, el, empty, icon, md, pill, refLabel, toast } from "../ui.js";

let topicTitle = "Learn";
export const title = () => topicTitle;

let state = null;

const wide = () => window.matchMedia("(min-width: 1280px)").matches;

function stepsBar() {
  const total = state.lesson.chunks.length + 2;
  return el("div", { class: "steps", "aria-label": `Step ${state.step + 1} of ${total}` },
    ...Array.from({ length: total }, (_, i) => el("span", { class: i < state.step ? "done" : i === state.step ? "now" : "" })));
}

function showRef(ref) {
  if (state.panel && wide()) {
    state.panelRef = ref;
    renderSlide(state.panelBody, ref);
  } else {
    openSlideModal(ref);
  }
}

function header() {
  const t = state.lesson.topic;
  return el("div", { class: "learn-head" },
    el("div", { class: "row between wrap" },
      el("a", { class: "small", href: `#/subject/${t.subject_id}` }, t.subject_name),
      el("div", { class: "row" }, el("span", { class: "small faint" }, `${t.deck_title}`))),
    el("h1", {}, t.title),
    stepsBar(),
    t.stale ? banner("The slides for this topic changed since the lesson was written. It will be updated at the next refresh.", "warn") : null);
}

function chunkView(chunk, index) {
  const view = el("div", { class: "stack lg" });
  const total = state.lesson.chunks.length;
  view.append(el("div", { class: "row between" }, el("span", { class: "label" }, `Part ${index + 1} of ${total}`),
    chunk.status === "known" ? pill("You said you know this", "good") : null));
  view.append(el("h2", {}, chunk.heading));
  view.append(el("div", { class: "lesson", html: md(chunk.explanation_md) }));

  if (chunk.examples.length) {
    view.append(el("div", { class: "prof-box" }, el("span", { class: "label" }, "From your professor's slides"),
      ...chunk.examples.map((x) => el("div", { class: "ex" }, el("b", {}, `${x.label}: `), x.text, " ",
        el("button", { class: "ref-chip", onclick: () => showRef(x.source_ref) }, icon("slide"), refLabel(x.source_ref))))));
  }
  if (chunk.key_terms.length) {
    view.append(el("div", {}, el("span", { class: "label" }, "Key terms"), el("div", { class: "terms" },
      ...chunk.key_terms.map((k) => el("div", { class: "term" }, el("b", {}, k.term), el("span", {}, k.meaning))))));
  }
  if (chunk.clarification) {
    view.append(el("div", { class: "clar" }, el("span", { class: "pill warn" }, "Not on slide"),
      el("b", {}, `${chunk.clarification.term}: `), chunk.clarification.text));
  }
  if (chunk.exam_line) {
    view.append(el("div", { class: "exam-line" }, el("span", { class: "label" }, "Remember"), el("div", {}, chunk.exam_line)));
  }
  view.append(el("div", {}, el("span", { class: "label" }, "Slides"), el("div", { style: { marginTop: "8px" } }, refChips(chunk.source_refs, showRef))));
  return view;
}

async function markChunk(chunk, status) {
  chunk.status = status === "known" ? "known" : chunk.status === "known" ? "known" : "seen";
  try {
    await api.post("/progress/chunk", { chunk_id: chunk.id, topic_id: state.lesson.topic.id, status });
  } catch (err) {
    toast(err.message);
  }
}

function renderChunkStage() {
  const chunk = state.lesson.chunks[state.step];
  if (chunk.status === "new") markChunk(chunk, "seen");
  if (chunk.source_refs.length && state.panel && wide()) showRef(chunk.source_refs[0]);

  const content = chunkView(chunk, state.step);
  const checksBox = el("div", { class: "stack lg" });
  const actions = el("div", { class: "row wrap section" });
  let checkIndex = 0;
  let checking = false;

  const goNext = () => { state.step += 1; draw(); };

  function showChecks() {
    checking = true;
    clear(actions);
    const qs = chunk.checks;
    if (!qs.length) { goNext(); return; }
    function nextQuestion() {
      clear(checksBox);
      const q = qs[checkIndex];
      const holder = el("div", { class: "card" }, el("div", { class: "row between" }, el("span", { class: "label" }, "Quick check"),
        el("span", { class: "label mono" }, `${checkIndex + 1} / ${qs.length}`)));
      const cont = el("button", { class: "btn primary", style: { display: "none" } }, checkIndex + 1 < qs.length ? "Next question" : "Continue", icon("arrow"));
      const card = questionCard(q, {
        context: "check",
        onOpenRef: showRef,
        onDone: () => { cont.style.display = ""; cont.focus(); state.enter = () => cont.click(); },
      });
      cont.addEventListener("click", () => {
        checkIndex += 1;
        if (checkIndex < qs.length) nextQuestion();
        else goNext();
      });
      holder.append(el("div", { style: { height: "10px" } }), card, el("div", { class: "row", style: { marginTop: "14px" } }, cont));
      checksBox.append(holder);
      state.keys = (e) => card._keys && card._keys(e);
      state.enter = null;
      holder.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    nextQuestion();
  }

  const cont = el("button", { class: "btn primary big" }, chunk.checks.length ? "Check myself" : "Continue", icon("arrow"));
  cont.addEventListener("click", showChecks);
  const know = el("button", { class: "btn ghost", title: "Skip the checks; recorded as known" }, "I know this");
  know.addEventListener("click", async () => { await markChunk(chunk, "known"); goNext(); });
  const back = state.step > 0 ? el("button", { class: "btn ghost", onclick: () => { state.step -= 1; draw(); } }, icon("back"), "Back") : null;
  add(actions, cont, know, el("span", { class: "spacer" }), back, el("span", { class: "small faint" }, el("span", { class: "kbd" }, "Enter"), " continue"));
  state.enter = () => { if (!checking) cont.click(); };
  state.keys = null;
  return el("div", {}, content, actions, el("div", { class: "section" }, checksBox));
}

function renderExplainStage() {
  const eb = state.lesson.explain_back;
  const box = el("div", { class: "stack lg" }, el("span", { class: "label" }, "Explain it back"));
  if (!eb) {
    box.append(el("p", { class: "muted" }, "This topic has no explain-it-back prompt."),
      el("button", { class: "btn primary", onclick: () => { state.step += 1; draw(); } }, "Continue", icon("arrow")));
    state.enter = () => { state.step += 1; draw(); };
    return box;
  }
  box.append(el("h2", {}, eb.prompt),
    el("p", { class: "muted" }, "Write it in your own words, as if answering in the exam. Then compare with the key points."));
  const ta = el("textarea", { placeholder: "Your answer", "aria-label": "Your explanation" });
  const result = el("div", {});
  const check = el("button", { class: "btn primary" }, "Check my answer");
  const skip = el("button", { class: "btn ghost", onclick: () => { state.step += 1; draw(); } }, "Skip for now");
  check.addEventListener("click", async () => {
    if (!ta.value.trim()) { toast("Write a few lines first."); return; }
    check.disabled = true;
    try {
      const r = await api.post("/written", { kind: "explain_back", topic_id: state.lesson.topic.id, text: ta.value });
      clear(result);
      const boxes = r.points.map((p, i) => {
        const cb = el("input", { type: "checkbox" });
        cb.checked = r.ticks[i];
        return { cb, row: el("label", {}, cb, el("span", { class: "grow" }, p, " ",
          el("button", { class: "ref-chip", onclick: (e) => { e.preventDefault(); showRef(r.refs[i]); } }, refLabel(r.refs[i])))) };
      });
      const score = el("b", {}, `${r.score} of ${r.max_score}`);
      const update = () => { score.textContent = `${boxes.filter((b) => b.cb.checked).length} of ${r.max_score}`; };
      boxes.forEach((b) => b.cb.addEventListener("change", update));
      const save = el("button", { class: "btn primary" }, "Save and continue", icon("arrow"));
      save.addEventListener("click", async () => {
        try {
          await api.put(`/written/${r.id}`, { ticks: boxes.map((b) => b.cb.checked) });
          state.step += 1;
          draw();
        } catch (err) { toast(err.message); }
      });
      const deep = el("button", { class: "btn ghost" }, "Send for deep review");
      deep.addEventListener("click", async () => {
        try {
          await api.put(`/written/${r.id}`, { ticks: boxes.map((b) => b.cb.checked), send_for_review: true });
          deep.disabled = true;
          deep.textContent = "Sent: graded at the next refresh";
        } catch (err) { toast(err.message); }
      });
      result.append(el("div", { class: "card stack" },
        el("div", { class: "row between" }, el("span", { class: "label" }, "Key points"), el("span", {}, "Score ", score)),
        el("p", { class: "small muted" }, "Ticked automatically by matching words. Fix any tick that is wrong."),
        el("div", { class: "rubric" }, boxes.map((b) => b.row)),
        el("div", { class: "row wrap" }, save, deep)));
      state.enter = () => save.click();
    } catch (err) {
      toast(err.message);
    } finally {
      check.disabled = false;
    }
  });
  box.append(ta, el("div", { class: "row" }, check, skip), result);
  state.enter = null;
  setTimeout(() => ta.focus(), 50);
  return box;
}

function renderConfidenceStage() {
  const box = el("div", { class: "stack lg" }, el("span", { class: "label" }, "Last step"),
    el("h2", {}, "How confident do you feel about this topic?"),
    el("p", { class: "muted" }, "Low confidence brings the flashcards back sooner."));
  const labels = ["Lost", "Shaky", "Okay", "Good", "Solid"];
  const result = el("div", {});
  const buttons = labels.map((label, i) => el("button", { class: "btn", "data-v": String(i + 1) }, el("b", {}, String(i + 1)), label));
  async function pick(v) {
    buttons.forEach((b) => b.classList.toggle("on", b.dataset.v === String(v)));
    buttons.forEach((b) => (b.disabled = true));
    try {
      const r = await api.post(`/topics/${encodeURIComponent(state.lesson.topic.id)}/complete`, { confidence: v });
      clear(result);
      const links = state.lesson.links;
      result.append(el("div", { class: "card stack" },
        el("h3", {}, "Topic done"),
        el("p", { class: "muted" }, r.cards_added ? `${r.cards_added} flashcards joined your review queue.` : "Your flashcards are already in the review queue."),
        links.length ? el("div", {}, el("span", { class: "label" }, "You've seen this in"),
          ...links.map((l) => el("div", { class: "small", style: { marginTop: "6px" } },
            el("a", { href: `#/learn/${encodeURIComponent(l.topic_id)}` }, `${l.subject_name}: ${l.topic_title}`), ` (${l.concept})`))) : null,
        state.lesson.videos.length ? el("div", {}, el("span", { class: "label" }, "Extra help, not exam source"),
          ...state.lesson.videos.map((v) => el("div", { class: "small", style: { marginTop: "6px" } },
            el("a", { href: v.url, target: "_blank", rel: "noopener" }, v.title), el("span", { class: "faint" }, ` · ${v.channel}`)))) : null,
        el("div", { class: "row wrap" },
          el("a", { class: "btn primary", href: "#/today" }, "Back to today"),
          el("a", { class: "btn", href: "#/review" }, "Review cards"),
          el("a", { class: "btn ghost", href: `#/subject/${state.lesson.topic.subject_id}` }, "More topics"))));
      state.enter = () => { location.hash = "#/today"; };
    } catch (err) {
      buttons.forEach((b) => (b.disabled = false));
      toast(err.message);
    }
  }
  buttons.forEach((b) => b.addEventListener("click", () => pick(Number(b.dataset.v))));
  box.append(el("div", { class: "confidence" }, buttons), result);
  state.keys = (e) => {
    const v = Number(e.key);
    if (v >= 1 && v <= 5 && !buttons[0].disabled) { e.preventDefault(); pick(v); }
  };
  state.enter = null;
  return box;
}

function draw() {
  clear(state.left);
  state.left.append(header());
  const n = state.lesson.chunks.length;
  let stage;
  if (state.step < n) stage = renderChunkStage();
  else if (state.step === n) stage = renderExplainStage();
  else stage = renderConfidenceStage();
  state.left.append(stage);
  window.scrollTo({ top: 0 });
}

export function onKey(e) {
  if (!state) return;
  if (e.key === "Enter" && state.enter) { e.preventDefault(); state.enter(); return; }
  if (state.keys) state.keys(e);
}

export async function render(root, { args, query }) {
  const lesson = await api.get(`/topics/${encodeURIComponent(args[0] || "")}`);
  topicTitle = lesson.topic.title;
  const layout = el("div", { class: "learn with-panel" });
  const left = el("div", {});
  const panelBody = el("div", {});
  const panel = el("aside", { class: "panel", "aria-label": "Slide" }, panelBody);
  layout.append(left, panel);
  const page = el("div", { class: "page" }, layout);
  root.append(page);
  state = { lesson, step: 0, left, panel, panelBody, keys: null, enter: null };

  if (!lesson.chunks.length) {
    left.append(header(), empty("No lesson parts", "This topic has no lesson content yet."));
    return;
  }
  const requested = Number(query.get("part"));
  const firstNew = lesson.chunks.findIndex((c) => c.status === "new");
  state.step = requested > 0 ? Math.min(requested - 1, lesson.chunks.length - 1)
    : lesson.progress.status === "learned" || firstNew < 0 ? 0 : firstNew;
  startTracking("learn", lesson.topic.subject_id, lesson.topic.id);
  draw();
}

export function cleanup() {
  state = null;
}
