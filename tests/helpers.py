"""Small builders for fake job boards, so tests need no network. Shapes copied from the real boards."""

import json

from watcher.sources import SOURCES

SRC = {s.name: s for s in SOURCES}


def dump(data):
    return json.dumps(data).encode()


def greenhouse(*jobs):
    """jobs: (id, title, location, first_published)"""
    return dump({"jobs": [
        {"id": i, "title": t, "location": {"name": loc}, "first_published": pub, "absolute_url": f"https://boards.example/gh/{i}"}
        for i, t, loc, pub in jobs], "meta": {"total": len(jobs)}})


def lever(*jobs):
    """jobs: (id, title, location, department, createdAt in ms)"""
    return dump([
        {"id": i, "text": t, "categories": {"location": loc, "department": dep, "team": "Team"}, "createdAt": ms,
         "hostedUrl": f"https://jobs.lever.co/wealthfront/{i}"} for i, t, loc, dep, ms in jobs])


def ashby(*jobs, unlisted=()):
    """jobs: (id, title, location, department, publishedAt)"""
    listed = [{"id": i, "title": t, "location": loc, "department": dep, "publishedAt": pub, "isListed": True,
               "jobUrl": f"https://jobs.ashbyhq.com/kalshi/{i}"} for i, t, loc, dep, pub in jobs]
    hidden = [{"id": i, "title": "Hidden", "location": "", "department": "", "publishedAt": None, "isListed": False,
               "jobUrl": f"https://jobs.ashbyhq.com/kalshi/{i}"} for i in unlisted]
    return dump({"jobs": listed + hidden, "apiVersion": "1"})


def workday_posting(req, title, location):
    return {"title": title, "externalPath": f"/job/Somewhere/{title.replace(' ', '-')}_{req}", "locationsText": location,
            "postedOn": "Posted 2 Days Ago", "bulletFields": [req]}


def workday(*postings):
    return dump({"total": len(postings), "jobPostings": [workday_posting(*p) for p in postings]})


def oracle(*jobs, keyword="analyst"):
    """jobs: (id, title, location, job family, posted date)"""
    return dump({"total": len(jobs), "keyword": keyword, "requisitionList": [
        {"Id": i, "Title": t, "PrimaryLocation": loc, "JobFamily": fam, "PostedDate": d} for i, t, loc, fam, d in jobs]})


def smartrecruiters(*jobs):
    """jobs: (id, name, city, country, department, releasedDate)"""
    return dump({"totalFound": len(jobs), "content": [
        {"id": i, "name": n, "location": {"city": city, "country": country}, "department": {"label": dep},
         "releasedDate": rel} for i, n, city, country, dep, rel in jobs]})


class FakeHttp:
    """Answers requests from a dict {part of the url: bytes or Exception}. Pages Workday, Oracle and
    SmartRecruiters the way the real servers do (Workday: the total only on the first page)."""

    def __init__(self, answers):
        self.answers = answers
        self.requests = []

    def _answer(self, url):
        for part, answer in self.answers.items():
            if part in url:
                if isinstance(answer, Exception):
                    raise answer
                return answer
        raise AssertionError(f"unexpected url {url}")

    def get(self, url):
        self.requests.append(url)
        body = self._answer(url)
        if "recruitingCEJobRequisitions" in url:  # Oracle: 25 a page
            full = json.loads(body)
            offset = int(url.split("offset=")[1].split(",")[0])
            return dump({"items": [{"TotalJobsCount": full["total"], "requisitionList": full["requisitionList"][offset:offset + 25]}]})
        if "smartrecruiters" in url:  # 100 a page
            full = json.loads(body)
            offset = int(url.split("offset=")[1])
            return dump({"totalFound": full["totalFound"], "content": full["content"][offset:offset + 100]})
        return body

    def post_json(self, url, payload):  # Workday: 20 a page
        self.requests.append((url, payload))
        full = json.loads(self._answer(url))
        offset = payload["offset"]
        return dump({"total": full["total"] if offset == 0 else 0, "jobPostings": full["jobPostings"][offset:offset + 20]})
