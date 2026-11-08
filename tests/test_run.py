import csv
import io
import json
from datetime import datetime, timezone

from tests.helpers import FakeHttp, answers_for_all, greenhouse
from watcher.run import run
from watcher.sources import SOURCES

OTHERS = greenhouse((900, "Software Engineer", "SF", None))  # what the other employers' boards say


def http_with(*jobs, fail=()):
    answers = answers_for_all(OTHERS)
    answers["boards/stripe/jobs"] = greenhouse(*[(i, t, "NYC", None) for i, t in jobs])
    for name in fail:
        source = next(s for s in SOURCES if s.name == name)
        answers[f"boards/{source.board}/jobs"] = OSError("down")
    return FakeHttp(answers)


def at(day, hour=9):
    return datetime(*map(int, day.split("-")), hour, 5, 0, tzinfo=timezone.utc)


class Env:
    def __init__(self, tmp_path):
        self.raw, self.history, self.status = tmp_path / "raw", tmp_path / "history.csv", tmp_path / "status.json"
        self.published = []

    def run(self, day, *jobs, hour=9, fail=()):
        return run(at(day, hour), raw_dir=self.raw, history_path=self.history, status_path=self.status,
                   http=http_with(*jobs, fail=fail), publish=lambda title, body: self.published.append((title, body)))

    def rows(self):
        return list(csv.DictReader(io.StringIO(self.history.read_text())))

    def stripe(self):
        return {r["source_id"]: r for r in self.rows() if r["source"] == "stripe"}


def test_a_second_run_on_the_same_day_counts_the_day_once(tmp_path):
    env = Env(tmp_path)
    env.run("2026-11-08", (1, "Financial Analyst"), (2, "Data Analyst"), hour=9)
    first = env.rows()
    status = env.run("2026-11-08", (1, "Financial Analyst"), (2, "Data Analyst"), (3, "Credit Analyst"), hour=18)
    rows = env.rows()
    ids = [r["posting_id"] for r in rows]

    assert status["days_with_success"] == 1 and status["first_run_date"] == "2026-11-08"
    assert len(ids) == len(set(ids)) == len(first) + 1  # no duplicates; the newer board added one
    assert env.stripe()["3"]["first_run"] == "true"  # it is in the first raw file of its source (the replaced one)
    assert status["new_today"] == 0 and status["run_time"] == "2026-11-08T18:05:00Z"


def test_the_second_run_the_same_day_updates_the_same_issue(tmp_path):
    env = Env(tmp_path)
    env.run("2026-11-08", (1, "Financial Analyst"), hour=9)
    env.run("2026-11-08", (1, "Financial Analyst"), hour=18)
    assert [title for title, _ in env.published] == ["2026-11-08", "2026-11-08"]


def test_new_and_removed_postings_on_the_second_day(tmp_path):
    env = Env(tmp_path)
    first = env.run("2026-11-08", (1, "Financial Analyst"), (2, "Account Executive"))
    status = env.run("2026-11-09", (2, "Account Executive"), (3, "Data Analyst"))
    assert first["new_today"] == 0 and first["removed_today"] == 0  # day one: everything is a first-run posting
    assert status["new_today"] == 1 and status["removed_today"] == 1
    assert status["open"] == sum(1 for r in env.rows() if r["status"] == "open")
    assert env.stripe()["1"]["status"] == "removed" and env.stripe()["3"]["first_seen"] == "2026-11-09"
    assert json.loads(env.status.read_text()) == status


def test_status_file_keys(tmp_path):
    env = Env(tmp_path)
    status = env.run("2026-11-08", (1, "Financial Analyst"))
    assert set(status) == {"run_time", "first_run_date", "days_with_success", "open", "new_today", "removed_today", "sources"}
    assert [s["name"] for s in status["sources"]] == [s.name for s in SOURCES]
    assert all({"name", "ok", "count"} <= set(s) for s in status["sources"])
    assert isinstance(status["open"], int) and isinstance(status["new_today"], int)


def test_a_failed_source_is_recorded_the_run_finishes_and_nothing_is_removed(tmp_path):
    env = Env(tmp_path)
    env.run("2026-11-08", (1, "Financial Analyst"))
    status = env.run("2026-11-09", (1, "Financial Analyst"), fail=("coinbase",))
    by_name = {s["name"]: s for s in status["sources"]}
    assert by_name["coinbase"]["ok"] is False and by_name["coinbase"]["count"] == 0 and "down" in by_name["coinbase"]["error"]
    assert by_name["stripe"]["ok"] is True
    assert status["removed_today"] == 0  # coinbase's postings are unknown today, not removed
    assert all(r["status"] == "open" for r in env.rows() if r["source"] == "coinbase")
    assert "coinbase" in env.published[-1][1]  # the issue names the failed source


def test_the_issue_is_opened_every_day_even_with_no_changes(tmp_path):
    env = Env(tmp_path)
    env.run("2026-11-08", (1, "Financial Analyst"))
    env.run("2026-11-09", (1, "Financial Analyst"))
    title, body = env.published[-1]
    assert title == "2026-11-09"
    assert "No new postings today." in body and "No postings were removed today." in body


def test_the_issue_lists_new_and_removed_postings_with_links(tmp_path):
    env = Env(tmp_path)
    env.run("2026-11-08", (1, "Gone Job"))
    env.run("2026-11-09", (2, "Financial Analyst"))
    body = env.published[-1][1]
    assert "## New postings (1)" in body and "## Removed postings (1)" in body
    assert "[Financial Analyst](<https://boards.example/gh/2>)" in body
    assert "[Gone Job](<https://boards.example/gh/1>)" in body
    assert "★ [Financial Analyst]" in body  # in my role


def test_a_failing_issue_does_not_stop_the_run(tmp_path):
    def broken(title, body):
        raise RuntimeError("no network")

    env = Env(tmp_path)
    status = run(at("2026-11-08"), raw_dir=env.raw, history_path=env.history, status_path=env.status,
                 http=http_with((1, "Financial Analyst")), publish=broken)
    assert status["days_with_success"] == 1 and env.history.exists()
