from __future__ import annotations

from datetime import date, timedelta

from .base import http_get, make_job, save_raw
from ..text import to_date

NAME = "openai"
LABEL = "OpenAI Careers"
URL = "https://openai.com/careers/"
NOTE = "Job board công khai của OpenAI (Ashby); giữ liên kết về tin gốc."

API = "https://api.ashbyhq.com/posting-api/job-board/openai"


def _location(item) -> str:
    places = [item.get("location") or ""]
    for place in item.get("secondaryLocations") or []:
        name = place.get("location") if isinstance(place, dict) else place
        if name:
            places.append(str(name))
    return ", ".join(dict.fromkeys(place for place in places if place))


def fetch():
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    payload = http_get(API)
    items = payload.get("jobs") or []
    save_raw(NAME, {"ids": [item.get("id") for item in items]})
    jobs = []
    for item in items:
        if item.get("isListed") is False:
            continue
        posted = to_date(item.get("publishedAt"))
        if posted and posted < cutoff:
            continue
        location = _location(item)
        remote = bool(item.get("isRemote")) or "remote" in (item.get("workplaceType") or "").lower()
        job = make_job(
            source=NAME,
            external_id=item.get("id"),
            url=item.get("jobUrl", ""),
            title=item.get("title", ""),
            company="OpenAI",
            location=("Remote · " + location) if remote and location else location,
            region="GLOBAL",
            remote=remote,
            employment_type=item.get("employmentType", ""),
            category=item.get("department") or item.get("team") or "",
            tags=[item.get("team") or "", item.get("department") or ""],
            description=item.get("descriptionHtml") or item.get("descriptionPlain", ""),
            posted_at=posted,
            raw={"id": item.get("id"), "team": item.get("team"), "department": item.get("department")},
        )
        if job:
            jobs.append(job)
    return jobs
