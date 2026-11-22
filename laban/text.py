from __future__ import annotations

import html
import re
import unicodedata
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Tuple

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SPACE_PUNCT_RE = re.compile(r"\s+([,.;:!?%)])")


def strip_html(value: Optional[str]) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</(p|li|div|h[1-6]|tr)>", "\n", value, flags=re.I)
    value = _TAG_RE.sub(" ", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = _SPACE_PUNCT_RE.sub(r"\1", value)
    lines = [_WS_RE.sub(" ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.lower().replace("đ", "d").replace("Đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d")
    return _WS_RE.sub(" ", value).strip()


def slugify(value: str) -> str:
    value = normalize(value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "unknown"


def short(value: str, limit: int = 260) -> str:
    value = _WS_RE.sub(" ", value or "").strip()
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def to_date(value) -> Optional[str]:
    """Chuẩn hoá nhiều kiểu ngày về ISO date (YYYY-MM-DD)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    text = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s*", "", text, flags=re.I)
    text = text.replace("Z", "+00:00")
    candidates = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d %b %Y %H:%M:%S %z",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_iso() -> str:
    return now_utc().date().isoformat()


def days_ago_iso(days: int) -> str:
    return (now_utc().date() - timedelta(days=days)).isoformat()


_CURRENCIES = {
    "$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP", "₫": "VND", "vnd": "VND", "đ": "VND",
    "sgd": "SGD", "aud": "AUD", "cad": "CAD", "jpy": "JPY", "krw": "KRW",
}
_AMOUNT_RE = re.compile(
    r"(?P<cur1>us\$|\$|€|£|₫|usd|eur|gbp|vnd|sgd|aud|cad|jpy|krw)?\s*"
    r"(?P<a>\d[\d.,]*)\s*(?P<ak>k|m|tr|triệu|trieu|nghìn|nghin|million)?"
    r"(?:\s*(?:-|–|—|to|đến|den)\s*"
    r"(?P<cur2>us\$|\$|€|£|₫|usd|eur|gbp|vnd|sgd|aud|cad|jpy|krw)?\s*"
    r"(?P<b>\d[\d.,]*)\s*(?P<bk>k|m|tr|triệu|trieu|nghìn|nghin|million)?)?",
    re.I,
)
_PERIOD_RE = re.compile(
    r"(/|per\s+|mỗi\s+|mot\s+)?(hour|giờ|gio|month|tháng|thang|year|năm|nam|annum|annual|yr)\b",
    re.I,
)


def _num(raw: str, suffix: str) -> Optional[float]:
    if not raw:
        return None
    text = raw.replace(" ", "")
    # 1.234,56 (EU) vs 1,234.56 (US)
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") == 1 and text.split(",")[-1].isdigit() and len(text.split(",")[-1]) <= 2:
        text = text.replace(",", ".")
    elif text.count(",") == 1 and len(text.split(",")[-1]) == 3:
        text = text.replace(",", "")
    elif text.count(".") == 1 and text.split(".")[-1].isdigit() and len(text.split(".")[-1]) <= 2:
        pass
    else:
        text = text.replace(".", "").replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    suffix = (suffix or "").lower()
    if suffix in ("k", "nghìn", "nghin"):
        value *= 1_000
    elif suffix in ("m", "million"):
        value *= 1_000_000
    elif suffix in ("tr", "triệu", "trieu"):
        value *= 1_000_000
    return value


def parse_salary(text: Optional[str]) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """Trả về (min, max, currency, period) từ chuỗi lương tự do."""
    if not text:
        return None, None, None, None
    cleaned = str(text).replace("\xa0", " ").strip()
    if not cleaned:
        return None, None, None, None
    cur = None
    low = cleaned.lower()
    for token, code in _CURRENCIES.items():
        if token in low:
            cur = code
            break
    match = _AMOUNT_RE.search(cleaned)
    if not match:
        return None, None, cur, _period_of(cleaned)
    cur = _CURRENCIES.get((match.group("cur1") or "").lower(), None) or \
        _CURRENCIES.get((match.group("cur2") or "").lower(), None) or cur
    ak = match.group("ak") or ""
    bk = match.group("bk") or ""
    a = _num(match.group("a"), ak)
    b = _num(match.group("b"), bk) if match.group("b") else None
    if a is not None and b is not None:
        if not ak and bk:
            a = _num(match.group("a"), bk)
        elif ak and not bk:
            b = _num(match.group("b"), ak)
    period = _period_of(cleaned)
    if period is None and a and a > 2_000_000 and (cur in (None, "VND")):
        period = "month"
    return a, b, cur, period


def _period_of(text: str) -> Optional[str]:
    m = _PERIOD_RE.search(text)
    if not m:
        return None
    unit = m.group(2).lower()
    if unit in ("hour", "giờ", "gio"):
        return "hour"
    if unit in ("month", "tháng", "thang"):
        return "month"
    if unit in ("year", "năm", "nam", "annum", "annual", "yr"):
        return "year"
    return None


def monthly_vnd(amount: Optional[float], currency: Optional[str], period: Optional[str], fx: dict) -> Optional[float]:
    if not amount:
        return None
    code = (currency or "VND").upper()
    rate = fx.get(code)
    if not rate:
        return None
    value = amount * rate
    period = (period or ("month" if code == "VND" else "year")).lower()
    if period in ("year", "yearly", "annual", "annum"):
        value /= 12.0
    elif period in ("hour", "hourly"):
        value *= 173.0
    elif period in ("day", "daily"):
        value *= 21.0
    return round(value, 0)


def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def fmt_vnd(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000_000:
        return "%.1f tỷ" % (value / 1_000_000_000)
    if value >= 1_000_000:
        return "%.0f triệu" % (value / 1_000_000)
    if value >= 1_000:
        return "%.0f nghìn" % (value / 1_000)
    return "%.0f" % value
