// "More" on phones: the pages that do not fit in the bottom tab bar.

import { whatNext } from "../app.js";
import { el, icon } from "../ui.js";

export const title = () => "More";

export async function render(root) {
  const items = [
    ["plan", "Plan", "Calendar, daily targets, exam countdown", "plan"],
    ["insights", "Insights", "Weak spots, time spent, accuracy, streak", "insights"],
    ["library", "Library", "Frameworks, examples, past papers, search", "library"],
    ["sources", "Sources", "Your slides and what still needs adding", "sources"],
    ["settings", "Settings", "Exam dates, study time, reminders", "settings"],
  ];
  const page = el("div", { class: "page narrow" },
    el("div", { class: "page-head" }, el("h1", {}, "More")),
    el("button", { class: "btn primary block big", onclick: whatNext }, icon("spark"), "What next?"),
    el("div", { class: "card section", style: { padding: "8px 16px" } }, el("div", { class: "list" },
      ...items.map(([route, label, desc, ic]) => el("a", { class: "list-row", href: `#/${route}` }, icon(ic),
        el("div", { class: "grow" }, el("div", { class: "title" }, label), el("div", { class: "small faint" }, desc)), icon("arrow"))))),
    el("button", { class: "btn ghost block section", onclick: () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem("athena-theme", next); } catch { /* private mode */ }
    } }, icon("sun"), "Switch light or dark"));
  root.append(page);
}
