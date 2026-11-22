from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..text import normalize, parse_salary, to_date
from .base import http_get, make_job, polite_sleep, save_raw

NAME = "vieclam123"
LABEL = "Vieclam123"
URL = "https://vieclam123.vn"
NOTE = "Danh mục việc làm công khai của Vieclam123; mô tả, yêu cầu và ngày đăng lấy từ trang chi tiết."

_ORIGIN = "https://vieclam123.vn"
_LISTING = _ORIGIN + "/viec-lam"
_CITY_LISTINGS = [
    ("ha-noi-c0p1", 4),
    ("ho-chi-minh-c0p45", 4),
    ("da-nang-c0p26", 2),
    ("binh-duong-c0p46", 2),
    ("can-tho-c0p48", 2),
]
_JOB_LINK = re.compile(r"^(/viec-lam/[^\"']*?-job\d+\.html)$")
_CANDIDATE_LIMIT = 220
_DETAIL_LIMIT = 150


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _links(html: str):
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.find_all("a", href=True):
        match = _JOB_LINK.match(anchor["href"])
        if match:
            yield _ORIGIN + match.group(1)


def _candidates():
    urls = []
    seen = set()

    def add(html):
        for url in _links(html):
            if url not in seen:
                seen.add(url)
                urls.append(url)

    add(http_get(_LISTING, as_text=True))
    for slug, pages in _CITY_LISTINGS:
        base = "%s/viec-lam/viec-lam-tai-%s.html" % (_ORIGIN, slug)
        for page in range(1, pages + 1):
            add(http_get(base if page == 1 else "%s/%d" % (base, page), as_text=True))
            polite_sleep()
            if len(urls) >= _CANDIDATE_LIMIT:
                return urls[:_CANDIDATE_LIMIT]
    return urls[:_CANDIDATE_LIMIT]


def _parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    result = {
        "title": _text(soup.select_one(".q-detail-job-left-header-title")),
        "company": _text(soup.select_one(".q-detail-job-left-header-com")),
        "expires": _text(soup.select_one(".q-detail-job-left-header-date-v2")),
        "info": {},
        "description": "",
        "requirements": "",
        "tags": [],
    }
    for column in soup.select(".q-detail-job-info-v2-column"):
        key = normalize(_text(column.select_one(".q-detail-job-info-title")))
        value = _text(column.select_one(".q-detail-job-info-des"))
        if key and value:
            result["info"][key] = value

    for box in soup.select("div.q-detail-job-left-info > div.q-detail-job-left-div"):
        heading = box.select_one(".q-detail-job-left-div-title")
        if not heading:
            continue
        key = normalize(_text(heading))
        content = box.select_one(".q-detail-job-left-div-content")
        lines = [line for line in content.get_text("\n", strip=True).split("\n") if line != "Xem Thêm"] if content else []
        text = "\n".join(lines).strip()
        if not text:
            continue
        if "mo ta cong viec" in key:
            result["description"] = text
        elif "yeu cau cong viec" in key:
            result["requirements"] = text
        elif "tu khoa tim kiem" in key:
            result["tags"] = [_text(a) for a in box.find_all("a") if not _text(a).isdigit()]
    return result


def _detail(url: str) -> dict:
    try:
        return _parse_detail(http_get(url, as_text=True))
    except Exception:  # noqa: BLE001 - one detail page must not stop the run
        return {}


def fetch():
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    jobs = []
    for url in _candidates():
        detail = _detail(url)
        info = detail.get("info") or {}
        posted = to_date(info.get("ngay dang tin"))
        if not posted or posted < cutoff:
            polite_sleep()
            continue
        if not (detail.get("description") or detail.get("requirements")):
            polite_sleep()
            continue
        match = re.search(r"-job(\d+)\.html$", url)
        salary_min, salary_max, currency, period = parse_salary(info.get("muc luong"))
        location = info.get("noi lam viec", "")
        title = detail.get("title", "")
        job = make_job(
            source=NAME,
            external_id=match.group(1) if match else url,
            url=url,
            title=title,
            company=detail.get("company", ""),
            location=location or "Việt Nam",
            country="Việt Nam",
            region="VN",
            remote=any(x in (title + " " + location).lower() for x in ("remote", "từ xa")),
            employment_type=info.get("loai hinh lam viec", ""),
            level_raw=info.get("cap bac", ""),
            category=info.get("nganh nghe", ""),
            tags=detail.get("tags") or [],
            description=detail.get("description", ""),
            requirements=detail.get("requirements", ""),
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            period=period or ("month" if currency else None),
            salary_text=info.get("muc luong", ""),
            posted_at=posted,
            expires_at=to_date(detail.get("expires")),
            raw={"id": match.group(1) if match else "", "level": info.get("cap bac"), "category": info.get("nganh nghe")},
        )
        if job:
            jobs.append(job)
        if len(jobs) >= _DETAIL_LIMIT:
            break
        polite_sleep()
    save_raw(NAME, {"ids": [job["external_id"] for job in jobs]})
    return jobs
