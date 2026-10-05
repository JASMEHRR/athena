// Extra practice modes: answer writing, case practice, timed mock papers.
// Each mode: { key, label, render(body, subjects, query, state) }.

import { api, qs } from "../api.js";
import { refChips, startTracking } from "../components.js";
import { add, clear, el, empty, icon, md, pill, toast } from "../ui.js";

function subjectPicker(subjects, preset) {
  const sel = el("select", { "aria-label": "Subject" }, ...subjects.map((s) => el("option", { value: s.id }, s.name)));
  if (preset && subjects.some((s) => s.id === preset)) sel.value = preset;
  return sel;
}

// ------------------------------------------------------------- written answers

function writtenRunner(body, subjects, query, types, labels) {
  clear(body);
  if (!subjects.length) { body.append(empty("No questions yet", "Questions appear as lessons are written.")); return; }
  const sel = subjectPicker(subjects, query.get("subject"));
  const area = el("div", { class: "section" });
  const next = el("button", { class: "btn primary" }, icon("play"), labels.button);
  async function load() {
    clear(area);
    const list = await api.get(`/quiz${qs({ subject_id: sel.value, types: types.join(","), count: 1, include_checks: false })}`);
    if (!list.length) {
      area.append(empty(labels.none, "The exam-style question bank for this subject is written after its lessons. Try another subject or a quick quiz."));
      return;
    }
    const q = list[0];
    startTracking("practice", sel.value, q.topic_id);
    const ta = el("textarea", { placeholder: "Write your answer as you would in the exam", "aria-label": "Your answer" });
    const result = el("div", {});
    const check = el("button", { class: "btn primary" }, "Check against the key points");
    check.addEventListener("click", async () => {
      if (!ta.value.trim()) { toast("Write your answer first."); return; }
      check.disabled = true;
      try {
        const r = await api.post("/written", { kind: "written", topic_id: q.topic_id, question_id: q.id, text: ta.value });
        clear(result);
        const boxes = r.points.map((p, i) => {
          const cb = el("input", { type: "checkbox" });
          cb.checked = r.ticks[i];
          return { cb, row: el("label", {}, cb, el("span", {}, p)) };
        });
        const score = el("b", {}, `${r.score} of ${r.max_score}`);
        boxes.forEach((b) => b.cb.addEventListener("change", () => { score.textContent = `${boxes.filter((x) => x.cb.checked).length} of ${r.max_score}`; }));
        const saveBtn = el("button", { class: "btn" }, "Save ticks");
        saveBtn.addEventListener("click", async () => {
          try { await api.put(`/written/${r.id}`, { ticks: boxes.map((b) => b.cb.checked) }); toast("Saved"); } catch (err) { toast(err.message); }
        });
        const deep = el("button", { class: "btn ghost" }, "Send for deep review");
        deep.addEventListener("click", async () => {
          try {
            await api.put(`/written/${r.id}`, { ticks: boxes.map((b) => b.cb.checked), send_for_review: true });
            deep.disabled = true;
            deep.textContent = "Sent: graded at the next refresh";
          } catch (err) { toast(err.message); }
        });
        result.append(el("div", { class: "card stack section" },
          el("div", { class: "row between" }, el("span", { class: "label" }, "Key points"), el("span", {}, "Score ", score)),
          el("p", { class: "small muted" }, "Ticked by matching words. Fix any tick that is wrong."),
          el("div", { class: "rubric" }, boxes.map((b) => b.row)),
          el("div", { class: "row wrap" }, saveBtn, deep)),
          el("div", { class: "card section" }, el("span", { class: "label" }, "Model answer"),
            el("div", { class: "lesson", html: md(r.model_answer_md), style: { marginTop: "10px", fontSize: "17px" } }),
            el("div", { style: { marginTop: "10px" } }, refChips(r.refs.filter((v, i, a) => a.indexOf(v) === i)))));
      } catch (err) {
        toast(err.message);
      } finally {
        check.disabled = false;
      }
    });
    area.append(el("div", { class: "card stack" },
      el("div", { class: "row between" }, el("span", { class: "label" }, labels.kind), q.marks ? pill(`${q.marks} marks`) : null),
      el("div", { class: "q-stem", html: md(q.stem) }), ta, el("div", { class: "row" }, check)), result);
  }
  next.addEventListener("click", () => load().catch((err) => toast(err.message)));
  body.append(el("div", { class: "card row wrap" }, el("div", { style: { flex: "1 1 260px" } }, sel), next));
  body.append(area);
}

// ------------------------------------------------------------- mock papers

function fmtClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h ? `${h}:` : ""}${String(m).padStart(h ? 2 : 1, "0")}:${String(sec).padStart(2, "0")}`;
}

function mockResults(body, paper) {
  clear(body);
  body.append(el("div", { class: "hero" },
    el("span", { class: "label" }, `${paper.subject_name} mock paper`),
    el("h2", {}, `${paper.score} of ${paper.max_score} marks`),
    el("p", { class: "muted" }, "Objective questions were marked automatically. Written answers were ticked against the key points by matching words; treat them as a guide.")));
  for (const s of paper.sections) {
    const box = el("div", { class: "card section stack" }, el("h3", {}, s.name));
    for (const q of s.items) {
      const r = q.result || {};
      const item = el("div", { class: "stack", style: { paddingBottom: "14px", borderBottom: "1px solid var(--border)" } },
        el("div", { class: "row between" }, el("div", { class: "q-stem", html: md(q.stem) }), pill(`${r.score ?? 0} / ${q.marks}`, r.score ? "good" : "bad")));
      if (s.kind === "objective") {
        add(item, el("div", { class: `feedback ${r.correct ? "good" : "bad"}` },
          r.correct ? "Correct." : `Your answer: ${r.given || "(blank)"}. Correct: ${q.answer}.`, q.explanation ? ` ${q.explanation}` : ""));
      } else {
        add(item, r.given ? el("details", {}, el("summary", { class: "small" }, "Your answer"), el("p", { class: "small muted", style: { whiteSpace: "pre-wrap" } }, r.given)) : el("p", { class: "small muted" }, "Left blank."),
          el("div", { class: "rubric" }, q.rubric.map((p, i) => el("label", {}, el("input", { type: "checkbox", checked: !!(r.ticks && r.ticks[i]), disabled: true }), el("span", {}, p)))),
          el("details", {}, el("summary", { class: "small" }, "Model answer"), el("div", { class: "lesson", html: md(q.model_answer_md), style: { fontSize: "16px", marginTop: "8px" } })));
      }
      add(item, refChips(q.source_refs));
      box.append(item);
    }
    body.append(box);
  }
  body.append(el("div", { class: "row section" }, el("a", { class: "btn primary", href: "#/practice?mode=mock" }, "Another mock"), el("a", { class: "btn", href: "#/review" }, "Review cards")));
}

function mockTaking(body, paper, state) {
  clear(body);
  startTracking("practice", paper.subject_id);
  const key = `athena-mock-${paper.id}`;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || "{}"); } catch { saved = {}; }
  const answers = { ...saved };
  const persist = () => { try { localStorage.setItem(key, JSON.stringify(answers)); } catch { /* storage full or private mode */ } };
  const started = new Date(paper.started_at).getTime();
  const clock = el("span", { class: "mono", style: { fontSize: "20px", fontWeight: "700" } });
  const tick = () => {
    const left = paper.minutes * 60 - (Date.now() - started) / 1000;
    clock.textContent = left > 0 ? fmtClock(left) : "Time is up";
    clock.style.color = left < 300 ? "var(--bad)" : "";
  };
  tick();
  const timer = setInterval(tick, 1000);
  state.cleanupMock = () => clearInterval(timer);

  body.append(el("div", { class: "card row between", style: { position: "sticky", top: "8px", zIndex: 5 } },
    el("div", {}, el("b", {}, `${paper.subject_name} mock`), el("div", { class: "small faint" }, `${paper.total_marks} marks · ${paper.minutes} minutes`)), clock));

  for (const s of paper.sections) {
    const box = el("div", { class: "card section stack" }, el("div", { class: "row between" }, el("h3", {}, s.name),
      el("span", { class: "small faint" }, s.kind === "objective" ? "Choose or type the answer" : "Write your answer")));
    s.items.forEach((q, idx) => {
      const item = el("div", { class: "stack", style: { paddingBottom: "16px", borderBottom: "1px solid var(--border)" } },
        el("div", { class: "row between", style: { alignItems: "flex-start" } }, el("div", { class: "q-stem", html: md(`${idx + 1}. ${q.stem}`) }), pill(`${q.marks} mark${q.marks === 1 ? "" : "s"}`)));
      if (q.type === "mcq" || q.type === "true_false") {
        const group = `q-${q.id}`;
        item.append(el("div", { class: "options" }, ...q.options.map((opt) => {
          const radio = el("input", { type: "radio", name: group, value: opt, checked: answers[q.id] === opt });
          radio.addEventListener("change", () => { answers[q.id] = opt; persist(); });
          return el("label", { class: "option" }, radio, el("span", {}, opt));
        })));
      } else if (q.type === "fill" || q.type === "one_line") {
        const input = el("input", { type: "text", value: answers[q.id] || "", "aria-label": "Answer" });
        input.addEventListener("input", () => { answers[q.id] = input.value; persist(); });
        item.append(input);
      } else {
        const ta = el("textarea", { "aria-label": "Answer" });
        ta.value = answers[q.id] || "";
        ta.addEventListener("input", () => { answers[q.id] = ta.value; persist(); });
        item.append(ta);
      }
      box.append(item);
    });
    body.append(box);
  }
  const submit = el("button", { class: "btn primary big" }, "Submit paper");
  submit.addEventListener("click", async () => {
    if (!confirm("Submit this mock paper? You can't change answers after this.")) return;
    submit.disabled = true;
    try {
      const done = await api.post(`/mocks/${paper.id}/submit`, { answers });
      clearInterval(timer);
      try { localStorage.removeItem(key); } catch { /* ignore */ }
      mockResults(body, done);
      window.scrollTo({ top: 0 });
    } catch (err) {
      submit.disabled = false;
      toast(err.message);
    }
  });
  body.append(el("div", { class: "row section" }, submit));
}

async function mockMode(body, subjects, query, state) {
  clear(body);
  if (!subjects.length) { body.append(empty("No questions yet", "Mock papers need lessons and a question bank first.")); return; }
  const sel = subjectPicker(subjects, query.get("subject"));
  const start = el("button", { class: "btn primary" }, icon("play"), "Start a timed mock paper");
  const history = el("div", { class: "section" });
  start.addEventListener("click", async () => {
    start.disabled = true;
    try {
      const paper = await api.post("/mocks", { subject_id: sel.value });
      mockTaking(body, paper, state);
    } catch (err) {
      toast(err.message);
    } finally {
      start.disabled = false;
    }
  });
  body.append(el("div", { class: "card stack" },
    el("p", { class: "muted" }, "A paper shaped like your professor's past papers, built only from your slides. Objective parts are marked for you; written parts are checked against the key points."),
    el("div", { class: "row wrap" }, el("div", { style: { flex: "1 1 260px" } }, sel), start)), history);
  const past = await api.get("/mocks");
  if (past.length) {
    const names = Object.fromEntries(subjects.map((s) => [s.id, s.short_name]));
    history.append(el("div", { class: "card" }, el("span", { class: "label" }, "Past mock papers"),
      el("div", { class: "list", style: { marginTop: "8px" } }, ...past.map((m) => el("button", {
        class: "list-row", style: { background: "transparent", border: 0, width: "100%", textAlign: "left", cursor: "pointer" },
        onclick: async () => {
          const paper = await api.get(`/mocks/${m.id}`);
          if (paper.finished_at) mockResults(body, paper); else mockTaking(body, paper, state);
        },
      }, el("div", { class: "grow" }, el("b", {}, names[m.subject_id] || m.subject_id), el("div", { class: "small faint" }, new Date(m.started_at).toLocaleString("en-IN"))),
        m.finished_at ? pill(`${m.score} / ${m.max_score}`, "accent") : pill("In progress", "warn"))))));
  }
}

async function answersMode(body) {
  clear(body);
  const items = await api.get("/written");
  if (!items.length) {
    body.append(empty("No written answers yet", "Explain-it-back answers and practice answers you write appear here, with feedback after a refresh."));
    return;
  }
  body.append(el("p", { class: "muted small" }, "Answers you sent for deep review are graded against your slides at the next refresh; the feedback shows here."));
  for (const a of items) {
    const fb = a.feedback;
    const status = fb ? pill(`Graded ${fb.score} / ${fb.max_score}`, "good") : a.queued ? pill("Waiting for deep review", "warn") : pill(`Self-check ${a.score ?? 0} / ${a.max_score ?? 0}`);
    add(body, el("div", { class: "card section stack" },
      el("div", { class: "row between" }, el("span", { class: "label" }, a.kind === "explain_back" ? "Explain it back" : "Exam answer"), status),
      el("div", { class: "small faint" }, `${new Date(a.created_at).toLocaleString("en-IN")} · `, el("a", { href: `#/learn/${encodeURIComponent(a.topic_id)}` }, "Open topic")),
      el("details", {}, el("summary", { class: "small" }, "Your answer"), el("p", { class: "small", style: { whiteSpace: "pre-wrap" } }, a.text)),
      fb ? el("div", { class: "card pad-sm", style: { background: "var(--surface-2)" } },
        el("span", { class: "label" }, "Feedback"),
        el("div", { class: "lesson", html: md(fb.feedback_md), style: { fontSize: "16px", marginTop: "8px" } }),
        fb.points_missed?.length ? el("div", { class: "small" }, el("b", {}, "Add next time: "), fb.points_missed.join("; ")) : null,
        fb.source_refs?.length ? el("div", { style: { marginTop: "8px" } }, refChips(fb.source_refs)) : null) : null));
  }
}

export const MODES = [
  { key: "write", label: "Answer writing", render: (b, s, q) => writtenRunner(b, s, q, ["short", "long", "differentiate"], { button: "Give me a question", none: "No written questions yet", kind: "Exam question" }) },
  { key: "case", label: "Case practice", render: (b, s, q) => writtenRunner(b, s, q, ["case"], { button: "Give me a case", none: "No case questions yet", kind: "Case question" }) },
  { key: "mock", label: "Mock paper", render: mockMode },
  { key: "answers", label: "My answers", render: answersMode },
];
