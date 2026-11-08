// Lesson pictures the app draws itself from the specs in a chunk's `visuals`
// (contract: athena/models.py): graphs, bell curves, trees, flows, comparisons, grids.
// Built with DOM calls only, so text from content is never parsed as HTML.
// Colours come from theme tokens (.t-a .. .t-d in app.css), so light and dark both work.

import { el, icon, refLabel } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";

function s(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    node.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const r1 = (n) => Math.round(n * 10) / 10;
const fmt = (n) => (Number.isInteger(n) ? String(n) : String(Number(n.toFixed(4))));

function svgBox(w, h, label) {
  return s("svg", { viewBox: `0 0 ${w} ${h}`, class: "viz-svg", role: "img", "aria-label": label || "Diagram" });
}

// Smooth curve through the points (Catmull-Rom turned into cubic Beziers).
function smoothPath(p) {
  let d = `M${p[0][0]},${p[0][1]}`;
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] || p[i];
    const p1 = p[i];
    const p2 = p[i + 1];
    const p3 = p[i + 2] || p2;
    const c1 = [r1(p1[0] + (p2[0] - p0[0]) / 6), r1(p1[1] + (p2[1] - p0[1]) / 6)];
    const c2 = [r1(p2[0] - (p3[0] - p1[0]) / 6), r1(p2[1] - (p3[1] - p1[1]) / 6)];
    d += ` C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${p2[0]},${p2[1]}`;
  }
  return d;
}

// Rough text width in SVG units at the given font size (no layout pass needed).
const textWidth = (text, size = 13) => String(text).length * size * 0.56;

// ------------------------------------------------------------- plot (axes from 0)

function plot(v) {
  const W = 440, H = 300, ml = 46, mr = 64, mt = 28, mb = 42;
  const X = (x) => r1(ml + (x / v.x_max) * (W - ml - mr));
  const Y = (y) => r1(H - mb - (y / v.y_max) * (H - mt - mb));
  const svg = svgBox(W, H, v.title || `Graph of ${v.y_label} against ${v.x_label}`);
  const areas = s("g"), guides = s("g"), axes = s("g"), lines = s("g"), dots = s("g");
  svg.append(areas, guides, axes, lines, dots);

  for (const a of v.areas) {
    areas.append(s("polygon", { points: a.points.map(([x, y]) => `${X(x)},${Y(y)}`).join(" "), class: `area t-${a.tone}` }));
    if (a.label) {
      const cx = a.points.reduce((sum, p) => sum + X(p[0]), 0) / a.points.length;
      const cy = a.points.reduce((sum, p) => sum + Y(p[1]), 0) / a.points.length;
      areas.append(s("text", { x: r1(cx), y: r1(cy + 4), class: "area-label", "text-anchor": "middle" }, a.label));
    }
  }

  const x0 = X(0), y0 = Y(0);
  axes.append(
    s("path", { d: `M${x0},${y0} V${mt - 10}`, class: "axis" }),
    s("path", { d: `M${x0},${y0} H${W - mr + 22}`, class: "axis" }),
    s("path", { d: `M${x0 - 4},${mt - 4} L${x0},${mt - 12} L${x0 + 4},${mt - 4}z`, class: "axis-head" }),
    s("path", { d: `M${W - mr + 18},${y0 - 4} L${W - mr + 26},${y0} L${W - mr + 18},${y0 + 4}z`, class: "axis-head" }),
    s("text", { x: x0 + 8, y: mt - 12, class: "axis-label" }, v.y_label),
    s("text", { x: W - 4, y: H - 6, class: "axis-label", "text-anchor": "end" }, v.x_label),
  );
  for (const t of v.x_ticks) {
    const x = X(t.at);
    axes.append(s("path", { d: `M${x},${y0} v5`, class: "tick" }),
      s("text", { x, y: y0 + 18, class: "tick-label", "text-anchor": "middle" }, t.label || fmt(t.at)));
  }
  for (const t of v.y_ticks) {
    const y = Y(t.at);
    axes.append(s("path", { d: `M${x0},${y} h-5`, class: "tick" }),
      s("text", { x: x0 - 8, y: y + 4, class: "tick-label", "text-anchor": "end" }, t.label || fmt(t.at)));
  }

  for (const l of v.lines) {
    const pts = l.points.map(([x, y]) => [X(x), Y(y)]);
    const d = l.curve && pts.length > 2 ? smoothPath(pts) : `M${pts.map((p) => p.join(",")).join(" L")}`;
    lines.append(s("path", { d, class: `line t-${l.tone}${l.bold ? " bold" : ""}${l.dashed ? " dashed" : ""}` }));
    if (!l.label) continue;
    if (l.label_at === "mid" || l.label_at === "below") {
      const [a, b] = [pts[0], pts[pts.length - 1]];
      const dy = l.label_at === "mid" ? -9 : 20;
      lines.append(s("text", { x: r1((a[0] + b[0]) / 2), y: r1((a[1] + b[1]) / 2 + dy), class: `line-label t-${l.tone}`,
        "text-anchor": "middle" }, l.label));
    } else {
      const [px, py] = pts[pts.length - 1];
      lines.append(s("text", { x: px + 7, y: py + 5, class: `line-label t-${l.tone}` }, l.label));
    }
  }

  for (const d of v.dots) {
    const x = X(d.x), y = Y(d.y);
    if (d.guides) guides.append(s("path", { d: `M${x0},${y} H${x} V${y0}`, class: "guide" }));
    dots.append(s("circle", { cx: x, cy: y, r: 4.5, class: "dot" }));
    if (d.label) dots.append(s("text", { x: x + 8, y: d.label_at === "below" ? y + 18 : y - 8, class: "dot-label" }, d.label));
  }
  return svg;
}

// ------------------------------------------------------------- normal curve

function normal(v) {
  const W = 440, H = 220, ml = 16, mr = 16, mt = 26, mb = 50, Z = 3.5;
  const pdf = (z) => Math.exp((-z * z) / 2) / Math.sqrt(2 * Math.PI);
  const X = (z) => r1(ml + ((z + Z) / (2 * Z)) * (W - ml - mr));
  const Y = (p) => r1(H - mb - (p / pdf(0)) * (H - mt - mb));
  const along = (a, b) => {
    const n = Math.max(2, Math.ceil((b - a) / 0.05));
    return Array.from({ length: n + 1 }, (_, i) => a + ((b - a) * i) / n).map((z) => `${X(z)},${Y(pdf(z))}`);
  };
  const svg = svgBox(W, H, v.title || "Normal curve");
  const base = Y(0);
  const labels = s("g");

  for (const sh of v.shades) {
    const a = Math.max(-Z, sh.from_z ?? -Z), b = Math.min(Z, sh.to_z ?? Z);
    if (a >= b) continue;
    svg.append(s("polygon", { points: [`${X(a)},${base}`, ...along(a, b), `${X(b)},${base}`].join(" "), class: `area t-${sh.tone}` }));
    if (sh.label) {
      const c = (a + b) / 2;
      const inside = base - Y(pdf(c)) > 46;
      labels.append(s("text", { x: X(c), y: inside ? r1((base + Y(pdf(c))) / 2 + 4) : Y(pdf(c)) - 10,
        class: "area-label", "text-anchor": "middle" }, sh.label));
    }
  }
  svg.append(s("polyline", { points: along(-Z, Z).join(" "), class: "curve" }),
    s("path", { d: `M${ml},${base} H${W - mr}`, class: "axis" }));

  const rows = [];
  [...v.marks].sort((m1, m2) => m1.z - m2.z).forEach((m) => {
    const x = X(m.z);
    svg.append(s("path", { d: `M${x},${base} V${Y(pdf(m.z))}`, class: "mark" }));
    const width = textWidth(m.label, 12);
    let row = rows.findIndex((right) => x - width / 2 > right + 6);
    if (row < 0) { rows.push(-Infinity); row = rows.length - 1; }
    rows[row] = x + width / 2;
    labels.append(s("text", { x, y: base + 18 + row * 16, class: "mark-label", "text-anchor": "middle" }, m.label));
  });
  svg.append(labels);
  return svg;
}

// ------------------------------------------------------------- trees

function layoutTree(nodes) {
  const byId = new Map(nodes.map((n) => [n.id, { ...n, kids: [] }]));
  let root = null;
  for (const n of byId.values()) {
    if (n.parent == null) root = n;
    else byId.get(n.parent).kids.push(n);
  }
  let slot = 0, depth = 0;
  (function place(n, d) {
    n.depth = d;
    depth = Math.max(depth, d);
    if (!n.kids.length) { n.slot = slot++; return; }
    n.kids.forEach((k) => place(k, d + 1));
    n.slot = (n.kids[0].slot + n.kids[n.kids.length - 1].slot) / 2;
  })(root, 0);
  return { all: [...byId.values()], byId, leaves: slot, depth };
}

function wrapWords(text, maxChars) {
  const out = [];
  let line = "";
  for (const word of String(text).split(/\s+/)) {
    if (line && (line + " " + word).length > maxChars) { out.push(line); line = word; }
    else line = line ? `${line} ${word}` : word;
  }
  if (line) out.push(line);
  return out;
}

function multiline(x, y, lines, attrs, lineHeight = 15) {
  const top = y - ((lines.length - 1) * lineHeight) / 2;
  return s("text", { x, y: top, ...attrs }, ...lines.map((t, i) => s("tspan", { x, dy: i ? lineHeight : 0 }, t)));
}

function treeRight(v, t) {
  const colW = 136, rowH = 46, pad = 18, mt = 26;
  const leafText = (n) => [n.label, n.value].filter(Boolean).join("   ");
  const longest = Math.max(80, ...t.all.filter((n) => !n.kids.length).map((n) => textWidth(leafText(n), 13)));
  const W = Math.ceil(pad * 2 + t.depth * colW + 18 + longest);
  const H = mt + t.leaves * rowH + 10;
  const pos = (n) => [pad + 12 + n.depth * colW, mt + n.slot * rowH + rowH / 2];
  const svg = svgBox(W, H, v.title || "Tree diagram");
  svg.style.minWidth = `${Math.round(W * 0.8)}px`;
  const edges = s("g"), nodes = s("g");
  svg.append(edges, nodes);

  for (const n of t.all) {
    const [x, y] = pos(n);
    if (n.parent != null) {
      const [px, py] = pos(t.byId.get(n.parent));
      const ax = px + 11, bx = x - 11;
      edges.append(s("path", { d: `M${ax},${py} L${bx},${y}`, class: "edge" }));
      if (n.edge) {
        const mx = ax + (bx - ax) * 0.5, my = py + (y - py) * 0.5;
        edges.append(s("text", { x: r1(mx), y: r1(my - 7), class: "edge-label", "text-anchor": "middle" }, n.edge));
      }
      if (n.cut) {
        const cx = ax + (bx - ax) * 0.25, cy = py + (y - py) * 0.25;
        edges.append(s("path", { d: `M${r1(cx - 3)},${r1(cy - 8)} v16 M${r1(cx + 3)},${r1(cy - 8)} v16`, class: "cut" }));
      }
    }
    if (n.shape === "decision") nodes.append(s("rect", { x: x - 10, y: y - 10, width: 20, height: 20, class: "node decision" }));
    else if (n.shape === "chance") nodes.append(s("circle", { cx: x, cy: y, r: 10, class: "node chance" }));
    else if (n.shape === "end" || !n.kids.length) nodes.append(s("path", { d: `M${x - 6},${y} L${x + 4},${y - 6} L${x + 4},${y + 6}z`, class: "node end" }));
    else nodes.append(s("circle", { cx: x, cy: y, r: 7, class: "node" }));

    if (!n.kids.length) {
      nodes.append(s("text", { x: x + 12, y: y + 5, class: "leaf-label" },
        n.label ? n.label : "", n.value ? s("tspan", { class: "node-value", dx: n.label ? 10 : 0 }, n.value) : ""));
    } else {
      if (n.value) nodes.append(s("text", { x, y: y - 17, class: "node-value", "text-anchor": "middle" }, n.value));
      if (n.label) nodes.append(s("text", { x, y: y + 27, class: "edge-label", "text-anchor": "middle" }, n.label));
    }
  }
  return svg;
}

function treeDown(v, t) {
  const boxW = 128, colW = 146, rowH = 96, pad = 12, mt = 12, chars = 17, lh = 15;
  const W = Math.max(boxW + pad * 2, pad * 2 + t.leaves * colW);
  const H = mt + (t.depth + 1) * rowH;
  const pos = (n) => [pad + n.slot * colW + colW / 2, mt + n.depth * rowH + 30];
  const svg = svgBox(W, H, v.title || "Tree diagram");
  svg.style.minWidth = `${Math.round(W * 0.8)}px`;
  const edges = s("g"), nodes = s("g");
  svg.append(edges, nodes);
  const boxH = (n) => Math.max(1, Math.min(3, wrapWords(n.label, chars).length)) * lh + 14 + (n.value ? lh : 0);

  for (const n of t.all) {
    const [x, y] = pos(n);
    if (n.parent != null) {
      const p = t.byId.get(n.parent);
      const [px, py] = pos(p);
      const top = y - boxH(n) / 2, bottom = py + boxH(p) / 2, mid = r1((bottom + top) / 2);
      edges.append(s("path", { d: `M${px},${bottom} V${mid} H${x} V${top}`, class: n.cut ? "edge cut" : "edge" }));
      if (n.edge) edges.append(s("text", { x: x + 4, y: mid - 5, class: "edge-label" }, n.edge));
    }
    const lines = wrapWords(n.label, chars).slice(0, 3);
    const h = boxH(n);
    nodes.append(s("rect", { x: x - boxW / 2, y: r1(y - h / 2), width: boxW, height: r1(h), rx: 9,
      class: n.depth === 0 ? "box root" : "box" }));
    nodes.append(multiline(x, n.value ? y - lh / 2 + 4 : y + 4, lines, { class: "box-label", "text-anchor": "middle" }, lh));
    if (n.value) nodes.append(s("text", { x, y: r1(y + (lines.length * lh) / 2 + 6), class: "node-value", "text-anchor": "middle" }, n.value));
  }
  return svg;
}

function tree(v) {
  const t = layoutTree(v.nodes);
  const wrap = el("div", { class: "viz-scroll" });
  wrap.append(v.direction === "down" ? treeDown(v, t) : treeRight(v, t));
  return wrap;
}

// ------------------------------------------------------------- flow, compare, matrix (HTML)

function flow(v) {
  const box = el("div", { class: "viz-flow", role: "list" });
  v.steps.forEach((st, i) => {
    if (i) box.append(el("div", { class: "flow-arrow", "aria-hidden": "true" }, icon("arrow")));
    box.append(el("div", { class: "flow-step", role: "listitem" },
      el("span", { class: "flow-n" }, `Step ${i + 1}`), el("b", {}, st.label),
      st.note ? el("span", { class: "note" }, st.note) : null));
  });
  if (v.cycle) box.append(el("div", { class: "flow-back" }, icon("back"), "Then back to step 1, and round again"));
  return box;
}

function compare(v) {
  const box = el("div", { class: "viz-compare" });
  box.style.setProperty("--n", String(v.sides.length));
  for (const side of v.sides) {
    box.append(el("div", { class: `cmp-side t-${side.tone}` }, el("h4", {}, side.title),
      el("ul", {}, ...side.points.map((p) => el("li", {}, p)))));
  }
  return box;
}

function matrix(v) {
  const hi = new Set(v.highlight.map(([r, c]) => `${r}:${c}`));
  const head = [];
  if (v.col_title) head.push(el("tr", {}, el("th", { class: "corner" }), el("th", { colspan: String(v.cols.length) }, v.col_title)));
  head.push(el("tr", {}, el("th", { class: "corner" }, v.row_title || ""), ...v.cols.map((c) => el("th", { scope: "col" }, c))));
  const body = v.rows.map((row, r) => el("tr", {}, el("th", { scope: "row" }, row),
    ...v.cells[r].map((cell, c) => el("td", { class: hi.has(`${r}:${c}`) ? "hi" : "" }, cell))));
  return el("div", { class: "table-wrap" }, el("table", { class: "viz-matrix" }, el("thead", {}, head), el("tbody", {}, body)));
}

const RENDERERS = { plot, normal, tree, flow, compare, matrix };

/** One picture as a <figure>: title, the drawing, the caption, and the slide it redraws. */
export function renderVisual(v, { onOpenRef } = {}) {
  const fig = el("figure", { class: `viz is-${v.kind}` });
  if (v.title) fig.append(el("div", { class: "viz-title" }, v.title));
  const make = RENDERERS[v.kind];
  try {
    if (!make) throw new Error(`unknown picture kind ${v.kind}`);
    fig.append(make(v));
  } catch (err) {
    console.error(err);
    fig.append(el("div", { class: "small faint" }, "This picture could not be drawn."));
  }
  if (v.caption) fig.append(el("figcaption", {}, v.caption));
  if (v.source_ref && onOpenRef) {
    const n = String(v.source_ref).split("#")[1];
    fig.append(el("div", {}, el("button", { class: "ref-chip", title: `Open ${refLabel(v.source_ref)}`, onclick: () => onOpenRef(v.source_ref) },
      icon("slide"), `Redrawn from slide ${n}`)));
  }
  return fig;
}
