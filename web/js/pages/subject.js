// One subject: topics with mastery, decks, examples, frameworks, past papers, syllabus, videos.

import { api } from "../api.js";
import { openSlideModal } from "../components.js";
import { banner, clear, el, empty, fmtDate, fmtMinutes, icon, pct, pill, ring, subjectDot } from "../ui.js";

let subjectName = "Subject";
export const title = () => subjectName;

const STATUS = { new: ["Not started", ""], started: ["In progress", "accent"], learned: ["Learned", "good"] };

function topicsTab(d) {
  if (!d.topics.length) {
    return empty("No lessons yet", d.decks.length
      ? "The slides are in, and lessons for them are being written."
      : "There are no slides for this subject on your PC yet. Add them to the inbox folder.");
  }
  const list = el("div", { class: "card", style: { padding: "8px 16px" } }, el("div", { class: "list" },
    ...d.topics.map((t) => el("a", { class: "list-row", href: `#/learn/${encodeURIComponent(t.id)}` },
      ring(t.mastery, 40, d.subject.color),
      el("div", { class: "grow" }, el("div", { class: "title ellipsis" }, t.title),
        el("div", { class: "small faint" }, `${fmtMinutes(t.est_minutes)} · difficulty ${t.difficulty} of 3`)),
      t.stale ? pill("Slides changed", "warn") : null,
      pill(...STATUS[t.status])))));
  return list;
}

function decksTab(d) {
  if (!d.decks.length) return empty("No slides yet", "Drop this subject's decks into the inbox folder and run a refresh.");
  return el("div", { class: "card", style: { padding: "8px 16px" } }, el("div", { class: "list" },
    ...d.decks.map((k) => el("div", { class: "list-row" }, icon("slide"),
      el("div", { class: "grow" }, el("div", { class: "title ellipsis" }, k.title || k.file_name),
        el("div", { class: "small faint ellipsis" }, `${k.file_name} · ${k.slides} slides · ${k.topics} topic${k.topics === 1 ? "" : "s"}`)),
      k.status.pass_a ? pill("Lessons ready", "good") : pill("Lessons coming"),
      el("button", { class: "btn small ghost", onclick: () => openSlideModal(`${k.id}#1`) }, "View")))));
}

function examplesTab(d) {
  if (!d.examples.length) return empty("No examples yet", "Every example from the slides is collected here as lessons are written.");
  return el("div", { class: "grid two" }, ...d.examples.map((x) => el("div", { class: "card pad-sm" },
    el("div", { class: "row between" }, el("b", {}, x.label), pill(x.kind)),
    el("p", { class: "small muted", style: { marginTop: "6px" } }, x.text),
    el("button", { class: "ref-chip", onclick: () => openSlideModal(`${x.deck_id}#${x.slide}`) }, icon("slide"), `Slide ${x.slide}`))));
}

function frameworksTab(d) {
  if (!d.frameworks.length) return empty("No frameworks yet", "Frameworks and models from the slides appear here.");
  return el("div", { class: "grid two" }, ...d.frameworks.map((f) => el("div", { class: "card pad-sm" },
    el("h3", {}, f.name), f.description ? el("p", { class: "small muted", style: { marginTop: "6px" } }, f.description) : null,
    el("ul", { class: "small" }, ...f.parts.map((p) => el("li", {}, el("b", {}, p.name), p.text ? `: ${p.text}` : ""))))));
}

function pyqTab(d) {
  const blocks = [];
  if (d.pattern) {
    blocks.push(el("div", { class: "card" }, el("span", { class: "label" }, "How this professor sets papers"),
      el("p", { style: { marginTop: "8px" } }, d.pattern.summary),
      d.pattern.paper_format ? el("p", { class: "small muted" }, d.pattern.paper_format) : null,
      d.pattern.repeated_topics?.length ? el("div", { class: "row wrap" }, ...d.pattern.repeated_topics.map((t) => pill(t))) : null));
  }
  if (!d.pyqs.length) {
    blocks.push(empty("No past papers yet", "Put past papers in the inbox/_pyqs folder and run a refresh."));
  } else {
    const groups = {};
    d.pyqs.forEach((q) => { (groups[`${q.exam} ${q.year}`] ||= []).push(q); });
    for (const [name, qs] of Object.entries(groups)) {
      blocks.push(el("div", { class: "card" }, el("h3", {}, name), el("div", { class: "list", style: { marginTop: "8px" } },
        ...qs.map((q) => el("div", { class: "list-row", style: { alignItems: "flex-start" } },
          el("span", { class: "mono small faint", style: { minWidth: "48px" } }, q.q_no),
          el("div", { class: "grow" }, el("div", {}, q.text), q.note ? el("div", { class: "small faint" }, q.note) : null),
          q.marks ? pill(`${q.marks} marks`) : null)))));
    }
  }
  return el("div", { class: "stack" }, ...blocks);
}

function syllabusTab(d) {
  const s = d.syllabus;
  if (!s) return empty("No course outline", "Add the course outline or session plan to the inbox folder.");
  const missing = s.sessions.filter((x) => !x.has_ppt).length;
  return el("div", { class: "stack" },
    missing ? banner(`${missing} session${missing === 1 ? "" : "s"} in the course plan have no slides on your PC yet. Grab them from Classroom so Athena can teach them.`, "info") : null,
    s.evaluation.length ? el("div", { class: "card pad-sm" }, el("span", { class: "label" }, "Evaluation"),
      el("div", { class: "row wrap", style: { marginTop: "8px" } }, ...s.evaluation.map((e) => pill(e)))) : null,
    el("div", { class: "card", style: { padding: "8px 16px" } }, el("div", { class: "list" },
      ...s.sessions.map((x) => el("div", { class: "list-row" },
        el("span", { class: "mono small faint", style: { minWidth: "84px" } }, x.n),
        el("div", { class: "grow" }, el("div", {}, x.topic), x.module ? el("div", { class: "small faint" }, x.module) : null),
        x.has_ppt ? pill("Slides here", "good") : pill("No slides yet", "warn"))))),
    s.note ? el("p", { class: "small muted" }, s.note) : null);
}

function videosTab(d) {
  if (!d.videos.length) return empty("No videos", "Extra-help videos appear here once they are picked.");
  return el("div", { class: "stack" }, banner("Extra help, not exam source. Your exam follows your professor's slides.", "info"),
    el("div", { class: "grid two" }, ...d.videos.map((v) => el("a", { class: "card link pad-sm", href: v.url, target: "_blank", rel: "noopener" },
      el("b", {}, v.title), el("div", { class: "small faint" }, v.channel)))));
}

export async function render(root, { args }) {
  const d = await api.get(`/subjects/${encodeURIComponent(args[0] || "")}`);
  subjectName = d.subject.short_name;
  const page = el("div", { class: "page" });
  root.append(page);
  const learned = d.topics.filter((t) => t.status === "learned").length;
  const avg = d.topics.length ? d.topics.reduce((a, t) => a + t.mastery, 0) / d.topics.length : 0;
  page.append(el("div", { class: "page-head" },
    el("div", {}, el("a", { class: "small", href: "#/subjects" }, "All subjects"),
      el("div", { class: "row", style: { marginTop: "8px" } }, subjectDot(d.subject.color), el("h1", {}, d.subject.name)),
      el("div", { class: "sub" }, [d.subject.code, d.subject.faculty].filter(Boolean).join(" · "))),
    el("div", { class: "row", style: { gap: "18px" } },
      el("div", { class: "stat" }, el("span", { class: "label" }, "Learned"), el("div", { class: "num" }, `${learned}`, el("small", {}, `/ ${d.topics.length}`))),
      el("div", { class: "stat" }, el("span", { class: "label" }, "Mastery"), el("div", { class: "num" }, pct(avg))),
      d.next_exam ? el("div", { class: "stat" }, el("span", { class: "label" }, "Exam"), el("div", { class: "num" }, `${d.next_exam.days_left}`, el("small", {}, "days")),
        el("div", { class: "small faint" }, fmtDate(d.next_exam.date))) : null)));

  const tabs = [
    ["topics", "Topics", topicsTab], ["decks", "Slides", decksTab], ["examples", "Examples", examplesTab],
    ["frameworks", "Frameworks", frameworksTab], ["pyqs", "Past papers", pyqTab], ["syllabus", "Course plan", syllabusTab],
    ["videos", "Videos", videosTab],
  ];
  const body = el("div", { class: "section" });
  const seg = el("div", { class: "seg", role: "tablist" });
  function show(key) {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.key === key));
    clear(body);
    body.append(tabs.find((t) => t[0] === key)[2](d));
  }
  tabs.forEach(([key, label]) => seg.append(el("button", { "data-key": key, role: "tab", onclick: () => show(key) }, label)));
  page.append(el("div", { style: { overflowX: "auto" } }, seg), body);
  show("topics");
}
