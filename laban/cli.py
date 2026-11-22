from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ingest
from .config import DATA_DIR, DB_PATH, RAW_DIR, RAW_KEEP_DAYS
from .db import connect, db_stats, init_db, set_meta
from .sources import SOURCES


def cmd_init(_args):
    conn = connect()
    init_db(conn)
    conn.close()
    print("Đã khởi tạo cơ sở dữ liệu:", DB_PATH)


def cmd_ingest(args):
    only = args.only.split(",") if args.only else None
    summary = ingest.run(only=only, max_pages=args.max_pages)
    total_new = sum(v.get("inserted", 0) for v in summary.values())
    total_upd = sum(v.get("updated", 0) for v in summary.values())
    print("Xong: %d bản ghi mới, %d cập nhật." % (total_new, total_upd))


def cmd_reclassify(_args):
    from .reclassify import run

    run()


def cmd_social_ingest(args):
    from . import social

    only = args.only.split(",") if args.only else None
    summary = social.run(only=only, mode=args.mode)
    total_new = sum(v.get("inserted", 0) for v in summary.values())
    total_upd = sum(v.get("updated", 0) for v in summary.values())
    print("Xong: %d chủ đề mới, %d cập nhật." % (total_new, total_upd))


def cmd_stats(_args):
    conn = connect()
    init_db(conn)
    info = db_stats(conn)
    runs = conn.execute(
        "SELECT source, finished_at, fetched, inserted, updated, errors FROM ingest_runs ORDER BY id DESC LIMIT 10"
    ).fetchall()
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print("\nLần chạy gần nhất:")
    for row in runs:
        print("  %-16s %s fetched=%s new=%s upd=%s err=%s" % tuple(row))
    conn.close()


def cmd_serve(args):
    import uvicorn

    uvicorn.run(
        "laban.web:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


def cmd_prune(args):
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=args.raw_days)
    removed = 0
    if RAW_DIR.exists():
        for folder in RAW_DIR.iterdir():
            if not folder.is_dir():
                continue
            try:
                folder_date = datetime.strptime(folder.name, "%Y-%m-%d").date()
            except ValueError:
                continue
            if folder_date < cutoff:
                shutil.rmtree(folder)
                removed += 1
    print("Đã xoá %d thư mục raw cũ hơn %d ngày." % (removed, args.raw_days))
    if args.vacuum:
        conn = connect()
        conn.execute("VACUUM")
        conn.close()
        print("Đã VACUUM.")


def cmd_export(args):
    from .analytics import build_export

    conn = connect()
    init_db(conn)
    data = build_export(conn, scope=args.scope, days=args.days)
    out = Path(args.out) if args.out else DATA_DIR / "export.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Đã xuất:", out, "(%d KB)" % (len(json.dumps(data)) // 1024))
    conn.close()


def cmd_sources(_args):
    for name, module in SOURCES.items():
        print("%-16s %-20s %s" % (name, getattr(module, "LABEL", ""), getattr(module, "NOTE", "")))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="laban", description="La Bàn Nghề CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="tạo cơ sở dữ liệu")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("ingest", help="crawl và cập nhật dữ liệu")
    p.add_argument("--only", help="danh sách nguồn, cách nhau bởi dấu phẩy")
    p.add_argument("--max-pages", type=int, default=30, help="số trang tối đa cho nguồn có phân trang")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("social-ingest", help="cập nhật tín hiệu cộng đồng từ RSS Voz")
    p.add_argument("--mode", default="auto", choices=["auto", "file", "http"])
    p.add_argument("--only", help="mã diễn đàn, cách nhau bởi dấu phẩy (ví dụ 91,42)")
    p.set_defaults(func=cmd_social_ingest)

    p = sub.add_parser("stats", help="xem thống kê dữ liệu")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("reclassify", help="phân loại lại nghề, kỹ năng, địa bàn và loại hình doanh nghiệp")
    p.set_defaults(func=cmd_reclassify)

    p = sub.add_parser("serve", help="chạy dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("prune", help="dọn raw cũ")
    p.add_argument("--raw-days", type=int, default=RAW_KEEP_DAYS)
    p.add_argument("--vacuum", action="store_true")
    p.set_defaults(func=cmd_prune)

    p = sub.add_parser("export", help="xuất JSON cho báo cáo/slide")
    p.add_argument("--scope", default="all", choices=["all", "vn", "global"])
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("sources", help="liệt kê nguồn")
    p.set_defaults(func=cmd_sources)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
