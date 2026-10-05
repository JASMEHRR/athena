// Practice: quick quiz (more modes are added by practice_modes.js).

import { api, qs } from "../api.js";
import { questionCard, startTracking } from "../components.js";
import { clear, el, empty, icon, toast } from "../ui.js";
import { MODES } from "./practice_modes.js";

export const title = () => "Practice";

let state = null;

const TYPE_LABELS = { mcq: "Multiple choice", true_false: "True or false", fill: "Fill the blank", one_line: "One line" };

async function subjectsWithTopics() {
  const subjects = await api.get("/subjects");
  return subjects.filter((s) => s.topics > 0);
}

export async function quizSetup(body, subjects, preset = {}) {
  clear(body);
  if (!subjects.length) {
    body.append(empty("No questions yet", "Questions appear as lessons are written from your slides."));
    return;
  }
  const subjectSel = el("select", { "aria-label": "Subject" }, el("option", { value: "" }, "All subjects"),
    ...subjects.map((s) => el("option", { value: s.id }, s.name)));
  if (preset.subject) subjectSel.value = preset.subject;
  const topicBox = el("div", { class: "stack", style: { maxHeight: "240px", overflow: "auto" } });
  async function loadTopics() {
    clear(topicBox);
    if (!subjectSel.value) {
      topicBox.append(el("div", { class: "small faint" }, "Pick a subject to choose topics, or quiz across everything."));
      return;
    }
    const d = await api.get(`/subjects/${subjectSel.value}`);
    d.topics.forEach((t) => topicBox.append(el("label", { class: "check" }, el("input", { type: "checkbox", value: t.id, checked: true }), t.title)));
  }
  subjectSel.addEventListener("change", loadTopics);
  const typeBoxes = Object.entries(TYPE_LABELS).map(([k, label]) =>
    el("label", { class: "check" }, el("input", { type: "checkbox", value: k, checked: true }), label));
  const count = el("select", { "aria-label": "Number of questions" }, ...[5, 10, 15, 20, 30].map((n) => el("option", { value: n, selected: n === 10 }, `${n} questions`)));
  const start = el("button", { class: "btn primary big" }, icon("play"), "Start quiz");
  start.addEventListener("click", async () => {
    const topics = [...topicBox.querySelectorAll("input:checked")].map((i) => i.value);
    const types = typeBoxes.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
    if (!types.length) { toast("Pick at least one question type."); return; }
    try {
      const questions = await api.get(`/quiz${qs({ subject_id: subjectSel.value, topics: topics.join(","), types: types.join(","), count: count.value })}`);
      runQuiz(body, questions, subjectSel.value);
    } catch (err) { toast(err.message); }
  });
  body.append(el("div", { class: "card stack lg" },
    el("div", { class: "grid two" }, el("label", { class: "field" }, el("span", {}, "Subject"), subjectSel),
      el("label", { class: "field" }, el("span", {}, "How many"), count)),
    el("div", {}, el("span", { class: "label" }, "Topics"), el("div", { style: { marginTop: "8px" } }, topicBox)),
    el("div", {}, el("span", { class: "label" }, "Question types"), el("div", { class: "row wrap", style: { marginTop: "8px", gap: "18px" } }, typeBoxes)),
    el("div", { class: "row" }, start, el("span", { class: "small faint" }, "Weak topics come up more often. Misses become review cards."))));
  await loadTopics();
}

function runQuiz(body, questions, subjectId) {
  clear(body);
  if (!questions.length) {
    body.append(empty("No questions match", "Try more topics or question types."));
    return;
  }
  startTracking("practice", subjectId || "");
  let i = 0;
  let score = 0;
  const holder = el("div", {});
  const progress = el("span", { class: "label mono" });
  body.append(el("div", { class: "card stack" }, el("div", { class: "row between" }, el("span", { class: "label" }, "Quick quiz"), progress), holder));
  function show() {
    clear(holder);
    progress.textContent = `${Math.min(i + 1, questions.length)} / ${questions.length}`;
    if (i >= questions.length) {
      state.keys = null;
      state.enter = null;
      holder.append(el("div", { class: "stack" }, el("h2", {}, `${score} of ${questions.length}`),
        el("p", { class: "muted" }, score === questions.length ? "Perfect round." : "The ones you missed are now review cards."),
        el("div", { class: "row" }, el("button", { class: "btn primary", onclick: () => state.restart() }, "Another quiz"),
          el("a", { class: "btn", href: "#/review" }, "Review cards"))));
      return;
    }
    const next = el("button", { class: "btn primary", style: { display: "none" } }, i + 1 < questions.length ? "Next" : "See score", icon("arrow"));
    next.addEventListener("click", () => { i += 1; show(); });
    const card = questionCard(questions[i], {
      context: "quiz",
      onDone: ({ correct }) => { if (correct) score += 1; next.style.display = ""; next.focus(); state.enter = () => next.click(); },
    });
    state.keys = (e) => card._keys && card._keys(e);
    state.enter = null;
    holder.append(card, el("div", { class: "row", style: { marginTop: "14px" } }, next));
  }
  show();
}

export function onKey(e) {
  if (!state) return;
  if (e.key === "Enter" && state.enter) { e.preventDefault(); state.enter(); return; }
  if (state.keys) state.keys(e);
}

export async function render(root, { query }) {
  const subjects = await subjectsWithTopics();
  const page = el("div", { class: "page narrow" });
  root.append(page);
  page.append(el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Practice"),
    el("div", { class: "sub" }, "Only questions built from your professors' slides."))));
  const body = el("div", { class: "section" });
  const seg = el("div", { class: "seg", role: "tablist" });
  const modes = [["quiz", "Quick quiz", (b) => quizSetup(b, subjects, { subject: query.get("subject") })], ...MODES.map((m) => [m.key, m.label, (b) => m.render(b, subjects, query, state)])];
  state = { keys: null, enter: null, restart: () => show("quiz") };
  async function show(key) {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.key === key));
    state.keys = null;
    state.enter = null;
    try {
      await modes.find((m) => m[0] === key)[2](body);
    } catch (err) {
      clear(body);
      body.append(empty("Could not load this", err.message));
    }
  }
  modes.forEach(([key, label]) => seg.append(el("button", { "data-key": key, role: "tab", onclick: () => show(key) }, label)));
  page.append(el("div", { style: { overflowX: "auto" } }, seg), body);
  const mode = query.get("mode");
  await show(modes.some((m) => m[0] === mode) ? mode : "quiz");
}

export function cleanup() {
  if (state && state.cleanupMock) state.cleanupMock();
  state = null;
}
