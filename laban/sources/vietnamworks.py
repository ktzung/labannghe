from __future__ import annotations

from datetime import date, timedelta
from typing import List

from .base import http_post, make_job, polite_sleep, save_raw

NAME = "vietnamworks"
LABEL = "VietnamWorks"
URL = "https://www.vietnamworks.com"
NOTE = "API tìm kiếm công khai của VietnamWorks; giữ liên kết về tin gốc."

API = "https://ms.vietnamworks.com/job-search/v1.0/search"
_ORIGIN = "https://www.vietnamworks.com"


def _category(item) -> str:
    function = item.get("jobFunction") or {}
    children = function.get("children") or []
    if children and children[0].get("nameVI"):
        return children[0]["nameVI"]
    if function.get("parentNameVI"):
        return function["parentNameVI"]
    industries = item.get("industriesV3") or []
    if industries:
        return industries[0].get("industryV3NameVI") or ""
    return ""


def _location(item) -> str:
    cities = []
    for place in item.get("workingLocations") or []:
        name = place.get("cityNameVI") or place.get("cityName") or ""
        if name and name not in cities:
            cities.append(name)
    if cities:
        return ", ".join(cities[:3])
    return item.get("address") or "Việt Nam"


def _tags(item) -> List[str]:
    names = []
    for skill in item.get("skills") or []:
        name = skill.get("skillName")
        if name:
            names.append(name)
    return names


def fetch(max_pages: int = 30):
    jobs = []
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    page = 0
    while page < max(1, max_pages):
        body = {
            "userId": 0,
            "query": "",
            "filter": [],
            "ranges": [],
            "order": [{"field": "approvedOn", "value": "desc"}],
            "hitsPerPage": 50,
            "page": page,
        }
        payload = http_post(API, body)
        save_raw("%s-p%d" % (NAME, page + 1), {"ids": [x.get("jobId") for x in payload.get("data", [])]})
        items = payload.get("data") or []
        if not items:
            break
        oldest = None
        for item in items:
            posted = str(item.get("approvedOn") or "")[:10]
            if posted:
                oldest = posted if oldest is None else min(oldest, posted)
                if posted < cutoff:
                    continue
            url = item.get("jobUrl") or ""
            if url.startswith("/"):
                url = _ORIGIN + url
            salary_min = item.get("salaryMin") or None
            salary_max = item.get("salaryMax") or None
            jobs.append(
                make_job(
                    source=NAME,
                    external_id=item.get("jobId"),
                    url=url,
                    title=item.get("jobTitle", ""),
                    company=item.get("companyName", ""),
                    company_logo=item.get("companyLogo", ""),
                    location=_location(item),
                    country="Việt Nam",
                    region="VN",
                    remote=any(
                        x in (item.get("jobTitle") or "").lower()
                        for x in ("remote", "từ xa", "lam viec tu xa")
                    ),
                    employment_type="",
                    level_raw=item.get("jobLevelVI") or "",
                    category=_category(item),
                    tags=_tags(item),
                    description=item.get("jobDescription") or "",
                    requirements=item.get("jobRequirement") or "",
                    salary_min=float(salary_min) if salary_min else None,
                    salary_max=float(salary_max) if salary_max else None,
                    currency=item.get("salaryCurrency") or "VND",
                    period="month",
                    salary_text=item.get("prettySalary") or "",
                    posted_at=item.get("approvedOn"),
                    expires_at=item.get("expiredOn"),
                    raw={
                        "id": item.get("jobId"),
                        "category": _category(item),
                        "level": item.get("jobLevelVI"),
                        "salary": item.get("prettySalary"),
                    },
                )
            )
        if oldest and oldest < (date.today() - timedelta(days=7)).isoformat():
            break
        page += 1
        polite_sleep()
    return [j for j in jobs if j]
