from __future__ import annotations

import json
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..text import normalize, parse_salary, to_date
from .base import http_get, make_job, polite_sleep, save_raw

NAME = "joboko"
LABEL = "JobOKO"
URL = "https://vn.joboko.com"
NOTE = "Danh mục và JSON-LD công khai của JobOKO; mô tả, yêu cầu, lương và ngày đăng lấy từ trang chi tiết."

_ORIGIN = "https://vn.joboko.com"
_LISTING = _ORIGIN + "/tim-viec-lam"
_JOB_LINK = re.compile(r"^(/viec-lam-[^\"']+-xvi\d+)$")
_DETAIL_LIMIT = 118


def _text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _json_ld(soup) -> dict:
    for node in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(node.string or "")
        except (TypeError, ValueError):
            continue
        if payload.get("@type") == "JobPosting":
            return payload
    return {}


def _sections(html: str) -> dict:
    result = {"description": "", "requirements": ""}
    soup = BeautifulSoup(html, "lxml")
    for heading in soup.find_all("h3"):
        key = normalize(_text(heading))
        parts = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) == "h3":
                break
            text = sibling.get_text("\n", strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
            if text:
                parts.append(text)
        text = "\n".join(parts).strip()
        if not text:
            continue
        if "mo ta cong viec" in key:
            result["description"] = text
        elif "yeu cau" in key:
            result["requirements"] = text
    return result


def _parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    data = _json_ld(soup)
    organization = data.get("hiringOrganization") or {}
    info = {}
    for item in soup.select(".int-job-detail-right .item-content"):
        label = normalize(_text(item.select_one(".item-label")))
        value = _text(item.select_one(".item-text"))
        if label and value:
            info[label.rstrip(":")] = value
    result = _sections(data.get("description") or "")
    if not (result["description"] or result["requirements"]):
        result = _sections(str(soup.select_one("div.int-job-detail-wysiwyg") or ""))
    result.update(
        {
            "title": data.get("title") or _text(soup.select_one("h1.int-job-detail-title")),
            "company": organization.get("name", "") if isinstance(organization, dict) else str(organization),
            "location": _location(data, soup),
            "posted": to_date(data.get("datePosted")),
            "expires": to_date(data.get("validThrough")),
            "employment_type": info.get("hinh thuc lam viec") or ", ".join(data.get("employmentType") or []),
            "category": data.get("industry") or "",
            "level": info.get("vi tri", ""),
            "salary": _salary(data),
        }
    )
    return result


def _location(data, soup) -> str:
    places = data.get("jobLocation") or []
    if isinstance(places, dict):
        places = [places]
    cities = []
    for place in places:
        address = place.get("address") or {}
        if isinstance(address, str):
            name = address
        else:
            name = address.get("addressLocality") or address.get("addressRegion") or ""
        if name and name not in cities:
            cities.append(name)
    if cities:
        return ", ".join(cities)
    return _text(soup.select_one(".int-job-detail-location")) or "Việt Nam"


def _salary(data):
    salary = data.get("baseSalary") or {}
    value = salary.get("value") or {}
    if isinstance(value, str):
        amount = value
        lo = hi = unit = None
    else:
        amount = value.get("value") or ""
        lo, hi, _, _ = parse_salary(amount)
        lo = lo or value.get("minValue")
        hi = hi or value.get("maxValue")
        unit = value.get("unitText") or ""
    _, _, currency, period = parse_salary(amount)
    currency = salary.get("currency") or currency
    if unit:
        period = {"MONTH": "month", "YEAR": "year", "HOUR": "hour", "DAY": "day"}.get(unit.upper(), period)
    return lo, hi, currency, period, amount


def fetch():
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    listing = http_get(_LISTING, as_text=True)
    soup = BeautifulSoup(listing, "lxml")
    urls = []
    for anchor in soup.find_all("a", href=True):
        match = _JOB_LINK.match(anchor["href"])
        if match and _ORIGIN + match.group(1) not in urls:
            urls.append(_ORIGIN + match.group(1))
    save_raw(NAME, {"ids": [url.rsplit("-", 1)[-1] for url in urls]})

    jobs = []
    for url in urls[:_DETAIL_LIMIT]:
        detail = _parse_detail(http_get(url, as_text=True))
        if not detail["posted"] or detail["posted"] < cutoff:
            continue
        if not (detail["description"] or detail["requirements"]):
            continue
        salary_min, salary_max, currency, period, salary_text = detail["salary"]
        job = make_job(
            source=NAME,
            external_id=url.rsplit("-", 1)[-1],
            url=url,
            title=detail["title"],
            company=detail["company"],
            location=detail["location"] or "Việt Nam",
            country="Việt Nam",
            region="VN",
            remote=any(x in detail["title"].lower() for x in ("remote", "từ xa")),
            employment_type=detail["employment_type"],
            level_raw=detail["level"],
            category=detail["category"],
            description=detail["description"],
            requirements=detail["requirements"],
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            period=period or ("month" if currency else None),
            salary_text=salary_text,
            posted_at=detail["posted"],
            expires_at=detail["expires"],
            raw={"id": url.rsplit("-", 1)[-1], "industry": detail["category"]},
        )
        if job:
            jobs.append(job)
        polite_sleep()
    return jobs
