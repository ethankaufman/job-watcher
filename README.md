# Finance Job Watcher

[![Tests](https://github.com/ethankaufman/job-watcher/actions/workflows/tests.yml/badge.svg)](https://github.com/ethankaufman/job-watcher/actions/workflows/tests.yml)

Once a day, a GitHub Action reads the public job boards of 27 finance and fintech employers, compares
them with the day before, records every posting (when it first appeared, when it was last listed, when it
disappeared), opens a GitHub Issue listing the new and removed postings with links, and publishes the
result to a website.

**Live site:** https://ethankaufman.github.io/job-watcher/ (installable as an app, works offline)

Project for Financial Data Analytics (Job Watcher Project).

**My role:** analyst jobs in finance and data (financial analyst, data analyst, FP&A, business
intelligence, credit and risk analyst, and similar). The tool keeps *every* posting a board returns and
marks each one as in my role or not with the title rule below.

## Sources

Each employer is one source. The tool reads each employer's job board through the applicant tracking
system (ATS) that hosts it, and every board returns JSON to a request with no login (no HTML is read).
The employers are in `watcher/sources.py`.

| Source name | Employer | ATS | Board |
|---|---|---|---|
| `stripe` | Stripe | Greenhouse | `stripe` |
| `coinbase` | Coinbase | Greenhouse | `coinbase` |
| `robinhood` | Robinhood | Greenhouse | `robinhood` |
| `brex` | Brex | Greenhouse | `brex` |
| `affirm` | Affirm | Greenhouse | `affirm` |
| `chime` | Chime | Greenhouse | `chime` |
| `sofi` | SoFi | Greenhouse | `sofi` |
| `block` | Block | Greenhouse | `block` |
| `carta` | Carta | Greenhouse | `carta` |
| `betterment` | Betterment | Greenhouse | `betterment` |
| `janestreet` | Jane Street | Greenhouse | `janestreet` |
| `point72` | Point72 | Greenhouse | `point72` |
| `imc` | IMC Trading | Greenhouse | `imc` |
| `wealthfront` | Wealthfront | Lever | `wealthfront` |
| `anchorage` | Anchorage Digital | Lever | `anchorage` |
| `ramp` | Ramp | Ashby | `ramp` |
| `plaid` | Plaid | Ashby | `plaid` |
| `kalshi` | Kalshi | Ashby | `kalshi` |
| `polymarket` | Polymarket | Ashby | `polymarket` |
| `capitalone` | Capital One | Workday | `capitalone.wd12` / `Capital_One` |
| `blackrock` | BlackRock | Workday | `blackrock.wd1` / `BlackRock_Professional` |
| `mastercard` | Mastercard | Workday | `mastercard.wd1` / `CorporateCareers` |
| `statestreet` | State Street | Workday | `statestreet.wd1` / `Global` |
| `fidelity` | Fidelity Investments | Workday | `fmr.wd1` / `FidelityCareers` |
| `paypal` | PayPal | Workday | `paypal.wd1` / `jobs` |
| `jpmorgan` | JPMorgan Chase | Oracle Recruiting | `jpmc.fa.oraclecloud.com`, site `CX_1001`, **search term `analyst`** |
| `experian` | Experian | SmartRecruiters | `Experian` |

The endpoints:

* **Greenhouse:** `https://boards-api.greenhouse.io/v1/boards/<board>/jobs`
* **Lever:** `https://api.lever.co/v0/postings/<board>?mode=json`
* **Ashby:** `https://api.ashbyhq.com/posting-api/job-board/<board>`
* **Workday:** `POST https://<tenant>.<server>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` (20 postings a page)
* **Oracle Recruiting:** `https://<host>/hcmRestApi/resources/latest/recruitingCEJobRequisitions?...finder=findReqs;siteNumber=<site>,limit=25,offset=<n>,keyword=<term>`
* **SmartRecruiters:** `https://api.smartrecruiters.com/v1/companies/<board>/postings?limit=100&offset=<n>`

**The search term.** A board that returns more than 5,000 postings must be requested with a search term.
JPMorgan Chase's board holds more than 7,000 postings, so it is requested with the term **`analyst`**
(about 1,000 postings). Its numbers therefore cover analyst-type jobs only. A board over 5,000 postings
with no term set is treated as a failure.

**Raw files.** `data/raw/<date>/<source>.json.gz` holds what the board returned, compressed. Boards that
come in pages (Workday, Oracle, SmartRecruiters) are merged into one JSON file with the same fields
(Workday's page-by-page filters and counts are not kept). A source that fails (error, no postings, or a
board that stops half way) writes no raw file that day.

## The title rule

A posting is **in my role** (`in_role = true`) when its title, compared in lower case,

1. contains the word **analyst** together with at least one of these words: `financ`, `data`,
   `business`, `credit`, `risk`, `investment`, `quantitative`, `quant`, `strategy`, `strategic`,
   `pricing`, `treasury`, `planning`, `portfolio`, `research`, `market`, `reporting`, `analytics`,
   `fraud`, `underwriting`, `accounting`, `economic`, `valuation`, `equity`, `capital`, `revenue`,
   `forecast` — **or** contains **FP&A** (or `FPA`) or **business intelligence**; and
2. contains **none** of: `cyber`, `security`, `threat`, `siem`, `soc analyst`, `help desk`, `helpdesk`,
   `systems analyst`, `it analyst`, `network`, `devops`, `infrastructure`.

So "Financial Analyst", "Senior Data Analyst, Payments", "Summer Analyst, Investment Banking" and
"FP&A Manager" are in my role; "Software Engineer", "Security Analyst", "Systems Analyst, Finance" and
"Analyst, Facilities" are not. The rule is in `watcher/rules.py`, with tests.

## The history file: `data/history.csv`

One row per posting, sorted by `posting_id`. Dates are UTC dates (`YYYY-MM-DD`). A column a source does
not provide is left empty for that source's rows.

| Column | Meaning |
|---|---|
| `posting_id` | `<source>:<source_id>`, which identifies the posting from day to day |
| `source` | The source name (the employer's board), e.g. `stripe` |
| `source_id` | The board's own ID for the posting (Workday: the requisition number) |
| `employer` | The employer's name |
| `title` | The posting's title (the latest one seen) |
| `location` | The location text (Workday's "3 Locations" is stored as `Multiple locations`) |
| `department` | Department or job family. Empty for Greenhouse and Workday, which do not give it in their lists |
| `posted_date` | The date the employer posted it, when the board says. Empty for Workday |
| `url` | Link to the posting, to apply |
| `in_role` | `true` or `false`: does the title match the title rule |
| `first_run` | `true` for a posting listed in the first raw file of its source: it was already open when watching began, so its real start is unknown |
| `first_seen` | The first day the posting was listed |
| `last_seen` | The latest day the source listed it |
| `status` | `open` or `removed` |
| `removed_date` | The day it was marked removed. Empty while open |

**How the build works.** `python -m watcher.history` replays the raw days oldest first. For every source
that has a raw file on a day:

* a posting seen for the first time gets that day as `first_seen`;
* every posting the source lists gets that day as `last_seen`;
* an open posting the source no longer lists is marked `removed`, with that day as `removed_date`;
* a removed posting the source lists again becomes `open` again: `removed_date` is cleared and `first_seen`
  stays the same.

A source with no raw file on a day (it failed) changes nothing that day: nothing is marked removed
because a board could not be read.

### Rebuild the history from the raw files

```
python -m watcher.history
```

The history depends on the raw files alone, so this always gives the same `data/history.csv`. If a rule
changes (the title rule, a conversion), running it applies the change to every day.

## The status file: `data/status.json`

Describes the latest run. Keys: `run_time` (UTC), `first_run_date` (the date of the earliest raw file),
`days_with_success` (the number of different dates with a raw file), `open` (the number of open
postings), `new_today` (postings first seen in the latest run, leaving out first-run postings),
`removed_today` (postings removed in the latest run), and `sources`: one entry per source with `name`,
`ok`, `count` (how many postings it listed) and also `employer`, `ats` and, when it failed, `error`.

## How a run works

The daily workflow (`.github/workflows/daily.yml`) runs `python -m watcher.run` once a day at 07:23 UTC,
and can also be started by hand from the Actions tab.

1. **Read the boards.** Every source is read (several at a time) and saved as
   `data/raw/<date>/<source>.json.gz`. One failing source does not stop the run; the result of every
   source goes in `status.json`.
2. **Build** `data/history.csv` from all the raw files.
3. **Status:** `data/status.json` is written.
4. **Issue.** A GitHub Issue titled with the date lists the new postings and the removed postings, each
   with a link (postings in my role first, marked ★), and says which sources failed. The previous day's
   issue is closed. The issue is opened every day, even when nothing changed. A very long list is cut to
   fit GitHub's size limit and says how many more there are.
5. **Commit.** The workflow commits the raw files, the history and the status.

A run is successful when it finishes and commits, even if some sources failed. A second run on the same
UTC day replaces that day's raw files, rebuilds the history and updates that day's issue, so each day
counts once. (If a source fails on the second run, the file from the first run is kept.)

## The site

Plain HTML, CSS and JavaScript (no build step), published with GitHub Pages from the `main` branch. The
pages load `data/status.json` and `data/history.csv` in the browser and do every calculation there. All
pages share one navigation bar (`assets/ui.mjs`) and one stylesheet (`assets/style.css`).

| Page | What it shows |
|---|---|
| `index.html` (Today) | Time of the last run, the status of every source, the four counts from `status.json` (days with a successful run, open, new today, removed today), and the lists of new and removed postings in the latest run, each with a link |
| `browse.html` (Browse) | The open postings. A switch between postings in my role (the default) and all postings; filters for employer, location and days open; a title search; a sort by first-seen date (and other columns); an apply link on every posting; a star on every posting that saves it to a shortlist in the browser (it is still there after a reload) |
| `market.html` (Market) | Six sections, each with a heading that states the finding, a paragraph, and a chart (plus a table of the numbers): new postings per day, removed postings per day, open postings per employer, days open (median), the share removed within seven days, and top locations among open postings |
| `guide.html` (Guide) | Plain-language explanation of the title rule, the words used, each page, each Market section, and the limits of the data |

The Market definitions follow the assignment. A posting with `first_run = true` was already open when
watching began, so its start date is unknown and it is left out of "new postings per day", "days open"
and "share removed within seven days". The calculations are in `assets/stats.mjs`. A test
(`tests/test_market_numbers.py`) runs them with Node on a history file and compares every number with a
separate calculation in Python, so the page cannot drift away from the history file.

**Installable and offline.** `manifest.webmanifest` and `sw.js` (a service worker) make the site
installable from the browser. When the computer is online, every page and data file is loaded from the
network (and a copy is saved). When it is offline, the saved copies are used, so the site still opens and
shows the last data it loaded.

### Run the site on your own computer

```
python3 -m http.server 8000
```

then open http://localhost:8000. (Opening the files directly does not work: browsers only allow the data
files to be loaded through a web server.)

## Health check

A second workflow (`.github/workflows/health.yml`) runs `python -m watcher.health` every day at 12:10 UTC,
after the daily run. It reads `data/status.json` and the latest daily workflow runs and checks that the
last run is less than 30 hours old, that the latest daily workflow run succeeded, that no source failed, and
that there is still time to reach 7 days with data before the due date. If anything is wrong it opens a
GitHub Issue labelled `health-check` that says what, and the check fails (so GitHub sends a
notification). When everything is fine again the issue is closed. The daily issues (one per date, labelled
`daily-report`) are separate and are not touched by this check.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

GitHub Actions runs the tests on every push. They cover the conversion of each source (all six systems) to
the common columns, the title rule, the first-seen, last-seen, removed and reopened logic, the status file,
the daily issue, a second run on the same day, a failed source, and that the Market numbers agree with the
history file (this one needs Node.js).

## Files

| File | What it does |
|---|---|
| `watcher/sources.py` | The 27 employers, and the code that reads one board (a reader for each of the six systems) and saves the raw file |
| `watcher/convert.py` | Turns one raw file into rows with the common columns, for each system |
| `watcher/rules.py` | The title rule: is a posting in my role |
| `watcher/history.py` | Builds `data/history.csv` from the raw files (`python -m watcher.history`) |
| `watcher/status.py` | Builds `data/status.json` |
| `watcher/report.py` | Writes the text of the daily issue |
| `watcher/issues.py` | Opens today's issue, updates it on a second run, closes the previous day's |
| `watcher/health.py` | The daily health check: is the pipeline running and are the sources working (`python -m watcher.health`) |
| `watcher/run.py` | The daily run that ties the steps together (`python -m watcher.run`) |
| `tests/` | The pytest suite |
| `watcher/__init__.py` | Marks `watcher/` as a Python package (no code) |
| `README.md` | This file |
| `.gitignore` | Files git should not track (the local test environment and caches) |
| `.github/workflows/daily.yml` | The daily run: read the boards, build, issue, commit |
| `.github/workflows/tests.yml` | Runs the tests on every push |
| `.github/workflows/health.yml` | The daily health check, which opens an issue when something is wrong |
| `data/raw/<date>/<source>.json.gz` | The raw answers, compressed, one folder per day |
| `data/history.csv` | The history, one row per posting |
| `data/status.json` | Describes the latest run |
| `index.html`, `browse.html`, `market.html`, `guide.html` | The pages of the site |
| `assets/style.css` | The look shared by all pages |
| `assets/ui.mjs` | Shared page code: navigation bar, formats, the shortlist, "Install app" button |
| `assets/data.mjs` | Loads and parses `status.json` and `history.csv` |
| `assets/stats.mjs` | Every calculation the pages show, as plain functions |
| `assets/charts.mjs` | The line, bar and column charts, tooltips and "show the numbers" tables |
| `assets/today.mjs`, `assets/browse.mjs`, `assets/market.mjs` | The code of each page (the Guide is plain HTML) |
| `manifest.webmanifest` | Web app manifest (name, colours, icons) so the site can be installed |
| `sw.js` | Service worker: saves copies of the pages and data so the site opens offline |
| `icons/` | The app icons (`icon.svg`, and PNGs made by `tools/make_icons.py`) |
| `tools/make_icons.py` | Draws the PNG app icons with only the Python standard library |
| `tools/market_numbers.mjs` | Prints the numbers the pages compute from a history file (used by a test) |
| `requirements-dev.txt` | Test dependency (the pipeline itself uses only the Python standard library) |
