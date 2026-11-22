from __future__ import annotations

from datetime import date, datetime, timedelta

from .base import http_get, make_job, save_raw

NAME = "amazon"
LABEL = "Amazon Careers"
URL = "https://www.amazon.jobs"
NOTE = "API tìm kiếm công khai của Amazon; tin mới toàn cầu và toàn bộ tin đang tuyển tại Việt Nam."

API = "https://www.amazon.jobs/en/search.json"
_ORIGIN = "https://www.amazon.jobs"


def _posted_date(value):
    text = str(value or "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _requirements(item) -> str:
    parts = []
    for label, key in (("Yêu cầu cơ bản", "basic_qualifications"), ("Ưu tiên", "preferred_qualifications")):
        text = item.get(key) or ""
        if text:
            parts.append("%s:\n%s" % (label, text))
    return "\n\n".join(parts)


def _tags(item):
    labels = item.get("optional_search_labels") or []
    if isinstance(labels, str):
        labels = [labels]
    return [str(label) for label in labels if label]


def fetch():
    cutoff = (date.today() - timedelta(days=45)).isoformat()
    found = {}
    for country, tag in (("", "global"), ("VNM", "vn")):
        params = {"base_query": "", "result_limit": 100, "sort": "recent"}
        if country:
            params["country"] = country
        payload = http_get(API, params=params)
        items = payload.get("jobs") or []
        save_raw("%s-%s" % (NAME, tag), {"ids": [item.get("id") for item in items]})
        for item in items:
            posted = _posted_date(item.get("posted_date"))
            if posted and posted < cutoff:
                continue
            location = item.get("normalized_location") or item.get("location") or ""
            job = make_job(
                source=NAME,
                external_id=item.get("id"),
                url=_ORIGIN + (item.get("job_path") or ""),
                title=item.get("title", ""),
                company=item.get("company_name", "Amazon"),
                location=location,
                country="Việt Nam" if country else item.get("country_code") or "",
                region="VN" if country else "GLOBAL",
                remote="remote" in location.lower() or "virtual" in location.lower(),
                employment_type=item.get("job_schedule_type", ""),
                category=item.get("job_category", ""),
                tags=_tags(item),
                description=item.get("description", ""),
                requirements=_requirements(item),
                posted_at=posted,
                raw={
                    "id": item.get("id"),
                    "category": item.get("job_category"),
                    "team": item.get("team"),
                    "posted": item.get("posted_date"),
                },
            )
            if job:
                found[job["external_id"]] = job
    return list(found.values())
