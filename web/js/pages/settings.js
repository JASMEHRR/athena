// Settings: exam dates, study time, reminders, display, backup and refresh.

import { api } from "../api.js";
import { banner, clear, el, icon, toast } from "../ui.js";

export const title = () => "Settings";

const DAYS = [["mon", "Mon"], ["tue", "Tue"], ["wed", "Wed"], ["thu", "Thu"], ["fri", "Fri"], ["sat", "Sat"], ["sun", "Sun"]];
const EXAM_TYPES = ["EST", "MST", "Quiz", "Viva", "Other"];

async function save(values, message = "Saved") {
  try {
    await api.put("/settings", values);
    toast(message);
    return true;
  } catch (err) {
    toast(err.message);
    return false;
  }
}

function section(titleText, desc, ...body) {
  return el("div", { class: "card section stack" }, el("h2", {}, titleText), desc ? el("p", { class: "muted small" }, desc) : null, ...body);
}

function examsSection(settings, contentExams, subjects) {
  const rows = el("div", { class: "stack" });
  const current = settings.exams ?? contentExams;
  function addRow(e = {}) {
    const subj = el("select", { "aria-label": "Subject" }, ...subjects.map((s) => el("option", { value: s.id }, s.name)));
    if (e.subject_id) subj.value = e.subject_id;
    const date = el("input", { type: "date", value: e.date || "", "aria-label": "Exam date" });
    const time = el("input", { type: "time", value: e.time || "", "aria-label": "Exam time" });
    const type = el("select", { "aria-label": "Exam type" }, ...EXAM_TYPES.map((t) => el("option", { value: t }, t)));
    type.value = e.type || "EST";
    const row = el("div", { class: "row wrap", "data-row": "1" }, el("div", { style: { flex: "2 1 220px" } }, subj),
      el("div", { style: { flex: "1 1 150px" } }, date), el("div", { style: { flex: "1 1 110px" } }, time),
      el("div", { style: { flex: "1 1 100px" } }, type),
      el("button", { class: "icon-btn", title: "Remove", onclick: () => row.remove() }, icon("close")));
    row._read = () => ({ subject_id: subj.value, date: date.value, time: time.value, type: type.value });
    rows.append(row);
  }
  current.forEach(addRow);
  if (!current.length) addRow();
  const saveBtn = el("button", { class: "btn primary", onclick: async () => {
    const exams = [...rows.querySelectorAll("[data-row]")].map((r) => r._read()).filter((e) => e.date);
    if (await save({ exams }, "Exam dates saved. Your plan was rebuilt.")) settings.exams = exams;
  } }, "Save exam dates");
  return section("Exam dates", "Athena plans backwards from these. The last two days before each exam become revision and a mock paper.",
    !current.length ? banner("No dates yet. Add each end-semester exam when the datesheet is out.", "info") : null,
    rows, el("div", { class: "row wrap" }, el("button", { class: "btn", onclick: () => addRow() }, "Add an exam"), saveBtn));
}

function studySection(settings) {
  const inputs = {};
  const grid = el("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(90px, 1fr))" } },
    ...DAYS.map(([key, label]) => {
      inputs[key] = el("input", { type: "number", min: "0", max: "720", step: "15", value: settings.study_minutes[key] ?? 120, "aria-label": `${label} minutes` });
      return el("label", { class: "field" }, el("span", {}, label), inputs[key]);
    }));
  const offList = el("div", { class: "row wrap" });
  const daysOff = [...(settings.days_off || [])];
  function drawOff() {
    clear(offList);
    daysOff.sort().forEach((d, i) => offList.append(el("span", { class: "pill" }, d,
      el("button", { class: "icon-btn", style: { width: "22px", height: "22px", border: "0" }, title: "Remove", onclick: () => { daysOff.splice(i, 1); drawOff(); } }, icon("close")))));
    if (!daysOff.length) offList.append(el("span", { class: "small faint" }, "No days off."));
  }
  drawOff();
  const offInput = el("input", { type: "date", "aria-label": "Day off", style: { maxWidth: "200px" } });
  return section("Study time", "Minutes you can study each day. Athena fills these with reviews, lessons and revision.",
    grid,
    el("div", { class: "stack" }, el("span", { class: "label" }, "Days off"), offList,
      el("div", { class: "row" }, offInput, el("button", { class: "btn", onclick: () => {
        if (offInput.value && !daysOff.includes(offInput.value)) { daysOff.push(offInput.value); drawOff(); }
      } }, "Add day off"))),
    el("button", { class: "btn primary", onclick: () => {
      const minutes = Object.fromEntries(DAYS.map(([k]) => [k, Math.max(0, Math.min(720, Number(inputs[k].value) || 0))]));
      save({ study_minutes: minutes, days_off: daysOff }, "Study time saved. Your plan was rebuilt.");
    } }, "Save study time"));
}

function remindersSection(settings) {
  const times = settings.nudge_times.map((t, i) => el("input", { type: "time", value: t, "aria-label": `Reminder ${i + 1}` }));
  const quietFrom = el("input", { type: "time", value: settings.quiet_hours[0], "aria-label": "Quiet from" });
  const quietTo = el("input", { type: "time", value: settings.quiet_hours[1], "aria-label": "Quiet until" });
  const push = el("input", { type: "checkbox", checked: settings.phone_push });
  const topic = el("input", { type: "text", value: settings.ntfy_topic || "", placeholder: "A private random name, e.g. athena-k3x9q2", "aria-label": "ntfy topic" });
  return section("Reminders", "Windows notifications at these times, at most 4 a day and never in quiet hours. Turn them on once with scripts\\install-reminders.ps1 (see MORNING.md).",
    el("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" } }, ...times.map((t, i) => el("label", { class: "field" }, el("span", {}, `Reminder ${i + 1}`), t))),
    el("div", { class: "grid two" }, el("label", { class: "field" }, el("span", {}, "Quiet from"), quietFrom), el("label", { class: "field" }, el("span", {}, "Quiet until"), quietTo)),
    el("label", { class: "check" }, push, "Also send reminders to my phone with the free ntfy app"),
    el("label", { class: "field" }, el("span", {}, "ntfy topic name (subscribe to the same name in the ntfy app)"), topic),
    el("button", { class: "btn primary", onclick: () => save({
      nudge_times: times.map((t) => t.value).filter(Boolean),
      quiet_hours: [quietFrom.value || "23:30", quietTo.value || "08:00"],
      phone_push: push.checked,
      ntfy_topic: topic.value.trim(),
    }, "Reminder settings saved") }, "Save reminders"));
}

function displaySection(settings) {
  const clar = el("input", { type: "checkbox", checked: settings.show_clarifications });
  const theme = el("div", { class: "seg" }, ...["dark", "light"].map((t) => el("button", {
    class: document.documentElement.dataset.theme === t ? "on" : "",
    onclick: (e) => {
      document.documentElement.dataset.theme = t;
      try { localStorage.setItem("athena-theme", t); } catch { /* private mode */ }
      theme.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === e.currentTarget));
      save({ theme: t }, `${t === "dark" ? "Dark" : "Light"} mode`);
    },
  }, t === "dark" ? "Dark" : "Light")));
  return section("Display", null,
    el("div", { class: "row between wrap" }, el("span", {}, "Theme"), theme),
    el("label", { class: "check" }, clar, "Show 'Not on slide' clarifications in lessons"),
    el("button", { class: "btn", onclick: () => save({ show_clarifications: clar.checked }) }, "Save"));
}

function dataSection() {
  const out = el("div", { class: "small muted" });
  return section("Backup, export and refresh", "Your progress lives in data\\athena.db on this PC. Athena backs it up each time it starts (keeps 14).",
    el("div", { class: "row wrap" },
      el("button", { class: "btn", onclick: async () => {
        try { const r = await api.post("/backup"); toast(r.ok ? "Backup saved" : "Nothing to back up yet"); } catch (err) { toast(err.message); }
      } }, "Back up now"),
      el("a", { class: "btn", href: "/api/v1/export", download: "athena-progress.json" }, "Export my progress"),
      el("button", { class: "btn primary", onclick: async () => {
        try {
          const r = await api.post("/refresh/prepare");
          clear(out);
          out.append(el("p", {}, `Refresh request saved (${r.weakest} weak topics, ${r.queued_answers} answers waiting for deep review).`),
            el("p", {}, "To update Athena with new slides, grade your answers and add questions, open PowerShell in the Athena folder and run:"),
            el("div", { class: "card pad-sm mono", style: { userSelect: "all" } }, r.command),
            el("button", { class: "btn small", onclick: () => navigator.clipboard?.writeText(r.command).then(() => toast("Copied")) }, "Copy command"));
        } catch (err) { toast(err.message); }
      } }, "Prepare a Claude Code refresh")),
    out);
}

export async function render(root) {
  const [{ settings, content_exams }, subjects] = await Promise.all([api.get("/settings"), api.get("/subjects")]);
  const page = el("div", { class: "page narrow" },
    el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Settings"), el("div", { class: "sub" }, "Changes rebuild today's plan."))),
    examsSection(settings, content_exams, subjects),
    studySection(settings),
    remindersSection(settings),
    displaySection(settings),
    dataSection());
  root.append(page);
}
