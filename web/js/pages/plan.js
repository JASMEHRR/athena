// Plan: day, week and month views of the study plan, targets, re-plan, .ics export.

import { api, qs } from "../api.js";
import { banner, clear, el, empty, fmtDate, fmtMinutes, icon, pill, subjectDot, toast } from "../ui.js";

export const title = () => "Plan";

const KIND = { review: "Review", learn: "Learn", revise: "Revise", exam_revision: "Exam revision", mock: "Mock paper" };

function taskHref(t) {
  if (t.kind === "review") return "#/review";
  if (t.kind === "mock") return `#/practice?mode=mock&subject=${t.subject_id}`;
  if (t.topic_id) return `#/learn/${encodeURIComponent(t.topic_id)}`;
  return `#/practice?subject=${t.subject_id}`;
}

function dayView(cal, subjects, redraw) {
  const today = cal.days[0];
  const box = el("div", { class: "card" });
  box.append(el("div", { class: "row between" }, el("span", { class: "label" }, `Today · ${fmtDate(today.date)}`),
    el("span", { class: "small faint" }, `${fmtMinutes(today.minutes)} planned of ${fmtMinutes(today.capacity || 0)}`)));
  if (!today.tasks.length) {
    box.append(el("p", { class: "muted", style: { marginTop: "10px" } }, "Nothing planned today."));
    return box;
  }
  const list = el("div", { class: "list", style: { marginTop: "8px" } });
  for (const t of today.tasks) {
    const s = subjects[t.subject_id];
    const setStatus = async (status) => {
      try { await api.put(`/plan/tasks/${t.id}`, { status }); redraw(); } catch (err) { toast(err.message); }
    };
    list.append(el("div", { class: "list-row" },
      t.status === "done" ? el("span", { class: "pill good" }, icon("check")) : subjectDot(s?.color),
      el("a", { class: "grow", href: taskHref(t), style: { color: "inherit" } },
        el("div", { class: "title", style: t.status !== "todo" ? { textDecoration: "line-through", color: "var(--faint)" } : {} }, t.title),
        el("div", { class: "small faint" }, `${KIND[t.kind] || t.kind}${s ? ` · ${s.short_name}` : ""} · ${fmtMinutes(t.minutes)}`)),
      t.status === "todo"
        ? el("div", { class: "row" }, el("button", { class: "btn small", onclick: () => setStatus("done") }, "Done"),
          el("button", { class: "btn small ghost", onclick: () => setStatus("skipped") }, "Skip"))
        : el("button", { class: "btn small ghost", onclick: () => setStatus("todo") }, "Undo")));
  }
  box.append(list);
  return box;
}

function gridView(cal, subjects, n) {
  const exams = {};
  cal.exams.forEach((e) => { (exams[e.date] ||= []).push(e); });
  const deadlines = {};
  cal.deadlines.forEach((d) => { (deadlines[d.due.slice(0, 10)] ||= []).push(d); });
  const grid = el("div", { class: "calendar" });
  cal.days.slice(0, n).forEach((d, i) => {
    const cell = el("div", { class: `cal-day ${i === 0 ? "today" : ""}` },
      el("div", { class: "row between" }, el("span", { class: "d" }, fmtDate(d.date, { weekday: "short", day: "numeric", month: "short" })),
        d.minutes ? el("span", { class: "d" }, fmtMinutes(d.minutes)) : null));
    for (const e of exams[d.date] || []) cell.append(el("div", { class: "cal-task", style: { background: "var(--bad-soft)", color: "var(--bad)" } }, `${e.short_name} ${e.type || "exam"}`));
    for (const dl of deadlines[d.date] || []) cell.append(el("div", { class: "cal-task", style: { background: "var(--warn-soft)" } }, `Due: ${dl.title}`));
    for (const t of d.tasks) {
      const s = subjects[t.subject_id];
      cell.append(el("a", { class: "cal-task", href: taskHref(t), title: t.title,
        style: { borderLeft: `3px solid ${s?.color || "var(--border-strong)"}`, display: "block", color: "inherit",
          opacity: t.status === "done" ? 0.5 : 1 } }, t.title));
    }
    if (d.capacity === 0) cell.append(el("div", { class: "small faint", style: { marginTop: "4px" } }, "Day off"));
    grid.append(cell);
  });
  return grid;
}

export async function render(root, { query }) {
  const page = el("div", { class: "page" });
  root.append(page);
  let view = query.get("view") || "day";
  const subjects = Object.fromEntries((await api.get("/subjects")).map((s) => [s.id, s]));
  const body = el("div", {});

  async function draw() {
    const cal = await api.get(`/plan/calendar${qs({ days: 35 })}`);
    clear(body);
    if (!cal.has_exams) {
      body.append(banner("No exam dates yet, so this is a balanced six-week rotation. Add your dates in Settings to plan backwards from them.", "warn",
        el("a", { class: "btn small", href: "#/settings" }, "Add dates")), el("div", { style: { height: "12px" } }));
    }
    cal.warnings.forEach((w) => body.append(banner(w, "warn"), el("div", { style: { height: "12px" } })));
    if (cal.targets.length) {
      body.append(el("div", { class: "card", style: { marginBottom: "16px" } }, el("span", { class: "label" }, "Targets"),
        el("div", { class: "list", style: { marginTop: "8px" } }, ...cal.targets.map((t) => el("div", { class: "list-row" },
          subjectDot(subjects[t.subject_id]?.color), el("div", { class: "grow" }, el("b", {}, subjects[t.subject_id]?.short_name || t.subject_id), ` · ${t.text}`),
          t.per_day ? pill(`${t.per_day}/day`, t.per_day > 3 ? "warn" : "") : null)))));
    }
    if (!cal.days.some((d) => d.tasks.length)) {
      body.append(empty("Nothing to plan yet", "The plan fills up as lessons are written from your slides."));
      return;
    }
    if (view === "day") body.append(dayView(cal, subjects, draw));
    else body.append(gridView(cal, subjects, view === "week" ? 7 : 35));
  }

  const seg = el("div", { class: "seg" }, ...[["day", "Day"], ["week", "Week"], ["month", "Month"]].map(([k, label]) =>
    el("button", { class: view === k ? "on" : "", onclick: (e) => {
      view = k;
      seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === e.currentTarget));
      draw().catch((err) => toast(err.message));
    } }, label)));
  page.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Plan"), el("div", { class: "sub" }, "Rebuilt every morning from your progress. Missed tasks roll forward.")),
    el("div", { class: "row wrap" }, seg,
      el("button", { class: "btn", onclick: async () => {
        try { await api.post("/plan/replan"); toast("Plan rebuilt"); await draw(); } catch (err) { toast(err.message); }
      } }, "Re-plan"),
      el("a", { class: "btn", href: "/api/v1/plan/export.ics", download: "athena-plan.ics", title: "Import into Google Calendar" }, icon("plan"), "Export .ics"))));
  page.append(body);
  await draw();
}
