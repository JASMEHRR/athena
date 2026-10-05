// Today: the 5-minute daily brief.

import { api } from "../api.js";
import { questionCard } from "../components.js";
import { banner, clear, el, empty, fmtDate, fmtMinutes, icon, pct, pill, ring, subjectDot } from "../ui.js";

export const title = () => "Today";

const KIND_LABEL = { review: "Review", learn: "Learn", revise: "Revise", exam_revision: "Exam revision", mock: "Mock paper" };

function taskHref(t) {
  if (t.kind === "review") return "#/review";
  if (t.kind === "mock") return `#/practice?mode=mock&subject=${t.subject_id}`;
  if (t.topic_id) return `#/learn/${encodeURIComponent(t.topic_id)}`;
  return `#/practice?subject=${t.subject_id}`;
}

function startHref(start) {
  if (!start) return "#/subjects";
  if (start.kind === "review") return "#/review";
  if (start.kind === "mock") return `#/practice?mode=mock&subject=${start.subject_id}`;
  if (start.topic_id) return `#/learn/${encodeURIComponent(start.topic_id)}`;
  return "#/subjects";
}

function warmupBlock(questions) {
  const box = el("div", { class: "card" });
  if (!questions.length) {
    box.append(el("div", { class: "label" }, "Warm-up"),
      el("p", { class: "muted", style: { marginTop: "8px" } }, "Your 5-question warm-up appears once you have started a topic."));
    return box;
  }
  let i = 0;
  let score = 0;
  const holder = el("div", {});
  const head = el("div", { class: "row between" }, el("span", { class: "label" }, "Warm-up"), el("span", { class: "label mono" }, ""));
  function show() {
    clear(holder);
    head.lastChild.textContent = `${Math.min(i + 1, questions.length)} / ${questions.length}`;
    if (i >= questions.length) {
      holder.append(el("div", { class: "stack" }, el("h3", {}, `Warm-up done: ${score} of ${questions.length}`),
        el("p", { class: "muted" }, score === questions.length ? "Clean sweep." : "Anything you missed is now in your review cards.")));
      return;
    }
    const next = el("button", { class: "btn", style: { display: "none", marginTop: "12px" }, onclick: () => { i++; show(); } }, "Next", icon("arrow"));
    const card = questionCard(questions[i], {
      context: "warmup",
      onDone: ({ correct }) => { if (correct) score++; next.style.display = ""; next.focus(); },
    });
    holder.append(card, next);
    box._card = card;
  }
  box.append(head, el("div", { style: { height: "12px" } }), holder);
  show();
  box._keys = (e) => box._card && box._card._keys && box._card._keys(e);
  return box;
}

let warm = null;
export function onKey(e) {
  if (warm && warm._keys) warm._keys(e);
}

export async function render(root) {
  const t = await api.get("/today");
  const page = el("div", { class: "page" });
  root.append(page);

  const dots = el("div", { class: "streak-dots", title: `${t.streak.days} day streak` },
    ...Array.from({ length: 7 }, (_, k) => el("span", { class: k < Math.min(7, t.streak.days) ? "on" : "" })));
  page.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, t.greeting), el("div", { class: "sub" }, t.date)),
    el("div", { class: "row", style: { gap: "14px" } },
      el("div", { class: "stat", style: { textAlign: "right" } },
        el("div", { class: "num" }, String(t.streak.days), el("small", {}, t.streak.days === 1 ? "day streak" : "day streak")),
        el("div", { class: "small faint" }, t.streak.done_today ? "Today counts already" : "Study 15 minutes or do a review to keep it")),
      dots)));

  if (!t.has_exam_dates) {
    page.append(banner("No exam dates yet. Add your end-semester dates and Athena will plan backwards from them. Until then it rotates through your subjects.",
      "warn", el("a", { class: "btn small", href: "#/settings" }, "Add dates")));
  }
  for (const w of t.plan.warnings || []) page.append(el("div", { style: { height: "10px" } }), banner(w, "warn"));

  const hero = el("div", { class: "hero section" },
    el("div", { class: "row between wrap" },
      el("div", { class: "stack", style: { gap: "4px" } }, el("span", { class: "label" }, "Up next"),
        el("h2", {}, t.start ? t.start.label : "Pick a subject to begin")),
      el("a", { class: "btn primary big", href: startHref(t.start) }, icon("play"), "Start")),
    el("div", { class: "grid three" },
      el("div", { class: "stat" }, el("span", { class: "label" }, "Reviews due"), el("div", { class: "num" }, String(t.due_reviews))),
      el("div", { class: "stat" }, el("span", { class: "label" }, "Studied today"), el("div", { class: "num" }, String(t.minutes_today), el("small", {}, "min"))),
      el("div", { class: "stat" }, el("span", { class: "label" }, "Planned today"), el("div", { class: "num" }, String(t.plan.minutes_planned), el("small", {}, "min")))));
  page.append(hero);

  // Plan and exams.
  const planCard = el("div", { class: "card" }, el("div", { class: "row between" }, el("span", { class: "label" }, "Today's plan"),
    el("a", { class: "small", href: "#/plan" }, "Full plan")));
  if (!t.plan.tasks.length) {
    planCard.append(el("p", { class: "muted", style: { marginTop: "10px" } }, "Nothing planned today. Enjoy the break, or do a quick quiz."));
  } else {
    const list = el("div", { class: "list", style: { marginTop: "8px" } });
    for (const task of t.plan.tasks) {
      const subj = t.subjects[task.subject_id];
      list.append(el("a", { class: "list-row", href: taskHref(task) },
        task.status === "done" ? el("span", { class: "pill good" }, icon("check")) : subjectDot(subj ? subj.color : null),
        el("div", { class: "grow" }, el("div", { class: "title ellipsis", style: task.status === "done" ? { textDecoration: "line-through", color: "var(--faint)" } : {} }, task.title),
          el("div", { class: "small faint" }, `${KIND_LABEL[task.kind] || task.kind}${subj ? ` · ${subj.short_name}` : ""}`)),
        el("span", { class: "small mono faint" }, fmtMinutes(task.minutes))));
    }
    planCard.append(list);
  }

  const examCard = el("div", { class: "card" }, el("span", { class: "label" }, "Exams"));
  if (!t.exams.length) {
    examCard.append(el("p", { class: "muted", style: { marginTop: "10px" } }, "No upcoming exams saved."),
      el("a", { class: "btn small", href: "#/settings" }, "Add exam dates"));
  } else {
    const list = el("div", { class: "list", style: { marginTop: "8px" } });
    for (const e of t.exams) {
      list.append(el("div", { class: "list-row" },
        el("div", { class: "countdown" }, el("span", { class: "n" }, String(e.days_left)), el("span", { class: "u" }, e.days_left === 1 ? "day" : "days")),
        el("div", { class: "grow" }, el("div", { class: "title" }, e.subject_name), el("div", { class: "small faint" }, `${e.type || "Exam"} · ${fmtDate(e.date)}${e.time ? ` · ${e.time}` : ""}`))));
    }
    examCard.append(list);
  }
  page.append(el("div", { class: "grid two section" }, planCard, examCard));

  // Weak spots, neglected subjects and the warm-up.
  const weakCard = el("div", { class: "card" }, el("span", { class: "label" }, "Weakest topics"));
  if (!t.weakest.length) {
    weakCard.append(el("p", { class: "muted", style: { marginTop: "10px" } }, "Start a topic and Athena will track where you are weakest."));
  } else {
    const list = el("div", { class: "list", style: { marginTop: "8px" } });
    for (const w of t.weakest) {
      list.append(el("a", { class: "list-row", href: `#/learn/${encodeURIComponent(w.id)}` }, ring(w.mastery, 38),
        el("div", { class: "grow" }, el("div", { class: "title ellipsis" }, w.title),
          el("div", { class: "small faint" }, `${t.subjects[w.subject_id]?.short_name || w.subject_id} · mastery ${pct(w.mastery)}`))));
    }
    weakCard.append(list);
  }
  const side = el("div", { class: "stack" }, weakCard);
  if (t.neglected.length) {
    side.append(banner(`Untouched for a while: ${t.neglected.map((n) => `${n.name} (${n.days} days)`).join(", ")}. A short review keeps it fresh.`, "warn"));
  }
  if (t.next_topics.length) {
    const next = el("div", { class: "card" }, el("span", { class: "label" }, "Next topics"));
    const list = el("div", { class: "list", style: { marginTop: "8px" } });
    for (const n of t.next_topics) {
      list.append(el("a", { class: "list-row", href: `#/learn/${encodeURIComponent(n.id)}` }, subjectDot(t.subjects[n.subject_id]?.color),
        el("div", { class: "grow" }, el("div", { class: "title ellipsis" }, n.title),
          el("div", { class: "small faint" }, `${t.subjects[n.subject_id]?.short_name || ""} · ${fmtMinutes(n.est_minutes)}`)),
        n.status === "started" ? pill("In progress", "accent") : null));
    }
    next.append(list);
    side.append(next);
  }
  warm = warmupBlock(t.warmup);
  page.append(el("div", { class: "grid two section" }, side, warm));

  if (!t.next_topics.length && !t.weakest.length) {
    page.append(el("div", { class: "section" }, empty("No lessons yet", "Lessons appear here once your slides have been turned into topics.",
      el("a", { class: "btn", href: "#/sources" }, "See your slides"))));
  }
}

export function cleanup() {
  warm = null;
}
