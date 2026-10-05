// Sources: every deck with its status, coverage and flags, plus the slides still missing.

import { api } from "../api.js";
import { openSlideModal } from "../components.js";
import { banner, el, empty, pill, subjectDot } from "../ui.js";

export const title = () => "Sources";

function statusPills(d) {
  return el("div", { class: "row wrap", style: { gap: "6px" } },
    pill("Read in", "good"),
    d.pass_a ? pill("Lessons", "good") : pill("Lessons coming"),
    d.pass_b ? pill("Question bank", "good") : pill("Questions coming"),
    d.verified ? pill("Verified", "good") : null);
}

export async function render(root) {
  const s = await api.get("/sources");
  const page = el("div", { class: "page" });
  root.append(page);
  const ready = s.decks.filter((d) => d.pass_a).length;
  page.append(el("div", { class: "page-head" },
    el("div", {}, el("h1", {}, "Sources"), el("div", { class: "sub" }, "Your professors' slides that Athena teaches from.")),
    el("div", { class: "row", style: { gap: "18px" } },
      el("div", { class: "stat" }, el("span", { class: "label" }, "Decks"), el("div", { class: "num" }, String(s.decks.length))),
      el("div", { class: "stat" }, el("span", { class: "label" }, "With lessons"), el("div", { class: "num" }, String(ready))),
      el("div", { class: "stat" }, el("span", { class: "label" }, "Answers to grade"), el("div", { class: "num" }, String(s.review_queue))))));

  if (s.content_errors.length) {
    page.append(banner(`Some content files have problems: ${s.content_errors.slice(0, 3).join("; ")}`, "warn"));
  }

  if (!s.decks.length) {
    page.append(empty("No slides yet", "Drop your PPTs into the inbox folder (one folder per subject), then run the overnight build again."));
  } else {
    const list = el("div", { class: "card", style: { padding: "8px 16px" } }, el("div", { class: "list" },
      ...s.decks.map((d) => el("div", { class: "list-row", style: { alignItems: "flex-start", flexWrap: "wrap" } },
        subjectDot(d.color),
        el("div", { class: "grow", style: { minWidth: "220px" } },
          el("div", { class: "title" }, `${d.subject} · ${d.title || d.file_name}`),
          el("div", { class: "small faint ellipsis", title: d.file }, d.file_name),
          el("div", { class: "small muted", style: { marginTop: "4px" } },
            `${d.slides} slides · ${d.content_slides} with content · pictures read ${d.visual_done}/${d.needs_visual}` +
            (d.coverage !== null ? ` · coverage ${d.coverage}%` : "") +
            (d.topics ? ` · ${d.topics} topics` : "") + (d.bank_questions ? ` · ${d.bank_questions} exam questions` : "") +
            (d.duplicates ? ` · ${d.duplicates} duplicate cop${d.duplicates === 1 ? "y" : "ies"} ignored` : "")),
          el("div", { style: { marginTop: "8px" } }, statusPills(d))),
        d.flagged ? pill(`${d.flagged} hidden for checking`, "warn") : null,
        el("button", { class: "btn small ghost", onclick: () => openSlideModal(`${d.id}#1`) }, "View")))));
    page.append(list);
  }

  page.append(el("div", { class: "section" }, el("h2", {}, "Slides still missing"),
    el("p", { class: "muted" }, "Sessions in your course plans that have no slides on this PC. Grab them from Classroom and drop them in the inbox folder.")));
  if (s.subjects_without_slides.length) {
    page.append(banner(`No slides at all for: ${s.subjects_without_slides.map((x) => x.name).join(", ")}.`, "warn"));
  }
  if (!s.gaps.length) {
    page.append(el("p", { class: "muted" }, "Every session in the course plans has slides."));
  } else {
    const grid = el("div", { class: "grid two", style: { marginTop: "12px" } });
    for (const g of s.gaps) {
      grid.append(el("div", { class: "card pad-sm" }, el("div", { class: "row between" }, el("b", {}, g.subject), pill(`${g.missing.length} missing`, "warn")),
        el("ul", { class: "small muted", style: { margin: "8px 0 0", paddingLeft: "18px" } },
          ...g.missing.map((m) => el("li", {}, `${m.n}: ${m.topic}`)))));
    }
    page.append(grid);
  }
  page.append(el("div", { class: "card section" }, el("span", { class: "label" }, "Adding new slides"),
    el("p", { style: { marginTop: "8px" } }, "Put files in the inbox folder inside the Athena folder, one folder per subject (for example inbox\\Marketing Management). Then run:"),
    el("div", { class: "card pad-sm mono", style: { userSelect: "all" } }, s.refresh_command)));
}
