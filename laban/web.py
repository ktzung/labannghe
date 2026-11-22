from __future__ import annotations

import json
import os
import sqlite3

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import analytics, social
from .config import STATIC_DIR, TEMPLATE_DIR
from .db import connect, get_meta, init_db
from .sources import SOURCES, UNAVAILABLE_SOURCES
from .taxonomy import load_roles

app = FastAPI(title="La Bàn Nghề", version="0.1.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

ALLOWED_SCOPES = {"vn", "global", "all"}


@app.on_event("startup")
def _startup() -> None:
    conn = connect()
    init_db(conn)
    conn.close()


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _scope(scope: str) -> str:
    return scope if scope in ALLOWED_SCOPES else "vn"


def _days(days: int) -> int:
    return max(1, min(int(days), 365))


def _page(request: Request, name: str, page: str) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"page": page})


@app.get("/", response_class=HTMLResponse)
def overview_page(request: Request):
    return _page(request, "overview.html", "overview")


@app.get("/ky-nang", response_class=HTMLResponse)
def skills_page(request: Request):
    return _page(request, "skills.html", "skills")


@app.get("/vi-tri", response_class=HTMLResponse)
def roles_page(request: Request):
    return _page(request, "roles.html", "roles")


@app.get("/nguon", response_class=HTMLResponse)
def sources_page(request: Request):
    return _page(request, "sources.html", "sources")


@app.get("/tin-hieu-cong-dong", response_class=HTMLResponse)
def social_page(request: Request):
    return _page(request, "social.html", "social")


@app.get("/bao-cao", response_class=HTMLResponse)
def report_page(request: Request):
    return _page(request, "report.html", "report")


@app.get("/cntt", response_class=HTMLResponse)
def it_page(request: Request):
    return _page(request, "it.html", "it")


@app.get("/sach-lat", response_class=HTMLResponse)
def flipbook_page(request: Request):
    return _page(request, "flipbook.html", "flipbook")


@app.get("/case-study-cv", response_class=HTMLResponse)
def case_study_cv_page(request: Request):
    return _page(request, "case_study_cv.html", "case_study_cv")


@app.get("/api/it")
def api_it(
    scope: str = Query("vn"),
    days: int = Query(30),
    conn: sqlite3.Connection = Depends(get_db),
):
    return analytics.it_overview(conn, scope=_scope(scope), days=_days(days))


@app.get("/api/overview")
def api_overview(
    scope: str = Query("vn"),
    days: int = Query(30),
    conn: sqlite3.Connection = Depends(get_db),
):
    scope, days = _scope(scope), _days(days)
    data = analytics.summary(conn, scope=scope, days=days)
    data["rising"] = analytics.rising_skills(conn, scope=scope, days=14, limit=5)
    data["roles"] = analytics.roles_breakdown(conn, scope=scope, days=days, limit=8)
    latest = analytics.jobs_search(conn, scope=scope, days=max(days, 30), limit=8)
    data["latest_jobs"] = latest["jobs"]
    data["all_scope_counts"] = data.get("db", {})
    return data


@app.get("/api/skills")
def api_skills(
    scope: str = Query("vn"),
    days: int = Query(30),
    role: str = Query("all"),
    q: str = Query(""),
    limit: int = Query(200),
    kind: str = Query("skill"),
    conn: sqlite3.Connection = Depends(get_db),
):
    scope, days = _scope(scope), _days(days)
    kind = kind if kind in ("skill", "knowledge") else "skill"
    items = analytics.top_skills(conn, scope=scope, days=days, role=role, limit=200, kind=kind)
    salaries = analytics.skill_salary_stats(conn, scope=scope, days=days, kind=kind)
    for item in items:
        stat = salaries.get(item["id"], {})
        item["median_salary"] = stat.get("median")
        item["median_salary_text"] = stat.get("median_text", "—")
        item["salary_premium"] = stat.get("premium")

    qn = q.strip().lower()
    if qn:
        items = [
            i for i in items
            if qn in i["label"].lower() or qn in i["group_label"].lower() or qn in i["id"]
        ]
    items = items[: max(1, min(limit, 300))]
    roles = sorted(
        [{"id": r["id"], "label": r["label"]} for r in load_roles()],
        key=lambda r: r["label"],
    )
    return {
        "scope": scope,
        "days": days,
        "role": role,
        "q": q,
        "kind": kind,
        "items": items,
        "roles": roles,
        "groups": analytics.GROUPS,
    }


@app.get("/api/skill/{skill_id}")
def api_skill(
    skill_id: str,
    scope: str = Query("vn"),
    days: int = Query(30),
    conn: sqlite3.Connection = Depends(get_db),
):
    return analytics.skill_detail(conn, skill_id, scope=_scope(scope), days=_days(days))


@app.get("/api/roles")
def api_roles(
    scope: str = Query("vn"),
    days: int = Query(30),
    conn: sqlite3.Connection = Depends(get_db),
):
    scope, days = _scope(scope), _days(days)
    items = analytics.roles_breakdown(conn, scope=scope, days=days, limit=30)
    return {
        "scope": scope,
        "days": days,
        "items": items,
        "total_jobs": sum(i["jobs"] for i in items),
        "roles": [{"id": r["id"], "label": r["label"]} for r in load_roles()],
    }


@app.get("/api/role/{role_id}")
def api_role(
    role_id: str,
    scope: str = Query("vn"),
    days: int = Query(30),
    conn: sqlite3.Connection = Depends(get_db),
):
    return analytics.role_detail(conn, role_id, scope=_scope(scope), days=_days(days))


@app.get("/api/social/overview")
def api_social_overview(
    days: int = Query(30),
    forum: str = Query("all"),
    conn: sqlite3.Connection = Depends(get_db),
):
    data = analytics.social_summary(conn, days=_days(days), forum=forum)
    data["forums_meta"] = [
        {"id": f["forum_id"], "label": f["label"], "url": f["rss"], "topic": f["topic"]}
        for f in social.VOZ_FORUMS
    ]
    return data


@app.get("/api/jobs")
def api_jobs(
    scope: str = Query("vn"),
    role: str = Query(""),
    skill: str = Query(""),
    level: str = Query(""),
    source: str = Query(""),
    q: str = Query(""),
    days: int = Query(90),
    limit: int = Query(30),
    offset: int = Query(0),
    conn: sqlite3.Connection = Depends(get_db),
):
    return analytics.jobs_search(
        conn,
        scope=_scope(scope),
        role=role,
        skill=skill,
        level=level,
        source=source,
        q=q,
        days=_days(days),
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )


@app.get("/api/method")
def api_method(conn: sqlite3.Connection = Depends(get_db)):
    data = analytics.method(conn)
    sources = []
    for name, module in SOURCES.items():
        stat = next((r for r in data["runs"] if r["source"] == name), {})
        sources.append(
            {
                "id": name,
                "label": getattr(module, "LABEL", name),
                "url": getattr(module, "URL", ""),
                "note": getattr(module, "NOTE", ""),
                "last_run": stat.get("finished_at"),
                "fetched": stat.get("fetched") or 0,
                "inserted": stat.get("inserted") or 0,
                "errors": stat.get("errors") or 0,
            }
        )
    data["source_list"] = sources
    data["unavailable_sources"] = UNAVAILABLE_SOURCES
    data["schedule"] = "06:30 hằng ngày (launchd/cron)"
    return data


@app.get("/api/health")
def api_health(conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()
    return {
        "ok": True,
        "jobs": row["n"] if row else 0,
        "last_ingest": get_meta(conn, "last_ingest"),
        "db": str(conn.execute("PRAGMA database_list").fetchone()[2]),
    }


@app.get("/api/export")
def api_export(
    scope: str = Query("vn"),
    days: int = Query(30),
    download: int = Query(0),
    conn: sqlite3.Connection = Depends(get_db),
):
    data = analytics.build_export(conn, scope=_scope(scope), days=_days(days))
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="laban-nghe-%s-%dd.json"' % (
            _scope(scope), _days(days)
        )
    return Response(content=payload, media_type="application/json; charset=utf-8", headers=headers)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "laban.web:app",
        host=os.environ.get("LABAN_HOST", "127.0.0.1"),
        port=int(os.environ.get("LABAN_PORT", "8000")),
        reload=bool(os.environ.get("LABAN_RELOAD")),
    )


if __name__ == "__main__":
    run()
