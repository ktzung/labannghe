from __future__ import annotations

from .base import http_get, make_job, save_raw

NAME = "remotive"
LABEL = "Remotive"
URL = "https://remotive.com"
NOTE = "API công khai dành cho job board; giữ liên kết về Remotive."


def fetch(limit: int = 1500):
    payload = http_get("https://remotive.com/api/remote-jobs", params={"limit": limit})
    save_raw(NAME, payload)
    jobs = []
    for item in payload.get("jobs", []):
        logo = item.get("company_logo_url") or item.get("company_logo") or ""
        if logo and not str(logo).startswith("http"):
            logo = ""
        jobs.append(
            make_job(
                source=NAME,
                external_id=item.get("id"),
                url=item.get("url", ""),
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                company_logo=logo,
                location=item.get("candidate_required_location", ""),
                region="GLOBAL",
                remote=True,
                employment_type=item.get("job_type", ""),
                category=item.get("category", ""),
                tags=item.get("tags") or [],
                description=item.get("description", ""),
                salary_text=item.get("salary"),
                posted_at=item.get("publication_date"),
                raw={
                    "id": item.get("id"),
                    "category": item.get("category"),
                    "job_type": item.get("job_type"),
                    "salary": item.get("salary"),
                },
            )
        )
    return [j for j in jobs if j]
