// Things every page uses: the navigation bar, formats, the shortlist, installing.

// Build an element. Text always goes in as text (never as HTML), so data can't inject markup.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Put nodes in a page area, skipping empty ones (replaceChildren would print "null").
export function render(host, ...nodes) {
  host.replaceChildren(...nodes.flat().filter(Boolean));
}

export const count = (n) => (n == null ? "–" : Number(n).toLocaleString("en-US"));
export const percent = (share) => (share == null ? "–" : `${(share * 100).toFixed(share > 0 && share < 0.1 ? 1 : 0)}%`);

export function formatDay(day) {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
export function formatShortDay(day) {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}
export function formatRunTime(iso) {
  const when = new Date(iso);
  const utc = when.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
  const local = when.toLocaleString("en-GB", { hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
  return `${utc} UTC (${local} for you)`;
}

// A link that opens the job posting in a new tab.
export const applyLink = (row, label = "Apply") =>
  el("a", { class: "apply", href: row.url, target: "_blank", rel: "noopener noreferrer", "aria-label": `${label}: ${row.title} at ${row.employer}` }, label);
export const roleBadge = () => el("span", { class: "badge role", title: "This title matches my role" }, "★ My role");

// ---------- the shortlist (stars), kept in this browser ----------
const SHORTLIST_KEY = "job-watcher-shortlist";
export function getShortlist() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SHORTLIST_KEY) ?? "[]"));
  } catch {
    return new Set();
  }
}
export function toggleShortlist(postingId) {
  const list = getShortlist();
  list.has(postingId) ? list.delete(postingId) : list.add(postingId);
  try {
    localStorage.setItem(SHORTLIST_KEY, JSON.stringify([...list]));
  } catch {
    /* storage blocked: the star just won't stick */
  }
  return list;
}

// ---------- the page frame ----------
const PAGES = [
  ["index.html", "Today", "today"],
  ["browse.html", "Browse", "browse"],
  ["market.html", "Market", "market"],
  ["guide.html", "Guide", "guide"],
];
export function startPage() {
  const current = document.body.dataset.page;
  const links = PAGES.map(([href, label, id]) => el("a", { href, "aria-current": id === current ? "page" : null }, label));
  const install = el("button", { class: "install", type: "button" }, "Install app");
  document.body.prepend(
    el("a", { class: "visually-hidden", href: "#main" }, "Skip to content"),
    el("header", { class: "nav" }, el("div", { class: "nav-inner" },
      el("a", { class: "brand", href: "index.html" }, "Finance Job Watcher"),
      el("nav", { class: "nav-links", "aria-label": "Pages" }, links),
      install)),
  );

  // "Install app": the browser tells us when the site can be installed.
  let prompt = null;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    prompt = event;
    install.style.display = "inline-block";
  });
  install.addEventListener("click", async () => {
    if (!prompt) return;
    prompt.prompt();
    await prompt.userChoice;
    prompt = null;
    install.style.display = "none";
  });
  window.addEventListener("appinstalled", () => (install.style.display = "none"));

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
}

export function showError(host, error) {
  host.replaceChildren(el("div", { class: "notice error", role: "alert" }, `Could not load the data (${error.message}). Check your connection and reload.`));
}
// Tell the visitor when the page is showing saved data.
export function offlineNotice() {
  return navigator.onLine === false
    ? el("div", { class: "notice", role: "status" }, "You are offline. Showing the last data this device loaded.")
    : null;
}
