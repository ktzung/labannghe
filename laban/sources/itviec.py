from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..text import normalize, parse_salary
from ..taxonomy import classify_role, extract_facets
from .base import http_get, make_job, polite_sleep, save_raw

NAME = "itviec"
LABEL = "ITviec"
URL = "https://itviec.com/it-jobs"
NOTE = "ITviec cho phép thu thập; phần lớn mức lương chỉ hiển thị sau đăng nhập."

_BASE = "https://itviec.com/it-jobs"
_REL = re.compile(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", re.I)
_DETAIL_LIMIT = 200
_MAX_PAGES = 10


def _parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    result = {"description": "", "requirements": ""}
    for box in soup.select("div.imy-5.paragraph"):
        heading = box.find(["h2", "h3"])
        if not heading:
            continue
        key = normalize(heading.get_text(" ", strip=True))
        parts = []
        for child in box.find_all(recursive=False):
            if child is heading:
                continue
            text = child.get_text("\n", strip=True)
            if text:
                parts.append(text)
        text = "\n".join(parts).strip()
        if not text:
            continue
        if "skills and experience" in key or "requirements" in key or "yeu cau" in key or "qualifications" in key:
            result["requirements"] = text
        elif "job description" in key or "mo ta cong viec" in key or "about the job" in key:
            result["description"] = text
    return result


def _fetch_detail(url: str) -> dict:
    try:
        return _parse_detail(http_get(url, as_text=True))
    except Exception:  # noqa: BLE001 - one detail page must not stop the listing
        return {}


def _refresh_job(job: dict, detail: dict) -> None:
    if detail.get("description"):
        job["description"] = detail["description"]
    if detail.get("requirements"):
        job["requirements"] = detail["requirements"]
    if not (detail.get("description") or detail.get("requirements")):
        return
    job["role"] = classify_role(job["title"], job.get("category", ""), job.get("tags") or [], job["description"])
    facets = extract_facets(
        job["title"], job.get("tags") or [], job.get("requirements") or "", job.get("description") or ""
    )
    job["_skills"] = facets["skills"]
    job["_knowledge"] = facets["knowledge"]


def _posted_date(text: str) -> str:
    match = _REL.search(text or "")
    if not match:
        return date.today().isoformat()
    amount, unit = int(match.group(1)), match.group(2).lower()
    days = {"minute": 0, "hour": 0, "day": amount, "week": amount * 7, "month": amount * 30}[unit]
    return (date.today() - timedelta(days=days)).isoformat()


def _salary(card):
    node = card.select_one(".salary")
    if not node:
        return None, None, None, None
    text = node.get_text(" ", strip=True)
    if "sign in" in text.lower() or not re.search(r"\d", text):
        return None, None, None, None
    lo, hi, currency, period = parse_salary(text)
    return lo, hi, currency, period


def fetch(max_pages: int = _MAX_PAGES):
    max_pages = min(max(1, max_pages), _MAX_PAGES)
    jobs = []
    for page in range(1, max_pages + 1):
        params = None if page == 1 else {"page": page, "query": "", "source": "search_job"}
        html = http_get(_BASE, params=params, as_text=True)
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(".job-card")
        if not cards:
            break
        save_raw("%s-p%d" % (NAME, page), {"count": len(cards)})
        for card in cards:
            link = card.select_one("h3 a[href]")
            if not link:
                continue
            url = link["href"].split("?")[0]
            if url.startswith("/"):
                url = "https://itviec.com" + url
            slug = card.get("data-search--job-selection-job-slug-value") or ""
            job_id = slug.rsplit("-", 1)[-1] if slug else url.rstrip("/").rsplit("-", 1)[-1]
            company_name = ""
            for anchor in card.select('a[href^="/companies/"]'):
                text = anchor.get_text(" ", strip=True)
                if text:
                    company_name = text
            logo = card.select_one("img[data-src]")
            location_box = card.select_one(".imt-1.text-dark-grey")
            working = ""
            city = ""
            if location_box:
                mode = location_box.select_one(".flex-shrink-0")
                working = mode.get_text(" ", strip=True) if mode else ""
                city_node = location_box.select_one(".text-truncate")
                city = city_node.get_text(" ", strip=True) if city_node else ""
            function_node = card.select_one(".imt-1")
            category = function_node.get_text(" ", strip=True) if function_node else ""
            tags = []
            for tag in card.select(".itag"):
                text = tag.get_text(" ", strip=True)
                if text:
                    tags.append(text)
            posted_text = ""
            posted_node = card.select_one(".small-text.text-dark-grey")
            if posted_node:
                posted_text = posted_node.get_text(" ", strip=True)
            salary_min, salary_max, currency, period = _salary(card)
            location = " · ".join(x for x in (working, city) if x) or "Việt Nam"
            jobs.append(
                make_job(
                    source=NAME,
                    external_id=job_id,
                    url=url,
                    title=link.get_text(" ", strip=True),
                    company=company_name,
                    company_logo=(logo.get("data-src") if logo else "") or "",
                    location=location,
                    country="Việt Nam",
                    region="VN",
                    remote="remote" in working.lower(),
                    employment_type="",
                    category=category,
                    tags=tags,
                    requirements="",
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    period=period or ("month" if currency else None),
                    posted_at=_posted_date(posted_text),
                    raw={"slug": slug, "working": working, "city": city},
                )
            )
        if page < max_pages:
            polite_sleep()
    fetched = 0
    for job in jobs:
        if fetched >= _DETAIL_LIMIT or not job.get("url"):
            break
        detail = _fetch_detail(job["url"])
        _refresh_job(job, detail)
        job.setdefault("raw", {})["detail_fetched"] = bool(detail)
        fetched += 1
        polite_sleep()
    return [j for j in jobs if j]
