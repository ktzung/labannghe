from __future__ import annotations

import feedparser

from .base import make_job, save_raw

NAME = "weworkremotely"
LABEL = "We Work Remotely"
URL = "https://weworkremotely.com"
NOTE = "RSS công khai của chuyên mục lập trình."

FEED = "https://weworkremotely.com/categories/remote-programming-jobs.rss"


def fetch(limit: int = 200):
    feed = feedparser.parse(FEED)
    save_raw(NAME, {"entries": [dict(e) for e in feed.entries]})
    jobs = []
    for item in feed.entries:
        raw_title = item.get("title", "")
        company, title = "", raw_title
        if ":" in raw_title:
            company, title = raw_title.split(":", 1)
            company, title = company.strip(), title.strip()
        jobs.append(
            make_job(
                source=NAME,
                external_id=item.get("guid") or item.get("link"),
                url=item.get("link", ""),
                title=title,
                company=company,
                location=item.get("region", ""),
                region="GLOBAL",
                remote=True,
                category=item.get("category", ""),
                tags=[item.get("category")] if item.get("category") else [],
                description=item.get("description", ""),
                posted_at=item.get("published"),
                raw={"guid": item.get("guid"), "region": item.get("region")},
            )
        )
        if len(jobs) >= limit:
            break
    return [j for j in jobs if j]
