// App shell: navigation rail, phone tab bar, hash router, theme, "What next?".

import { api } from "./api.js";
import { stopTracking } from "./components.js";
import { clear, el, errorBox, icon, toast } from "./ui.js";

const NAV = [
  { route: "today", label: "Today", icon: "today" },
  { route: "subjects", label: "Subjects", icon: "subjects" },
  { route: "review", label: "Review", icon: "review", badge: true },
  { route: "practice", label: "Practice", icon: "practice" },
  { route: "plan", label: "Plan", icon: "plan" },
  { route: "insights", label: "Insights", icon: "insights" },
  { route: "library", label: "Library", icon: "library" },
  { route: "sources", label: "Sources", icon: "sources" },
  { route: "settings", label: "Settings", icon: "settings" },
];
const TABS = ["today", "subjects", "review", "practice", "more"];
const PAGES = new Set(["today", "subjects", "subject", "learn", "review", "practice", "plan", "insights", "library", "sources", "settings", "more"]);

const main = document.getElementById("main");
let current = null;

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const page = parts[0] || "today";
  return { page: PAGES.has(page) ? page : "today", args: parts.slice(1), query: new URLSearchParams(query) };
}

export function go(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

function navActive(page) {
  const group = { subject: "subjects", learn: "subjects" }[page] || page;
  document.querySelectorAll("[data-route]").forEach((a) => a.classList.toggle("active", a.dataset.route === group ||
    (a.dataset.route === "more" && !TABS.includes(group))));
}

async function route() {
  const { page, args, query } = parseHash();
  stopTracking();
  if (current && current.cleanup) {
    try { current.cleanup(); } catch { /* page already gone */ }
  }
  current = null;
  navActive(page);
  clear(main);
  main.append(el("div", { class: "page" }, el("div", { class: "skeleton" })));
  window.scrollTo(0, 0);
  try {
    const mod = await import(`./pages/${page}.js`);
    clear(main);
    current = mod;
    await mod.render(main, { args, query, go });
    document.title = `${(mod.title && mod.title(args)) || page[0].toUpperCase() + page.slice(1)} · Athena`;
  } catch (err) {
    console.error(err);
    clear(main);
    main.append(el("div", { class: "page" }, errorBox(err, route)));
  }
  refreshBadge();
}

export async function refreshBadge() {
  try {
    const q = await api.get("/review?limit=1");
    document.querySelectorAll(".due-badge").forEach((b) => {
      b.textContent = q.due;
      b.style.display = q.due ? "" : "none";
    });
  } catch { /* offline: keep the old badge */ }
}

export async function whatNext() {
  try {
    const plan = await api.get("/plan/today");
    const task = plan.tasks.find((t) => t.status === "todo");
    if (!task) {
      toast("Today's plan is done. Nice work.");
      return go("#/practice");
    }
    if (task.kind === "review") return go("#/review");
    if (task.kind === "mock") return go(`#/practice?mode=mock&subject=${task.subject_id}`);
    if (task.topic_id) return go(`#/learn/${encodeURIComponent(task.topic_id)}`);
    if (task.subject_id) return go(`#/practice?subject=${task.subject_id}`);
    go("#/today");
  } catch (err) {
    toast(err.message);
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("athena-theme", theme); } catch { /* private mode */ }
  const btn = document.getElementById("theme-btn");
  if (btn) {
    clear(btn);
    btn.append(icon(theme === "dark" ? "sun" : "moon"), theme === "dark" ? "Light mode" : "Dark mode");
  }
}

function buildShell() {
  const rail = document.getElementById("rail");
  rail.append(
    el("a", { class: "brand", href: "#/today" }, el("span", { class: "brand-mark" }, "A"), el("span", { class: "brand-name" }, "Athena")),
    ...NAV.map((n) => el("a", { class: "nav-link", href: `#/${n.route}`, "data-route": n.route }, icon(n.icon), n.label,
      n.badge ? el("span", { class: "count due-badge", style: { display: "none" } }, "0") : null)),
    el("div", { class: "rail-foot" },
      el("button", { class: "btn primary block", onclick: whatNext, title: "Open the next task in today's plan (W)" }, icon("spark"), "What next?"),
      el("button", { class: "btn ghost block", id: "theme-btn", onclick: () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark") })),
  );
  const tabbar = document.getElementById("tabbar");
  const tabIcon = { today: "today", subjects: "subjects", review: "review", practice: "practice", more: "more" };
  const tabLabel = { today: "Today", subjects: "Subjects", review: "Review", practice: "Practice", more: "More" };
  TABS.forEach((t) => tabbar.append(el("a", { href: `#/${t}`, "data-route": t }, icon(tabIcon[t]), tabLabel[t])));
}

document.addEventListener("keydown", (e) => {
  const tag = (e.target && e.target.tagName) || "";
  if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "w" || e.key === "W") { e.preventDefault(); whatNext(); }
  if (current && current.onKey) current.onKey(e);
});

let theme = "dark";
try { theme = localStorage.getItem("athena-theme") || "dark"; } catch { /* default */ }
buildShell();
applyTheme(theme);
window.addEventListener("hashchange", route);
route();
