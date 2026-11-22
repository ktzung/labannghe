from __future__ import annotations

from datetime import date, timedelta

from .base import http_get, make_job, save_raw
from ..text import to_date

NAME = "anthropic"
LABEL = "Anthropic Careers"
URL = "https://www.anthropic.com/careers"
NOTE = "Job board công khai của Anthropic (Greenhouse); giữ liên kết về tin gốc."

API = "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs"


def _meta(item, name: str) -> str:
    for entry in item.get("metadata") or []:
        if str(entry.get("name", "")).lower() == name.lower():
            return str(entry.get("value") or "")
    return ""


def fetch():
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    payload = http_get(API, params={"content": "true"})
    items = payload.get("jobs") or []
    save_raw(NAME, {"ids": [item.get("id") for item in items]})
    jobs = []
    for item in items:
        posted = to_date(item.get("first_published") or item.get("updated_at"))
        if posted and posted < cutoff:
            continue
        location = (item.get("location") or {}).get("name", "")
        location_type = _meta(item, "Location Type")
        remote = "remote" in location_type.lower() or "remote" in location.lower()
        job = make_job(
            source=NAME,
            external_id=item.get("id"),
            url=item.get("absolute_url", ""),
            title=item.get("title", ""),
            company="Anthropic",
            location=location,
            region="GLOBAL",
            remote=remote,
            employment_type=_meta(item, "Employment Type"),
            description=item.get("content", ""),
            posted_at=posted,
            raw={"id": item.get("id"), "requisition": item.get("requisition_id")},
        )
        if job:
            jobs.append(job)
    return jobs
