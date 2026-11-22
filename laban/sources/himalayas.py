from __future__ import annotations

from .base import http_get, make_job, save_raw

NAME = "himalayas"
LABEL = "Himalayas"
URL = "https://himalayas.app"
NOTE = "API công khai; trường lương có thể để trống."


def _num(value):
    try:
        return float(value) if value not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


def fetch(limit: int = 100):
    payload = http_get("https://himalayas.app/jobs/api", params={"limit": limit})
    save_raw(NAME, payload)
    jobs = []
    items = payload.get("jobs", payload if isinstance(payload, list) else [])
    for item in items:
        locations = item.get("locationRestrictions") or []
        categories = item.get("categories") or []
        seniority = item.get("seniority") or []
        jobs.append(
            make_job(
                source=NAME,
                external_id=item.get("guid") or item.get("applicationLink"),
                url=item.get("applicationLink", ""),
                title=item.get("title", ""),
                company=item.get("companyName", ""),
                company_logo=item.get("companyLogo", ""),
                location=", ".join(locations) if isinstance(locations, list) else str(locations),
                country=locations[0] if isinstance(locations, list) and locations else "",
                region="GLOBAL",
                remote=True,
                employment_type=item.get("employmentType", ""),
                level_raw=", ".join(seniority) if isinstance(seniority, list) else str(seniority),
                tags=categories,
                description=item.get("description", ""),
                salary_min=_num(item.get("minSalary")),
                salary_max=_num(item.get("maxSalary")),
                currency=item.get("currency") or None,
                period=item.get("salaryPeriod") or None,
                posted_at=item.get("pubDate"),
                expires_at=item.get("expiryDate"),
                raw={"guid": item.get("guid"), "seniority": seniority},
            )
        )
    return [j for j in jobs if j]
