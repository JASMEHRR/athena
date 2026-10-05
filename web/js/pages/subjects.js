// Subjects: all subjects with progress, coverage and next exam.

import { api } from "../api.js";
import { el, fmtDate, pct, pill, ring, subjectDot } from "../ui.js";

export const title = () => "Subjects";

export async function render(root) {
  const subjects = await api.get("/subjects");
  const page = el("div", { class: "page" });
  root.append(page);
  page.append(el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Subjects"),
    el("div", { class: "sub" }, "Everything here comes from your professors' slides."))));

  const withLessons = subjects.filter((s) => s.topics > 0);
  const without = subjects.filter((s) => s.topics === 0);
  const grid = el("div", { class: "grid auto" });
  for (const s of [...withLessons, ...without]) {
    const exam = s.next_exam;
    grid.append(el("a", { class: "card link", href: `#/subject/${s.id}` },
      el("div", { class: "row between" },
        el("div", { class: "row" }, subjectDot(s.color), el("span", { class: "label" }, s.short_name)),
        s.topics ? ring(s.mastery, 40, s.color) : pill(s.decks ? "Lessons coming" : "No slides yet")),
      el("h3", { style: { marginTop: "12px" } }, s.name),
      el("div", { class: "small faint", style: { marginTop: "4px" } }, s.code),
      el("div", { class: "divider" }),
      el("div", { class: "row between small" },
        el("span", { class: "muted" }, s.topics ? `${s.learned} of ${s.topics} topics learned` : `${s.decks} deck${s.decks === 1 ? "" : "s"} of slides`),
        el("span", { class: "muted" }, `${s.decks_with_lessons}/${s.decks} decks ready`)),
      el("div", { class: "row between small", style: { marginTop: "6px" } },
        el("span", { class: "faint" }, exam ? `${exam.type || "Exam"} ${fmtDate(exam.date)}` : "No exam date"),
        exam ? pill(`${exam.days_left} days`, exam.days_left <= 7 ? "warn" : "") : el("span", {}, s.topics ? `Mastery ${pct(s.mastery)}` : ""))));
  }
  page.append(grid);
}
