from __future__ import annotations

from .base import http_get, make_job, save_raw

NAME = "remoteok"
LABEL = "Remote OK"
URL = "https://remoteok.com"
NOTE = "API công khai; điều khoản yêu cầu giữ liên kết về Remote OK."


def fetch(limit: int = 2000):
    payload = http_get("https://remoteok.com/api")
    save_raw(NAME, payload)
    jobs = []
    if not isinstance(payload, list):
        return jobs
    for item in payload:
        if not isinstance(item, dict) or not item.get("id") or not item.get("position"):
            continue
        salary_min = item.get("salary_min") or None
        salary_max = item.get("salary_max") or None
        jobs.append(
            make_job(
                source=NAME,
                external_id=item.get("id"),
                url=item.get("url") or item.get("apply_url", ""),
                title=item.get("position", ""),
                company=item.get("company", ""),
                company_logo=item.get("company_logo") or item.get("logo") or "",
                location=item.get("location", ""),
                region="GLOBAL",
                remote=True,
                tags=item.get("tags") or [],
                description=item.get("description", ""),
                salary_min=float(salary_min) if salary_min else None,
                salary_max=float(salary_max) if salary_max else None,
                currency="USD",
                period="year",
                posted_at=item.get("date") or item.get("epoch"),
                raw={
                    "id": item.get("id"),
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                },
            )
        )
        if len(jobs) >= limit:
            break
    return [j for j in jobs if j]
