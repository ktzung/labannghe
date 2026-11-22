from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import DB_PATH, DATA_DIR
from .text import normalize, today_iso

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    title_norm TEXT NOT NULL,
    company TEXT,
    company_slug TEXT,
    company_logo TEXT,
    company_type TEXT NOT NULL DEFAULT 'unknown',
    location TEXT,
    country TEXT,
    region TEXT NOT NULL DEFAULT 'GLOBAL',
    remote INTEGER NOT NULL DEFAULT 0,
    level TEXT,
    employment_type TEXT,
    role TEXT NOT NULL DEFAULT 'other',
    category TEXT,
    salary_min REAL,
    salary_max REAL,
    currency TEXT,
    period TEXT,
    salary_vnd_min REAL,
    salary_vnd_max REAL,
    description TEXT,
    requirements TEXT,
    tags TEXT,
    url TEXT,
    posted_at TEXT,
    expires_at TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    company_tier INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_at);
CREATE INDEX IF NOT EXISTS idx_jobs_region ON jobs(region);
CREATE INDEX IF NOT EXISTS idx_jobs_role ON jobs(role);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_slug);

CREATE TABLE IF NOT EXISTS job_sources (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT,
    raw TEXT,
    PRIMARY KEY (source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_job_sources_job ON job_sources(job_id);

CREATE TABLE IF NOT EXISTS job_skills (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill_id TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 1,
    kind TEXT NOT NULL DEFAULT 'skill',
    PRIMARY KEY (job_id, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill_id);

CREATE TABLE IF NOT EXISTS job_locations (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    city TEXT NOT NULL,
    PRIMARY KEY (job_id, city)
);
CREATE INDEX IF NOT EXISTS idx_job_locations_city ON job_locations(city);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    fetched INTEGER DEFAULT 0,
    inserted INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    note TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    k TEXT PRIMARY KEY,
    v TEXT
);

CREATE TABLE IF NOT EXISTS social_threads (
    thread_id INTEGER PRIMARY KEY,
    forum_id TEXT NOT NULL,
    forum_label TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    author_hash TEXT,
    excerpt TEXT,
    posted_at TEXT,
    replies INTEGER NOT NULL DEFAULT 0,
    views INTEGER NOT NULL DEFAULT 0,
    is_job_ad INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'other',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_social_threads_forum ON social_threads(forum_id);
CREATE INDEX IF NOT EXISTS idx_social_threads_posted ON social_threads(posted_at);
CREATE INDEX IF NOT EXISTS idx_social_threads_replies ON social_threads(replies);

CREATE TABLE IF NOT EXISTS social_thread_tags (
    thread_id INTEGER NOT NULL REFERENCES social_threads(thread_id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (thread_id, kind, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_social_tags_kind ON social_thread_tags(kind, tag_id);

CREATE TABLE IF NOT EXISTS social_thread_stats (
    thread_id INTEGER NOT NULL REFERENCES social_threads(thread_id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    replies INTEGER NOT NULL DEFAULT 0,
    views INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (thread_id, observed_at)
);

CREATE TABLE IF NOT EXISTS social_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    fetched INTEGER DEFAULT 0,
    inserted INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    note TEXT
);
"""


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "company_type" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN company_type TEXT NOT NULL DEFAULT 'unknown'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company_type ON jobs(company_type)")
    skill_columns = {row[1] for row in conn.execute("PRAGMA table_info(job_skills)")}
    if "kind" not in skill_columns:
        conn.execute("ALTER TABLE job_skills ADD COLUMN kind TEXT NOT NULL DEFAULT 'skill'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_skills_kind ON job_skills(kind)")
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (key, value),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT v FROM app_meta WHERE k=?", (key,)).fetchone()
    return row["v"] if row else default


def canonical_key(title: str, company: str, location: str, posted_at: Optional[str]) -> str:
    month = (posted_at or today_iso())[:7]
    raw = "|".join([normalize(title), normalize(company), normalize(location or "global"), month])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _clean(value, limit: int = 0) -> str:
    text = "" if value is None else str(value)
    if limit and len(text) > limit:
        return text[:limit]
    return text


def upsert_job(
    conn: sqlite3.Connection,
    job: Dict,
    skills: Dict[str, int],
    knowledge: Optional[Dict[str, int]] = None,
) -> str:
    """Trả về 'inserted' | 'updated' | 'skipped'."""
    source = job["source"]
    external_id = str(job["external_id"])
    today = today_iso()
    row = conn.execute(
        "SELECT job_id FROM job_sources WHERE source=? AND external_id=?",
        (source, external_id),
    ).fetchone()

    if row:
        job_id = row["job_id"]
        action = "updated"
    else:
        ckey = canonical_key(
            job["title"], job.get("company", ""), job.get("location", ""), job.get("posted_at")
        )
        found = conn.execute("SELECT id FROM jobs WHERE canonical_key=?", (ckey,)).fetchone()
        if found:
            job_id = found["id"]
            action = "updated"
        else:
            cur = conn.execute(
                """INSERT INTO jobs (
                    canonical_key, title, title_norm, company, company_slug, company_logo,
                    company_type, location, country, region, remote, level, employment_type, role, category,
                    salary_min, salary_max, currency, period, salary_vnd_min, salary_vnd_max,
                    description, requirements, tags, url, posted_at, expires_at,
                    first_seen, last_seen, is_active, company_tier
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
                (
                    ckey,
                    _clean(job["title"], 500),
                    normalize(job["title"]),
                    _clean(job.get("company"), 300),
                    _clean(job.get("company_slug"), 300),
                    _clean(job.get("company_logo"), 1000),
                    job.get("company_type") or "unknown",
                    _clean(job.get("location"), 400),
                    _clean(job.get("country"), 100),
                    job.get("region", "GLOBAL"),
                    1 if job.get("remote") else 0,
                    job.get("level", "mid"),
                    _clean(job.get("employment_type"), 100),
                    job.get("role", "other"),
                    _clean(job.get("category"), 200),
                    job.get("salary_min"),
                    job.get("salary_max"),
                    job.get("currency"),
                    job.get("period"),
                    job.get("salary_vnd_min"),
                    job.get("salary_vnd_max"),
                    _clean(job.get("description"), 20000),
                    _clean(job.get("requirements"), 20000),
                    json.dumps(job.get("tags") or [], ensure_ascii=False),
                    _clean(job.get("url"), 1200),
                    job.get("posted_at"),
                    job.get("expires_at"),
                    today,
                    today,
                    job.get("company_tier", 0),
                ),
            )
            job_id = cur.lastrowid
            action = "inserted"

    conn.execute(
        """UPDATE jobs SET
            last_seen=?, is_active=1,
            url=CASE WHEN COALESCE(url, '')='' THEN ? ELSE url END,
            company_logo=COALESCE(NULLIF(?, ''), company_logo),
            company_type=COALESCE(NULLIF(?, 'unknown'), company_type),
            role=COALESCE(NULLIF(?, ''), role),
            level=COALESCE(NULLIF(?, ''), level),
            description=CASE WHEN length(COALESCE(?, '')) > length(COALESCE(description, ''))
                             THEN ? ELSE description END,
            requirements=CASE WHEN length(COALESCE(?, '')) > length(COALESCE(requirements, ''))
                              THEN ? ELSE requirements END,
            salary_min=COALESCE(NULLIF(?, 0), salary_min),
            salary_max=COALESCE(NULLIF(?, 0), salary_max),
            currency=COALESCE(NULLIF(?, ''), currency),
            period=COALESCE(NULLIF(?, ''), period),
            salary_vnd_min=COALESCE(NULLIF(?, 0), salary_vnd_min),
            salary_vnd_max=COALESCE(NULLIF(?, 0), salary_vnd_max),
            posted_at=COALESCE(posted_at, ?),
            expires_at=COALESCE(expires_at, ?),
            company_tier=MAX(company_tier, ?)
        WHERE id=?""",
        (
            today,
            job.get("url") or "",
            job.get("company_logo") or "",
            job.get("company_type") or "unknown",
            job.get("role") or "other",
            job.get("level") or "mid",
            job.get("description") or "",
            job.get("description") or "",
            job.get("requirements") or "",
            job.get("requirements") or "",
            job.get("salary_min") or 0,
            job.get("salary_max") or 0,
            job.get("currency") or "",
            job.get("period") or "",
            job.get("salary_vnd_min") or 0,
            job.get("salary_vnd_max") or 0,
            job.get("posted_at"),
            job.get("expires_at"),
            job.get("company_tier", 0),
            job_id,
        ),
    )
    conn.execute(
        """INSERT INTO job_sources(job_id, source, external_id, url, raw)
           VALUES(?,?,?,?,?)
           ON CONFLICT(source, external_id) DO UPDATE SET
             job_id=excluded.job_id, url=excluded.url, raw=excluded.raw""",
        (
            job_id,
            source,
            external_id,
            _clean(job.get("url"), 1200),
            json.dumps(job.get("raw") or {}, ensure_ascii=False)[:60000],
        ),
    )
    conn.execute("DELETE FROM job_skills WHERE job_id=?", (job_id,))
    facets = [(skill, weight, "skill") for skill, weight in (skills or {}).items()]
    facets.extend((item, weight, "knowledge") for item, weight in (knowledge or {}).items())
    if facets:
        conn.executemany(
            "INSERT OR REPLACE INTO job_skills(job_id, skill_id, weight, kind) VALUES(?,?,?,?)",
            [(job_id, item, weight, kind) for item, weight, kind in facets],
        )
    conn.execute("DELETE FROM job_locations WHERE job_id=?", (job_id,))
    locations = job.get("locations") or []
    if locations:
        conn.executemany(
            "INSERT OR IGNORE INTO job_locations(job_id, city) VALUES(?,?)",
            [(job_id, city) for city in locations],
        )
    return action


def log_run(conn: sqlite3.Connection, source: str, started: str, stats: Dict, note: str = "") -> None:
    conn.execute(
        """INSERT INTO ingest_runs(
            source, started_at, finished_at, fetched, inserted, updated, skipped, errors, note
        ) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            source,
            started,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            stats.get("fetched", 0),
            stats.get("inserted", 0),
            stats.get("updated", 0),
            stats.get("skipped", 0),
            stats.get("errors", 0),
            note[:1000],
        ),
    )
    conn.commit()


def log_social_run(conn: sqlite3.Connection, source: str, started: str, stats: Dict, note: str = "") -> None:
    conn.execute(
        """INSERT INTO social_runs(
            source, started_at, finished_at, fetched, inserted, updated, errors, note
        ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            source,
            started,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            stats.get("fetched", 0),
            stats.get("inserted", 0),
            stats.get("updated", 0),
            stats.get("errors", 0),
            note[:1000],
        ),
    )
    conn.commit()


def social_db_stats(conn: sqlite3.Connection) -> Dict:
    row = conn.execute(
        """SELECT
            COUNT(*) threads,
            SUM(CASE WHEN is_job_ad=0 THEN 1 ELSE 0 END) discussions,
            SUM(CASE WHEN is_job_ad=1 THEN 1 ELSE 0 END) job_ads,
            COUNT(DISTINCT forum_id) forums,
            MAX(posted_at) max_posted,
            MAX(last_seen) last_seen
        FROM social_threads"""
    ).fetchone()
    return dict(row) if row else {}


def mark_inactive(conn: sqlite3.Connection, days: int = 45) -> int:
    cur = conn.execute(
        "UPDATE jobs SET is_active=0 WHERE last_seen < date(?, ?)",
        (today_iso(), "-%d days" % days),
    )
    conn.commit()
    return cur.rowcount


def db_stats(conn: sqlite3.Connection) -> Dict:
    row = conn.execute(
        """SELECT
            COUNT(*) total,
            SUM(CASE WHEN region='VN' THEN 1 ELSE 0 END) vn,
            SUM(CASE WHEN region='GLOBAL' THEN 1 ELSE 0 END) global,
            COUNT(DISTINCT company_slug) companies,
            MIN(posted_at) min_date,
            MAX(posted_at) max_date,
            MAX(last_seen) last_seen
        FROM jobs"""
    ).fetchone()
    return dict(row) if row else {}
