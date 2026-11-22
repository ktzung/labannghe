from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import feedparser
import httpx
from bs4 import BeautifulSoup

from .config import TAXONOMY_DIR, TIMEOUT, TRUST_ENV, USER_AGENT, VOZ_MODE, VOZ_RSS_DIR
from .db import connect, init_db, log_social_run, set_meta
from .taxonomy import classify_role, extract_skills
from .text import normalize, short, today_iso

SOURCE = "voz"

VOZ_FORUMS = [
    {
        "id": "tuyen-dung-tim-viec.95",
        "forum_id": "95",
        "label": "Tuyển dụng - Tìm việc",
        "rss": "https://voz.vn/f/tuyen-dung-tim-viec.95/index.rss",
        "file": "tuyen-dung-tim-viec.xml",
        "topic": "tuyen_dung",
    },
    {
        "id": "lap-trinh-cntt.91",
        "forum_id": "91",
        "label": "Lập trình / CNTT",
        "rss": "https://voz.vn/f/lap-trinh-cntt.91/index.rss",
        "file": "lap-trinh-cntt.xml",
        "topic": "it",
    },
    {
        "id": "ai.42",
        "forum_id": "42",
        "label": "AI",
        "rss": "https://voz.vn/f/ai.42/index.rss",
        "file": "ai.xml",
        "topic": "ai",
    },
    {
        "id": "ngoai-ngu.90",
        "forum_id": "90",
        "label": "Ngoại ngữ",
        "rss": "https://voz.vn/f/ngoai-ngu.90/index.rss",
        "file": "ngoai-ngu.xml",
        "topic": "ngoai_ngu",
    },
]

_AUTHOR_SALT = os.environ.get("LABAN_VOZ_SALT", "laban-voz-v1")
_WORD_START = r"(?<![a-z0-9])"
_WORD_END = r"(?![a-z0-9])"
_THREAD_RE = re.compile(r"/t/([^/?#]+)\.(\d+)")


class SocialTag:
    __slots__ = ("id", "label", "patterns", "raw_patterns")

    def __init__(self, id: str, label: str, patterns: List[re.Pattern], raw_patterns: List[re.Pattern]):
        self.id = id
        self.label = label
        self.patterns = patterns
        self.raw_patterns = raw_patterns


def _alias_pattern(alias: str) -> str:
    alias = normalize(alias).strip()
    escaped = re.escape(alias)
    pre = _WORD_START if alias and alias[0].isalnum() else ""
    post = _WORD_END if alias and alias[-1].isalnum() else ""
    return pre + escaped + post


@lru_cache(maxsize=1)
def load_social_tags() -> Tuple[List[SocialTag], List[SocialTag]]:
    data = json.loads((TAXONOMY_DIR / "social.json").read_text(encoding="utf-8"))
    topics = []
    for item in data.get("topics", []):
        patterns = [re.compile(_alias_pattern(a)) for a in item.get("aliases", []) if len(a.strip()) >= 2]
        raw_patterns = [re.compile(p) for p in item.get("raw_patterns", [])]
        topics.append(SocialTag(item["id"], item["label"], patterns, raw_patterns))
    issues = []
    for item in data.get("issues", []):
        patterns = [re.compile(_alias_pattern(a)) for a in item.get("aliases", []) if len(a.strip()) >= 2]
        raw_patterns = [re.compile(p) for p in item.get("raw_patterns", [])]
        issues.append(SocialTag(item["id"], item["label"], patterns, raw_patterns))
    return topics, issues


def social_labels() -> Dict[str, Dict[str, str]]:
    topics, issues = load_social_tags()
    return {
        "topic": {item.id: item.label for item in topics},
        "issue": {item.id: item.label for item in issues},
    }


def _classify(text: str, tags: Iterable[SocialTag]) -> List[str]:
    norm = normalize(text)
    found = []
    for tag in tags:
        if any(p.search(norm) for p in tag.patterns) or any(p.search(text) for p in tag.raw_patterns):
            found.append(tag.id)
    return found


def author_hash(name: str) -> str:
    if not name:
        return ""
    raw = (_AUTHOR_SALT + "|" + normalize(name)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def parse_thread_link(link: str) -> Optional[dict]:
    match = _THREAD_RE.search(link or "")
    if not match:
        return None
    slug, thread_id = match.group(1), match.group(2)
    return {
        "thread_id": int(thread_id),
        "url": "https://voz.vn/t/%s.%s/" % (slug, thread_id),
    }


def clean_excerpt(html: str, limit: int = 700) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return short(text, limit)


def detect_job_ad(title: str, excerpt: str = "") -> bool:
    text = normalize(title)
    if not text:
        return False
    if text.startswith(
        (
            "review ", "xin review", "hoi ", "chia se", "cach ", "nen ", "co nen",
            "tim viec", "xin viec", "chon ", "kinh nghiem",
        )
    ):
        return False
    if text.startswith(
        (
            "tuyen dung", "tuyen ", "can tuyen", "mo tuyen", "tim nguoi",
            "hiring", "co hoi lam viec", "chuong trinh intern", "chuong trinh fresher",
        )
    ):
        return True
    signals = (
        "upto $", "thu nhap", "hoa hong", "gui cv", "ung tuyen",
        "job description", "mo ta cong viec", "quyen loi", "yeu cau cong viec",
        "lam viec tai", "dia chi lam viec",
    )
    if any(signal in text for signal in signals) and any(
        marker in text for marker in ("tuyen", "cv", "job", "vi tri", "ung vien")
    ):
        return True
    return False


def _author_name(entry) -> str:
    raw = entry.get("author") or entry.get("dc_creator") or ""
    match = re.search(r"\(([^)]+)\)\s*$", raw)
    if match:
        return match.group(1).strip()
    return str(raw).strip()


def _entry_date(entry) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()
        except Exception:  # noqa: BLE001
            pass
    return today_iso()


def _safe_int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_rss(payload, forum: dict) -> List[dict]:
    feed = feedparser.parse(payload)
    topics, issues = load_social_tags()
    records = []
    for entry in feed.entries:
        parsed = parse_thread_link(entry.get("link", ""))
        if not parsed:
            continue
        title = short(clean_excerpt(entry.get("title", ""), 400), 400)
        if not title:
            continue
        body = entry.get("summary", "")
        if not body and entry.get("content"):
            body = entry["content"][0].get("value", "")
        excerpt = clean_excerpt(body)
        text = title + "\n" + excerpt
        topic_ids = _classify(text, topics)
        forum_topic = forum.get("topic")
        if forum_topic and forum_topic not in topic_ids:
            topic_ids.insert(0, forum_topic)
        issue_ids = _classify(text, issues)
        skills = extract_skills(title, [], "", excerpt)
        records.append(
            {
                "thread_id": parsed["thread_id"],
                "forum_id": forum["forum_id"],
                "forum_label": forum["label"],
                "title": title,
                "url": parsed["url"],
                "author_hash": author_hash(_author_name(entry)),
                "excerpt": excerpt,
                "posted_at": _entry_date(entry),
                "replies": _safe_int(entry.get("slash_comments") or entry.get("comments")),
                "views": _safe_int(entry.get("views")),
                "is_job_ad": 1 if detect_job_ad(title, excerpt) else 0,
                "role": classify_role(title, "", [], excerpt),
                "topics": topic_ids,
                "issues": issue_ids,
                "skills": skills,
            }
        )
    return records


def upsert_records(conn: sqlite3.Connection, records: List[dict], observed_at: Optional[str] = None) -> Tuple[int, int]:
    observed_at = observed_at or today_iso()
    inserted = updated = 0
    for record in records:
        exists = conn.execute(
            "SELECT 1 FROM social_threads WHERE thread_id=?", (record["thread_id"],)
        ).fetchone()
        conn.execute(
            """INSERT INTO social_threads(
                thread_id, forum_id, forum_label, title, url, author_hash, excerpt,
                posted_at, replies, views, is_job_ad, role, first_seen, last_seen
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(thread_id) DO UPDATE SET
                forum_id=excluded.forum_id,
                forum_label=excluded.forum_label,
                title=excluded.title,
                url=excluded.url,
                author_hash=COALESCE(NULLIF(excluded.author_hash, ''), social_threads.author_hash),
                excerpt=excluded.excerpt,
                posted_at=COALESCE(social_threads.posted_at, excluded.posted_at),
                replies=MAX(social_threads.replies, excluded.replies),
                views=MAX(social_threads.views, excluded.views),
                is_job_ad=excluded.is_job_ad,
                role=COALESCE(NULLIF(excluded.role, ''), social_threads.role),
                last_seen=excluded.last_seen""",
            (
                record["thread_id"],
                record["forum_id"],
                record["forum_label"],
                record["title"],
                record["url"],
                record["author_hash"],
                record["excerpt"],
                record["posted_at"],
                record["replies"],
                record["views"],
                record["is_job_ad"],
                record["role"],
                observed_at,
                observed_at,
            ),
        )
        if exists:
            updated += 1
        else:
            inserted += 1
        conn.execute(
            """INSERT INTO social_thread_stats(thread_id, observed_at, replies, views)
               VALUES (?,?,?,?)
               ON CONFLICT(thread_id, observed_at) DO UPDATE SET
                 replies=MAX(social_thread_stats.replies, excluded.replies),
                 views=MAX(social_thread_stats.views, excluded.views)""",
            (record["thread_id"], observed_at, record["replies"], record["views"]),
        )
        conn.execute("DELETE FROM social_thread_tags WHERE thread_id=?", (record["thread_id"],))
        tags = []
        tags.extend((record["thread_id"], "topic", tag_id, 0) for tag_id in record["topics"])
        tags.extend((record["thread_id"], "issue", tag_id, 0) for tag_id in record["issues"])
        tags.extend(
            (record["thread_id"], "skill", skill_id, weight)
            for skill_id, weight in record["skills"].items()
        )
        if tags:
            conn.executemany(
                "INSERT OR IGNORE INTO social_thread_tags(thread_id, kind, tag_id, weight) VALUES(?,?,?,?)",
                tags,
            )
    conn.commit()
    return inserted, updated


def _http_fetch(forum: dict) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        "Accept-Language": "vi,en;q=0.8",
    }
    with httpx.Client(
        timeout=min(TIMEOUT, 15),
        headers=headers,
        follow_redirects=True,
        trust_env=TRUST_ENV,
    ) as client:
        response = client.get(forum["rss"])
    if response.status_code != 200:
        raise RuntimeError("HTTP %s" % response.status_code)
    if "<rss" not in response.text[:1000].lower() and "xml" not in response.headers.get("content-type", ""):
        raise RuntimeError("phản hồi không phải RSS")
    return response.text


def _load_feed(forum: dict, mode: str, allow_http: bool) -> Tuple[str, str, str, bool]:
    error = ""
    if allow_http and mode in {"auto", "http"}:
        try:
            return _http_fetch(forum), "http", "", False
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:160]
            if mode == "http":
                raise RuntimeError("Không tải được RSS trực tiếp: %s" % error)

    path = VOZ_RSS_DIR / forum["file"]
    if path.exists():
        note = "Dùng snapshot %s" % path.name
        if error:
            note = "%s; %s" % (error, note)
        return path.read_text(encoding="utf-8"), "file", note, bool(error)
    if error:
        raise RuntimeError("Không tải được RSS và không có snapshot: %s" % error)
    raise RuntimeError("Không tìm thấy snapshot: %s" % path)


def run(
    only: Optional[Iterable[str]] = None,
    mode: Optional[str] = None,
    verbose: bool = True,
    observed_at: Optional[str] = None,
) -> Dict[str, dict]:
    mode = (mode or VOZ_MODE or "auto").lower()
    if mode not in {"auto", "file", "http"}:
        mode = "auto"
    selected = [
        forum for forum in VOZ_FORUMS
        if not only or forum["id"] in set(only) or forum["forum_id"] in set(only)
    ]
    conn = connect()
    init_db(conn)
    summary: Dict[str, dict] = {}
    any_success = False
    allow_http = mode in {"auto", "http"}

    for forum in selected:
        stats = {"fetched": 0, "inserted": 0, "updated": 0, "errors": 0}
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        note = ""
        used_mode = mode
        t0 = time.time()
        if verbose:
            print("[social] %-24s ..." % forum["label"], flush=True)
        try:
            payload, used_mode, note, http_failed = _load_feed(forum, mode, allow_http)
            if http_failed:
                allow_http = False
            records = parse_rss(payload, forum)
            if not records:
                raise RuntimeError("RSS không có mục hợp lệ")
            stats["fetched"] = len(records)
            inserted, updated = upsert_records(conn, records, observed_at=observed_at)
            stats["inserted"] = inserted
            stats["updated"] = updated
            any_success = True
            note = "[%s] %s" % (used_mode, note) if note else "[%s] RSS trực tiếp" % used_mode
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            stats["errors"] = 1
            note = str(exc)[:500]
            if verbose:
                print("[social] %-24s LỖI: %s" % (forum["label"], note), flush=True)
        log_social_run(conn, "%s:%s" % (SOURCE, forum["forum_id"]), started, stats, note)
        summary[forum["id"]] = {**stats, "mode": used_mode, "note": note}
        if verbose:
            print(
                "[social] %-24s fetched=%-3d new=%-3d upd=%-3d err=%-2d %.1fs"
                % (forum["label"], stats["fetched"], stats["inserted"], stats["updated"], stats["errors"], time.time() - t0),
                flush=True,
            )

    if any_success:
        set_meta(conn, "last_social_ingest", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        set_meta(conn, "last_social_stats", json.dumps(summary, ensure_ascii=False))
    conn.close()
    return summary
