from __future__ import annotations

from .base import http_get, make_job, save_raw

NAME = "jobicy"
LABEL = "Jobicy"
URL = "https://jobicy.com"
NOTE = "API công khai cho remote jobs; giữ ghi công Jobicy."


def fetch(limit: int = 100):
    payload = http_get(
        "https://jobicy.com/api/v2/remote-jobs",
        params={"count": min(limit, 100), "geo": "anywhere"},
    )
    save_raw(NAME, payload)
    jobs = []
    for item in payload.get("jobs", []):
        industries = item.get("jobIndustry") or []
        job_types = item.get("jobType") or []
        geo = item.get("jobGeo") or ""
        jobs.append(
            make_job(
                source=NAME,
                external_id=item.get("id"),
                url=item.get("url", ""),
                title=item.get("jobTitle", ""),
                company=item.get("companyName", ""),
                company_logo=item.get("companyLogo", ""),
                location=geo,
                region="GLOBAL",
                remote=True,
                employment_type=", ".join(job_types) if isinstance(job_types, list) else str(job_types),
                level_raw=item.get("jobLevel", ""),
                category=", ".join(industries) if isinstance(industries, list) else str(industries),
                tags=industries if isinstance(industries, list) else [],
                description=item.get("jobDescription") or item.get("jobExcerpt", ""),
                posted_at=item.get("pubDate"),
                raw={"id": item.get("id"), "geo": geo, "level": item.get("jobLevel")},
            )
        )
    return [j for j in jobs if j]
