from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..taxonomy import classify_role, extract_facets
from ..text import parse_salary
from .base import http_get, make_job, polite_sleep, save_raw

NAME = "itjobs"
LABEL = "ITJobs"
URL = "https://itjobs.com.vn/vi/search"
NOTE = "ITJobs công khai trang tìm kiếm; gom 15 từ khóa công nghệ, chỉ giữ tin đăng trong 60 ngày."

_BASE = "https://itjobs.com.vn/vi/search"
_DETAIL_LIMIT = 120
_MAX_AGE_DAYS = 60
_KEYWORDS = (
    "",
    "Java",
    "Python",
    "JavaScript",
    "React",
    "NodeJS",
    ".NET",
    "PHP",
    "Mobile",
    "QA",
    "DevOps",
    "Data",
    "AI",
    "Security",
    "Cloud",
)
_POSTED = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _section_text(soup, selector: str) -> str:
    section = soup.select_one(selector)
    if not section:
        return ""
    parts = []
    for box in section.select(".jp_overview_wrapper"):
        text = box.get_text("\n", strip=True)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    tags = []
    for node in soup.select(".tech-skills-detail-page li"):
        text = node.get_text(" ", strip=True)
        if text:
            tags.append(text)
    return {
        "description": _section_text(soup, ".job-description-section"),
        "requirements": _section_text(soup, ".job-requirement-section"),
        "tags": tags,
    }


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
    extra = [t for t in detail.get("tags") or [] if t not in (job.get("tags") or [])]
    if extra:
        job["tags"] = (job.get("tags") or []) + extra
    if not (detail.get("description") or detail.get("requirements")):
        return
    job["role"] = classify_role(
        job["title"], job.get("category", ""), job.get("tags") or [], job["description"]
    )
    facets = extract_facets(
        job["title"], job.get("tags") or [], job.get("requirements") or "", job.get("description") or ""
    )
    job["_skills"] = facets["skills"]
    job["_knowledge"] = facets["knowledge"]


def _posted_date(text: str) -> str:
    match = _POSTED.search(text or "")
    if not match:
        return date.today().isoformat()
    day, month, year = (int(x) for x in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return date.today().isoformat()


def _text(card, selector: str) -> str:
    node = card.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def _icon_value(card, icon_class: str) -> str:
    icon = card.select_one("i.%s" % icon_class)
    if not icon:
        return ""
    parent = icon.find_parent("li")
    if not parent:
        return ""
    span = parent.select_one("span")
    return span.get_text(" ", strip=True) if span else parent.get_text(" ", strip=True)


def _tags(card) -> list:
    node = card.select_one(".jp_job_post_keyword_wrapper")
    if not node:
        return []
    text = node.get_text(" ", strip=True)
    if ":" in text:
        text = text.split(":", 1)[1]
    return [part.strip() for part in text.split(",") if part.strip()]


def _card(card):
    href = card.get("href") or ""
    if "/vi/job/" not in href:
        return None
    url = href.split("?")[0]
    if url.startswith("/"):
        url = "https://itjobs.com.vn" + url
    parts = url.rstrip("/").split("/")
    job_id = parts[-2] if len(parts) >= 2 and parts[-2].isdigit() else url
    title = _text(card, "h3")
    if not title:
        return None
    company = _text(card, ".jp_job_post_detail_cont > p")
    logo = card.select_one(".company-logo img")
    location = _icon_value(card, "fa-map-marker")
    salary_text = _icon_value(card, "j-usd")
    salary_min = salary_max = currency = period = None
    if salary_text and re.search(r"\d", salary_text):
        salary_min, salary_max, currency, period = parse_salary(salary_text)
    return make_job(
        source=NAME,
        external_id=job_id,
        url=url,
        title=title,
        company=company,
        company_logo=(logo.get("src") if logo else "") or "",
        location=location or "Việt Nam",
        country="Việt Nam",
        region="VN",
        remote="remote" in (location or "").lower(),
        employment_type=_icon_value(card, "j-clock"),
        level_raw=_icon_value(card, "j-suitcase"),
        tags=_tags(card),
        salary_min=salary_min,
        salary_max=salary_max,
        currency=currency,
        period=period or ("month" if currency else None),
        salary_text=salary_text,
        posted_at=_posted_date(_text(card, ".j-calendar") or card.get_text(" ", strip=True)),
        raw={"keyword": None},
    )


def fetch(max_pages: int = 1):
    keywords = list(_KEYWORDS)
    cutoff = (date.today() - timedelta(days=_MAX_AGE_DAYS)).isoformat()
    seen = {}
    for keyword in keywords:
        params = {"Keyword": keyword} if keyword else None
        try:
            html = http_get(_BASE, params=params, as_text=True)
        except Exception:  # noqa: BLE001 - one query must not stop the rest
            polite_sleep()
            continue
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("a.jp_job_post_link")
        save_raw("%s-%s" % (NAME, keyword or "latest"), {"count": len(cards)})
        for node in cards:
            job = _card(node)
            if not job or job["posted_at"] < cutoff:
                continue
            job["raw"]["keyword"] = keyword or "latest"
            seen.setdefault(job["external_id"], job)
        polite_sleep()
    jobs = list(seen.values())
    fetched = 0
    for job in jobs:
        if fetched >= _DETAIL_LIMIT or not job.get("url"):
            break
        detail = _fetch_detail(job["url"])
        _refresh_job(job, detail)
        job["raw"]["detail_fetched"] = bool(detail)
        fetched += 1
        polite_sleep()
    return jobs
