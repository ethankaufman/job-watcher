import { loadData } from "./data.mjs";
import { lastRunDay, daysOpenSoFar, daysBetween, inRole, topLocations } from "./stats.mjs";
import { el, startPage, render, showError, offlineNotice, count, formatDay, formatShortDay, applyLink, roleBadge, getShortlist, toggleShortlist } from "./ui.mjs";

startPage();
const app = document.getElementById("app");
const PAGE = 100; // postings shown at a time

const state = { view: "role", employer: "", location: "", minDays: "", maxDays: "", search: "", shortlistOnly: false, sort: { key: "first_seen", dir: "desc" }, shown: PAGE };

function compare(a, b, { key, dir }) {
  const x = a[key], y = b[key];
  const result = typeof x === "number" ? x - y : String(x).localeCompare(String(y));
  return dir === "asc" ? result : -result;
}

function build(rows) {
  const last = lastRunDay(rows);
  const everything = rows.map((r) => ({ ...r, days_open: r.status === "open" ? daysOpenSoFar(r, last) : r.removed_date ? daysBetween(r.first_seen, r.removed_date) : 0 }));
  const open = everything.filter((r) => r.status === "open");
  const employers = [...new Set(open.map((r) => r.employer))].sort((a, b) => a.localeCompare(b));
  let shortlist = getShortlist();

  const summary = el("p", { class: "muted", role: "status" });
  const head = el("tr");
  const body = el("tbody");
  const moreButton = el("button", { class: "plain", type: "button", onclick: () => { state.shown += PAGE; draw(); } });

  // ----- controls -----
  const viewButtons = [["role", `In my role (${count(inRole(open).length)})`], ["all", `All postings (${count(open.length)})`]].map(([view, label]) =>
    el("button", { type: "button", "data-view": view, onclick: () => { state.view = view; state.shown = PAGE; draw(); } }, label));
  const switcher = el("div", { class: "segmented", role: "group", "aria-label": "Which postings to show" }, viewButtons);
  const field = (label, input) => el("label", { class: "control" }, label, input);
  const reset = (fn) => (e) => { fn(e); state.shown = PAGE; draw(); };
  const employerSelect = el("select", { onchange: reset((e) => (state.employer = e.target.value)) }, el("option", { value: "" }, "All employers"), employers.map((n) => el("option", { value: n }, n)));
  const locationList = el("datalist", { id: "locations" }, topLocations(open, 60).top.filter((l) => l.location !== "Multiple locations").map((l) => el("option", { value: l.location })));
  const locationInput = el("input", { type: "search", list: "locations", placeholder: "e.g. New York", autocomplete: "off", oninput: reset((e) => (state.location = e.target.value)) });
  const minDays = el("input", { type: "number", min: "0", step: "1", placeholder: "0", oninput: reset((e) => (state.minDays = e.target.value)) });
  const maxDays = el("input", { type: "number", min: "0", step: "1", placeholder: "any", oninput: reset((e) => (state.maxDays = e.target.value)) });
  const search = el("input", { type: "search", placeholder: "e.g. financial analyst", autocomplete: "off", oninput: reset((e) => (state.search = e.target.value)) });
  const starred = el("input", { type: "checkbox", onchange: reset((e) => (state.shortlistOnly = e.target.checked)) });
  const clear = el("button", { class: "plain", type: "button", onclick: () => {
    Object.assign(state, { employer: "", location: "", minDays: "", maxDays: "", search: "", shortlistOnly: false, shown: PAGE });
    employerSelect.value = ""; locationInput.value = ""; minDays.value = ""; maxDays.value = ""; search.value = ""; starred.checked = false; draw();
  } }, "Clear filters");

  const controls = el("div", { class: "card" },
    el("div", { class: "controls" }, switcher),
    el("div", { class: "controls" },
      field("Search titles", search), field("Employer", employerSelect), field("Location contains", locationInput),
      field("Days open, at least", minDays), field("Days open, at most", maxDays)),
    datalistHolder(locationList),
    el("div", { class: "controls" }, el("label", { class: "check" }, starred, "★ Shortlist only"), clear),
    summary);
  function datalistHolder(list) { return el("div", { hidden: true }, list); }

  // ----- table head: every column sorts up and down -----
  const COLS = [["title", "Title", false], ["employer", "Employer", false], ["location", "Location", false], ["first_seen", "First seen", false], ["days_open", "Days open", true]];
  head.append(el("th", { scope: "col" }, el("span", { class: "visually-hidden" }, "Shortlist")));
  for (const [key, label, numeric] of COLS) {
    const th = el("th", { class: numeric ? "num" : null, scope: "col", "data-key": key });
    th.append(el("button", { type: "button", onclick: () => {
      state.sort = state.sort.key === key ? { key, dir: state.sort.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "first_seen" || numeric ? "desc" : "asc" };
      draw();
    } }, label, el("span", { "aria-hidden": "true", "data-arrow": "" })));
    head.append(th);
  }
  head.append(el("th", { scope: "col" }, el("span", { class: "visually-hidden" }, "Apply")));

  function visible() {
    const search_ = state.search.trim().toLowerCase();
    const where = state.location.trim().toLowerCase();
    const min = state.minDays === "" ? null : Number(state.minDays);
    const max = state.maxDays === "" ? null : Number(state.maxDays);
    // The shortlist view also shows starred postings that have since been removed.
    const pool = state.shortlistOnly ? everything.filter((r) => shortlist.has(r.posting_id)) : open;
    return pool
      .filter((r) => state.shortlistOnly || state.view === "all" || r.in_role)
      .filter((r) => !state.employer || r.employer === state.employer)
      .filter((r) => !where || r.location.toLowerCase().includes(where))
      .filter((r) => !search_ || r.title.toLowerCase().includes(search_))
      .filter((r) => min == null || r.days_open >= min)
      .filter((r) => max == null || r.days_open <= max)
      .sort((a, b) => compare(a, b, state.sort) || (a.posting_id < b.posting_id ? -1 : 1));
  }

  function draw() {
    shortlist = getShortlist();
    for (const b of viewButtons) b.setAttribute("aria-pressed", String(b.dataset.view === state.view));
    for (const th of head.querySelectorAll("th[data-key]")) {
      const active = th.dataset.key === state.sort.key;
      th.setAttribute("aria-sort", active ? (state.sort.dir === "asc" ? "ascending" : "descending") : "none");
      th.querySelector("[data-arrow]").textContent = active ? (state.sort.dir === "asc" ? " ▲" : " ▼") : "";
    }
    const list = visible();
    const shownRows = list.slice(0, state.shown);
    summary.textContent = `Showing ${count(shownRows.length)} of ${count(list.length)} ${state.shortlistOnly ? "starred postings" : state.view === "role" ? "open postings in my role" : "open postings"} · as of ${formatDay(last)} · ${shortlist.size} starred`;
    body.replaceChildren(...shownRows.map((r) => {
      const on = shortlist.has(r.posting_id);
      const label = `${r.title} at ${r.employer}`;
      return el("tr", {},
        el("td", {}, el("button", { class: "star", type: "button", "aria-pressed": String(on), "aria-label": `${on ? "Remove" : "Add"} ${label} ${on ? "from" : "to"} shortlist`, title: on ? "Remove from shortlist" : "Add to shortlist",
          onclick: () => { toggleShortlist(r.posting_id); draw(); } }, on ? "★" : "☆")),
        el("td", { class: "title-cell" }, r.status === "open" ? el("a", { href: r.url, target: "_blank", rel: "noopener noreferrer" }, r.title) : r.title, " ", r.in_role ? roleBadge() : null, r.status === "removed" ? el("span", { class: "badge fail" }, "Removed") : null),
        el("td", {}, r.employer),
        el("td", { class: "muted wrap" }, r.location || "–"),
        el("td", {}, formatShortDay(r.first_seen), r.first_run ? el("abbr", { title: "Already open when watching began, so the real start date is unknown" }, " *") : null),
        el("td", { class: "num" }, r.days_open),
        el("td", {}, r.status === "open" ? applyLink(r) : el("span", { class: "muted" }, "closed")));
    }));
    if (!list.length) body.append(el("tr", {}, el("td", { colspan: 7, class: "muted" }, state.shortlistOnly ? "Nothing starred yet. Star a posting with the ☆ button." : "No postings match these filters.")));
    moreButton.textContent = `Show ${Math.min(PAGE, list.length - shownRows.length)} more`;
    moreButton.hidden = shownRows.length >= list.length;
  }

  draw();
  return [controls,
    el("div", { class: "card" }, el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), body)), el("p", {}, moreButton),
      el("p", { class: "muted small" }, "* Already open when watching began, so the real start is unknown; its days open count from the first day we saw it. Days open = days from first seen to the last run. A location of \"Multiple locations\" means the employer lists several offices.")),
  ];
}

try {
  const { rows } = await loadData();
  render(app, offlineNotice(), build(rows));
} catch (error) {
  showError(app, error);
}
