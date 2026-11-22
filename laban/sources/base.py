from __future__ import annotations

import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import httpx

from ..config import (
    FX_TO_VND,
    MAX_RETRIES,
    RAW_DIR,
    REQUEST_DELAY,
    TIMEOUT,
    TRUST_ENV,
    USER_AGENT,
)
from ..company import classify_company_type
from ..geo import parse_locations
from ..taxonomy import classify_role, company_tier, detect_level, extract_facets
from ..text import (
    monthly_vnd,
    normalize,
    parse_salary,
    short,
    slugify,
    strip_html,
    to_date,
)

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "vi,en;q=0.8",
}


def http_get(url: str, params: Optional[dict] = None, as_text: bool = False):
    return _request("GET", url, params=params, as_text=as_text)


def http_post(url: str, payload: dict):
    return _request("POST", url, payload=payload, as_text=False)


def _request(method: str, url: str, params=None, payload=None, as_text: bool = False):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(
                timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True, trust_env=TRUST_ENV
            ) as client:
                if method == "POST":
                    response = client.post(url, json=payload)
                else:
                    response = client.get(url, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    "retryable status", request=response.request, response=response
                )
            response.raise_for_status()
            return response.text if as_text else response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("%s %s failed: %s" % (method, url, last_error))


def polite_sleep() -> None:
    time.sleep(REQUEST_DELAY)


def save_raw(source: str, payload) -> Path:
    day = datetime.now(timezone.utc).date().isoformat()
    target = RAW_DIR / day
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    path = target / ("%s-%s.json.gz" % (source, stamp))
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return path


def make_job(
    *,
    source: str,
    external_id,
    url: str,
    title: str,
    company: str = "",
    company_logo: str = "",
    location: str = "",
    country: str = "",
    region: str = "GLOBAL",
    remote: bool = True,
    employment_type: str = "",
    level_raw: str = "",
    category: str = "",
    tags=None,
    description: str = "",
    requirements: str = "",
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    currency: Optional[str] = None,
    period: Optional[str] = None,
    salary_text: Optional[str] = None,
    posted_at=None,
    expires_at=None,
    raw=None,
) -> Optional[Dict]:
    title = short(strip_html(title or ""), 400)
    if not title:
        return None
    company = short(strip_html(company or ""), 300)
    description = short(strip_html(description), 20000)
    requirements = short(strip_html(requirements), 20000)
    tags = [short(str(t), 80) for t in (tags or []) if t][:30]

    if salary_text and not (salary_min or salary_max):
        salary_min, salary_max, parsed_cur, parsed_period = parse_salary(salary_text)
        currency = currency or parsed_cur
        period = period or parsed_period
    if (salary_min or salary_max) and not currency:
        currency = "VND" if region == "VN" else "USD"
    if (salary_min or salary_max) and not period:
        period = "month" if currency == "VND" else "year"

    vnd_min = monthly_vnd(salary_min, currency, period, FX_TO_VND)
    vnd_max = monthly_vnd(salary_max, currency, period, FX_TO_VND)

    role = classify_role(title, category, tags, description)
    level = detect_level(title, level_raw)
    facets = extract_facets(title, tags, requirements, description)
    company_type = classify_company_type(company, region)

    return {
        "source": source,
        "external_id": str(external_id),
        "url": url or "",
        "title": title,
        "company": company,
        "company_slug": slugify(company) if company else "",
        "company_logo": company_logo or "",
        "company_type": company_type,
        "locations": parse_locations(location) if region == "VN" else [],
        "location": short(location or "", 400),
        "country": country or "",
        "region": region,
        "remote": bool(remote),
        "employment_type": employment_type or "",
        "level": level,
        "role": role,
        "category": category or "",
        "tags": tags,
        "description": description,
        "requirements": requirements,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "period": period,
        "salary_vnd_min": vnd_min,
        "salary_vnd_max": vnd_max,
        "posted_at": to_date(posted_at),
        "expires_at": to_date(expires_at),
        "company_tier": company_tier(company),
        "raw": raw or {},
        "_skills": facets["skills"],
        "_knowledge": facets["knowledge"],
    }


def payload_size(payload) -> int:
    return len(json.dumps(payload, ensure_ascii=False))


__all__ = ["http_get", "http_post", "polite_sleep", "save_raw", "make_job", "payload_size", "normalize"]
