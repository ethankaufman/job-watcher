import gzip
import json

import pytest

from tests.helpers import SRC, FakeHttp, greenhouse, oracle, smartrecruiters, workday
from watcher import sources
from watcher.sources import SOURCES, fetch_all, fetch_source, raw_path

GOOD = greenhouse((1, "Financial Analyst", "NYC", "2026-11-01T10:00:00Z"), (2, "Software Engineer", "SF", None))


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(sources, "PAGE_PAUSE", 0)


def answers_for_all(good=GOOD):
    """Every source answers with something valid (the paged systems get a one-page board)."""
    answers = {}
    for s in SOURCES:
        if s.ats == "workday":
            answers[f"{s.board}.{s.host}.myworkdayjobs.com"] = workday(("R1", "Analyst", "NYC"))
        elif s.ats == "oracle":
            answers[s.host] = oracle(("1", "Analyst", "NYC", "Fam", "2026-11-01"))
        elif s.ats == "smartrecruiters":
            answers[f"companies/{s.board}/"] = smartrecruiters(("1", "Analyst", "NYC", "us", "Dept", "2026-11-01T00:00:00Z"))
        elif s.ats == "greenhouse":
            answers[f"boards/{s.board}/jobs"] = good
        elif s.ats == "lever":
            answers[f"postings/{s.board}"] = json.dumps([{"id": "a", "text": "Analyst", "categories": {}, "createdAt": 0, "hostedUrl": "u"}]).encode()
        elif s.ats == "ashby":
            answers[f"job-board/{s.board}"] = json.dumps({"jobs": [{"id": "a", "title": "Analyst", "isListed": True, "jobUrl": "u"}]}).encode()
    return answers


def test_a_good_board_is_saved_compressed_as_it_came(tmp_path):
    http = FakeHttp({"boards/stripe/jobs": GOOD})
    result = fetch_source(SRC["stripe"], "2026-11-08", tmp_path, http)
    assert result == {"name": "stripe", "employer": "Stripe", "ats": "greenhouse", "ok": True, "count": 2, "error": None}
    path = raw_path(tmp_path, "2026-11-08", "stripe")
    assert path.name == "stripe.json.gz"
    assert gzip.decompress(path.read_bytes()) == GOOD


def test_workday_pages_are_merged_into_one_raw_file(tmp_path):
    board = workday(*[(f"R{i}", f"Analyst {i}", "NYC") for i in range(45)])  # 3 pages of 20
    http = FakeHttp({"blackrock.wd1.myworkdayjobs.com": board})
    result = fetch_source(SRC["blackrock"], "2026-11-08", tmp_path, http)
    assert result["ok"] and result["count"] == 45
    assert len(http.requests) == 3
    saved = json.loads(gzip.decompress(raw_path(tmp_path, "2026-11-08", "blackrock").read_bytes()))
    assert saved["total"] == 45 and len(saved["jobPostings"]) == 45


def test_oracle_is_requested_with_its_search_term_and_paged(tmp_path):
    board = oracle(*[(str(i), f"Analyst {i}", "NYC", "Fam", "2026-11-01") for i in range(60)])
    http = FakeHttp({"jpmc.fa.oraclecloud.com": board})
    result = fetch_source(SRC["jpmorgan"], "2026-11-08", tmp_path, http)
    assert result["ok"] and result["count"] == 60
    assert all("keyword=analyst" in url for url in http.requests) and len(http.requests) == 3
    saved = json.loads(gzip.decompress(raw_path(tmp_path, "2026-11-08", "jpmorgan").read_bytes()))
    assert saved["keyword"] == "analyst"


def test_smartrecruiters_pages_are_merged(tmp_path):
    board = smartrecruiters(*[(str(i), f"Analyst {i}", "NYC", "us", "Dept", "2026-11-01T00:00:00Z") for i in range(150)])
    http = FakeHttp({"companies/Experian/": board})
    result = fetch_source(SRC["experian"], "2026-11-08", tmp_path, http)
    assert result["ok"] and result["count"] == 150 and len(http.requests) == 2


def test_a_failed_source_writes_no_file_and_does_not_stop_the_run(tmp_path):
    answers = answers_for_all()
    answers["boards/coinbase/jobs"] = OSError("network down")
    results = fetch_all("2026-11-08", tmp_path, FakeHttp(answers))
    by_name = {r["name"]: r for r in results}
    assert [r["name"] for r in results] == [s.name for s in SOURCES]  # one result per source, in order
    assert by_name["coinbase"]["ok"] is False and "network down" in by_name["coinbase"]["error"]
    assert by_name["coinbase"]["count"] == 0
    assert not raw_path(tmp_path, "2026-11-08", "coinbase").exists()
    assert all(r["ok"] for name, r in by_name.items() if name != "coinbase")
    assert raw_path(tmp_path, "2026-11-08", "stripe").exists()


def test_a_board_that_stops_halfway_is_a_failure_not_a_short_list(tmp_path):
    class Truncating(FakeHttp):
        def post_json(self, url, payload):
            return json.dumps({"total": 45 if payload["offset"] == 0 else 0, "jobPostings": [] if payload["offset"] else [{"title": "t", "externalPath": "/job/x/t_R1", "locationsText": ""}] * 20}).encode()

    result = fetch_source(SRC["blackrock"], "2026-11-08", tmp_path, Truncating({}))
    assert result["ok"] is False and "stopped after" in result["error"]
    assert not raw_path(tmp_path, "2026-11-08", "blackrock").exists()  # a half list would mark postings removed


def test_an_empty_board_counts_as_a_failure(tmp_path):
    result = fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": greenhouse()}))
    assert result["ok"] is False and "no postings" in result["error"]
    assert not raw_path(tmp_path, "2026-11-08", "stripe").exists()


def test_garbage_counts_as_a_failure(tmp_path):
    result = fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": b"<html>oops"}))
    assert result["ok"] is False


def test_a_board_over_5000_postings_is_refused_so_a_search_term_gets_used(tmp_path):
    big = greenhouse(*[(i, f"Job {i}", "X", None) for i in range(5001)])
    result = fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": big}))
    assert result["ok"] is False and "5000" in result["error"]
    big_workday = json.dumps({"total": 5001, "jobPostings": []}).encode()
    result = fetch_source(SRC["blackrock"], "2026-11-08", tmp_path, FakeHttp({"blackrock.wd1.myworkdayjobs.com": big_workday}))
    assert result["ok"] is False and "5000" in result["error"]


def test_second_run_the_same_day_replaces_the_raw_file(tmp_path):
    fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": GOOD}))
    newer = greenhouse((1, "Financial Analyst", "NYC", None))
    fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": newer}))
    path = raw_path(tmp_path, "2026-11-08", "stripe")
    assert gzip.decompress(path.read_bytes()) == newer
    assert len(list(path.parent.iterdir())) == 1


def test_a_failed_second_run_keeps_the_earlier_file(tmp_path):
    fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": GOOD}))
    fetch_source(SRC["stripe"], "2026-11-08", tmp_path, FakeHttp({"boards/stripe/jobs": OSError("down")}))
    assert gzip.decompress(raw_path(tmp_path, "2026-11-08", "stripe").read_bytes()) == GOOD


def test_there_are_at_least_15_employers_and_several_systems():
    assert len(SOURCES) >= 15
    assert len({s.ats for s in SOURCES}) >= 4
    assert len({s.name for s in SOURCES}) == len(SOURCES)  # names are unique (they are file names)
