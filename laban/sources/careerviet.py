from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..text import normalize, parse_salary, to_date
from .base import http_get, make_job, polite_sleep, save_raw

NAME = "careerviet"
LABEL = "CareerViet"
URL = "https://careerviet.vn"
NOTE = "Danh mục việc làm công khai của CareerViet; ngày trên thẻ là ngày cập nhật, mô tả/yêu cầu lấy từ trang chi tiết."

_ORIGIN = "https://careerviet.vn"
_CATEGORY_SITEMAP = _ORIGIN + "/sitemap/searchjob.xml"
_ALL_JOBS = _ORIGIN + "/viec-lam/tat-ca-viec-lam-vi.html"
_DETAIL_LIMIT = 200
_CATEGORY_LIMIT = 30

_CATEGORY_RE = re.compile(r"<loc>(https://careerviet\.vn/viec-lam/[^<]+-c\d+-vi\.html)</loc>")


def _categories():
    try:
        xml = http_get(_CATEGORY_SITEMAP, as_text=True)
        found = _CATEGORY_RE.findall(xml)
        if found:
            return found[:_CATEGORY_LIMIT]
    except Exception:  # noqa: BLE001 - fall back to the all-jobs listing
        pass
    return [_ALL_JOBS]


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _parse_card(item):
    link = item.select_one("a.job_link[data-id]")
    if not link:
        return None
    times = [node.get_text(strip=True) for node in item.select(".time time")]
    posted = to_date(times[1]) if len(times) > 1 else None
    if not posted:
        return None
    categories = [_text(node) for node in item.select(".welfare li")]
    locations = [_text(node) for node in item.select(".location li")]
    return {
        "id": link.get("data-id"),
        "url": _ORIGIN + link.get("href", ""),
        "title": link.get("title") or _text(link),
        "company": _text(item.select_one(".company-name")),
        "location": ", ".join(dict.fromkeys(x for x in locations if x)),
        "salary": _text(item.select_one(".salary")),
        "category": " · ".join(x for x in categories if x),
        "posted": posted,
        "expires": to_date(times[0]) if times else None,
    }


def _parse_detail(html: str):
    soup = BeautifulSoup(html, "lxml")
    result = {"description": "", "requirements": ""}
    for row in soup.select(".job-detail-content .detail-row"):
        heading = row.select_one(".detail-title")
        if not heading:
            continue
        key = normalize(_text(heading))
        box = row.find("div")
        text = box.get_text("\n", strip=True) if box else ""
        if not text:
            continue
        if "mo ta cong viec" in key:
            result["description"] = text
        elif "yeu cau cong viec" in key:
            result["requirements"] = text
    return result


def _detail(url: str):
    try:
        return _parse_detail(http_get(url, as_text=True))
    except Exception:  # noqa: BLE001 - one detail page must not stop the source
        return {}


def fetch():
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    cards = {}
    for category_url in _categories():
        try:
            html = http_get(category_url, as_text=True)
        except Exception:  # noqa: BLE001
            continue
        soup = BeautifulSoup(html, "lxml")
        for item in soup.select(".job-item"):
            card = _parse_card(item)
            if not card or not card["id"] or card["posted"] < cutoff:
                continue
            cards.setdefault(card["id"], card)
        polite_sleep()

    ordered = sorted(cards.values(), key=lambda c: c["posted"], reverse=True)
    save_raw(NAME, {"ids": [card["id"] for card in ordered]})
    jobs = []
    for card in ordered[:_DETAIL_LIMIT]:
        detail = _detail(card["url"])
        if not (detail.get("description") or detail.get("requirements")):
            continue
        salary_min, salary_max, currency, period = parse_salary(card["salary"])
        title = card["title"]
        job = make_job(
            source=NAME,
            external_id=card["id"],
            url=card["url"],
            title=title,
            company=card["company"],
            location=card["location"] or "Việt Nam",
            country="Việt Nam",
            region="VN",
            remote=any(x in (title + " " + card["location"]).lower() for x in ("remote", "từ xa")),
            category=card["category"],
            description=detail.get("description", ""),
            requirements=detail.get("requirements", ""),
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            period=period or ("month" if currency else None),
            salary_text=card["salary"],
            posted_at=card["posted"],
            expires_at=card["expires"],
            raw={"id": card["id"], "categories": card["category"]},
        )
        if job:
            jobs.append(job)
        polite_sleep()
    return jobs
