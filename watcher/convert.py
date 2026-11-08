"""Turn one employer's raw job board into rows with the common columns.

Every posting the board returns is kept. Columns a board does not give are left empty
(Greenhouse gives no department, Workday gives no department or posted date).
"""

import json
import re
from datetime import datetime, timezone

# What every converter gives for a posting. The history build adds in_role and the lifecycle columns.
POSTING_COLUMNS = ["posting_id", "source", "source_id", "employer", "title", "location", "department", "posted_date", "url"]


def clean(value):
    """Text with extra white space removed; None becomes empty."""
    return re.sub(r"\s+", " ", str(value)).strip() if value not in (None, "") else ""


def utc_date(value):
    """A UTC date (YYYY-MM-DD) from an ISO timestamp, a date, or milliseconds since 1970. Empty if unknown."""
    if value in (None, ""):
        return ""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
        text = str(value)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return ""


def posting(source, source_id, title, location="", department="", posted_date="", url=""):
    source_id = clean(source_id)
    return {
        "posting_id": f"{source.name}:{source_id}",
        "source": source.name,
        "source_id": source_id,
        "employer": source.employer,
        "title": clean(title),
        "location": clean(location),
        "department": clean(department),
        "posted_date": posted_date,
        "url": clean(url),
    }


def load(raw):
    return json.loads(raw) if isinstance(raw, (bytes, str)) else raw


def convert_greenhouse(source, raw):
    """Greenhouse: {"jobs": [{id, title, location: {name}, first_published, absolute_url}]}"""
    return [
        posting(source, job["id"], job.get("title"), (job.get("location") or {}).get("name"), "",
                utc_date(job.get("first_published")), job.get("absolute_url"))
        for job in load(raw)["jobs"]
    ]


def convert_lever(source, raw):
    """Lever: a list of {id, text, categories: {location, department, team}, createdAt, hostedUrl}"""
    rows = []
    for job in load(raw):
        categories = job.get("categories") or {}
        rows.append(posting(source, job["id"], job.get("text"), categories.get("location"),
                            categories.get("department") or categories.get("team"),
                            utc_date(job.get("createdAt")), job.get("hostedUrl")))
    return rows


def convert_ashby(source, raw):
    """Ashby: {"jobs": [{id, title, location, department, publishedAt, jobUrl, isListed}]}"""
    return [
        posting(source, job["id"], job.get("title"), job.get("location"), job.get("department"),
                utc_date(job.get("publishedAt")), job.get("jobUrl"))
        for job in load(raw)["jobs"]
        if job.get("isListed", True)  # unlisted jobs are not on the public board
    ]


def workday_id(external_path):
    """'/job/New-York-NY/Director_R267152' -> 'R267152' (the requisition number)."""
    last = external_path.rstrip("/").rsplit("/", 1)[-1]
    match = re.search(r"_([^_]+)$", last)
    return match.group(1) if match else last


def convert_workday(source, raw):
    """Workday: {"total", "jobPostings": [{title, externalPath, locationsText}]} (all pages merged)"""
    rows = []
    for job in load(raw)["jobPostings"]:
        path = job["externalPath"]
        url = f"https://{source.board}.{source.host}.myworkdayjobs.com/en-US/{source.site}{path}"
        rows.append(posting(source, workday_id(path), job.get("title"), job.get("locationsText"), "", "", url))
    return rows


def convert_oracle(source, raw):
    """Oracle Recruiting: {"total", "requisitionList": [{Id, Title, PrimaryLocation, JobFamily, PostedDate}]}"""
    return [
        posting(source, job["Id"], job.get("Title"), job.get("PrimaryLocation"), job.get("JobFamily"),
                utc_date(job.get("PostedDate")),
                f"https://{source.host}/hcmUI/CandidateExperience/en/sites/{source.site}/job/{job['Id']}")
        for job in load(raw)["requisitionList"]
    ]


def convert_smartrecruiters(source, raw):
    """SmartRecruiters: {"totalFound", "content": [{id, name, location, department, releasedDate}]}"""
    rows = []
    for job in load(raw)["content"]:
        where = job.get("location") or {}
        parts = [where.get("city"), where.get("region"), (where.get("country") or "").upper()]
        rows.append(posting(source, job["id"], job.get("name"), ", ".join(p for p in parts if p),
                            (job.get("department") or {}).get("label"), utc_date(job.get("releasedDate")),
                            f"https://jobs.smartrecruiters.com/{source.board}/{job['id']}"))
    return rows


CONVERTERS = {
    "greenhouse": convert_greenhouse,
    "lever": convert_lever,
    "ashby": convert_ashby,
    "workday": convert_workday,
    "oracle": convert_oracle,
    "smartrecruiters": convert_smartrecruiters,
}


def convert(source, raw):
    """Convert one raw file of this source into posting rows (one per posting, no duplicates)."""
    seen, rows = set(), []
    for row in CONVERTERS[source.ats](source, raw):
        if row["posting_id"] not in seen:  # a board that lists a posting twice still counts it once
            seen.add(row["posting_id"])
            rows.append(row)
    return rows
