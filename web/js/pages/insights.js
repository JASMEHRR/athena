// Insights: weak-topic heatmap, time per subject, accuracy over time, streak calendar.

import { api } from "../api.js";
import { el, empty, fmtMinutes, pct } from "../ui.js";

export const title = () => "Insights";

const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, ...kids) {
  const node = document.createElementNS(SVG, tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  kids.forEach((k) => k && node.append(k));
  return node;
}

function heatmap(rows) {
  if (!rows.length) return empty("No topics yet", "The heatmap fills in as lessons are written.");
  const wrap = el("div", { class: "heat" });
  for (const row of rows) {
    const cells = row.topics.map((t) => {
      const alpha = t.status === "new" ? 0 : 0.18 + 0.82 * t.mastery;
      return el("a", {
        class: "heat-cell", href: `#/learn/${encodeURIComponent(t.id)}`,
        title: `${t.title}: ${t.status === "new" ? "not started" : `mastery ${pct(t.mastery)}`}`,
        style: { background: t.status === "new" ? "var(--surface-3)" : `color-mix(in srgb, ${row.color || "var(--accent)"} ${Math.round(alpha * 100)}%, var(--surface-3))` },
        "aria-label": `${t.title}, ${t.status === "new" ? "not started" : `mastery ${pct(t.mastery)}`}`,
      });
    });
    wrap.append(el("div", { class: "heat-row" }, el("span", { class: "small mono" }, row.short_name), el("div", { class: "heat-cells" }, cells)));
  }
  return el("div", {}, wrap, el("div", { class: "small faint", style: { marginTop: "10px" } }, "Each square is a topic. Grey: not started. Brighter: stronger. Click a square to study it."));
}

function timeBars(items) {
  if (!items.length) return el("p", { class: "muted" }, "No study time recorded in the last 30 days.");
  const max = Math.max(...items.map((i) => i.minutes), 1);
  return el("div", { class: "stack" }, ...items.map((i) => el("div", { class: "stack", style: { gap: "4px" } },
    el("div", { class: "row between small" }, el("span", {}, i.name), el("span", { class: "mono faint" }, fmtMinutes(i.minutes))),
    el("div", { class: "bar" }, el("span", { style: { width: `${(i.minutes / max) * 100}%`, background: i.color || "var(--accent)" } })))));
}

function lineChart(series) {
  const pts = series.map((d, i) => ({ i, v: d.accuracy })).filter((p) => p.v !== null);
  if (!pts.length) return el("p", { class: "muted" }, "Answer some questions and your accuracy shows up here.");
  const W = 600, H = 160, P = 24;
  const x = (i) => P + (i / Math.max(1, series.length - 1)) * (W - 2 * P);
  const y = (v) => H - P - v * (H - 2 * P);
  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", role: "img", "aria-label": "Accuracy over the last 30 days" });
  [0, 0.5, 1].forEach((g) => chart.append(svg("line", { x1: P, x2: W - P, y1: y(g), y2: y(g), stroke: "var(--border)", "stroke-width": 1 }),
    svg("text", { x: 2, y: y(g) + 4, fill: "var(--faint)", "font-size": 10, "font-family": "monospace" }, document.createTextNode(`${g * 100}`))));
  chart.append(svg("polyline", { points: pts.map((p) => `${x(p.i)},${y(p.v)}`).join(" "), fill: "none", stroke: "var(--accent)", "stroke-width": 2.5, "stroke-linejoin": "round" }));
  pts.forEach((p) => chart.append(svg("circle", { cx: x(p.i), cy: y(p.v), r: 3.5, fill: "var(--accent)" },
    svg("title", {}, document.createTextNode(`${series[p.i].date}: ${pct(p.v)} of ${series[p.i].answered}`)))));
  return chart;
}

function minutesChart(series) {
  if (!series.some((d) => d.minutes)) return el("p", { class: "muted" }, "No study time recorded yet.");
  const W = 600, H = 120, P = 20;
  const max = Math.max(...series.map((d) => d.minutes), 15);
  const bw = (W - 2 * P) / series.length;
  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", role: "img", "aria-label": "Minutes studied per day" });
  series.forEach((d, i) => {
    const h = (d.minutes / max) * (H - 2 * P);
    chart.append(svg("rect", { x: P + i * bw + 2, y: H - P - h, width: Math.max(2, bw - 4), height: Math.max(h, d.minutes ? 2 : 0), rx: 3,
      fill: d.minutes >= 15 ? "var(--accent)" : "var(--border-strong)" }, svg("title", {}, document.createTextNode(`${d.date}: ${d.minutes} min`))));
  });
  return chart;
}

function streakCalendar(days) {
  const grid = el("div", { style: { display: "grid", gridTemplateRows: "repeat(7, 14px)", gridAutoFlow: "column", gridAutoColumns: "14px", gap: "4px" } });
  days.forEach((d) => grid.append(el("span", {
    title: d.date, style: { borderRadius: "4px", background: d.future ? "transparent" : d.active ? "var(--accent)" : "var(--surface-3)" },
  })));
  return el("div", { style: { overflowX: "auto" } }, grid);
}

export async function render(root) {
  const d = await api.get("/insights");
  const t = d.totals;
  const page = el("div", { class: "page" },
    el("div", { class: "page-head" }, el("div", {}, el("h1", {}, "Insights"), el("div", { class: "sub" }, "Where you are strong, where you are not, and how much you have put in."))),
    el("div", { class: "grid", style: { gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))" } },
      el("div", { class: "card pad-sm stat" }, el("span", { class: "label" }, "Topics learned"), el("div", { class: "num" }, `${t.learned}`, el("small", {}, `/ ${t.topics}`))),
      el("div", { class: "card pad-sm stat" }, el("span", { class: "label" }, "Accuracy"), el("div", { class: "num" }, t.accuracy === null ? "-" : pct(t.accuracy))),
      el("div", { class: "card pad-sm stat" }, el("span", { class: "label" }, "Questions"), el("div", { class: "num" }, String(t.answered))),
      el("div", { class: "card pad-sm stat" }, el("span", { class: "label" }, "Reviews"), el("div", { class: "num" }, String(t.reviews))),
      el("div", { class: "card pad-sm stat" }, el("span", { class: "label" }, "Time"), el("div", { class: "num" }, fmtMinutes(t.minutes))),
      el("div", { class: "card pad-sm stat" }, el("span", { class: "label" }, "Best streak"), el("div", { class: "num" }, String(d.streak.best), el("small", {}, "days")))),
    el("div", { class: "card section" }, el("h2", {}, "Weak-topic heatmap"), el("div", { style: { height: "14px" } }), heatmap(d.heatmap)),
    el("div", { class: "grid two section" },
      el("div", { class: "card" }, el("h2", {}, "Accuracy, last 30 days"), el("div", { style: { height: "10px" } }), lineChart(d.series)),
      el("div", { class: "card" }, el("h2", {}, "Time per subject"), el("p", { class: "small faint" }, "Last 30 days"), timeBars(d.time_by_subject))),
    el("div", { class: "grid two section" },
      el("div", { class: "card" }, el("h2", {}, "Minutes per day"), el("p", { class: "small faint" }, "Bright bars are days with 15+ minutes"), minutesChart(d.series)),
      el("div", { class: "card" }, el("h2", {}, "Streak calendar"), el("p", { class: "small faint" }, `${d.streak.days} day streak · last 12 weeks`), streakCalendar(d.calendar))));
  root.append(page);
}
