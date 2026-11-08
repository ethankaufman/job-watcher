// Prints, as JSON, the numbers the Market and Today pages compute from a history file.
// It runs the same functions the browser runs (assets/stats.mjs); tests/test_market_numbers.py
// compares the output with an independent calculation in Python.
//
//   node tools/market_numbers.mjs data/history.csv
import { readFileSync } from "node:fs";
import { parseHistory } from "../assets/data.mjs";
import * as stats from "../assets/stats.mjs";

const rows = parseHistory(readFileSync(process.argv[2], "utf8"));
const last = stats.lastRunDay(rows);
console.log(JSON.stringify({
  last,
  first: stats.firstDay(rows),
  newPerDay: stats.newPerDay(rows),
  removedPerDay: stats.removedPerDay(rows),
  openPerEmployer: stats.openPerEmployer(rows),
  daysOpen: stats.daysOpen(rows),
  daysOpenRole: stats.daysOpen(stats.inRole(rows)),
  withinSeven: stats.removedWithinSeven(rows),
  withinSevenRole: stats.removedWithinSeven(stats.inRole(rows)),
  locations: stats.topLocations(rows),
  newInRun: stats.newInRun(rows, last).map((r) => r.posting_id),
  removedInRun: stats.removedInRun(rows, last).map((r) => r.posting_id),
}));
