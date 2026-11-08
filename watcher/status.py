"""Build data/status.json, which describes the latest run."""

import json
from pathlib import Path

from watcher.history import raw_days


def days_with_raw_files(raw_dir):
    """Dates that have at least one raw file (a day on which every source failed does not count)."""
    return [day for day in raw_days(raw_dir) if any((Path(raw_dir) / day).glob("*.json.gz"))]


def build_status(run_time, raw_dir, rows, results):
    """The status dictionary for a run at run_time (a UTC datetime)."""
    day = run_time.strftime("%Y-%m-%d")
    days = days_with_raw_files(raw_dir)
    sources = []
    for result in results:
        entry = {"name": result["name"], "ok": result["ok"], "count": result["count"],
                 "employer": result["employer"], "ats": result["ats"]}
        if result.get("error"):
            entry["error"] = result["error"]
        sources.append(entry)
    return {
        "run_time": run_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_run_date": days[0] if days else None,
        "days_with_success": len(days),
        "open": sum(1 for row in rows if row["status"] == "open"),
        # first seen in this run, leaving out the postings that were already open when watching began
        "new_today": sum(1 for row in rows if row["first_seen"] == day and not row["first_run"]),
        "removed_today": sum(1 for row in rows if row["removed_date"] == day),
        "sources": sources,
    }


def write_status(status, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
