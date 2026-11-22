from __future__ import annotations

from datetime import date, datetime, timedelta

from .base import http_get, make_job, polite_sleep, save_raw
from ..text import to_date

NAME = "netflix"
LABEL = "Netflix Careers"
URL = "https://explore.jobs.netflix.net/careers"
NOTE = "API công khai của trang tuyển dụng Netflix; mô tả lấy từ trang chi tiết."

API = "https://explore.jobs.netflix.net/api/apply/v2/jobs"


def _posting_date(value):
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%m-%d-%Y").date().isoformat()
    except ValueError:
        return None


def fetch(limit: int = 15):
    cutoff = (date.today() - timedelta(days=45)).isoformat()
    payload = http_get(
        API,
        params={"domain": "netflix.com", "start": 0, "num": limit, "sort_by": "recent"},
    )
    positions = (payload.get("positions") or [])[:limit]
    save_raw(NAME, {"ids": [item.get("id") for item in positions]})
    jobs = []
    for item in positions:
        job_id = item.get("id")
        if not job_id:
            continue
        try:
            polite_sleep()
            detail = http_get(API + "/%s" % job_id, params={"domain": "netflix.com"})
        except Exception:  # noqa: BLE001
            detail = {}
        fields = ((detail.get("custom_JD") or {}).get("data_fields") or {})
        posted = _posting_date((fields.get("posting_date") or [None])[0]) or to_date(
            detail.get("t_create") or item.get("t_create")
        )
        if posted and posted < cutoff:
            continue
        locations = detail.get("locations") or item.get("locations") or []
        location = ", ".join(str(place) for place in locations if place) or item.get("location", "")
        method = (detail.get("work_location_option") or item.get("work_location_option") or "").lower()
        job = make_job(
            source=NAME,
            external_id=job_id,
            url=detail.get("canonicalPositionUrl") or item.get("canonicalPositionUrl", ""),
            title=detail.get("name") or item.get("name", ""),
            company="Netflix",
            location=location,
            region="GLOBAL",
            remote="remote" in method or "remote" in location.lower(),
            employment_type="Full-time" if item.get("type") == "ATS" else item.get("type", ""),
            category=detail.get("department") or item.get("department", ""),
            description=detail.get("job_description", ""),
            posted_at=posted,
            raw={"id": job_id, "business_unit": item.get("business_unit")},
        )
        if job:
            jobs.append(job)
    return jobs
