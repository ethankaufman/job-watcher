import { loadData } from "./data.mjs";
import { newPerDay, removedPerDay, openPerEmployer, daysOpen, removedWithinSeven, topLocations, inRole, openRows, lastRunDay, firstDay, calendar } from "./stats.mjs";
import { el, startPage, render, showError, offlineNotice, count, percent, formatDay, formatShortDay } from "./ui.mjs";
import { lineChart, barChart, columnChart, tableView, SERIES_COLORS } from "./charts.mjs";

startPage();
const app = document.getElementById("app");

const ALL = SERIES_COLORS[0], ROLE = SERIES_COLORS[1];
const plural = (n, word) => `${count(n)} ${word}${n === 1 ? "" : "s"}`;
const days = (n) => `${Number.isInteger(n) ? n : Number(n.toFixed(1))} day${n === 1 ? "" : "s"}`;
const sum = (list) => list.reduce((a, b) => a + b, 0);
const waiting = (text) => el("div", { class: "empty" }, text);
const chartIn = (draw) => { const host = el("div"); draw(host); return host; };

// A section: a heading that states the finding, a paragraph, a chart, how it is computed, and the table behind the chart.
function section(id, heading, paragraphs, how, chart, table) {
  return el("section", { class: "card finding", "aria-labelledby": id },
    el("h2", { id }, heading), paragraphs.map((p) => el("p", {}, p)), chart,
    el("p", { class: "how small" }, el("strong", {}, "How it is computed: "), how), table);
}

function sections(rows) {
  const out = [];
  const last = lastRunDay(rows);
  const role = inRole(rows);

  // 1. New postings per day
  const created = newPerDay(rows);
  const li = created.days.length - 1;
  const totalNew = sum(created.all), totalNewRole = sum(created.role);
  const busiest = created.all.indexOf(Math.max(...created.all));
  out.push(section("s-new",
    totalNew === 0 ? "No new postings to count yet: every posting was already open when watching began"
      : `${plural(created.all[li], "new posting")} appeared on ${formatDay(created.days[li])}, ${count(created.role[li])} in my role`,
    [totalNew === 0
      ? "Postings that were already open on the first day have an unknown start date, so they are not counted as new. This fills in from the second day."
      : `Since watching began, ${plural(totalNew, "posting")} have appeared, ${count(totalNewRole)} of them in my role. The busiest day was ${formatDay(created.days[busiest])}, with ${count(created.all[busiest])} new postings.`],
    "Count the postings whose first-seen date is each day, leaving out first-run postings (the ones already open when the tool started watching their employer). The second line counts only the postings in my role.",
    chartIn((host) => lineChart(host, { days: created.days, series: [{ id: "all", label: "All postings", color: ALL, values: created.all }, { id: "role", label: "In my role", color: ROLE, values: created.role }], format: count, dayLabel: formatShortDay, height: 260, name: "New postings per day" })),
    tableView(["Day", "All postings", "In my role"], created.days.map((d, i) => [formatShortDay(d), count(created.all[i]), count(created.role[i])]))));

  // 2. Removed postings per day
  const gone = removedPerDay(rows);
  const totalGone = sum(gone.all);
  out.push(section("s-removed",
    totalGone === 0 ? "No postings have been removed yet"
      : `${plural(gone.all[li], "posting")} ${gone.all[li] === 1 ? "was" : "were"} removed on ${formatDay(gone.days[li])}, ${count(gone.role[li])} in my role`,
    [totalGone === 0
      ? "A posting is removed when its employer's board no longer lists it (filled, closed or taken down). Removals appear from the second day."
      : `Since watching began, ${plural(totalGone, "posting")} ${totalGone === 1 ? "has" : "have"} been removed, ${count(sum(gone.role))} of them in my role. A posting that comes back is open again and no longer counts as removed.`],
    "Count the postings with each removed date. The second line counts only the postings in my role. A day on which an employer's board could not be read removes nothing for that employer.",
    chartIn((host) => lineChart(host, { days: gone.days, series: [{ id: "all", label: "All postings", color: ALL, values: gone.all }, { id: "role", label: "In my role", color: ROLE, values: gone.role }], format: count, dayLabel: formatShortDay, height: 260, name: "Removed postings per day" })),
    tableView(["Day", "All postings", "In my role"], gone.days.map((d, i) => [formatShortDay(d), count(gone.all[i]), count(gone.role[i])]))));

  // 3. Open postings per employer
  const perEmployer = openPerEmployer(rows);
  const open = sum(perEmployer.map((e) => e.open));
  const mostRole = [...perEmployer].sort((a, b) => b.role - a.role || (a.employer < b.employer ? -1 : 1))[0];
  out.push(section("s-employers",
    `${perEmployer[0].employer} has the most open postings: ${count(perEmployer[0].open)} of ${count(open)}`,
    [`${perEmployer.length} employers have open postings as of ${formatDay(last)}. ${perEmployer[0].employer} alone holds ${percent(perEmployer[0].open / open)} of them. The most postings in my role are at ${mostRole.employer}: ${count(mostRole.role)}, out of ${count(sum(perEmployer.map((e) => e.role)))} in my role across all employers.`],
    "Count the postings with status open for each employer, as of the last run. The table also counts the ones in my role.",
    chartIn((host) => barChart(host, { rows: perEmployer.map((e) => ({ label: e.employer, value: e.open, color: ALL, detail: `${count(e.role)} in my role` })), format: count, name: "Open postings per employer" })),
    tableView(["Employer", "Open postings", "In my role"], perEmployer.map((e) => [e.employer, count(e.open), count(e.role)]))));

  // 4. Days open
  const open4 = daysOpen(rows), open4Role = daysOpen(role);
  out.push(section("s-days",
    open4.count === 0 ? "No postings have closed yet, so there is no time open to measure"
      : `Postings that closed were open a median of ${days(open4.median)}`,
    [open4.count === 0
      ? "This measures postings that were first seen after watching began and have since been removed. It fills in once postings start closing."
      : `Of the ${plural(open4.count, "closed posting")} that were first seen after watching began, half were removed within ${days(open4.median)}.${open4Role.count ? ` For postings in my role (${count(open4Role.count)} closed), the median is ${days(open4Role.median)}.` : ""} Only postings that have already closed are counted, so very long-lasting ones are not in this number yet.`],
    "For each removed posting that is not a first-run posting, subtract its first-seen date from its removed date. The median is the middle value of those numbers (the average of the two middle values when there is an even number).",
    open4.count === 0 ? waiting("Waiting for the first closed postings.")
      : chartIn((host) => columnChart(host, { rows: open4.bins.map((b) => ({ label: `${b.label} days open`, axis: b.label, value: b.count, color: ALL, detail: "postings" })), format: count, height: 240, name: "Days open for removed postings" })),
    open4.count === 0 ? null : tableView(["Days open", "Removed postings"], open4.bins.map((b) => [b.label, count(b.count)]))));

  // 5. Share removed within seven days
  const fast = removedWithinSeven(rows), fastRole = removedWithinSeven(role);
  const employerRows = fast.employers.filter((e) => e.cohort >= 5);
  out.push(section("s-seven",
    fast.cohort === 0 ? "It is too early to say how many postings are removed within a week"
      : `${percent(fast.share)} of postings were removed within seven days`,
    [fast.cohort === 0
      ? "This needs postings first seen at least seven days before the last run, which needs more than a week of history. It fills in from the ninth day."
      : `Of the ${count(fast.cohort)} postings that were first seen at least seven days before ${formatDay(fast.last)} (leaving out first-run postings), ${count(fast.removed)} were removed within seven days of being first seen.${fastRole.cohort ? ` For postings in my role, it is ${percent(fastRole.share)} (${count(fastRole.removed)} of ${count(fastRole.cohort)}).` : ""}`],
    "Take the postings that are not first-run and were first seen at least seven days before the last run. The share is how many of them have a removed date seven days or fewer after their first-seen date. The chart shows employers with at least 5 postings in that group.",
    fast.cohort === 0 ? waiting("Waiting for more than a week of history.")
      : chartIn((host) => barChart(host, { rows: employerRows.map((e) => ({ label: e.employer, value: e.share, color: ALL, detail: `${count(e.removed)} of ${count(e.cohort)} removed within 7 days` })), format: percent, name: "Share removed within seven days, by employer" })),
    fast.cohort === 0 ? null : tableView(["Employer", "Postings counted", "Removed within 7 days", "Share"], fast.employers.map((e) => [e.employer, count(e.cohort), count(e.removed), percent(e.share)]))));

  // 6. Top locations
  const where = topLocations(rows);
  const named = where.topNamed[0];
  out.push(section("s-locations",
    `${count(where.several)} of ${count(open)} open postings list several locations; the top single place is ${named?.location ?? "unknown"}`,
    [`As of ${formatDay(last)}, the most common location text is "${where.top[0].location}" (${count(where.top[0].count)} postings)${named && where.top[0].location !== named.location ? `, followed by ${named.location} (${count(named.count)})` : ""}. Locations are counted exactly as each employer writes them, so "New York, NY" and "New York, NY, United States" are separate entries. "Multiple locations" is a posting that lists several offices. ${where.withoutLocation === 1 ? "1 posting has" : `${count(where.withoutLocation)} postings have`} no location and ${where.withoutLocation === 1 ? "is" : "are"} left out.`],
    "Count the open postings by their location text, exactly as in the history file, and show the 10 most common. Postings with an empty location are not counted.",
    chartIn((host) => barChart(host, { rows: where.top.map((l) => ({ label: l.location, value: l.count, color: ALL })), format: count, name: "Top locations among open postings" })),
    tableView(["Location", "Open postings"], where.top.map((l) => [l.location, count(l.count)]))));

  return out;
}

try {
  const { rows } = await loadData();
  const all = calendar(rows);
  render(app, offlineNotice(),
    el("div", { class: "notice", role: "status" }, `Built from ${count(rows.length)} postings seen over ${all.length} day${all.length === 1 ? "" : "s"} (${formatDay(firstDay(rows))} to ${formatDay(lastRunDay(rows))}). ${count(openRows(rows).length)} are open now.`),
    sections(rows));
} catch (error) {
  showError(app, error);
}
