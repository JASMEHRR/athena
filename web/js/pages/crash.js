// One-shot: a whole exam in one guided page. JasMehr says how many hours he has; the
// server fits the course into them (athena/crash.py) and each part teaches with a
// picture, worked steps, try-it practice and a graded quick quiz. Ticks stay in localStorage.

import { api } from "../api.js";
import { openSlideModal, questionCard, refChips, startTracking, workedSteps } from "../components.js";
import { banner, clear, el, empty, fmtDate, fmtMinutes, icon, md, pill, subjectDot } from "../ui.js";
import { renderVisual } from "../visuals.js";

let pageTitle = "One-shot";
export const title = () => pageTitle;

const PRIORITY = { 1: ["Must know", "bad"], 2: ["Likely", "warn"], 3: ["If time", ""] };
const BLOCK = { break: ["Break", ""], paper: ["Timed paper", "accent"], final: ["Revision", "good"], practice: ["Practice", "accent"] };
const HOURS = [2, 4, 8, 12, 24];

function saved(sid) {
  const key = `athena-crash-${sid}`;
  return {
    read() {
      try { return JSON.parse(localStorage.getItem(key)) || {}; } catch { return {}; }
    },
    write(value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode: ticks last this visit */ }
    },
  };
}

const clock = (min) => `${Math.floor(min / 60)}:${String(min % 60).padStart(2, "0")}`;

// ------------------------------------------------------------- list of courses

async function renderIndex(root) {
  const list = await api.get("/crash");
  const page = el("div", { class: "page narrow" },
    el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "One-shot"),
      el("div", { class: "sub" }, "A whole exam in one guided page. Tell it your hours; it plans them and teaches every part."))));
  if (!list.length) {
    page.append(empty("No one-shot yet", "One-shots are written subject by subject, next exam first."));
  }
  for (const c of list) {
    page.append(el("a", { class: "card link crash-pick section", href: `#/crash/${c.subject_id}` },
      el("div", { class: "row between wrap" },
        el("div", { class: "row" }, subjectDot(c.color), el("div", {}, el("h2", {}, c.title),
          el("div", { class: "muted" }, `${c.subject_name} · ${c.exam} · ${c.sections} parts · ${fmtMinutes(c.minutes)} to learn it all`))),
        c.next_exam ? pill(`Exam in ${c.next_exam.days_left} ${c.next_exam.days_left === 1 ? "day" : "days"}`, "warn") : null,
        el("span", { class: "btn primary" }, "Open", icon("arrow")))));
  }
  root.append(page);
}

// ------------------------------------------------------------- one course

function formulaSheet(formulas) {
  const grid = el("div", { class: "formula-grid" });
  const cards = formulas.map((f) => {
    const card = el("button", { class: "fcard", "aria-pressed": "false", title: "Tap to see the formula" },
      el("span", { class: "fname" }, f.name),
      el("span", { class: "fbody" }, el("span", { class: "fformula" }, f.formula), f.note ? el("span", { class: "fnote" }, f.note) : null),
      el("span", { class: "fhint" }, "Tap to see"));
    card.addEventListener("click", () => {
      const on = card.classList.toggle("open");
      card.setAttribute("aria-pressed", String(on));
    });
    grid.append(card);
    return card;
  });
  const toggle = el("button", { class: "btn small" }, "Show all");
  toggle.addEventListener("click", () => {
    const open = toggle.textContent === "Show all";
    cards.forEach((c) => { c.classList.toggle("open", open); c.setAttribute("aria-pressed", String(open)); });
    toggle.textContent = open ? "Hide all (test yourself)" : "Show all";
  });
  return el("div", { class: "stack" },
    el("div", { class: "row between wrap" }, el("p", { class: "muted", style: { margin: 0 } },
      "Say the formula out loud, then tap the card to check. Do this until every card is easy."), toggle), grid);
}

function sectionBody(s, onOpenRef) {
  const box = el("div", { class: "stack lg teach crash-body" });
  box.append(el("div", { class: "why" }, el("div", { class: "sec-h" }, icon("info"), "Why it matters"), el("p", {}, s.why)));
  box.append(el("div", { class: "big-idea" }, el("div", { class: "sec-h" }, "In one line"), el("p", {}, s.big_idea)));
  box.append(el("div", { class: "lesson", html: md(s.body_md) }));
  if (s.visuals.length) {
    box.append(el("section", { class: "tsec" }, el("h3", { class: "sec-h" }, icon("eye"), "See it"),
      ...s.visuals.map((v) => renderVisual(v, { onOpenRef }))));
  }
  if (s.analogy) {
    box.append(el("div", { class: "analogy" },
      el("div", { class: "row wrap" }, el("span", { class: "sec-h" }, icon("bulb"), "Think of it like this"), pill("Not on slide", "warn")),
      el("p", {}, s.analogy.text)));
  }
  if (s.worked) {
    box.append(el("section", { class: "tsec" }, el("h3", { class: "sec-h" }, icon("steps"), "Step by step"), workedSteps(s.worked).node));
  }
  if (s.watch_out.length) {
    box.append(el("div", { class: "watch" }, el("div", { class: "sec-h" }, icon("alert"), "Watch out"),
      el("div", { class: "lesson", html: md(s.watch_out.map((t) => `- ${t}`).join("\n")) })));
  }
  if (s.memory_trick) {
    box.append(el("div", { class: "trick" }, el("div", { class: "sec-h" }, icon("spark"), "Memory trick"),
      el("div", { class: "lesson", html: md(s.memory_trick) })));
  }
  if (s.exam_answer_md) {
    box.append(el("div", { class: "exam-sheet" }, el("div", { class: "sec-h" }, icon("pen"), "Write it like this in the exam"),
      el("div", { class: "lesson", html: md(s.exam_answer_md) })));
  }
  if (s.practice.length) {
    box.append(el("section", { class: "tsec" }, el("h3", { class: "sec-h" }, icon("practice"), `Try it (${s.practice.length})`),
      ...s.practice.map((p) => el("div", { class: "practice" },
        p.marks || p.pyq_id ? el("div", { class: "row wrap" }, p.pyq_id ? pill("Past paper", "accent") : null,
          p.marks ? pill(`${p.marks} marks`) : null) : null,
        workedSteps({ question_md: p.question_md, steps: p.steps, answer_md: p.answer_md }, { tryFirst: true }).node))));
  }
  if (s.quiz.length) {
    box.append(el("section", { class: "tsec" }, el("h3", { class: "sec-h" }, icon("check"), "Quick quiz"),
      el("p", { class: "muted", style: { margin: 0 } }, "Wrong answers go into your review cards so they come back."),
      ...s.quiz.map((q) => el("div", { class: "card pad-sm" }, questionCard(q, { context: "quiz", onOpenRef })))));
  }
  if (s.topics.length) {
    box.append(el("div", { class: "stack" }, el("div", { class: "sec-h" }, icon("learn"), "Go deeper: the full lessons"),
      el("div", { class: "row wrap" }, ...s.topics.map((t) => el("a", { class: "btn small multiline", href: `#/learn/${encodeURIComponent(t.id)}` }, t.title)))));
  }
  box.append(el("details", { class: "slides-more" }, el("summary", {}, icon("slide"), `The professor's slides for this part (${s.source_refs.length})`),
    el("div", { style: { marginTop: "4px" } }, refChips(s.source_refs, onOpenRef))));
  return box;
}

async function renderCourse(root, sid, query, go) {
  const store = saved(sid);
  const state = store.read();
  state.done = Array.isArray(state.done) ? state.done : [];
  const asked = Number(query.get("hours"));
  const hours = asked >= 0.5 && asked <= 200 ? asked : state.hours || 12;
  const data = await api.get(`/crash/${encodeURIComponent(sid)}?hours=${hours}`);
  const { course, plan } = data;
  pageTitle = course.title;
  if (state.hours !== plan.hours) { state.hours = plan.hours; store.write(state); }

  const sections = course.sections;
  const minutesFor = {};
  for (const b of plan.blocks) if (b.kind === "section") minutesFor[b.id] = (minutesFor[b.id] || 0) + b.minutes;
  const done = new Set(state.done.filter((id) => sections.some((s) => s.id === id)));
  const page = el("div", { class: "page crash" });
  root.append(page);

  // Header: what this is, the exam, the hours question.
  const exam = data.next_exam;
  page.append(el("div", { class: "crash-hero" },
    el("a", { class: "small", href: `#/subject/${sid}` }, data.subject_name),
    el("h1", {}, course.title),
    el("div", { class: "row wrap" }, pill(course.exam, "accent"),
      exam ? pill(`${exam.days_left} ${exam.days_left === 1 ? "day" : "days"} to go · ${fmtDate(exam.date)}${exam.time ? ` · ${exam.time}` : ""}`, "warn")
        : el("a", { class: "small", href: "#/settings" }, "Add the exam date")),
    el("div", { class: "lesson", html: md(course.intro_md) })));

  const hoursInput = el("input", { type: "number", min: "0.5", max: "200", step: "0.5", value: String(plan.hours), "aria-label": "Hours you have" });
  const replan = () => {
    const h = Number(hoursInput.value);
    if (h >= 0.5 && h <= 200) go(`#/crash/${sid}?hours=${h}`);
  };
  hoursInput.addEventListener("keydown", (e) => { if (e.key === "Enter") replan(); });
  page.append(el("div", { class: "card hours-card" },
    el("div", { class: "sec-h" }, icon("plan"), "How many hours do you have before the exam?"),
    el("div", { class: "row wrap" },
      ...HOURS.map((h) => el("button", { class: `btn small${h === plan.hours ? " primary" : ""}`, onclick: () => go(`#/crash/${sid}?hours=${h}`) }, `${h} h`)),
      el("div", { class: "row hours-own" }, hoursInput, el("button", { class: "btn small", onclick: replan }, "Plan it"))),
    el("p", { class: "small muted", style: { margin: 0 } },
      "Must-know parts come first. With 6 hours or more you also sit one past paper under exam conditions. A short break every 90 minutes.")));

  // Progress and the quick jump bar.
  const bar = el("div", { class: "bar" }, el("span", {}));
  const progressText = el("span", { class: "small" });
  const updateProgress = () => {
    bar.firstChild.style.width = `${(done.size / sections.length) * 100}%`;
    progressText.textContent = `${done.size} of ${sections.length} parts done`;
    state.done = [...done];
    store.write(state);
    page.querySelectorAll("[data-done-for]").forEach((n) => n.classList.toggle("is-done", done.has(n.dataset.doneFor)));
  };
  const jump = (id) => {
    const target = page.querySelector(`#crash-${id}`);
    if (!target) return;
    if (target.tagName === "DETAILS") target.open = true;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const nextUp = () => plan.blocks.find((b) => b.kind === "section" && !done.has(b.id)) || null;
  const continueBtn = el("button", { class: "btn primary" }, icon("play"), "Continue");
  continueBtn.addEventListener("click", () => { const n = nextUp(); jump(n ? n.id : "last"); });
  page.append(el("div", { class: "crash-nav" },
    el("div", { class: "row wrap" },
      ...[["plan", "Plan"], ["formulas", "Formulas"], ["learn", "Learn"], ["paper", "The paper"], ["last", "Last hour"]]
        .map(([id, label]) => el("button", { class: "btn ghost small", onclick: () => jump(id) }, label)),
      el("span", { class: "spacer" }), continueBtn),
    el("div", { class: "row" }, el("div", { class: "grow" }, bar), progressText)));

  // The plan, hour by hour.
  const timeline = el("div", { class: "timeline" });
  for (const b of plan.blocks) {
    const [label, kind] = b.kind === "section" ? PRIORITY[b.priority] : BLOCK[b.kind];
    const note = b.kind === "section" && b.status === "short" ? "short version" : b.part ? `part ${b.part}` : "";
    const row = el(b.kind === "section" ? "button" : "div", { class: `tl-row tl-${b.kind}`, "data-done-for": b.kind === "section" ? b.id : null },
      el("span", { class: "tl-time" }, `${clock(b.start)} to ${clock(b.end)}`),
      el("span", { class: "tl-title" }, b.title, note ? el("span", { class: "faint" }, ` (${note})`) : null),
      pill(label, kind), el("span", { class: "tl-min" }, fmtMinutes(b.minutes)));
    if (b.kind === "section") row.addEventListener("click", () => jump(b.id));
    if (b.kind === "paper") row.addEventListener("click", () => jump("paper"));
    timeline.append(row);
  }
  const planBox = el("section", { class: "card", id: "crash-plan" },
    el("div", { class: "row between wrap" }, el("h2", {}, `Your ${plan.hours}-hour plan`),
      el("span", { class: "small muted" }, `${fmtMinutes(plan.planned_minutes)} planned`)), timeline);
  if (plan.skipped.length) {
    planBox.append(banner(`Not enough time for: ${plan.skipped.map((s) => s.title).join(", ")}. They are still below if you finish early.`, "warn"));
  }
  if (course.gaps_md) planBox.append(el("div", { class: "banner info" }, icon("info"), el("div", { class: "grow lesson", html: md(course.gaps_md) })));
  page.append(planBox);

  // Formula sheet.
  if (course.formulas.length) {
    page.append(el("section", { class: "card", id: "crash-formulas" }, el("h2", {}, "Formula sheet"), formulaSheet(course.formulas)));
  }

  // The parts, in course order. Each opens on demand; the first one not done starts open.
  const learn = el("section", { id: "crash-learn", class: "stack" }, el("h2", {}, "Learn it, part by part"));
  const firstOpen = (nextUp() || {}).id;
  sections.forEach((s, i) => {
    const [label, kind] = PRIORITY[s.priority];
    const planned = minutesFor[s.id];
    const tick = el("button", { class: "btn small tick", "data-done-for": s.id });
    const paintTick = () => { clear(tick); tick.append(icon("check"), done.has(s.id) ? "Done" : "Mark as done"); };
    tick.addEventListener("click", (e) => {
      e.preventDefault();
      if (done.has(s.id)) done.delete(s.id); else done.add(s.id);
      paintTick();
      updateProgress();
    });
    paintTick();
    const details = el("details", { class: "crash-sec", id: `crash-${s.id}`, "data-done-for": s.id },
      el("summary", {},
        el("span", { class: "sec-n" }, String(i + 1)),
        el("span", { class: "sec-title" }, el("b", {}, s.title), el("span", { class: "small muted" },
          `${s.unit ? `${s.unit} · ` : ""}${planned ? `${fmtMinutes(planned)} in your plan` : "not in your plan"}`)),
        pill(label, kind)));
    let built = false;
    const build = () => {
      if (built) return;
      built = true;
      details.append(sectionBody(s, openSlideModal), el("div", { class: "row section" }, tick,
        sections[i + 1] ? el("button", { class: "btn ghost small", onclick: () => jump(sections[i + 1].id) }, "Next part", icon("arrow")) : null));
    };
    details.addEventListener("toggle", () => { if (details.open) build(); });
    if (s.id === firstOpen) {
      details.open = true;
      build();
    }
    learn.append(details);
  });
  page.append(learn);

  // How the paper works, then the final hour.
  page.append(el("section", { class: "card", id: "crash-paper" }, el("h2", {}, "The paper: how to score"),
    el("div", { class: "lesson", html: md(course.paper_md) })));
  if (course.last_hour.length) {
    page.append(el("section", { class: "card", id: "crash-last" }, el("h2", {}, "The last hour: read this before you walk in"),
      el("div", { class: "lesson", html: md(course.last_hour.map((t) => `- ${t}`).join("\n")) })));
  } else {
    page.append(el("span", { id: "crash-last" }));
  }

  updateProgress();
  startTracking("learn", sid, "");
}

export async function render(root, { args, query, go }) {
  pageTitle = "One-shot";
  if (!args[0]) return renderIndex(root);
  return renderCourse(root, args[0], query, go);
}
