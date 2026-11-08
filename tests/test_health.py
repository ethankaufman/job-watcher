import json
from datetime import datetime, timezone

from watcher import health
from watcher.health import assess, report


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def status(run_time="2026-11-10T06:20:00Z", days=3, failed=()):
    names = ["title", "relegation", "standings"]
    return {"run_time": run_time, "days_with_success": days,
            "sources": [{"name": n, "ok": n not in failed, "count": 20, **({} if n not in failed else {"error": "HTTPError: 429"})} for n in names]}


OK_RUNS = [{"conclusion": "success", "createdAt": "2026-11-10T06:17:00Z"}]


def test_a_healthy_pipeline_has_no_problems():
    problems, notes = assess(status(), OK_RUNS, at("2026-11-10 12:10"))
    assert problems == []
    assert any("3 day(s) with data" in n for n in notes)


def test_an_old_last_run_is_a_problem():
    problems, _ = assess(status(run_time="2026-11-08T07:00:00Z"), OK_RUNS, at("2026-11-10 12:10"))
    assert len(problems) == 1 and "hours ago" in problems[0]


def test_just_under_the_limit_is_fine():
    problems, _ = assess(status(run_time="2026-11-09T07:30:00Z"), OK_RUNS, at("2026-11-10 12:10"))  # 28.7 hours
    assert problems == []


def test_a_failed_workflow_run_is_a_problem_but_a_running_one_is_not():
    failed = [{"conclusion": "failure", "createdAt": "2026-11-10T06:17:00Z"}]
    assert "ended with 'failure'" in assess(status(), failed, at("2026-11-10 12:10"))[0][0]
    running = [{"conclusion": "", "createdAt": "2026-11-10T06:17:00Z"}]
    assert assess(status(), running, at("2026-11-10 12:10"))[0] == []


def test_failed_sources_are_named_with_their_error():
    problems, _ = assess(status(failed=("relegation",)), OK_RUNS, at("2026-11-10 12:10"))
    assert len(problems) == 1 and "`relegation`: HTTPError: 429" in problems[0] and "1 of 3 sources" in problems[0]


def test_not_enough_days_left_to_reach_seven_is_a_problem():
    problems, _ = assess(status(days=3, run_time="2026-11-30T06:20:00Z"), OK_RUNS, at("2026-11-30 12:10"))  # 3 days + 3 left = 6
    assert any("can no longer be reached" in p for p in problems)
    ok, _ = assess(status(days=4, run_time="2026-11-30T06:20:00Z"), OK_RUNS, at("2026-11-30 12:10"))  # 4 + 3 = 7
    assert not any("can no longer be reached" in p for p in ok)


class FakeGh:
    def __init__(self, open_issues):
        self.open_issues, self.calls = open_issues, []

    def __call__(self, *args):
        self.calls.append(args)
        return json.dumps(self.open_issues) if args[:2] == ("issue", "list") else ""


def test_problems_open_an_issue():
    fake = FakeGh([])
    report(["something broke"], ["note"], at("2026-11-10 12:10"), run=fake)
    create = next(c for c in fake.calls if c[:2] == ("issue", "create"))
    assert "Health check: problems found (2026-11-10)" in create and "health-check" in create
    assert "- something broke" in create[create.index("--body") + 1]


def test_a_second_problem_day_updates_the_same_issue():
    fake = FakeGh([{"number": 5}])
    report(["still broken"], [], at("2026-11-11 12:10"), run=fake)
    kinds = [c[:2] for c in fake.calls]
    assert ("issue", "edit") in kinds and ("issue", "create") not in kinds


def test_when_all_is_clear_the_issue_is_closed():
    fake = FakeGh([{"number": 5}])
    report([], ["3 day(s) with data"], at("2026-11-12 12:10"), run=fake)
    close = next(c for c in fake.calls if c[:2] == ("issue", "close"))
    assert close[2] == "5" and "All clear on 2026-11-12" in close[-1]


def test_no_problems_and_no_issue_means_nothing_to_close():
    fake = FakeGh([])
    report([], [], at("2026-11-12 12:10"), run=fake)
    assert not any(c[:2] in (("issue", "close"), ("issue", "create")) for c in fake.calls)


def test_the_check_has_the_right_due_date():
    assert health.DUE_DATE.isoformat() == "2026-12-03" and health.DAYS_NEEDED == 7
