from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from .company import type_label, type_order, type_short_label
from .config import DEFAULT_WINDOW_DAYS, TOP_LEVEL_COMPANIES
from .db import db_stats, get_meta, social_db_stats
from .geo import parse_locations
from .social import social_labels
from .taxonomy import LEVEL_LABELS, find_evidence, load_skills, plan_for, role_index
from .text import fmt_vnd, median, today_iso

SKILLS, GROUPS = load_skills()
ROLES = role_index()


def _scope(scope: str) -> Tuple[str, list]:
    if scope == "vn":
        return "j.region='VN'", []
    if scope == "global":
        return "j.region='GLOBAL'", []
    return "1=1", []


def _comparable(total: int, prev_total: int) -> bool:
    # Kỳ trước quá mỏng thường do vừa bổ sung nguồn; so sánh sẽ tạo % tăng ảo.
    return prev_total >= 30 and prev_total >= total * 0.2


def _window(days: int) -> Tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def _date_clause(alias: str = "") -> str:
    prefix = (alias + ".") if alias else ""
    return "COALESCE(%sposted_at, %sfirst_seen) BETWEEN ? AND ?" % (prefix, prefix)


def _prev_clause(alias: str = "") -> str:
    prefix = (alias + ".") if alias else ""
    return "COALESCE(%sposted_at, %sfirst_seen) >= ? AND COALESCE(%sposted_at, %sfirst_seen) < ?" % (
        prefix, prefix, prefix, prefix,
    )


def _role_label(role_id: str) -> str:
    role = ROLES.get(role_id)
    return role["label"] if role else "Khác"


def _skill_label(skill_id: str) -> str:
    skill = SKILLS.get(skill_id)
    return skill.label if skill else skill_id


def _skill_group(skill_id: str) -> str:
    skill = SKILLS.get(skill_id)
    return skill.group if skill else "other"


def city_of(location: str) -> str:
    names = parse_locations(location)
    return names[0] if names else "Khác"


def detail_coverage(
    conn: sqlite3.Connection,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
    role: str = "",
) -> dict:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    role_sql = ""
    params = list(scope_params) + [start, end]
    if role:
        role_sql = " AND j.role=?"
        params.append(role)
    row = conn.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN length(trim(COALESCE(j.description, ''))) > 0 THEN 1 ELSE 0 END) with_description,
                  SUM(CASE WHEN length(trim(COALESCE(j.requirements, ''))) > 0 THEN 1 ELSE 0 END) with_requirements,
                  SUM(CASE WHEN length(trim(COALESCE(j.description, ''))) > 0
                            OR length(trim(COALESCE(j.requirements, ''))) > 0 THEN 1 ELSE 0 END) with_any
           FROM jobs j WHERE %s AND %s%s""" % (scope_sql, _date_clause("j"), role_sql),
        params,
    ).fetchone()
    total = row["total"] or 0
    return {
        "total": total,
        "with_description": row["with_description"] or 0,
        "with_requirements": row["with_requirements"] or 0,
        "with_any": row["with_any"] or 0,
        "description_coverage": round((row["with_description"] or 0) / total * 100.0, 1) if total else 0,
        "requirements_coverage": round((row["with_requirements"] or 0) / total * 100.0, 1) if total else 0,
        "any_coverage": round((row["with_any"] or 0) / total * 100.0, 1) if total else 0,
    }


def salary_midpoint(row) -> Optional[float]:
    lo, hi = row["salary_vnd_min"], row["salary_vnd_max"]
    if lo and hi:
        return (lo + hi) / 2.0
    return lo or hi


_CUR_SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£", "VND": "₫", "SGD": "S$", "AUD": "A$", "CAD": "C$", "JPY": "¥", "KRW": "₩"}
_PERIOD_SUFFIX = {"year": "/năm", "month": "/tháng", "hour": "/giờ", "day": "/ngày"}


def _compact_money(value: float) -> str:
    if value >= 1000:
        return ("%.0fk" % (value / 1000)) if value < 10000 else ("%.0fk" % (value / 1000))
    return "%.0f" % value


def salary_text(row) -> str:
    if row["region"] == "GLOBAL":
        lo, hi = row["salary_min"], row["salary_max"]
        if not lo and not hi:
            return "Thương lượng"
        currency = row["currency"] or "USD"
        symbol = _CUR_SYMBOL.get(currency, currency + " ")
        suffix = _PERIOD_SUFFIX.get(row["period"] or "year", "")
        if lo and hi and lo != hi:
            return "%s%s – %s%s%s" % (symbol, _compact_money(lo), symbol, _compact_money(hi), suffix)
        return "%s%s%s" % (symbol, _compact_money(lo or hi), suffix)
    lo, hi = row["salary_vnd_min"], row["salary_vnd_max"]
    if not lo and not hi:
        return "Thương lượng"
    if lo and hi:
        if lo == hi:
            return fmt_vnd(lo) + " ₫/tháng"
        return "%s – %s ₫/tháng" % (fmt_vnd(lo), fmt_vnd(hi))
    return fmt_vnd(lo or hi) + " ₫/tháng"


def _skill_map_for_jobs(conn, job_ids: Iterable[int]) -> Dict[int, List[dict]]:
    ids = list(job_ids)
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(
        "SELECT job_id, skill_id, weight, kind FROM job_skills WHERE job_id IN (%s) ORDER BY weight DESC, skill_id" % marks,
        ids,
    ).fetchall()
    result: Dict[int, List[dict]] = defaultdict(list)
    for row in rows:
        result[row["job_id"]].append(
            {
                "id": row["skill_id"],
                "label": _skill_label(row["skill_id"]),
                "group": _skill_group(row["skill_id"]),
                "kind": row["kind"],
            }
        )
    return result


def _job_dict(row, facets: Optional[List[dict]] = None) -> dict:
    company_type = row["company_type"] if "company_type" in row.keys() else "unknown"
    skills = [item for item in (facets or []) if item.get("kind") != "knowledge"]
    knowledge = [item for item in (facets or []) if item.get("kind") == "knowledge"]
    return {
        "id": row["id"],
        "title": row["title"],
        "company": row["company"],
        "company_logo": row["company_logo"],
        "company_tier": row["company_tier"],
        "company_type": company_type,
        "company_type_label": type_label(company_type),
        "location": row["location"],
        "region": row["region"],
        "remote": bool(row["remote"]),
        "level": row["level"],
        "level_label": LEVEL_LABELS.get(row["level"], row["level"]),
        "role": row["role"],
        "role_label": _role_label(row["role"]),
        "category": row["category"],
        "salary_text": salary_text(row),
        "salary_vnd": salary_midpoint(row),
        "currency": row["currency"],
        "posted_at": row["posted_at"],
        "url": row["url"],
        "source": row["source"] if "source" in row.keys() else "",
        "skills": [s["label"] for s in skills][:8],
        "skill_ids": [s["id"] for s in skills][:8],
        "knowledge": [s["label"] for s in knowledge][:6],
        "knowledge_ids": [s["id"] for s in knowledge][:6],
    }


def _source_for_jobs(conn, job_ids: Iterable[int]) -> Dict[int, str]:
    ids = list(job_ids)
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(
        "SELECT job_id, GROUP_CONCAT(source) AS sources FROM job_sources WHERE job_id IN (%s) GROUP BY job_id" % marks,
        ids,
    ).fetchall()
    return {r["job_id"]: (r["sources"] or "").split(",")[0] for r in rows}


def summary(conn: sqlite3.Connection, scope: str = "vn", days: int = DEFAULT_WINDOW_DAYS) -> dict:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    prev_start = (date.fromisoformat(start) - timedelta(days=days)).isoformat()
    today = today_iso()

    base = "FROM jobs j WHERE " + scope_sql
    row = conn.execute(
        """SELECT COUNT(*) jobs,
                  COUNT(DISTINCT CASE WHEN COALESCE(j.company_type, 'unknown') != 'agency'
                                      THEN j.company_slug END) companies,
                  COUNT(DISTINCT j.role) roles,
                  SUM(CASE WHEN date(COALESCE(j.posted_at, j.first_seen))=? THEN 1 ELSE 0 END) new_today,
                  SUM(CASE WHEN j.region='VN' THEN 1 ELSE 0 END) vn_jobs
           %s AND %s""" % (base, _date_clause("j")),
        [today] + scope_params + [start, end],
    ).fetchone()

    prev = conn.execute(
        "SELECT COUNT(*) n %s AND %s" % (base, _date_clause("j")),
        scope_params + [prev_start, start],
    ).fetchone()

    salary_rows = conn.execute(
        """SELECT j.salary_vnd_min, j.salary_vnd_max, j.currency
           %s AND %s AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (base, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    salaries = [salary_midpoint(r) for r in salary_rows]
    salaries = [s for s in salaries if s]
    vn_median = median(salaries)

    salary_cov = conn.execute(
        """SELECT COUNT(*) n %s AND %s AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) > 0""" % (base, _date_clause("j")),
        scope_params + [start, end],
    ).fetchone()["n"]

    global_salary = conn.execute(
        """SELECT j.salary_min, j.salary_max FROM jobs j
           WHERE %s AND %s AND j.region='GLOBAL' AND j.currency='USD'
             AND COALESCE(j.salary_min, j.salary_max) > 0""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    annual = []
    for r in global_salary:
        lo, hi = r["salary_min"], r["salary_max"]
        annual.append((lo + hi) / 2.0 if lo and hi else (lo or hi))
    global_median = median(annual)

    daily_rows = conn.execute(
        """SELECT date(COALESCE(j.posted_at, j.first_seen)) d, COUNT(*) n
           %s AND %s GROUP BY d ORDER BY d""" % (base, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    daily_map = {r["d"]: r["n"] for r in daily_rows}
    daily = []
    for i in range(min(days, 30), -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        daily.append({"date": d, "count": daily_map.get(d, 0)})

    source_rows = conn.execute(
        """SELECT js.source, COUNT(DISTINCT j.id) n
           FROM job_sources js JOIN jobs j ON j.id=js.job_id
           WHERE %s AND %s GROUP BY js.source ORDER BY n DESC""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()

    total = row["jobs"] or 0
    prev_total = prev["n"] or 0
    change = None
    if _comparable(total, prev_total):
        change = round((total - prev_total) / prev_total * 100.0, 1)

    top = top_skills(conn, scope=scope, days=days, limit=40)
    top_standards = sorted(
        [item for item in top if item["strong_jobs"]],
        key=lambda item: (item["strong_jobs"], item["jobs"]),
        reverse=True,
    )[:8]
    return {
        "scope": scope,
        "days": days,
        "window": {"start": start, "end": end},
        "details": detail_coverage(conn, scope=scope, days=days),
        "kpis": {
            "jobs": total,
            "jobs_prev": prev_total,
            "jobs_change": change,
            "companies": row["companies"] or 0,
            "roles": row["roles"] or 0,
            "new_today": row["new_today"] or 0,
            "skills_tracked": len(SKILLS),
            "vn_median_salary": vn_median,
            "vn_median_salary_text": fmt_vnd(vn_median) + " ₫" if vn_median else "—",
            "salary_coverage": round(salary_cov / total * 100.0, 1) if total else 0,
            "global_median_usd": round(global_median) if global_median else None,
        },
        "top_skills": top[:8],
        "top_standards": top_standards,
        "top_companies": top_companies(conn, scope=scope, days=days, limit=8),
        "top_locations": top_locations(conn, scope=scope, days=days, limit=8),
        "company_types": company_type_breakdown(conn, scope=scope, days=days),
        "daily": daily,
        "sources": [{"id": r["source"], "count": r["n"]} for r in source_rows],
        "db": db_stats(conn),
        "last_ingest": get_meta(conn, "last_ingest"),
    }


def top_skills(
    conn: sqlite3.Connection,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
    role: str = "",
    limit: int = 20,
    kind: str = "skill",
) -> List[dict]:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    prev_start = (date.fromisoformat(start) - timedelta(days=days)).isoformat()
    role_sql = ""
    params: list = []
    if role and role != "all":
        role_sql = " AND j.role=?"
        params.append(role)

    rows = conn.execute(
        """SELECT js.skill_id,
                  SUM(CASE WHEN %s THEN 1 ELSE 0 END) recent,
                  SUM(CASE WHEN %s AND js.weight >= 4 THEN 1 ELSE 0 END) strong_recent,
                  SUM(CASE WHEN %s THEN 1 ELSE 0 END) prev
           FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE %s AND (%s OR %s) %s AND js.kind=?
           GROUP BY js.skill_id
           ORDER BY recent DESC
           LIMIT ?""" % (
            _date_clause("j"), _date_clause("j"), _prev_clause("j"), scope_sql,
            _date_clause("j"), _prev_clause("j"), role_sql,
        ),
        scope_params + [start, end] + [start, end] + [prev_start, start] + [start, end] + [prev_start, start] + params + [kind, max(limit * 3, 40)],
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) n FROM jobs j WHERE %s AND %s %s" % (scope_sql, _date_clause("j"), role_sql),
        scope_params + [start, end] + params,
    ).fetchone()["n"]
    prev_total = conn.execute(
        "SELECT COUNT(*) n FROM jobs j WHERE %s AND %s %s" % (scope_sql, _prev_clause("j"), role_sql),
        scope_params + [prev_start, start] + params,
    ).fetchone()["n"]

    result = []
    for row in rows:
        if not row["recent"]:
            continue
        share = row["recent"] / total if total else 0
        prev_share = row["prev"] / prev_total if prev_total else 0
        delta = (share - prev_share) * 100.0 if _comparable(total, prev_total) else None
        strong_share = row["strong_recent"] / total if total else 0
        result.append(
            {
                "id": row["skill_id"],
                "label": _skill_label(row["skill_id"]),
                "group": _skill_group(row["skill_id"]),
                "group_label": GROUPS.get(_skill_group(row["skill_id"]), "Khác"),
                "kind": kind,
                "jobs": row["recent"],
                "share": round(share * 100.0, 1),
                "strong_jobs": row["strong_recent"] or 0,
                "strong_share": round(strong_share * 100.0, 1),
                "prev_jobs": row["prev"],
                "delta": round(delta, 1) if delta is not None else None,
            }
        )
    result.sort(key=lambda x: (x["jobs"], x["delta"] or 0), reverse=True)
    return result[:limit]


def skill_salary_stats(
    conn,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
    kind: str = "skill",
) -> Dict[str, dict]:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    rows = conn.execute(
        """SELECT js.skill_id, j.salary_vnd_min, j.salary_vnd_max
           FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE %s AND %s AND js.kind=? AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end, kind],
    ).fetchall()
    buckets: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        mid = salary_midpoint(r)
        if mid:
            buckets[r["skill_id"]].append(mid)
    all_rows = conn.execute(
        """SELECT j.salary_vnd_min, j.salary_vnd_max FROM jobs j
           WHERE %s AND %s AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    overall = median([salary_midpoint(r) for r in all_rows])
    result = {}
    for skill_id, values in buckets.items():
        m = median(values)
        result[skill_id] = {
            "median": m,
            "median_text": fmt_vnd(m) + " ₫" if m else "—",
            "premium": round((m / overall - 1) * 100.0, 1) if m and overall else None,
        }
    return result


def rising_skills(conn, scope: str = "vn", days: int = 14, limit: int = 6) -> List[dict]:
    skills = top_skills(conn, scope=scope, days=days, limit=60)
    candidates = [s for s in skills if s["jobs"] >= max(3, skills[0]["jobs"] * 0.05 if skills else 3) and s["delta"] is not None]
    candidates = [s for s in candidates if s["delta"] > 0]
    candidates.sort(key=lambda s: s["delta"] * math.sqrt(s["jobs"]), reverse=True)
    return candidates[:limit]


def role_standards(
    conn: sqlite3.Connection,
    role_id: str,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 8,
    evidence: bool = True,
    kind: str = "skill",
) -> dict:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    total = conn.execute(
        "SELECT COUNT(*) n FROM jobs j WHERE j.role=? AND %s AND %s" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchone()["n"] or 0
    details = detail_coverage(conn, scope=scope, days=days, role=role_id)
    rows = conn.execute(
        """SELECT js.skill_id, COUNT(*) jobs,
                  SUM(CASE WHEN js.weight >= 4 THEN 1 ELSE 0 END) strong_jobs
           FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE j.role=? AND %s AND %s AND js.kind=?
           GROUP BY js.skill_id
           ORDER BY strong_jobs DESC, jobs DESC
           LIMIT ?""" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end, kind, limit],
    ).fetchall()

    items = []
    for row in rows:
        item = {
            "id": row["skill_id"],
            "label": _skill_label(row["skill_id"]),
            "group": _skill_group(row["skill_id"]),
            "group_label": GROUPS.get(_skill_group(row["skill_id"]), "Khác"),
            "kind": kind,
            "jobs": row["jobs"],
            "share": round(row["jobs"] / total * 100.0, 1) if total else 0,
            "strong_jobs": row["strong_jobs"] or 0,
            "strong_share": round((row["strong_jobs"] or 0) / total * 100.0, 1) if total else 0,
            "evidence": [],
        }
        if evidence:
            job_rows = conn.execute(
                """SELECT j.title, j.company, j.url, j.requirements, j.description
                   FROM job_skills js JOIN jobs j ON j.id=js.job_id
                   WHERE js.skill_id=? AND j.role=? AND %s AND %s AND js.kind=?
                   ORDER BY COALESCE(j.posted_at, j.first_seen) DESC
                   LIMIT 4""" % (scope_sql, _date_clause("j")),
                [row["skill_id"], role_id] + scope_params + [start, end, kind],
            ).fetchall()
            for job in job_rows:
                text = "\n".join([job["requirements"] or "", job["description"] or ""])
                for sentence in find_evidence(row["skill_id"], text, limit=2):
                    item["evidence"].append(
                        {
                            "job_title": job["title"],
                            "company": job["company"],
                            "url": job["url"],
                            "text": sentence,
                        }
                    )
                    if len(item["evidence"]) >= 2:
                        break
                if len(item["evidence"]) >= 2:
                    break
        items.append(item)
    return {
        "total_jobs": total,
        "detail_jobs": details["with_any"],
        "detail_coverage": details["any_coverage"],
        "items": items,
        "note": "Bằng chứng mạnh = xuất hiện trong thẻ, yêu cầu hoặc mô tả chi tiết; tiêu đề chỉ là tín hiệu phụ.",
    }


def roles_breakdown(conn, scope: str = "vn", days: int = DEFAULT_WINDOW_DAYS, limit: int = 12) -> List[dict]:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    rows = conn.execute(
        """SELECT j.role, COUNT(*) n FROM jobs j
           WHERE %s AND %s GROUP BY j.role ORDER BY n DESC""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    total = sum(r["n"] for r in rows) or 1
    detail_rows = conn.execute(
        """SELECT j.role,
                  SUM(CASE WHEN length(trim(COALESCE(j.description, ''))) > 0
                            OR length(trim(COALESCE(j.requirements, ''))) > 0 THEN 1 ELSE 0 END) detail
           FROM jobs j WHERE %s AND %s GROUP BY j.role""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    detail_map = {r["role"]: r["detail"] or 0 for r in detail_rows}
    result = []
    for row in rows[:limit]:
        top = conn.execute(
            """SELECT js.skill_id, COUNT(*) n,
                      SUM(CASE WHEN js.weight >= 4 THEN 1 ELSE 0 END) strong
               FROM job_skills js JOIN jobs j ON j.id=js.job_id
               WHERE j.role=? AND %s AND %s AND js.kind='skill' GROUP BY js.skill_id
               ORDER BY strong DESC, n DESC LIMIT 3""" % (scope_sql, _date_clause("j")),
            [row["role"]] + scope_params + [start, end],
        ).fetchall()
        salary_rows = conn.execute(
            """SELECT j.salary_vnd_min, j.salary_vnd_max FROM jobs j
               WHERE j.role=? AND %s AND %s AND j.region='VN'
                 AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (scope_sql, _date_clause("j")),
            [row["role"]] + scope_params + [start, end],
        ).fetchall()
        salary = median([salary_midpoint(r) for r in salary_rows])
        detail_jobs = detail_map.get(row["role"], 0)
        result.append(
            {
                "id": row["role"],
                "label": _role_label(row["role"]),
                "jobs": row["n"],
                "share": round(row["n"] / total * 100.0, 1),
                "top_skills": [_skill_label(t["skill_id"]) for t in top],
                "standard_skills": [
                    {
                        "id": t["skill_id"],
                        "label": _skill_label(t["skill_id"]),
                        "jobs": t["n"],
                        "strong_jobs": t["strong"] or 0,
                        "share": round(t["n"] / row["n"] * 100.0, 1) if row["n"] else 0,
                        "strong_share": round((t["strong"] or 0) / row["n"] * 100.0, 1) if row["n"] else 0,
                    }
                    for t in top
                ],
                "detail_jobs": detail_jobs,
                "detail_coverage": round(detail_jobs / row["n"] * 100.0, 1) if row["n"] else 0,
                "median_salary": salary,
                "median_salary_text": fmt_vnd(salary) + " ₫" if salary else "—",
            }
        )
    result.sort(key=lambda x: (x["id"] == "other", -x["jobs"]))
    return result


def role_detail(conn, role_id: str, scope: str = "vn", days: int = DEFAULT_WINDOW_DAYS) -> dict:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    row = conn.execute(
        "SELECT COUNT(*) n FROM jobs j WHERE j.role=? AND %s AND %s" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) n FROM jobs j WHERE %s AND %s" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchone()["n"]
    skills = top_skills(conn, scope=scope, days=days, role=role_id, limit=10, kind="skill")
    knowledge = top_skills(conn, scope=scope, days=days, role=role_id, limit=8, kind="knowledge")

    salary_rows = conn.execute(
        """SELECT j.salary_vnd_min, j.salary_vnd_max FROM jobs j
           WHERE j.role=? AND %s AND %s AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchall()
    salary = median([salary_midpoint(r) for r in salary_rows])

    levels = conn.execute(
        "SELECT level, COUNT(*) n FROM jobs j WHERE j.role=? AND %s AND %s GROUP BY level ORDER BY n DESC" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchall()

    companies = conn.execute(
        """SELECT company, company_tier, COUNT(*) n FROM jobs j
           WHERE j.role=? AND %s AND %s AND company != ''
             AND COALESCE(j.company_type, 'unknown') != 'agency'
           GROUP BY company ORDER BY company_tier DESC, n DESC LIMIT 8""" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchall()

    locations = conn.execute(
        """SELECT jl.city, COUNT(DISTINCT j.id) n
           FROM jobs j JOIN job_locations jl ON jl.job_id=j.id
           WHERE j.role=? AND %s AND %s
           GROUP BY jl.city ORDER BY n DESC, jl.city LIMIT 5""" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchall()
    top_cities = [(row["city"], row["n"]) for row in locations]

    job_rows = conn.execute(
        """SELECT j.*, (SELECT js.source FROM job_sources js WHERE js.job_id=j.id LIMIT 1) source
           FROM jobs j WHERE j.role=? AND %s AND %s
           ORDER BY COALESCE(j.posted_at, j.first_seen) DESC LIMIT 12""" % (scope_sql, _date_clause("j")),
        [role_id] + scope_params + [start, end],
    ).fetchall()
    skill_map = _skill_map_for_jobs(conn, [r["id"] for r in job_rows])
    standards = role_standards(conn, role_id, scope=scope, days=days, limit=8, evidence=True)

    role = ROLES.get(role_id, {})
    return {
        "id": role_id,
        "label": _role_label(role_id),
        "jobs": row["n"],
        "share": round((row["n"] or 0) / total * 100.0, 1) if total else 0,
        "median_salary": salary,
        "median_salary_text": fmt_vnd(salary) + " ₫/tháng" if salary else "Chưa đủ dữ liệu",
        "skills": skills,
        "knowledge": knowledge,
        "standards": standards,
        "detail_jobs": standards["detail_jobs"],
        "detail_coverage": standards["detail_coverage"],
        "levels": [{"id": r["level"], "label": LEVEL_LABELS.get(r["level"], r["level"]), "jobs": r["n"]} for r in levels],
        "companies": [
            {"name": r["company"], "jobs": r["n"], "tier": r["company_tier"]} for r in companies
        ],
        "cities": [{"name": name, "jobs": n} for name, n in top_cities],
        "jobs_list": [_job_dict(r, skill_map.get(r["id"])) for r in job_rows],
        "plan": plan_for(role_id),
        "total_in_scope": total,
    }


def skill_detail(conn, skill_id: str, scope: str = "vn", days: int = DEFAULT_WINDOW_DAYS) -> dict:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    skill = SKILLS.get(skill_id)
    if not skill:
        return {"id": skill_id, "label": skill_id, "jobs": 0, "share": 0, "trend": [], "roles": [], "companies": [], "jobs_list": []}
    total = conn.execute(
        "SELECT COUNT(*) n FROM jobs j WHERE %s AND %s" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchone()["n"]
    n = conn.execute(
        """SELECT COUNT(*) n FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE js.skill_id=? AND %s AND %s""" % (scope_sql, _date_clause("j")),
        [skill_id] + scope_params + [start, end],
    ).fetchone()["n"]
    role_rows = conn.execute(
        """SELECT j.role, COUNT(*) n FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE js.skill_id=? AND %s AND %s GROUP BY j.role ORDER BY n DESC LIMIT 6""" % (scope_sql, _date_clause("j")),
        [skill_id] + scope_params + [start, end],
    ).fetchall()
    company_rows = conn.execute(
        """SELECT j.company, COUNT(*) n FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE js.skill_id=? AND %s AND %s AND j.company != ''
             AND COALESCE(j.company_type, 'unknown') != 'agency'
           GROUP BY j.company ORDER BY n DESC LIMIT 8""" % (scope_sql, _date_clause("j")),
        [skill_id] + scope_params + [start, end],
    ).fetchall()
    job_rows = conn.execute(
        """SELECT j.*, (SELECT js.source FROM job_sources js WHERE js.job_id=j.id LIMIT 1) source
           FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE js.skill_id=? AND %s AND %s
           ORDER BY COALESCE(j.posted_at, j.first_seen) DESC LIMIT 8""" % (scope_sql, _date_clause("j")),
        [skill_id] + scope_params + [start, end],
    ).fetchall()

    salary_rows = conn.execute(
        """SELECT j.salary_vnd_min, j.salary_vnd_max FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE js.skill_id=? AND %s AND %s AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (scope_sql, _date_clause("j")),
        [skill_id] + scope_params + [start, end],
    ).fetchall()
    all_salary_rows = conn.execute(
        """SELECT j.salary_vnd_min, j.salary_vnd_max FROM jobs j
           WHERE %s AND %s AND j.region='VN'
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    skill_salary = median([salary_midpoint(r) for r in salary_rows])
    all_salary = median([salary_midpoint(r) for r in all_salary_rows])

    trend = _skill_weekly(conn, skill_id, scope_sql, scope_params, weeks=12)
    skill_map = _skill_map_for_jobs(conn, [r["id"] for r in job_rows])
    return {
        "id": skill_id,
        "label": skill.label,
        "group": skill.group,
        "group_label": GROUPS.get(skill.group, "Khác"),
        "kind": skill.kind,
        "jobs": n,
        "share": round(n / total * 100.0, 1) if total else 0,
        "median_salary": skill_salary,
        "median_salary_text": fmt_vnd(skill_salary) + " ₫/tháng" if skill_salary else "—",
        "salary_premium": round((skill_salary / all_salary - 1) * 100.0, 1) if skill_salary and all_salary else None,
        "trend": trend,
        "roles": [{"id": r["role"], "label": _role_label(r["role"]), "jobs": r["n"]} for r in role_rows],
        "companies": [{"name": r["company"], "jobs": r["n"]} for r in company_rows],
        "jobs_list": [_job_dict(r, skill_map.get(r["id"])) for r in job_rows],
    }


def _skill_weekly(conn, skill_id: str, scope_sql: str, scope_params: list, weeks: int = 12) -> List[dict]:
    rows = conn.execute(
        """SELECT date(COALESCE(j.posted_at, j.first_seen), 'weekday 0', '-6 days') week_start, COUNT(*) n
           FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE js.skill_id=? AND %s AND COALESCE(j.posted_at, j.first_seen) >= date('now', ?)
           GROUP BY week_start ORDER BY week_start""" % scope_sql,
        [skill_id] + scope_params + ["-%d days" % (weeks * 7)],
    ).fetchall()
    counts = {r["week_start"]: r["n"] for r in rows}
    result = []
    monday = date.today() - timedelta(days=date.today().weekday())
    for i in range(weeks - 1, -1, -1):
        d = (monday - timedelta(weeks=i)).isoformat()
        result.append({"week": d, "count": counts.get(d, 0)})
    return result


def top_locations(
    conn: sqlite3.Connection,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 8,
) -> dict:
    if scope == "global":
        return {"items": [], "total": 0, "with_location": 0, "coverage": 0, "note": "Chỉ phân tích tin Việt Nam."}
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    base = "FROM jobs j WHERE %s AND %s AND j.region='VN'" % (scope_sql, _date_clause("j"))
    total = conn.execute("SELECT COUNT(*) n " + base, scope_params + [start, end]).fetchone()["n"] or 0
    with_location = conn.execute(
        "SELECT COUNT(*) n " + base + " AND EXISTS (SELECT 1 FROM job_locations jl WHERE jl.job_id=j.id)",
        scope_params + [start, end],
    ).fetchone()["n"] or 0
    rows = conn.execute(
        """SELECT jl.city, COUNT(DISTINCT j.id) n
           FROM jobs j JOIN job_locations jl ON jl.job_id=j.id
           WHERE %s AND %s AND j.region='VN'
           GROUP BY jl.city ORDER BY n DESC, jl.city LIMIT ?""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end, limit],
    ).fetchall()
    return {
        "items": [
            {"name": row["city"], "jobs": row["n"], "share": round(row["n"] / total * 100.0, 1) if total else 0}
            for row in rows
        ],
        "total": total,
        "with_location": with_location,
        "coverage": round(with_location / total * 100.0, 1) if total else 0,
        "note": "Một tin có thể có nhiều địa điểm; tỷ lệ tính trên tổng tin Việt Nam trong phạm vi.",
    }


def company_type_breakdown(
    conn: sqlite3.Connection,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    if scope == "global":
        return {"items": [], "total": 0, "known": 0, "coverage": 0, "note": "Chỉ phân tích tin Việt Nam."}
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    rows = conn.execute(
        """SELECT COALESCE(j.company_type, 'unknown') company_type,
                  j.salary_vnd_min, j.salary_vnd_max
           FROM jobs j
           WHERE %s AND %s AND j.region='VN'""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    ).fetchall()
    buckets: Dict[str, dict] = {}
    for row in rows:
        key = row["company_type"] or "unknown"
        bucket = buckets.setdefault(key, {"jobs": 0, "salaries": []})
        bucket["jobs"] += 1
        value = salary_midpoint(row)
        if value and 1000000 <= value <= 500000000:
            bucket["salaries"].append(value)
    total = sum(bucket["jobs"] for bucket in buckets.values())
    known = total - buckets.get("unknown", {}).get("jobs", 0)
    order = {key: index for index, key in enumerate(type_order())}
    items = []
    for key, bucket in buckets.items():
        salary = median(bucket["salaries"])
        items.append(
            {
                "id": key,
                "label": type_label(key),
                "short_label": type_short_label(key),
                "jobs": bucket["jobs"],
                "share": round(bucket["jobs"] / total * 100.0, 1) if total else 0,
                "median_salary": salary,
                "median_salary_text": fmt_vnd(salary) + " ₫/tháng" if salary else "—",
            }
        )
    items.sort(key=lambda item: (-item["jobs"], order.get(item["id"], 99)))
    return {
        "items": items,
        "total": total,
        "known": known,
        "coverage": round(known / total * 100.0, 1) if total else 0,
        "note": "Phân loại tham chiếu theo tên doanh nghiệp; nhóm Chưa xác định không bị gán bừa.",
    }


def _social_forum_sql(forum: str) -> Tuple[str, list]:
    if forum and forum != "all":
        return " AND s.forum_id=?", [forum]
    return "", []


def _social_tag_counts(
    conn: sqlite3.Connection,
    kind: str,
    start: str,
    end: str,
    forum: str = "all",
) -> Dict[str, dict]:
    forum_sql, forum_params = _social_forum_sql(forum)
    rows = conn.execute(
        """SELECT st.tag_id, COUNT(DISTINCT s.thread_id) threads,
                  COALESCE(SUM(s.replies), 0) replies,
                  COALESCE(SUM(st.weight), 0) weight
           FROM social_thread_tags st JOIN social_threads s ON s.thread_id=st.thread_id
           WHERE st.kind=? AND s.is_job_ad=0 AND COALESCE(s.posted_at, s.first_seen) BETWEEN ? AND ?%s
           GROUP BY st.tag_id""" % forum_sql,
        [kind, start, end] + forum_params,
    ).fetchall()
    return {row["tag_id"]: dict(row) for row in rows}


def social_summary(conn: sqlite3.Connection, days: int = DEFAULT_WINDOW_DAYS, forum: str = "all", limit: int = 8) -> dict:
    start, end = _window(days)
    prev_start = (date.fromisoformat(start) - timedelta(days=days)).isoformat()
    forum_sql, forum_params = _social_forum_sql(forum)
    base = "FROM social_threads s WHERE " + _date_clause("s") + forum_sql
    row = conn.execute(
        """SELECT COUNT(*) threads,
                  SUM(CASE WHEN s.is_job_ad=0 THEN 1 ELSE 0 END) discussions,
                  SUM(CASE WHEN s.is_job_ad=1 THEN 1 ELSE 0 END) job_ads,
                  COALESCE(SUM(s.replies), 0) replies,
                  COUNT(DISTINCT s.forum_id) forums,
                  SUM(CASE WHEN EXISTS (
                      SELECT 1 FROM social_thread_tags st WHERE st.thread_id=s.thread_id AND st.kind='skill'
                  ) THEN 1 ELSE 0 END) with_skills
           %s""" % base,
        [start, end] + forum_params,
    ).fetchone()
    prev = conn.execute(
        "SELECT COUNT(*) n FROM social_threads s WHERE s.is_job_ad=0 AND " + _prev_clause("s") + forum_sql,
        [prev_start, start] + forum_params,
    ).fetchone()
    discussions = row["discussions"] or 0
    prev_discussions = prev["n"] or 0

    forum_rows = conn.execute(
        """SELECT s.forum_id, s.forum_label, COUNT(*) threads,
                  SUM(CASE WHEN s.is_job_ad=0 THEN 1 ELSE 0 END) discussions,
                  COALESCE(SUM(s.replies), 0) replies
           FROM social_threads s WHERE %s%s
           GROUP BY s.forum_id ORDER BY discussions DESC""" % (_date_clause("s"), forum_sql),
        [start, end] + forum_params,
    ).fetchall()

    labels = social_labels()
    current_topics = _social_tag_counts(conn, "topic", start, end, forum)
    previous_topics = _social_tag_counts(conn, "topic", prev_start, start, forum)
    current_issues = _social_tag_counts(conn, "issue", start, end, forum)
    previous_issues = _social_tag_counts(conn, "issue", prev_start, start, forum)
    current_skills = _social_tag_counts(conn, "skill", start, end, forum)
    job_skills = {item["id"]: item for item in top_skills(conn, scope="vn", days=days, limit=200)}

    def build_tag_items(current, previous, label_map, limit_count):
        items = []
        for tag_id, stat in current.items():
            prev_stat = previous.get(tag_id, {})
            share = stat["threads"] / discussions * 100.0 if discussions else 0
            prev_share = prev_stat.get("threads", 0) / prev_discussions * 100.0 if prev_discussions else 0
            delta = share - prev_share if prev_discussions >= 20 else None
            items.append(
                {
                    "id": tag_id,
                    "label": label_map.get(tag_id, tag_id),
                    "threads": stat["threads"],
                    "replies": stat["replies"],
                    "share": round(share, 1),
                    "prev_threads": prev_stat.get("threads", 0),
                    "delta": round(delta, 1) if delta is not None else None,
                }
            )
        items.sort(key=lambda item: (item["threads"], item["replies"]), reverse=True)
        return items[:limit_count]

    skill_items = []
    for tag_id, stat in current_skills.items():
        if stat["threads"] < 3:
            continue
        social_share = stat["threads"] / discussions * 100.0 if discussions else 0
        job = job_skills.get(tag_id, {})
        job_share = job.get("share", 0)
        skill_items.append(
            {
                "id": tag_id,
                "label": _skill_label(tag_id),
                "group": _skill_group(tag_id),
                "group_label": GROUPS.get(_skill_group(tag_id), "Khác"),
                "threads": stat["threads"],
                "replies": stat["replies"],
                "share": round(social_share, 1),
                "job_share": job_share,
                "gap": round(social_share - job_share, 1),
            }
        )
    skill_items.sort(key=lambda item: (item["threads"], item["replies"]), reverse=True)

    thread_rows = conn.execute(
        """SELECT s.* FROM social_threads s
           WHERE s.is_job_ad=0 AND %s%s
           ORDER BY s.replies DESC, COALESCE(s.posted_at, s.first_seen) DESC
           LIMIT ?""" % (_date_clause("s"), forum_sql),
        [start, end] + forum_params + [max(limit, 6)],
    ).fetchall()
    thread_ids = [r["thread_id"] for r in thread_rows]
    tag_map: Dict[int, dict] = defaultdict(lambda: {"topics": [], "issues": []})
    if thread_ids:
        marks = ",".join("?" for _ in thread_ids)
        tag_rows = conn.execute(
            """SELECT thread_id, kind, tag_id FROM social_thread_tags
               WHERE thread_id IN (%s) AND kind IN ('topic', 'issue')""" % marks,
            thread_ids,
        ).fetchall()
        for tag in tag_rows:
            if tag["kind"] == "topic":
                tag_map[tag["thread_id"]]["topics"].append(labels["topic"].get(tag["tag_id"], tag["tag_id"]))
            else:
                tag_map[tag["thread_id"]]["issues"].append(labels["issue"].get(tag["tag_id"], tag["tag_id"]))
    hot_threads = [
        {
            "id": r["thread_id"],
            "title": r["title"],
            "url": r["url"],
            "forum": r["forum_label"],
            "replies": r["replies"],
            "posted_at": r["posted_at"],
            "role": r["role"],
            "role_label": _role_label(r["role"]),
            "excerpt": (r["excerpt"] or "")[:220],
            "topics": tag_map[r["thread_id"]]["topics"],
            "issues": tag_map[r["thread_id"]]["issues"],
        }
        for r in thread_rows
    ]

    daily_rows = conn.execute(
        """SELECT date(COALESCE(s.posted_at, s.first_seen)) d, COUNT(*) n
           FROM social_threads s
           WHERE s.is_job_ad=0 AND %s%s GROUP BY d ORDER BY d""" % (_date_clause("s"), forum_sql),
        [start, end] + forum_params,
    ).fetchall()
    daily_map = {r["d"]: r["n"] for r in daily_rows}
    daily = []
    for i in range(min(days, 30), -1, -1):
        day = (date.today() - timedelta(days=i)).isoformat()
        daily.append({"date": day, "count": daily_map.get(day, 0)})

    runs = conn.execute(
        """SELECT source, finished_at, fetched, inserted, updated, errors, note
           FROM social_runs ORDER BY id DESC LIMIT 8"""
    ).fetchall()
    last_note = runs[0]["note"] if runs else ""
    mode = "file" if "[file]" in last_note else "http" if "[http]" in last_note else "unknown"

    return {
        "days": days,
        "forum": forum,
        "window": {"start": start, "end": end},
        "kpis": {
            "threads": row["threads"] or 0,
            "discussions": discussions,
            "job_ads": row["job_ads"] or 0,
            "replies": row["replies"] or 0,
            "forums": row["forums"] or 0,
            "with_skills": row["with_skills"] or 0,
            "skills_tracked": len(SKILLS),
        },
        "forums": [
            {
                "id": r["forum_id"],
                "label": r["forum_label"],
                "threads": r["threads"],
                "discussions": r["discussions"],
                "replies": r["replies"],
            }
            for r in forum_rows
        ],
        "topics": build_tag_items(current_topics, previous_topics, labels["topic"], limit),
        "issues": build_tag_items(current_issues, previous_issues, labels["issue"], limit + 2),
        "skills": skill_items[:12],
        "hot_threads": hot_threads,
        "daily": daily,
        "runs": [dict(r) for r in runs],
        "mode": mode,
        "db": social_db_stats(conn),
        "last_ingest": get_meta(conn, "last_social_ingest"),
        "note": "Chỉ đọc tiêu đề và phần trích đoạn RSS công khai; không lưu tên tác giả, không thu thập bình luận.",
        "caveat": "Mỗi chuyên mục chỉ có khoảng 20 thớt mới nhất trong RSS; mẫu không đại diện cho toàn bộ diễn đàn.",
    }


def top_companies(conn, scope: str = "vn", days: int = DEFAULT_WINDOW_DAYS, limit: int = 8) -> List[dict]:
    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    rows = conn.execute(
        """SELECT j.company, j.company_slug, j.company_tier, COUNT(*) n
           FROM jobs j
           WHERE %s AND %s AND j.company != ''
             AND COALESCE(j.company_type, 'unknown') != 'agency'
             AND instr(lower(j.company), 'client') = 0
             AND instr(lower(j.company), 'navigos search') = 0
           GROUP BY j.company_slug
           ORDER BY n DESC, j.company_tier DESC LIMIT ?""" % (scope_sql, _date_clause("j")),
        scope_params + [start, end, limit],
    ).fetchall()
    return [
        {"name": r["company"], "slug": r["company_slug"], "tier": r["company_tier"], "jobs": r["n"]}
        for r in rows
    ]


def weekly_jobs(conn, scope: str = "vn", weeks: int = 12) -> List[dict]:
    scope_sql, scope_params = _scope(scope)
    rows = conn.execute(
        """SELECT date(COALESCE(j.posted_at, j.first_seen), 'weekday 0', '-6 days') week_start, COUNT(*) n
           FROM jobs j WHERE %s AND COALESCE(j.posted_at, j.first_seen) >= date('now', ?)
           GROUP BY week_start ORDER BY week_start""" % scope_sql,
        scope_params + ["-%d days" % (weeks * 7)],
    ).fetchall()
    counts = {r["week_start"]: r["n"] for r in rows}
    result = []
    monday = date.today() - timedelta(days=date.today().weekday())
    for i in range(weeks - 1, -1, -1):
        d = (monday - timedelta(weeks=i)).isoformat()
        result.append({"week": d, "count": counts.get(d, 0)})
    return result


def jobs_search(
    conn,
    scope: str = "vn",
    role: str = "",
    skill: str = "",
    level: str = "",
    source: str = "",
    q: str = "",
    days: int = 90,
    limit: int = 30,
    offset: int = 0,
) -> dict:
    scope_sql, params = _scope(scope)
    start, end = _window(days)
    clauses = [scope_sql, _date_clause("j")]
    params = params + [start, end]
    if role and role != "all":
        clauses.append("j.role=?")
        params.append(role)
    if level and level != "all":
        clauses.append("j.level=?")
        params.append(level)
    if source:
        clauses.append("EXISTS (SELECT 1 FROM job_sources s WHERE s.job_id=j.id AND s.source=?)")
        params.append(source)
    if skill:
        clauses.append("EXISTS (SELECT 1 FROM job_skills sk WHERE sk.job_id=j.id AND sk.skill_id=?)")
        params.append(skill)
    if q:
        clauses.append("(j.title LIKE ? OR j.company LIKE ?)")
        needle = "%" + q.strip() + "%"
        params.extend([needle, needle])
    where = " AND ".join(clauses)
    total = conn.execute("SELECT COUNT(*) n FROM jobs j WHERE " + where, params).fetchone()["n"]
    rows = conn.execute(
        """SELECT j.*, (SELECT js.source FROM job_sources js WHERE js.job_id=j.id LIMIT 1) source
           FROM jobs j WHERE %s ORDER BY COALESCE(j.posted_at, j.first_seen) DESC, j.id DESC
           LIMIT ? OFFSET ?""" % where,
        params + [limit, offset],
    ).fetchall()
    skill_map = _skill_map_for_jobs(conn, [r["id"] for r in rows])
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "jobs": [_job_dict(r, skill_map.get(r["id"])) for r in rows],
    }


IT_ROLES = ("software", "devops", "qa", "data", "ai_ml", "security", "mobile")
IT_GROUPS = ("programming", "data", "web", "cloud", "tools", "soft", "language")
IT_TECH_GROUPS = ("programming", "data", "web", "cloud")

# Từ khoá mô tả nội dung công việc; chỉ dùng để đọc tín hiệu, không phải phân loại cứng.
CONTENT_THEMES = (
    {
        "id": "build",
        "label": "Xây dựng & phát triển sản phẩm",
        "keywords": ("phat trien", "xay dung", "lap trinh", "coding", "backend", "frontend",
                     "tinh nang", "ung dung", "api", "giao dien"),
    },
    {
        "id": "data_ai",
        "label": "Dữ liệu, mô hình & phân tích",
        "keywords": ("du lieu", "mo hinh", "machine learning", "deep learning", "tri tue nhan tao",
                     "phan tich", "dashboard", "bao cao", "etl", "pipeline"),
    },
    {
        "id": "infra",
        "label": "Hạ tầng, cloud & vận hành",
        "keywords": ("ha tang", "van hanh", "trien khai", "may chu", "server", "cloud",
                     "docker", "kubernetes", "ci/cd", "giam sat", "he dieu hanh"),
    },
    {
        "id": "quality",
        "label": "Kiểm thử & chất lượng",
        "keywords": ("kiem thu", "test case", " kiem tra ", "chat luong", "loi ", "bug", "qc", "qa"),
    },
    {
        "id": "security",
        "label": "Bảo mật & tuân thủ",
        "keywords": ("bao mat", "an ninh", "security", "tuan thu", "rui ro", "iso 27001"),
    },
    {
        "id": "process",
        "label": "Phối hợp & quy trình",
        "keywords": ("phoi hop", "quy trinh", "agile", "scrum", "jira", "tai lieu", "tien do"),
    },
    {
        "id": "customer",
        "label": "Khách hàng & nghiệp vụ",
        "keywords": ("khach hang", "tu van", "ho tro", "nghiep vu", "stakeholder", "yeu cau"),
    },
)


def it_overview(
    conn: sqlite3.Connection,
    scope: str = "vn",
    days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    from .text import normalize

    scope_sql, scope_params = _scope(scope)
    start, end = _window(days)
    role_sql = "j.role IN (%s)" % ",".join("?" for _ in IT_ROLES)

    def one(sql: str, params: list):
        return conn.execute(sql, params).fetchone()

    total_scope = one(
        "SELECT COUNT(*) n FROM jobs j WHERE %s AND %s" % (scope_sql, _date_clause("j")),
        scope_params + [start, end],
    )["n"] or 0
    total_it = one(
        "SELECT COUNT(*) n FROM jobs j WHERE %s AND %s AND " % (scope_sql, _date_clause("j")) + role_sql,
        scope_params + [start, end] + list(IT_ROLES),
    )["n"] or 0
    detail_it = one(
        """SELECT SUM(CASE WHEN length(trim(COALESCE(j.description,''))) > 0
                            OR length(trim(COALESCE(j.requirements,''))) > 0 THEN 1 ELSE 0 END) n
           FROM jobs j WHERE %s AND %s AND """ % (scope_sql, _date_clause("j")) + role_sql,
        scope_params + [start, end] + list(IT_ROLES),
    )["n"] or 0

    salary_rows = conn.execute(
        """SELECT j.salary_vnd_min, j.salary_vnd_max FROM jobs j
           WHERE %s AND %s AND j.region='VN' AND """ % (scope_sql, _date_clause("j")) + role_sql + """
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()
    median_salary = median([salary_midpoint(r) for r in salary_rows])

    role_counts = {r["role"]: r["n"] for r in conn.execute(
        "SELECT j.role, COUNT(*) n FROM jobs j WHERE %s AND %s AND " % (scope_sql, _date_clause("j")) + role_sql + " GROUP BY j.role",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()}
    role_detail_counts = {r["role"]: r["n"] for r in conn.execute(
        """SELECT j.role, SUM(CASE WHEN length(trim(COALESCE(j.description,''))) > 0
                                    OR length(trim(COALESCE(j.requirements,''))) > 0 THEN 1 ELSE 0 END) n
           FROM jobs j WHERE %s AND %s AND """ % (scope_sql, _date_clause("j")) + role_sql + " GROUP BY j.role",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()}
    role_salary_rows = conn.execute(
        """SELECT j.role, j.salary_vnd_min, j.salary_vnd_max FROM jobs j
           WHERE %s AND %s AND j.region='VN' AND """ % (scope_sql, _date_clause("j")) + role_sql + """
             AND COALESCE(j.salary_vnd_min, j.salary_vnd_max) BETWEEN 1000000 AND 500000000""",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()
    salary_by_role: Dict[str, list] = defaultdict(list)
    for row in role_salary_rows:
        salary_by_role[row["role"]].append(salary_midpoint(row))

    skill_rows = conn.execute(
        """SELECT js.skill_id, j.role,
                  SUM(CASE WHEN js.weight >= 4 THEN 1 ELSE 0 END) strong,
                  COUNT(*) jobs
           FROM job_skills js JOIN jobs j ON j.id=js.job_id
           WHERE %s AND %s AND """ % (scope_sql, _date_clause("j")) + role_sql + """
           GROUP BY js.skill_id, j.role""",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()

    skill_total: Dict[str, dict] = {}
    by_role: Dict[str, Dict[str, int]] = defaultdict(dict)
    for row in skill_rows:
        entry = skill_total.setdefault(row["skill_id"], {"strong": 0, "jobs": 0})
        entry["strong"] += row["strong"] or 0
        entry["jobs"] += row["jobs"] or 0
        by_role[row["skill_id"]][row["role"]] = row["strong"] or 0

    role_standards_map: Dict[str, list] = defaultdict(list)
    for skill_id, entry in skill_total.items():
        if entry["strong"]:
            role_standards_map[skill_id] = sorted(
                ((role, strong) for role, strong in by_role[skill_id].items() if strong),
                key=lambda item: -item[1],
            )

    matrix_skills = sorted(
        (sid for sid, e in skill_total.items()
         if e["strong"] >= 3 and _skill_group(sid) in IT_TECH_GROUPS),
        key=lambda sid: (-skill_total[sid]["strong"], -skill_total[sid]["jobs"]),
    )[:12]

    def share(value: int, base: int) -> float:
        return round(value / base * 100.0, 1) if base else 0.0

    matrix = []
    for sid in matrix_skills:
        cells = []
        for rid in IT_ROLES:
            strong = by_role[sid].get(rid, 0)
            cells.append({"role": rid, "strong": strong, "share": share(strong, role_counts.get(rid, 0))})
        matrix.append({
            "id": sid,
            "label": _skill_label(sid),
            "group": _skill_group(sid),
            "group_label": GROUPS.get(_skill_group(sid), "Khác"),
            "jobs": skill_total[sid]["jobs"],
            "strong_jobs": skill_total[sid]["strong"],
            "strong_share": share(skill_total[sid]["strong"], total_it),
            "cells": cells,
        })

    roles = []
    for rid in IT_ROLES:
        jobs = role_counts.get(rid, 0)
        standards = []
        for sid, pairs in role_standards_map.items():
            if _skill_group(sid) not in IT_TECH_GROUPS:
                continue
            match = next((n for r, n in pairs if r == rid), 0)
            if match:
                standards.append({
                    "id": sid,
                    "label": _skill_label(sid),
                    "strong_jobs": match,
                    "strong_share": share(match, jobs),
                })
        standards.sort(key=lambda item: (-item["strong_share"], -item["strong_jobs"]))
        detail_jobs = role_detail_counts.get(rid, 0)
        salary = median(salary_by_role.get(rid, []))
        roles.append({
            "id": rid,
            "label": _role_label(rid),
            "jobs": jobs,
            "share_in_it": share(jobs, total_it),
            "share_scope": share(jobs, total_scope),
            "detail_jobs": detail_jobs,
            "detail_coverage": share(detail_jobs, jobs),
            "median_salary": salary,
            "median_salary_text": fmt_vnd(salary) + " ₫" if salary else "—",
            "top_skills": standards[:4],
            "thin": jobs < 15,
        })

    group_jobs: Dict[str, set] = defaultdict(set)
    group_strong: Dict[str, set] = defaultdict(set)
    job_rows = conn.execute(
        "SELECT j.id FROM jobs j WHERE %s AND %s AND " % (scope_sql, _date_clause("j")) + role_sql,
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()
    job_ids = {row["id"] for row in job_rows}
    if job_ids:
        placeholders = ",".join("?" for _ in job_ids)
        for row in conn.execute(
            "SELECT job_id, skill_id, weight FROM job_skills WHERE job_id IN (%s)" % placeholders,
            list(job_ids),
        ).fetchall():
            group = _skill_group(row["skill_id"])
            group_jobs[group].add(row["job_id"])
            if (row["weight"] or 0) >= 4:
                group_strong[group].add(row["job_id"])

    groups = [
        {
            "id": gid,
            "label": GROUPS[gid],
            "jobs": len(group_strong.get(gid, ())),
            "all_jobs": len(group_jobs.get(gid, ())),
            "share": share(len(group_strong.get(gid, ())), total_it),
        }
        for gid in IT_GROUPS
    ]
    groups.sort(key=lambda item: -item["jobs"])

    level_rows = conn.execute(
        "SELECT j.level, COUNT(*) n FROM jobs j WHERE %s AND %s AND " % (scope_sql, _date_clause("j")) + role_sql + " GROUP BY j.level ORDER BY n DESC",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()
    levels = [
        {"id": r["level"], "label": LEVEL_LABELS.get(r["level"], r["level"]), "jobs": r["n"], "share": share(r["n"], total_it)}
        for r in level_rows
    ]

    detail_rows = conn.execute(
        """SELECT j.title, j.company, j.url, j.requirements, j.description
           FROM jobs j WHERE %s AND %s AND """ % (scope_sql, _date_clause("j")) + role_sql + """
             AND (length(trim(COALESCE(j.description,''))) > 0 OR length(trim(COALESCE(j.requirements,''))) > 0)
           ORDER BY COALESCE(j.posted_at, j.first_seen) DESC LIMIT 800""",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()
    content_counts = {theme["id"]: 0 for theme in CONTENT_THEMES}
    for row in detail_rows:
        text = normalize(" ".join([row["requirements"] or "", row["description"] or ""]))
        for theme in CONTENT_THEMES:
            if any(keyword in text for keyword in theme["keywords"]):
                content_counts[theme["id"]] += 1
    contents = [
        {
            "id": theme["id"],
            "label": theme["label"],
            "jobs": content_counts[theme["id"]],
            "share": share(content_counts[theme["id"]], len(detail_rows)),
        }
        for theme in CONTENT_THEMES
    ]
    contents.sort(key=lambda item: -item["jobs"])

    evidence = []
    evidence_skills = [
        item for item in matrix
        if _skill_group(item["id"]) not in ("soft", "language")
    ][:4]
    for item in evidence_skills:
        quotes = []
        rows = conn.execute(
            """SELECT j.title, j.company, j.url, j.requirements, j.description
               FROM job_skills js JOIN jobs j ON j.id=js.job_id
               WHERE js.skill_id=? AND js.weight>=4 AND %s AND %s AND """ % (scope_sql, _date_clause("j")) + role_sql + """
               ORDER BY COALESCE(j.posted_at, j.first_seen) DESC LIMIT 8""",
            [item["id"]] + scope_params + [start, end] + list(IT_ROLES),
        ).fetchall()
        for job in rows:
            text = "\n".join([job["requirements"] or "", job["description"] or ""])
            for sentence in find_evidence(item["id"], text, limit=1):
                quotes.append({
                    "job_title": job["title"],
                    "company": job["company"],
                    "url": job["url"],
                    "text": sentence,
                })
                break
            if len(quotes) >= 2:
                break
        if quotes:
            evidence.append({
                "id": item["id"],
                "label": item["label"],
                "group": item["group"],
                "group_label": item["group_label"],
                "strong_share": item["strong_share"],
                "quotes": quotes,
            })

    companies = conn.execute(
        """SELECT j.company, j.company_tier, COUNT(*) n FROM jobs j
           WHERE %s AND %s AND j.company != '' AND COALESCE(j.company_type,'unknown') != 'agency' AND """ % (scope_sql, _date_clause("j")) + role_sql + """
           GROUP BY j.company ORDER BY j.company_tier DESC, n DESC LIMIT 6""",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()
    cities = conn.execute(
        """SELECT jl.city, COUNT(DISTINCT j.id) n FROM jobs j JOIN job_locations jl ON jl.job_id=j.id
           WHERE %s AND %s AND """ % (scope_sql, _date_clause("j")) + role_sql + """
           GROUP BY jl.city ORDER BY n DESC, jl.city LIMIT 6""",
        scope_params + [start, end] + list(IT_ROLES),
    ).fetchall()

    top_skill = matrix[0] if matrix else None
    return {
        "scope": scope,
        "days": days,
        "kpis": {
            "jobs": total_it,
            "share_scope": share(total_it, total_scope),
            "detail_jobs": detail_it,
            "detail_coverage": share(detail_it, total_it),
            "median_salary_text": fmt_vnd(median_salary) + " ₫" if median_salary else "—",
            "salary_coverage": share(len(salary_rows), total_it),
            "top_skill": top_skill["label"] if top_skill else "—",
            "top_skill_share": top_skill["strong_share"] if top_skill else 0,
            "total_scope": total_scope,
        },
        "roles": roles,
        "matrix": matrix,
        "matrix_roles": [{"id": rid, "label": _role_label(rid), "jobs": role_counts.get(rid, 0)} for rid in IT_ROLES],
        "groups": groups,
        "levels": levels,
        "contents": contents,
        "evidence": evidence,
        "companies": [{"name": r["company"], "jobs": r["n"], "tier": r["company_tier"]} for r in companies],
        "cities": [{"name": r["city"], "jobs": r["n"]} for r in cities],
        "note": (
            "Tỷ lệ mạnh = tin có kỹ năng trong thẻ, yêu cầu hoặc mô tả chi tiết, "
            "chia cho số tin CNTT trong phạm vi. Nội dung công việc là tín hiệu từ khoá, "
            "chỉ nên đọc như xu hướng, không phải phân loại tuyệt đối."
        ),
    }


def method(conn) -> dict:
    info = db_stats(conn)
    runs = conn.execute(
        """SELECT r.source, r.finished_at, r.fetched, r.inserted, r.errors
           FROM ingest_runs r
           JOIN (SELECT source, MAX(id) id FROM ingest_runs GROUP BY source) last
             ON last.id = r.id
           ORDER BY r.source"""
    ).fetchall()
    social_runs = conn.execute(
        """SELECT r.source, r.finished_at, r.fetched, r.inserted, r.errors
           FROM social_runs r
           JOIN (SELECT source, MAX(id) id FROM social_runs GROUP BY source) last
             ON last.id = r.id
           ORDER BY r.source"""
    ).fetchall()
    return {
        "db": info,
        "last_ingest": get_meta(conn, "last_ingest"),
        "last_social_ingest": get_meta(conn, "last_social_ingest"),
        "runs": [dict(r) for r in runs],
        "social": {
            "db": social_db_stats(conn),
            "runs": [dict(r) for r in social_runs],
        },
        "skills": len(SKILLS),
        "groups": GROUPS,
    }


def build_export(conn, scope: str = "vn", days: int = DEFAULT_WINDOW_DAYS) -> dict:
    data = summary(conn, scope=scope, days=days)
    data["rising"] = rising_skills(conn, scope=scope, days=14)
    data["roles"] = roles_breakdown(conn, scope=scope, days=days, limit=15)
    data["weekly"] = weekly_jobs(conn, scope=scope, weeks=12)
    data["social"] = social_summary(conn, days=days)
    data["generated_at"] = datetime.now().isoformat(timespec="seconds")
    data["method"] = method(conn)
    return data
