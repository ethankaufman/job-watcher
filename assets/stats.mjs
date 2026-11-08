// Every calculation the pages show. Pure functions of the history rows (no page code), so the
// numbers can be checked against the history file outside the browser.
//
// A "first-run" posting (first_run = true) was already open when the tool started watching its
// source, so its start date is unknown. The definitions below leave those out where noted.

const DAY_MS = 86400000;
const parseDay = (day) => Date.UTC(+day.slice(0, 4), +day.slice(5, 7) - 1, +day.slice(8, 10));
export const daysBetween = (from, to) => Math.round((parseDay(to) - parseDay(from)) / DAY_MS);
export const addDays = (day, n) => new Date(parseDay(day) + n * DAY_MS).toISOString().slice(0, 10);

export const inRole = (rows) => rows.filter((r) => r.in_role);
export const openRows = (rows) => rows.filter((r) => r.status === "open");

// The latest day in the history: the date of the last run that saved anything.
export function lastRunDay(rows) {
  let latest = "";
  for (const r of rows) for (const d of [r.first_seen, r.last_seen, r.removed_date]) if (d > latest) latest = d;
  return latest || null;
}
export function firstDay(rows) {
  let first = null;
  for (const r of rows) if (first === null || r.first_seen < first) first = r.first_seen;
  return first;
}
// Every calendar day from the first to the last day in the history (a day with no run counts as zero).
export function calendar(rows) {
  const first = firstDay(rows), last = lastRunDay(rows);
  if (!first) return [];
  const out = [];
  for (let d = first; d <= last; d = addDays(d, 1)) out.push(d);
  return out;
}

function countByDay(rows, days, dateOf, keep) {
  const counts = new Map(days.map((d) => [d, 0]));
  for (const r of rows) {
    const d = dateOf(r);
    if (d && counts.has(d) && keep(r)) counts.set(d, counts.get(d) + 1);
  }
  return days.map((d) => counts.get(d));
}

// 1. New postings per day: first seen that day, leaving out first-run postings. All, and in my role.
export function newPerDay(rows) {
  const days = calendar(rows);
  return {
    days,
    all: countByDay(rows, days, (r) => r.first_seen, (r) => !r.first_run),
    role: countByDay(rows, days, (r) => r.first_seen, (r) => !r.first_run && r.in_role),
  };
}

// 2. Removed postings per day: postings with that removed date. All, and in my role.
export function removedPerDay(rows) {
  const days = calendar(rows);
  return {
    days,
    all: countByDay(rows, days, (r) => r.removed_date, () => true),
    role: countByDay(rows, days, (r) => r.removed_date, (r) => r.in_role),
  };
}

// 3. Open postings per employer as of the last run.
export function openPerEmployer(rows) {
  const byEmployer = new Map();
  for (const r of openRows(rows)) {
    const entry = byEmployer.get(r.employer) ?? { employer: r.employer, open: 0, role: 0 };
    entry.open += 1;
    if (r.in_role) entry.role += 1;
    byEmployer.set(r.employer, entry);
  }
  return [...byEmployer.values()].sort((a, b) => b.open - a.open || (a.employer < b.employer ? -1 : 1));
}

export function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// 4. Days open: for removed postings that are not first-run, the removed date minus the first-seen date.
export function daysOpen(rows) {
  const values = rows.filter((r) => r.status === "removed" && r.removed_date && !r.first_run).map((r) => daysBetween(r.first_seen, r.removed_date));
  const CAP = 14; // the chart groups everything longer into "15+"
  const bins = Array.from({ length: CAP + 2 }, (_, i) => ({ label: i <= CAP ? String(i) : `${CAP + 1}+`, count: 0 }));
  for (const v of values) bins[Math.min(v, CAP + 1)].count += 1;
  return { count: values.length, median: median(values), bins };
}

// 5. Share removed within seven days: among non-first-run postings first seen at least seven days
// before the last run, the share whose removed date minus first-seen date is seven days or less.
export function removedWithinSeven(rows) {
  const last = lastRunDay(rows);
  const cohort = last ? rows.filter((r) => !r.first_run && daysBetween(r.first_seen, last) >= 7) : [];
  const fast = (r) => r.removed_date !== "" && daysBetween(r.first_seen, r.removed_date) <= 7;
  const removedFast = cohort.filter(fast).length;
  const byEmployer = new Map();
  for (const r of cohort) {
    const entry = byEmployer.get(r.employer) ?? { employer: r.employer, cohort: 0, removed: 0 };
    entry.cohort += 1;
    if (fast(r)) entry.removed += 1;
    byEmployer.set(r.employer, entry);
  }
  return {
    last, cohort: cohort.length, removed: removedFast, share: cohort.length ? removedFast / cohort.length : null,
    employers: [...byEmployer.values()].map((e) => ({ ...e, share: e.removed / e.cohort })).sort((a, b) => b.share - a.share || (a.employer < b.employer ? -1 : 1)),
  };
}

// 6. Top locations among open postings (the location text exactly as the history file has it;
// postings with no location are left out). "Multiple locations" is Workday's "3 Locations".
export const MULTIPLE_LOCATIONS = "Multiple locations";
export function topLocations(rows, n = 10) {
  const counts = new Map();
  let none = 0;
  for (const r of openRows(rows)) {
    if (!r.location) { none += 1; continue; }
    counts.set(r.location, (counts.get(r.location) ?? 0) + 1);
  }
  const list = [...counts.entries()].map(([location, count]) => ({ location, count }))
    .sort((a, b) => b.count - a.count || (a.location < b.location ? -1 : 1));
  const named = list.filter((l) => l.location !== MULTIPLE_LOCATIONS); // a single, named place
  const several = list.find((l) => l.location === MULTIPLE_LOCATIONS)?.count ?? 0;
  return { top: list.slice(0, n), topNamed: named.slice(0, n), distinct: list.length, withoutLocation: none, several };
}

// Today page: the postings first seen in a run (not first-run) and the postings removed in it.
export const newInRun = (rows, day) => rows.filter((r) => r.first_seen === day && !r.first_run);
export const removedInRun = (rows, day) => rows.filter((r) => r.removed_date === day);

// Browse page: how many days an open posting has been open, as of the last run.
export const daysOpenSoFar = (row, last) => daysBetween(row.first_seen, last);
