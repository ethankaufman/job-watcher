"""The employers we watch, and the code that reads one employer's job board."""

import gzip
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from watcher.convert import convert

MAX_POSTINGS = 5000  # a board with more postings than this must be requested with a search term
PAGE_PAUSE = 0.1  # seconds between two pages of the same board, to be polite


@dataclass(frozen=True)
class Source:
    name: str  # file name (data/raw/<date>/<name>.json.gz) and the "source" column
    employer: str  # shown on the site
    ats: str  # the applicant tracking system: greenhouse, lever, ashby, workday, oracle, smartrecruiters
    board: str  # the employer's id on that system
    site: str = ""  # Workday: the career site name. Oracle: the site number
    host: str = ""  # Workday: the server ("wd12"). Oracle: the full host name
    term: str = ""  # search term, used when the whole board has more than 5,000 postings


SOURCES = [
    # Greenhouse
    Source("stripe", "Stripe", "greenhouse", "stripe"),
    Source("coinbase", "Coinbase", "greenhouse", "coinbase"),
    Source("robinhood", "Robinhood", "greenhouse", "robinhood"),
    Source("brex", "Brex", "greenhouse", "brex"),
    Source("affirm", "Affirm", "greenhouse", "affirm"),
    Source("chime", "Chime", "greenhouse", "chime"),
    Source("sofi", "SoFi", "greenhouse", "sofi"),
    Source("block", "Block", "greenhouse", "block"),
    Source("carta", "Carta", "greenhouse", "carta"),
    Source("betterment", "Betterment", "greenhouse", "betterment"),
    Source("janestreet", "Jane Street", "greenhouse", "janestreet"),
    Source("point72", "Point72", "greenhouse", "point72"),
    Source("imc", "IMC Trading", "greenhouse", "imc"),
    # Lever
    Source("wealthfront", "Wealthfront", "lever", "wealthfront"),
    Source("anchorage", "Anchorage Digital", "lever", "anchorage"),
    # Ashby
    Source("ramp", "Ramp", "ashby", "ramp"),
    Source("plaid", "Plaid", "ashby", "plaid"),
    Source("kalshi", "Kalshi", "ashby", "kalshi"),
    Source("polymarket", "Polymarket", "ashby", "polymarket"),
    # Workday
    Source("capitalone", "Capital One", "workday", "capitalone", site="Capital_One", host="wd12"),
    Source("blackrock", "BlackRock", "workday", "blackrock", site="BlackRock_Professional", host="wd1"),
    Source("mastercard", "Mastercard", "workday", "mastercard", site="CorporateCareers", host="wd1"),
    Source("statestreet", "State Street", "workday", "statestreet", site="Global", host="wd1"),
    Source("fidelity", "Fidelity Investments", "workday", "fmr", site="FidelityCareers", host="wd1"),
    Source("paypal", "PayPal", "workday", "paypal", site="jobs", host="wd1"),
    # Oracle Recruiting (7,000+ postings, so it is requested with a search term)
    Source("jpmorgan", "JPMorgan Chase", "oracle", "jpmc", site="CX_1001", host="jpmc.fa.oraclecloud.com", term="analyst"),
    # SmartRecruiters
    Source("experian", "Experian", "smartrecruiters", "Experian"),
]
SOURCE_NAMES = [s.name for s in SOURCES]


class Http:
    """The two kinds of request we make. Each is tried a few times before giving up."""

    def __init__(self, attempts=3, timeout=45):
        self.attempts = attempts
        self.timeout = timeout

    def get(self, url):
        return self._send(url, None)

    def post_json(self, url, payload):
        return self._send(url, json.dumps(payload).encode())

    def _send(self, url, body):
        headers = {"User-Agent": "job-watcher (student project)", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        last_error = None
        for attempt in range(self.attempts):
            try:
                request = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read()
            except Exception as error:  # network errors, HTTP errors, timeouts
                last_error = error
                time.sleep(2 * (attempt + 1))
        raise last_error


def dumps(data):
    return json.dumps(data, separators=(",", ":")).encode()


# ----- one fetcher per applicant tracking system: they return the raw JSON bytes to save -----


def fetch_greenhouse(source, http):
    return http.get(f"https://boards-api.greenhouse.io/v1/boards/{source.board}/jobs")


def fetch_lever(source, http):
    return http.get(f"https://api.lever.co/v0/postings/{source.board}?mode=json")


def fetch_ashby(source, http):
    return http.get(f"https://api.ashbyhq.com/posting-api/job-board/{source.board}")


def fetch_workday(source, http):
    """Workday gives 20 postings a page (and the total only on the first page). The pages are merged."""
    url = f"https://{source.board}.{source.host}.myworkdayjobs.com/wday/cxs/{source.board}/{source.site}/jobs"
    postings, total = [], None
    while total is None or len(postings) < total:
        page = json.loads(http.post_json(url, {"appliedFacets": {}, "limit": 20, "offset": len(postings), "searchText": source.term}))
        if total is None:
            total = page["total"]
            if total > MAX_POSTINGS:
                raise ValueError(f"{total} postings is over the {MAX_POSTINGS} limit: set a search term")
        batch = page.get("jobPostings", [])
        if not batch:
            raise ValueError(f"the board stopped after {len(postings)} of {total} postings")
        postings += batch
        time.sleep(PAGE_PAUSE)
    return dumps({"total": total, "jobPostings": postings})


def fetch_oracle(source, http):
    """Oracle Recruiting gives 25 postings a page. The pages are merged."""
    keyword = f",keyword={urllib.parse.quote(source.term)}" if source.term else ""
    url = (f"https://{source.host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true"
           "&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={site},limit=25,offset={offset}{keyword},sortBy=POSTING_DATES_DESC")
    requisitions, total = [], None
    while total is None or len(requisitions) < total:
        page = json.loads(http.get(url.format(site=source.site, offset=len(requisitions), keyword=keyword)))["items"][0]
        if total is None:
            total = page["TotalJobsCount"]
            if total > MAX_POSTINGS:
                raise ValueError(f"{total} postings is over the {MAX_POSTINGS} limit: set a search term")
        batch = page.get("requisitionList", [])
        if not batch:
            raise ValueError(f"the board stopped after {len(requisitions)} of {total} postings")
        requisitions += batch
        time.sleep(PAGE_PAUSE)
    return dumps({"total": total, "keyword": source.term, "requisitionList": requisitions})


def fetch_smartrecruiters(source, http):
    """SmartRecruiters gives up to 100 postings a page. The pages are merged."""
    jobs, total = [], None
    while total is None or len(jobs) < total:
        page = json.loads(http.get(f"https://api.smartrecruiters.com/v1/companies/{source.board}/postings?limit=100&offset={len(jobs)}"))
        if total is None:
            total = page["totalFound"]
            if total > MAX_POSTINGS:
                raise ValueError(f"{total} postings is over the {MAX_POSTINGS} limit: set a search term")
        batch = page.get("content", [])
        if not batch:
            raise ValueError(f"the board stopped after {len(jobs)} of {total} postings")
        jobs += batch
        time.sleep(PAGE_PAUSE)
    return dumps({"totalFound": total, "content": jobs})


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
    "oracle": fetch_oracle,
    "smartrecruiters": fetch_smartrecruiters,
}


def raw_path(raw_dir, day, source_name):
    return Path(raw_dir) / day / f"{source_name}.json.gz"


def fetch_source(source, day, raw_dir, http=None):
    """Read one employer's board and save it as data/raw/<day>/<name>.json.gz.

    Returns {"name", "employer", "ats", "ok", "count", "error"}. Never raises. A source that
    fails (or returns no postings, or more than 5,000) writes no raw file: a missing file means
    "unknown today", so nothing is marked removed because of it. An older file for the same day
    is left alone.
    """
    result = {"name": source.name, "employer": source.employer, "ats": source.ats, "ok": False, "count": 0, "error": None}
    try:
        body = FETCHERS[source.ats](source, http or Http())
        count = len(convert(source, body))  # check the answer is usable before keeping it
        if count == 0:
            raise ValueError("the board returned no postings")
        if count > MAX_POSTINGS:
            raise ValueError(f"{count} postings is over the {MAX_POSTINGS} limit: set a search term")
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        return result

    path = raw_path(raw_dir, day, source.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(gzip.compress(body, mtime=0))  # mtime=0: same input, same bytes
    temp.replace(path)  # replaces any file from an earlier run the same day
    result.update(ok=True, count=count)
    return result


def fetch_all(day, raw_dir, http=None, sources=SOURCES, workers=6):
    """Read every board (several at a time). One failing source does not stop the others."""
    http = http or Http()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda source: fetch_source(source, day, raw_dir, http), sources))
