import { loadData } from "./data.mjs";
import { newInRun, removedInRun } from "./stats.mjs";
import { el, startPage, render, showError, offlineNotice, count, formatDay, formatRunTime, roleBadge } from "./ui.mjs";

startPage();
const app = document.getElementById("app");

const SYSTEMS = { greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", workday: "Workday", oracle: "Oracle Recruiting", smartrecruiters: "SmartRecruiters" };
const SHOWN = 100; // how many postings a list shows before "Show all"

function statCard(label, value, note) {
  return el("div", { class: "stat" }, el("div", { class: "label" }, label), el("div", { class: "value" }, value), note ? el("div", { class: "note" }, note) : null);
}

function sourcesCard(status) {
  const ok = status.sources.filter((s) => s.ok).length;
  return el("div", { class: "card" },
    el("h2", {}, "Sources"),
    el("p", { class: "muted small" }, `${ok} of ${status.sources.length} employers were read successfully in the last run. If one fails, the others still update and nothing is marked removed because of it.`),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Employer", "Job board system", "Status", "Postings", "Details"].map((h, i) => el("th", { class: i === 3 ? "num" : null, scope: "col" }, h)))),
      el("tbody", {}, status.sources.map((s) => el("tr", {},
        el("td", {}, s.employer ?? s.name),
        el("td", { class: "muted" }, SYSTEMS[s.ats] ?? s.ats ?? ""),
        el("td", {}, s.ok ? el("span", { class: "badge ok" }, "✓ OK") : el("span", { class: "badge fail" }, "✕ Failed")),
        el("td", { class: "num" }, count(s.count)),
        el("td", { class: "muted" }, s.error ?? ""))))))
  );
}

// A list of postings with a "my role only" switch and a "show all" button for long lists.
function postingList(id, heading, intro, postings, empty, removed) {
  const state = { onlyRole: false, all: false };
  const list = el("ul", { class: "postings" });
  const summary = el("p", { class: "muted small", role: "status" });
  const more = el("button", { class: "plain", type: "button", onclick: () => { state.all = true; draw(); } });
  const check = el("input", { type: "checkbox", onchange: (e) => { state.onlyRole = e.target.checked; state.all = false; draw(); } });
  const ordered = [...postings].sort((a, b) => Number(b.in_role) - Number(a.in_role) || a.employer.localeCompare(b.employer) || a.title.localeCompare(b.title));

  function draw() {
    const shown = ordered.filter((r) => !state.onlyRole || r.in_role);
    const visible = state.all ? shown : shown.slice(0, SHOWN);
    list.replaceChildren(...visible.map((r) => el("li", {},
      el("span", { class: "what" }, el("a", { href: r.url, target: "_blank", rel: "noopener noreferrer" }, r.title), " ", r.in_role ? roleBadge() : null),
      el("span", { class: "meta" }, [r.employer, r.location].filter(Boolean).join(" · ")))));
    summary.textContent = shown.length ? `Showing ${visible.length} of ${shown.length}${state.onlyRole ? " in my role" : ""}.` : "";
    more.textContent = `Show all ${count(shown.length)}`;
    more.hidden = state.all || shown.length <= SHOWN;
    if (!shown.length) list.append(el("li", { class: "muted" }, state.onlyRole && postings.length ? "None of them are in my role." : empty));
  }
  draw();
  return el("section", { class: "card", "aria-labelledby": id },
    el("h2", { id }, `${heading} (${count(postings.length)})`),
    el("p", { class: "muted small" }, intro),
    el("label", { class: "check" }, check, "Only postings in my role (★)"),
    summary, list, more, removed ? el("p", { class: "muted small" }, "A link to a removed posting may no longer work.") : null);
}

try {
  const { status, rows } = await loadData();
  const runDay = status.run_time.slice(0, 10);
  const added = newInRun(rows, runDay);
  const gone = removedInRun(rows, runDay);
  render(app,
    offlineNotice(),
    el("div", { class: "notice", role: "status" }, el("strong", {}, "Last run: "), formatRunTime(status.run_time)),
    el("div", { class: "stats" },
      statCard("Days with a successful run", count(status.days_with_success), `since ${formatDay(status.first_run_date)}`),
      statCard("Open postings", count(status.open), "listed on the boards right now"),
      statCard("New today", count(status.new_today), "first seen in the last run"),
      statCard("Removed today", count(status.removed_today), "no longer listed")),
    sourcesCard(status),
    postingList("new-postings", "New postings in the latest run",
      "First seen in the latest run. Postings that were already open when watching began are not counted as new, so there are none on the first day.",
      added, "No new postings in the latest run.", false),
    postingList("removed-postings", "Removed postings in the latest run",
      "Listed the day before but not in the latest run: filled, closed, or taken down.",
      gone, "No postings were removed in the latest run.", true));
} catch (error) {
  showError(app, error);
}
