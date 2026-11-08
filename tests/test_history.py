import csv
import gzip

from tests.helpers import SRC, greenhouse
from watcher.history import COLUMNS, build_history, raw_days, write_history

STRIPE, COINBASE = "stripe", "coinbase"


def save(raw_dir, day, source, body):
    path = raw_dir / day / f"{source}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(body))


def board(*ids, title="Financial Analyst"):
    return greenhouse(*[(i, f"{title} {i}", "NYC", None) for i in ids])


def by_id(rows):
    return {r["source_id"]: r for r in rows if r["source"] == STRIPE}


def test_first_seen_last_seen_and_first_run(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-09", STRIPE, board(1, 2, 3))
    save(tmp_path, "2026-11-10", STRIPE, board(1, 2, 3))
    rows = by_id(build_history(tmp_path))
    assert (rows["1"]["first_seen"], rows["1"]["last_seen"], rows["1"]["first_run"]) == ("2026-11-08", "2026-11-10", True)
    assert (rows["3"]["first_seen"], rows["3"]["last_seen"], rows["3"]["first_run"]) == ("2026-11-09", "2026-11-10", False)
    assert rows["3"]["status"] == "open" and rows["3"]["removed_date"] == ""


def test_a_posting_that_disappears_is_removed_on_that_day(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-09", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-10", STRIPE, board(1))  # 2 is gone
    save(tmp_path, "2026-11-11", STRIPE, board(1))
    rows = by_id(build_history(tmp_path))
    assert rows["2"]["status"] == "removed"
    assert rows["2"]["removed_date"] == "2026-11-10"
    assert rows["2"]["last_seen"] == "2026-11-09"  # the last day it was listed
    assert rows["1"]["status"] == "open"


def test_a_removed_posting_that_comes_back_is_open_again(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-09", STRIPE, board(1))  # 2 removed
    save(tmp_path, "2026-11-10", STRIPE, board(1, 2))  # 2 is back
    row = by_id(build_history(tmp_path))["2"]
    assert row["status"] == "open"
    assert row["removed_date"] == ""  # cleared
    assert row["first_seen"] == "2026-11-08"  # unchanged
    assert row["last_seen"] == "2026-11-10"
    assert row["first_run"] is True


def test_a_failed_source_marks_nothing_removed(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-08", COINBASE, board(7))
    save(tmp_path, "2026-11-09", COINBASE, board(7))  # stripe has no raw file on the 9th: it failed
    save(tmp_path, "2026-11-10", STRIPE, board(1, 2))
    rows = by_id(build_history(tmp_path))
    assert rows["1"]["status"] == rows["2"]["status"] == "open"
    assert rows["1"]["last_seen"] == "2026-11-10"
    assert raw_days(tmp_path) == ["2026-11-08", "2026-11-09", "2026-11-10"]


def test_sources_are_independent_and_each_has_its_own_first_run(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1))
    save(tmp_path, "2026-11-09", STRIPE, board(1))
    save(tmp_path, "2026-11-09", COINBASE, board(5))  # coinbase's first raw file is the 9th
    save(tmp_path, "2026-11-10", COINBASE, board(5, 6))
    rows = {(r["source"], r["source_id"]): r for r in build_history(tmp_path)}
    assert rows[(COINBASE, "5")]["first_run"] is True and rows[(COINBASE, "5")]["first_seen"] == "2026-11-09"
    assert rows[(COINBASE, "6")]["first_run"] is False
    assert rows[(STRIPE, "1")]["first_run"] is True


def test_a_posting_new_on_a_sources_second_day_is_not_first_run(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1))
    save(tmp_path, "2026-11-09", STRIPE, board(1, 2))
    assert by_id(build_history(tmp_path))["2"]["first_run"] is False


def test_the_latest_title_and_location_win_and_the_title_rule_is_applied_to_it(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, greenhouse((1, "Software Engineer", "SF", None)))
    save(tmp_path, "2026-11-09", STRIPE, greenhouse((1, "Financial Analyst", "NYC", None)))
    row = by_id(build_history(tmp_path))["1"]
    assert (row["title"], row["location"], row["in_role"]) == ("Financial Analyst", "NYC", True)


def test_every_posting_is_kept_and_marked_in_role_or_not(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, greenhouse((1, "Financial Analyst", "NYC", None), (2, "Account Executive", "NYC", None)))
    rows = by_id(build_history(tmp_path))
    assert (rows["1"]["in_role"], rows["2"]["in_role"]) == (True, False)


def test_rows_are_sorted_by_posting_id(tmp_path):
    save(tmp_path, "2026-11-08", COINBASE, board(2, 1))
    save(tmp_path, "2026-11-08", STRIPE, board(9, 3))
    ids = [r["posting_id"] for r in build_history(tmp_path)]
    assert ids == sorted(ids) == ["coinbase:1", "coinbase:2", "stripe:3", "stripe:9"]


def test_building_twice_gives_the_same_file(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-09", STRIPE, board(1, 3))
    write_history(build_history(tmp_path), tmp_path / "a.csv")
    write_history(build_history(tmp_path), tmp_path / "b.csv")
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()


def test_csv_has_the_required_columns_and_true_false_values(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1, 2))
    save(tmp_path, "2026-11-09", STRIPE, board(1))
    out = tmp_path / "history.csv"
    write_history(build_history(tmp_path), out)
    assert COLUMNS == ["posting_id", "source", "source_id", "employer", "title", "location", "department", "posted_date", "url",
                       "in_role", "first_run", "first_seen", "last_seen", "status", "removed_date"]
    rows = list(csv.DictReader(out.open(newline="")))
    assert list(rows[0]) == COLUMNS
    gone = next(r for r in rows if r["source_id"] == "2")
    assert (gone["status"], gone["removed_date"], gone["in_role"], gone["first_run"]) == ("removed", "2026-11-09", "true", "true")
    assert gone["department"] == "" and gone["posted_date"] == ""  # not given by this source: left empty


def test_other_folders_and_files_are_ignored(tmp_path):
    save(tmp_path, "2026-11-08", STRIPE, board(1))
    (tmp_path / "notes").mkdir()
    (tmp_path / "2026-11-08" / "readme.txt").write_text("hi")
    save(tmp_path, "2026-11-08", "not-a-source", board(99))
    assert raw_days(tmp_path) == ["2026-11-08"]
    assert len(build_history(tmp_path)) == 1
