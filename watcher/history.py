"""Build data/history.csv from the raw files alone.

Run it with:  python -m watcher.history
The result depends only on the files in data/raw/, so running it again gives the same file, and a
change to a rule (the title rule, a conversion) applies to every day of the history.

The raw days are replayed oldest first. For each source that has a raw file on a day:
  * a posting seen for the first time gets that day as first_seen. It is a first-run posting
    (first_run = true) when that day is the source's first raw file: it was already open when
    the tool started watching, so its real start date is unknown;
  * every posting the source lists gets that day as last_seen;
  * an open posting the source no longer lists is marked removed, with that day as removed_date;
  * a removed posting the source lists again becomes open again: removed_date is cleared and
    first_seen stays what it was.
A source with no raw file on a day (it failed) changes nothing that day.
"""

import csv
import gzip
import re
from pathlib import Path

from watcher.convert import convert
from watcher.rules import in_role
from watcher.sources import SOURCES, raw_path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
HISTORY_PATH = ROOT / "data" / "history.csv"

COLUMNS = [
    "posting_id", "source", "source_id", "employer", "title", "location", "department", "posted_date", "url",
    "in_role", "first_run", "first_seen", "last_seen", "status", "removed_date",
]
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def raw_days(raw_dir):
    """The dates that have a raw folder, oldest first."""
    raw_dir = Path(raw_dir)
    if not raw_dir.is_dir():
        return []
    return sorted(p.name for p in raw_dir.iterdir() if p.is_dir() and DATE_PATTERN.match(p.name))


def build_history(raw_dir=RAW_DIR):
    """Replay every raw file and return the history rows, sorted by posting_id."""
    postings = {}  # posting_id -> row
    open_ids = {source.name: set() for source in SOURCES}
    first_day = {}  # source name -> the date of its first raw file

    for day in raw_days(raw_dir):
        for source in SOURCES:
            path = raw_path(raw_dir, day, source.name)
            if not path.exists():
                continue  # no raw file: unknown today, so nothing changes
            first_day.setdefault(source.name, day)
            listed = {row["posting_id"]: row for row in convert(source, gzip.decompress(path.read_bytes()))}

            for posting_id, row in listed.items():
                known = postings.get(posting_id)
                if known is None:
                    postings[posting_id] = {
                        **row, "first_run": day == first_day[source.name],
                        "first_seen": day, "last_seen": day, "status": "open", "removed_date": "",
                    }
                else:
                    known.update(row)  # keep the latest title, location and so on
                    known.update(last_seen=day, status="open", removed_date="")  # a relisted posting is open again
                open_ids[source.name].add(posting_id)

            for posting_id in open_ids[source.name] - set(listed):
                postings[posting_id].update(status="removed", removed_date=day)
                open_ids[source.name].discard(posting_id)

    rows = sorted(postings.values(), key=lambda row: row["posting_id"])
    for row in rows:
        row["in_role"] = in_role(row["title"])
    return rows


def format_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def write_history(rows, path=HISTORY_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([format_value(row[column]) for column in COLUMNS])


def main():
    rows = build_history()
    write_history(rows)
    print(f"Wrote {len(rows)} postings to {HISTORY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
