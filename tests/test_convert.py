from tests.helpers import SRC, ashby, greenhouse, lever, oracle, smartrecruiters, workday
from watcher.convert import POSTING_COLUMNS, convert, utc_date, workday_id, workday_location


def test_greenhouse():
    raw = greenhouse((8172487, "Abuse  Investigator", "Dublin", "2026-09-03T13:30:34-04:00"))
    row = convert(SRC["stripe"], raw)[0]
    assert list(row) == POSTING_COLUMNS
    assert row["posting_id"] == "stripe:8172487"
    assert (row["source"], row["source_id"], row["employer"]) == ("stripe", "8172487", "Stripe")
    assert row["title"] == "Abuse Investigator"  # extra white space removed
    assert row["location"] == "Dublin"
    assert row["department"] == ""  # Greenhouse's job list has no department
    assert row["posted_date"] == "2026-09-03"  # 13:30 in New York is 17:30 UTC, the same day
    assert row["url"] == "https://boards.example/gh/8172487"


def test_greenhouse_posted_date_is_the_utc_date():
    raw = greenhouse((1, "A", "X", "2026-09-03T22:30:00-04:00"))  # 02:30 UTC the next day
    assert convert(SRC["stripe"], raw)[0]["posted_date"] == "2026-09-04"


def test_lever():
    raw = lever(("abc-123", "Android Engineer", "Palo Alto, CA", "Engineering", 1694463796009))
    row = convert(SRC["wealthfront"], raw)[0]
    assert row["posting_id"] == "wealthfront:abc-123"
    assert (row["employer"], row["title"], row["location"], row["department"]) == ("Wealthfront", "Android Engineer", "Palo Alto, CA", "Engineering")
    assert row["posted_date"] == "2023-09-11"  # createdAt is milliseconds since 1970
    assert row["url"] == "https://jobs.lever.co/wealthfront/abc-123"


def test_ashby_skips_unlisted_postings():
    raw = ashby(("id1", "Site Reliability Engineer", "New York Office", "Engineering", "2025-12-04T16:04:53.469+00:00"), unlisted=("hidden",))
    rows = convert(SRC["kalshi"], raw)
    assert [r["posting_id"] for r in rows] == ["kalshi:id1"]
    assert (rows[0]["department"], rows[0]["posted_date"], rows[0]["location"]) == ("Engineering", "2025-12-04", "New York Office")
    assert rows[0]["url"] == "https://jobs.ashbyhq.com/kalshi/id1"


def test_workday():
    raw = workday(("R267152", "Director Retail", "New York, NY"))
    row = convert(SRC["blackrock"], raw)[0]
    assert row["posting_id"] == "blackrock:R267152"
    assert (row["employer"], row["location"]) == ("BlackRock", "New York, NY")
    assert row["department"] == "" and row["posted_date"] == ""  # Workday's list gives neither
    assert row["url"] == "https://blackrock.wd1.myworkdayjobs.com/en-US/BlackRock_Professional/job/Somewhere/Director-Retail_R267152"


def test_workday_several_offices_become_one_label():
    assert workday_location("3 Locations") == "Multiple locations"
    assert workday_location("2 Locations") == "Multiple locations"
    assert workday_location("1 Location") == "Multiple locations"
    assert workday_location("New York, NY") == "New York, NY"
    assert workday_location("Locations Road, Leeds") == "Locations Road, Leeds"  # only the exact "N Locations" pattern
    row = convert(SRC["blackrock"], workday(("R1", "Analyst", "4 Locations")))[0]
    assert row["location"] == "Multiple locations"


def test_workday_ids():
    assert workday_id("/job/New-York-NY/Director--Retail---Multi-Channel_R267152") == "R267152"
    assert workday_id("/job/Lithuania---Vilnius/Junior-Software-Engineer_R0026959-1") == "R0026959-1"
    assert workday_id("/job/X/NoUnderscoreHere") == "NoUnderscoreHere"


def test_oracle():
    raw = oracle(("210807763", "Margin & Collateral Analyst", "Newark, DE, United States", "Margin&Collateral", "2026-11-07"))
    row = convert(SRC["jpmorgan"], raw)[0]
    assert row["posting_id"] == "jpmorgan:210807763"
    assert (row["employer"], row["department"], row["posted_date"]) == ("JPMorgan Chase", "Margin&Collateral", "2026-11-07")
    assert row["location"] == "Newark, DE, United States"
    assert row["url"] == "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210807763"


def test_smartrecruiters():
    raw = smartrecruiters(("744000160288009", "Fraud Prevention Specialist", "São Paulo", "br", "Data Management", "2026-11-06T19:41:34.221Z"))
    row = convert(SRC["experian"], raw)[0]
    assert row["posting_id"] == "experian:744000160288009"
    assert (row["location"], row["department"], row["posted_date"]) == ("São Paulo, BR", "Data Management", "2026-11-06")
    assert row["url"] == "https://jobs.smartrecruiters.com/Experian/744000160288009"


def test_every_posting_is_kept_not_only_ones_in_my_role():
    raw = greenhouse((1, "Financial Analyst", "NYC", None), (2, "Software Engineer", "SF", None))
    assert [r["title"] for r in convert(SRC["stripe"], raw)] == ["Financial Analyst", "Software Engineer"]


def test_a_posting_listed_twice_counts_once():
    raw = greenhouse((1, "A", "X", None), (1, "A", "X", None), (2, "B", "Y", None))
    assert [r["source_id"] for r in convert(SRC["stripe"], raw)] == ["1", "2"]


def test_missing_values_are_left_empty():
    raw = greenhouse((1, "A", None, None))
    row = convert(SRC["stripe"], raw)[0]
    assert row["location"] == "" and row["posted_date"] == ""


def test_utc_date():
    assert utc_date(None) == "" and utc_date("") == ""
    assert utc_date("2026-11-07") == "2026-11-07"
    assert utc_date("not a date") == ""
    assert utc_date("2026-11-06T19:41:34.221Z") == "2026-11-06"
