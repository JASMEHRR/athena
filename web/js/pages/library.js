// Library: search across slides, topics and examples; frameworks; examples; past papers; links.

import { api, qs } from "../api.js";
import { openSlideModal } from "../components.js";
import { clear, el, empty, escapeHtml, icon, pill, subjectDot } from "../ui.js";

export const title = () => "Library";

const KIND = { slide: "Slide", topic: "Lesson", example: "Example", framework: "Framework", pyq: "Past paper" };

function snippetNode(text) {
  // Server marks matches with control characters 2 and 3; show them in bold, everything else escaped.
  const html = escapeHtml(text || "").replace(/\u0002/g, "<b>").replace(/\u0003/g, "</b>");
  return el("div", { class: "small muted", html });
}

function searchTab(body, lib, initial) {
  const input = el("input", { type: "search", placeholder: "Search your slides, lessons and examples", "aria-label": "Search", value: initial || "" });
  const results = el("div", { class: "stack", style: { marginTop: "14px" } });
  const short = Object.fromEntries(lib.subjects.map((s) => [s.id, s]));
  let timer = null;
  async function run() {
    const q = input.value.trim();
    clear(results);
    if (!q) { results.append(el("p", { class: "muted small" }, "Try a term from class, a company from a slide, or a framework name.")); return; }
    const hits = await api.get(`/search${qs({ q })}`);
    if (!hits.length) { results.append(empty("Nothing found", "Check the spelling, or try a shorter word.")); return; }
    for (const h of hits) {
      const s = short[h.subject_id];
      const open = () => {
        if (h.kind === "slide") openSlideModal(h.ref_id);
        else if (h.kind === "topic") location.hash = `#/learn/${encodeURIComponent(h.ref_id)}`;
        else if (h.kind === "example") {
          const ex = lib.examples.find((e) => e.id === h.ref_id);
          if (ex) openSlideModal(`${ex.deck_id}#${ex.slide}`);
        } else if (h.kind === "pyq" && s) location.hash = `#/subject/${h.subject_id}`;
      };
      results.append(el("button", { class: "card link pad-sm", style: { textAlign: "left", width: "100%", cursor: "pointer" }, onclick: open },
        el("div", { class: "row between" }, el("div", { class: "row" }, subjectDot(s?.color), el("b", {}, h.title)), pill(KIND[h.kind] || h.kind)),
        snippetNode(h.snip)));
    }
  }
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => run().catch(() => {}), 220); });
  body.append(input, results);
  run().catch(() => {});
  setTimeout(() => input.focus(), 30);
}

function frameworksTab(body, lib) {
  if (!lib.frameworks.length) { body.append(empty("No frameworks yet", "Frameworks, models and matrices from your slides collect here.")); return; }
  body.append(el("div", { class: "grid two" }, ...lib.frameworks.map((f) => el("div", { class: "card pad-sm" },
    el("div", { class: "row between" }, el("h3", {}, f.name), pill(f.subject)),
    f.description ? el("p", { class: "small muted", style: { marginTop: "6px" } }, f.description) : null,
    el("ul", { class: "small", style: { paddingLeft: "18px" } }, ...f.parts.map((p) => el("li", {}, el("b", {}, p.name), p.text ? `: ${p.text}` : ""))),
    el("div", { class: "row wrap" }, ...f.source_refs.map((r) => el("button", { class: "ref-chip", onclick: () => openSlideModal(r) }, icon("slide"), `Slide ${r.split("#")[1]}`)))))));
}

function examplesTab(body, lib) {
  if (!lib.examples.length) { body.append(empty("No examples yet", "Every example from your slides collects here.")); return; }
  const filter = el("select", { "aria-label": "Subject" }, el("option", { value: "" }, "All subjects"),
    ...lib.subjects.filter((s) => lib.examples.some((e) => e.subject_id === s.id)).map((s) => el("option", { value: s.id }, s.short_name)));
  const grid = el("div", { class: "grid two", style: { marginTop: "14px" } });
  function draw() {
    clear(grid);
    lib.examples.filter((x) => !filter.value || x.subject_id === filter.value).forEach((x) => grid.append(el("div", { class: "card pad-sm" },
      el("div", { class: "row between" }, el("b", {}, x.label), pill(x.subject)),
      el("p", { class: "small muted", style: { marginTop: "6px" } }, x.text),
      el("button", { class: "ref-chip", onclick: () => openSlideModal(`${x.deck_id}#${x.slide}`) }, icon("slide"), `Slide ${x.slide}`))));
  }
  filter.addEventListener("change", draw);
  body.append(el("div", { style: { maxWidth: "240px" } }, filter), grid);
  draw();
}

function pyqTab(body, lib) {
  if (!lib.pyqs.length) { body.append(empty("No past papers yet", "Drop past papers into inbox\\_pyqs and run a refresh.")); return; }
  const groups = {};
  lib.pyqs.forEach((q) => { (groups[`${q.subject} · ${q.exam} ${q.year}`] ||= []).push(q); });
  for (const [name, list] of Object.entries(groups)) {
    body.append(el("div", { class: "card", style: { marginBottom: "14px" } }, el("h3", {}, name),
      el("div", { class: "list", style: { marginTop: "8px" } }, ...list.map((q) => el("div", { class: "list-row", style: { alignItems: "flex-start" } },
        el("span", { class: "mono small faint", style: { minWidth: "48px" } }, q.q_no), el("div", { class: "grow" }, q.text),
        q.marks ? pill(`${q.marks} marks`) : null)))));
  }
}

function linksTab(body, lib) {
  if (!lib.links.length) { body.append(empty("No cross-subject links yet", "When the same idea shows up in two subjects' slides, it is linked here.")); return; }
  body.append(el("div", { class: "stack" }, ...lib.links.map((l) => el("div", { class: "card pad-sm" },
    el("b", {}, l.concept), l.note ? el("p", { class: "small muted" }, l.note) : null,
    el("div", { class: "row wrap small" },
      el("a", { href: `#/learn/${encodeURIComponent(l.a.topic_id)}` }, `${l.a.subject}: ${l.a.topic_title}`), el("span", { class: "faint" }, "and"),
      el("a", { href: `#/learn/${encodeURIComponent(l.b.topic_id)}` }, `${l.b.subject}: ${l.b.topic_title}`))))));
}

export async function render(root, { query }) {
  const lib = await api.get("/library");
  const page = el("div", { class: "page" }, el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Library"),
    el("div", { class: "sub" }, "Everything from your slides in one place."))));
  root.append(page);
  const tabs = [["search", "Search", searchTab], ["frameworks", "Frameworks", frameworksTab], ["examples", "Examples", examplesTab],
    ["pyqs", "Past papers", pyqTab], ["links", "Links", linksTab]];
  const body = el("div", { class: "section" });
  const seg = el("div", { class: "seg", role: "tablist" });
  function show(key) {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.key === key));
    clear(body);
    tabs.find((t) => t[0] === key)[2](body, lib, query.get("q"));
  }
  tabs.forEach(([key, label]) => seg.append(el("button", { "data-key": key, role: "tab", onclick: () => show(key) }, label)));
  page.append(el("div", { style: { overflowX: "auto" } }, seg), body);
  show(query.get("tab") || "search");
}
