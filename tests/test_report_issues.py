import json

from watcher.issues import publish_issue
from watcher.report import MAX_SECTION, issue_body, ordered


def row(i, title="Job", role=False, **extra):
    base = {"posting_id": f"stripe:{i}", "employer": "Stripe", "title": title, "location": "NYC", "url": f"https://x/{i}",
            "in_role": role, "first_run": False, "first_seen": "2026-11-09", "removed_date": ""}
    return {**base, **extra}


def test_postings_in_my_role_come_first():
    rows = [row(1, "B Job"), row(2, "A Analyst", role=True), row(3, "A Job")]
    assert [r["posting_id"] for r in ordered(rows)] == ["stripe:2", "stripe:3", "stripe:1"]


def test_square_brackets_in_a_title_do_not_break_the_link():
    body = issue_body("2026-11-09", [row(1, "Analyst [Remote]")], [])
    assert "[Analyst (Remote)](<https://x/1>)" in body


def test_a_long_list_is_cut_to_fit_a_github_issue():
    rows = [row(i, "A very long job title " * 4) for i in range(2000)]
    body = issue_body("2026-11-09", rows, [])
    assert len(body) < 65536
    assert "more (they are all in the history" in body
    assert body.count("](<https://x/") <= MAX_SECTION // 50


def test_first_run_postings_are_not_listed_as_new():
    rows = [row(1, first_run=True, first_seen="2026-11-09"), row(2)]
    body = issue_body("2026-11-09", rows, [])
    assert "## New postings (1)" in body and "https://x/2" in body and "https://x/1" not in body


class FakeGh:
    def __init__(self, issues):
        self.issues, self.calls = issues, []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("issue", "list"):
            return json.dumps(self.issues)
        if args[:2] == ("issue", "create"):
            return "https://github.com/me/repo/issues/42\n"
        return ""


def test_new_day_creates_an_issue_and_closes_the_previous_one():
    fake = FakeGh([{"number": 7, "title": "2026-11-08"}])
    assert publish_issue("2026-11-09", "body", run=fake) == 42
    kinds = [c[:2] for c in fake.calls]
    assert ("issue", "create") in kinds and ("issue", "close") in kinds and fake.calls[-1][2] == "7"


def test_second_run_the_same_day_edits_the_issue_and_keeps_it_open():
    fake = FakeGh([{"number": 9, "title": "2026-11-09"}, {"number": 7, "title": "2026-11-08"}])
    assert publish_issue("2026-11-09", "new body", run=fake) == 9
    kinds = [c[:2] for c in fake.calls]
    assert ("issue", "create") not in kinds and ("issue", "edit") in kinds
    assert [c[2] for c in fake.calls if c[:2] == ("issue", "close")] == ["7"]
