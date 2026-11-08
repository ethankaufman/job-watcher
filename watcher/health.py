"""A daily health check of the pipeline:  python -m watcher.health

Looks at data/status.json and the latest runs of the daily workflow, and says what is wrong:
  * the last run is old (the schedule did not fire, or the run did not commit);
  * the latest daily workflow run failed;
  * a source failed in the last run;
  * there are not enough days left before the due date to reach 7 days with data.
Problems open (or update) one GitHub Issue labelled "health-check" and make this check fail, so
GitHub sends a notification. When everything is fine again the issue is closed.
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = ROOT / "data" / "status.json"
LABEL = "health-check"
DUE_DATE = date(2026, 12, 3)  # the project is due this day
DAYS_NEEDED = 7  # successful runs on at least this many different days
STOP_AFTER = DUE_DATE + timedelta(days=2)  # the check goes quiet after the project is handed in
MAX_AGE = timedelta(hours=float(os.environ.get("HEALTH_MAX_AGE_HOURS", 30)))


def parse_time(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def assess(status, runs, now):
    """Return (problems, notes). status is data/status.json; runs are the latest daily workflow runs
    ({"conclusion", "createdAt"}, newest first)."""
    problems, notes = [], []

    age = now - parse_time(status["run_time"])
    if age > MAX_AGE:
        problems.append(f"The last run was {age.total_seconds() / 3600:.0f} hours ago ({status['run_time']}). "
                        "The daily run did not happen, or it ran but did not commit.")

    if runs and runs[0].get("conclusion") not in ("success", None, ""):  # None/"" = still running
        problems.append(f"The latest daily workflow run ended with '{runs[0]['conclusion']}' ({runs[0]['createdAt']}). "
                        "Open the Actions tab and read its log.")

    failed = [s for s in status["sources"] if not s["ok"]]
    if failed:
        listing = "; ".join(f"`{s['name']}`: {s.get('error', 'failed')}" for s in failed)
        problems.append(f"{len(failed)} of {len(status['sources'])} sources failed in the last run: {listing}")

    days_left = (DUE_DATE - now.date()).days
    if status["days_with_success"] + max(days_left, 0) < DAYS_NEEDED:
        problems.append(f"Only {status['days_with_success']} day(s) with data and {max(days_left, 0)} day(s) until the due date: "
                        f"the {DAYS_NEEDED} days needed can no longer be reached.")

    notes.append(f"{status['days_with_success']} day(s) with data (need {DAYS_NEEDED}); {days_left} day(s) until the due date ({DUE_DATE}).")
    notes.append(f"Last run: {status['run_time']}, {age.total_seconds() / 3600:.1f} hours ago; "
                 f"{sum(1 for s in status['sources'] if s['ok'])} of {len(status['sources'])} sources ok.")
    return problems, notes


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def latest_runs(run=gh):
    out = run("run", "list", "--workflow", "daily.yml", "--limit", "3", "--json", "conclusion,createdAt")
    return json.loads(out)


def report(problems, notes, now, run=gh):
    """Open or update the health-check issue when there are problems; close it when there are none."""
    run("label", "create", LABEL, "--color", "d93f0b", "--description", "Pipeline health problems", "--force")
    open_issues = json.loads(run("issue", "list", "--label", LABEL, "--state", "open", "--json", "number"))
    day = now.strftime("%Y-%m-%d")
    if problems:
        body = "\n".join([f"Health check of **{day}** found problems:", ""] + [f"- {p}" for p in problems] + ["", *notes])
        title = f"Health check: problems found ({day})"
        if open_issues:
            run("issue", "edit", str(open_issues[0]["number"]), "--title", title, "--body", body)
        else:
            run("issue", "create", "--title", title, "--body", body, "--label", LABEL)
    else:
        for issue in open_issues:
            run("issue", "close", str(issue["number"]), "--comment", f"All clear on {day}. " + " ".join(notes))


def main():
    now = datetime.now(timezone.utc)
    if now.date() > STOP_AFTER:
        print("The project is past its due date: nothing to check.")
        return 0
    status = json.loads(STATUS_PATH.read_text())
    try:
        runs = latest_runs()
    except Exception as error:  # no gh or no permission: still check the status file
        print(f"Could not read the workflow runs: {error}", file=sys.stderr)
        runs = []
    problems, notes = assess(status, runs, now)
    for line in notes:
        print(line)
    for line in problems:
        print("PROBLEM:", line)
    try:
        report(problems, notes, now)
    except Exception as error:
        print(f"Could not update the health-check issue: {error}", file=sys.stderr)
    if problems:
        return 1  # the failed check is itself a notification
    print("All clear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
