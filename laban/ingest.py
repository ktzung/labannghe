from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .db import connect, init_db, log_run, mark_inactive, set_meta, upsert_job
from .sources import SOURCES, VN_SOURCES


def _stats() -> Dict[str, int]:
    return {"fetched": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": 0}


def run(
    only: Optional[Iterable[str]] = None,
    skip: Optional[Iterable[str]] = None,
    max_pages: int = 30,
    verbose: bool = True,
) -> Dict[str, Dict[str, int]]:
    selected = [s for s in SOURCES if (not only or s in set(only)) and (not skip or s not in set(skip))]
    conn = connect()
    init_db(conn)
    summary: Dict[str, Dict[str, int]] = {}
    any_success = False

    for name in selected:
        module = SOURCES[name]
        stats = _stats()
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        note = ""
        if verbose:
            print("[ingest] %-16s ..." % name, flush=True)
        t0 = time.time()
        try:
            records = (
                module.fetch(max_pages=max_pages)
                if name in {"vietnamworks", "itviec"}
                else module.fetch()
            )
            stats["fetched"] = len(records)
            seen = set()
            for job in records:
                key = (job["source"], job["external_id"])
                if key in seen:
                    stats["skipped"] += 1
                    continue
                seen.add(key)
                skills = job.pop("_skills", {})
                knowledge = job.pop("_knowledge", {})
                try:
                    action = upsert_job(conn, job, skills, knowledge)
                    stats[action] = stats.get(action, 0) + 1
                except Exception as exc:  # noqa: BLE001
                    stats["errors"] += 1
                    note = str(exc)[:500]
            conn.commit()
            any_success = True
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            stats["errors"] += 1
            note = str(exc)[:500]
            if verbose:
                print("[ingest] %-16s LỖI: %s" % (name, note), flush=True)
        log_run(conn, name, started, stats, note)
        summary[name] = stats
        if verbose:
            print(
                "[ingest] %-16s fetched=%-4d new=%-4d upd=%-4d skip=%-3d err=%-3d %.1fs"
                % (
                    name,
                    stats["fetched"],
                    stats["inserted"],
                    stats["updated"],
                    stats["skipped"],
                    stats["errors"],
                    time.time() - t0,
                ),
                flush=True,
            )

    if any_success:
        mark_inactive(conn, 60)
        set_meta(conn, "last_ingest", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        set_meta(conn, "last_ingest_stats", json.dumps(summary, ensure_ascii=False))
    conn.close()
    return summary


def run_vn_only(max_pages: int = 30, verbose: bool = True):
    return run(only=VN_SOURCES, max_pages=max_pages, verbose=verbose)


def run_global(max_pages: int = 3, verbose: bool = True):
    return run(skip=VN_SOURCES, max_pages=max_pages, verbose=verbose)
