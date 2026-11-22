from __future__ import annotations

from .base import http_get, make_job, polite_sleep, save_raw

NAME = "arbeitnow"
LABEL = "Arbeitnow"
URL = "https://www.arbeitnow.com"
NOTE = "API công khai, không cần khoá."


def fetch(limit: int = 600):
    jobs = []
    page = 1
    while len(jobs) < limit and page <= 8:
        payload = http_get(
            "https://www.arbeitnow.com/api/job-board-api", params={"page": page}
        )
        save_raw("%s-p%d" % (NAME, page), payload)
        items = payload.get("data", [])
        if not items:
            break
        for item in items:
            jobs.append(
                make_job(
                    source=NAME,
                    external_id=item.get("slug"),
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("location", ""),
                    region="GLOBAL",
                    remote=bool(item.get("remote")),
                    employment_type=", ".join(item.get("job_types") or []),
                    tags=item.get("tags") or [],
                    description=item.get("description", ""),
                    posted_at=item.get("created_at"),
                    raw={"slug": item.get("slug"), "remote": item.get("remote")},
                )
            )
        page += 1
        polite_sleep()
    return [j for j in jobs if j]
