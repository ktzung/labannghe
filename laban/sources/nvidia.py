from __future__ import annotations

from datetime import date, timedelta

from .base import http_get, http_post, make_job, polite_sleep, save_raw

NAME = "nvidia"
LABEL = "NVIDIA Careers"
URL = "https://www.nvidia.com/en-us/about-nvidia/careers/"
NOTE = "API công khai của trang tuyển dụng NVIDIA (Workday); mô tả lấy từ trang chi tiết."

LIST_API = (
    "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/"
    "NVIDIAExternalCareerSite/jobs"
)
DETAIL_API = (
    "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/"
    "NVIDIAExternalCareerSite"
)


def _relative_date(value):
    text = str(value or "").strip().lower()
    if "today" in text:
        return date.today().isoformat()
    if "yesterday" in text:
        return (date.today() - timedelta(days=1)).isoformat()
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        days = int(digits)
        return (date.today() - timedelta(days=days)).isoformat()
    return None


def fetch(limit: int = 20):
    # Workday CXS trả 400 khi limit > 20.
    limit = min(limit, 20)
    payload = http_post(
        LIST_API,
        {"appliedFacets": {}, "limit": limit, "offset": 0, "searchText": ""},
    )
    postings = (payload.get("jobPostings") or [])[:limit]
    save_raw(NAME, {"ids": [item.get("bulletFields", [None])[0] for item in postings]})
    jobs = []
    for item in postings:
        path = item.get("externalPath") or ""
        if not path:
            continue
        try:
            polite_sleep()
            detail = http_get(DETAIL_API + path)
            info = detail.get("jobPostingInfo") or {}
        except Exception:  # noqa: BLE001
            info = {}
        title = info.get("title") or item.get("title", "")
        posted = info.get("startDate") or _relative_date(info.get("postedOn") or item.get("postedOn"))
        job = make_job(
            source=NAME,
            external_id=info.get("jobReqId") or item.get("bulletFields", [path])[0],
            url=info.get("externalUrl") or ("https://nvidia.wd5.myworkdayjobs.com" + path),
            title=title,
            company="NVIDIA",
            location=info.get("location") or item.get("locationsText", ""),
            country=(info.get("country") or {}).get("descriptor", ""),
            region="GLOBAL",
            remote="remote" in (item.get("locationsText") or "").lower(),
            employment_type=info.get("timeType", ""),
            description=info.get("jobDescription", ""),
            posted_at=str(posted)[:10] if posted else None,
            raw={"path": path, "posted": info.get("postedOn") or item.get("postedOn")},
        )
        if job:
            jobs.append(job)
    return jobs
