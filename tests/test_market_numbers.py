"""The Market page must show numbers that agree with data/history.csv.

The page's calculations (assets/stats.mjs) are run with Node on a history file, and the results are
compared with a separate calculation done here in Python straight from the CSV.
"""

import csv
import json
import random
import shutil
import statistics
import subprocess
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

from watcher.history import COLUMNS, write_history

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")

EMPLOYERS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
PLACES = ["New York, NY", "London, UK", "Multiple locations", "Remote", "Chicago, IL", ""]


def day(n):
    return (date(2026, 11, 1) + timedelta(days=n)).isoformat()


def sample_rows():
    """A varied history: first-run and later postings, removals after 0 to 12 days (7 and 8 included),
    reopened postings, empty locations, and a gap of days with no run."""
    rng = random.Random(3)
    run_days = [0, 1, 2, 3, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18]  # days 4, 5 and 11 had no run
    rows = []
    for i in range(400):
        first_run = i < 150
        first = 0 if first_run else rng.choice(run_days[1:])
        row = {c: "" for c in COLUMNS}
        employer = EMPLOYERS[i % len(EMPLOYERS)]
        row.update(
            posting_id=f"{employer.lower()}:{i}", source=employer.lower(), source_id=str(i), employer=employer,
            title=f"Job {i}", location=PLACES[(i * 7) % len(PLACES)] if i % 11 else "", url=f"https://x/{i}",
            in_role=rng.random() < 0.3, first_run=first_run, first_seen=day(first), status="open",
        )
        if rng.random() < 0.55:  # removed some days later (never before the first day it was seen)
            gap = rng.choice([0, 1, 1, 2, 3, 5, 7, 7, 8, 9, 12])
            later = [d for d in run_days if d > first and d >= first + gap] or [run_days[-1]]
            removed = later[0] if later[0] > first else run_days[-1]
            row.update(status="removed", removed_date=day(removed))
        rows.append(row)
    last = day(run_days[-1])
    for row in rows:
        row["last_seen"] = last if row["status"] == "open" else day(max(0, (date.fromisoformat(row["removed_date"]) - date(2026, 11, 1)).days - 1))
    rows.sort(key=lambda r: r["posting_id"])
    return rows


def page_numbers(csv_path):
    out = subprocess.run(["node", str(ROOT / "tools" / "market_numbers.mjs"), str(csv_path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def median(values):
    return statistics.median(values) if values else None


def test_page_numbers_agree_with_the_history_file(tmp_path):
    path = tmp_path / "history.csv"
    write_history(sample_rows(), path)
    rows = list(csv.DictReader(path.open(newline="")))  # read back from the file, as the page does
    page = page_numbers(path)
    D = date.fromisoformat
    as_bool = lambda text: text == "true"
    first_seen = lambda r: D(r["first_seen"])

    dates = [d for r in rows for d in (r["first_seen"], r["last_seen"], r["removed_date"]) if d]
    last, first = max(dates), min(r["first_seen"] for r in rows)
    assert (page["last"], page["first"]) == (last, first)
    calendar = [(D(first) + timedelta(days=n)).isoformat() for n in range((D(last) - D(first)).days + 1)]

    # 1. new postings per day (not first-run), all and in role
    assert page["newPerDay"]["days"] == calendar
    assert page["newPerDay"]["all"] == [sum(1 for r in rows if r["first_seen"] == d and not as_bool(r["first_run"])) for d in calendar]
    assert page["newPerDay"]["role"] == [sum(1 for r in rows if r["first_seen"] == d and not as_bool(r["first_run"]) and as_bool(r["in_role"])) for d in calendar]

    # 2. removed postings per day
    assert page["removedPerDay"]["all"] == [sum(1 for r in rows if r["removed_date"] == d) for d in calendar]
    assert page["removedPerDay"]["role"] == [sum(1 for r in rows if r["removed_date"] == d and as_bool(r["in_role"])) for d in calendar]

    # 3. open postings per employer
    open_rows = [r for r in rows if r["status"] == "open"]
    expected = sorted(({"employer": e, "open": sum(1 for r in open_rows if r["employer"] == e), "role": sum(1 for r in open_rows if r["employer"] == e and as_bool(r["in_role"]))}
                       for e in {r["employer"] for r in open_rows}), key=lambda x: (-x["open"], x["employer"]))
    assert page["openPerEmployer"] == expected

    # 4. days open: removed date minus first-seen date, removed postings that are not first-run
    def days_open(selection):
        return [(D(r["removed_date"]) - first_seen(r)).days for r in selection if r["status"] == "removed" and not as_bool(r["first_run"])]

    for key, selection in (("daysOpen", rows), ("daysOpenRole", [r for r in rows if as_bool(r["in_role"])])):
        values = days_open(selection)
        assert page[key]["count"] == len(values) and page[key]["median"] == median(values)
        assert [b["count"] for b in page[key]["bins"]] == [sum(1 for v in values if min(v, 15) == n) for n in range(16)]
    assert median(days_open(rows)) is not None  # the sample really has removed postings to measure

    # 5. share removed within seven days
    def within_seven(selection):
        cohort = [r for r in selection if not as_bool(r["first_run"]) and (D(last) - first_seen(r)).days >= 7]
        fast = [r for r in cohort if r["removed_date"] and (D(r["removed_date"]) - first_seen(r)).days <= 7]
        return cohort, fast

    for key, selection in (("withinSeven", rows), ("withinSevenRole", [r for r in rows if as_bool(r["in_role"])])):
        cohort, fast = within_seven(selection)
        assert (page[key]["cohort"], page[key]["removed"]) == (len(cohort), len(fast))
        assert page[key]["share"] == pytest.approx(len(fast) / len(cohort))
    cohort, fast = within_seven(rows)
    per_employer = {e["employer"]: (e["cohort"], e["removed"]) for e in page["withinSeven"]["employers"]}
    assert per_employer == {e: (sum(1 for r in cohort if r["employer"] == e), sum(1 for r in fast if r["employer"] == e)) for e in {r["employer"] for r in cohort}}
    assert len(cohort) > 0 and 0 < len(fast) < len(cohort)  # the boundary cases (exactly 7 and 8 days) are in play

    # 6. top locations among open postings
    counts = Counter(r["location"] for r in open_rows if r["location"])
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    assert [(l["location"], l["count"]) for l in page["locations"]["top"]] == ranked[:10]
    assert [(l["location"], l["count"]) for l in page["locations"]["topNamed"]] == [kv for kv in ranked if kv[0] != "Multiple locations"][:10]
    assert page["locations"]["withoutLocation"] == sum(1 for r in open_rows if not r["location"])
    assert page["locations"]["several"] == counts["Multiple locations"]

    # Today page lists
    assert sorted(page["newInRun"]) == sorted(r["posting_id"] for r in rows if r["first_seen"] == last and not as_bool(r["first_run"]))
    assert sorted(page["removedInRun"]) == sorted(r["posting_id"] for r in rows if r["removed_date"] == last)


def test_the_real_history_file_loads_in_the_page_code():
    path = ROOT / "data" / "history.csv"
    rows = list(csv.DictReader(path.open(newline="")))
    page = page_numbers(path)
    assert page["last"] == max(r["last_seen"] for r in rows)
    assert sum(e["open"] for e in page["openPerEmployer"]) == sum(1 for r in rows if r["status"] == "open")
