#!/usr/bin/env python3
"""Build a read-only GitHub Pages snapshot of La Bàn Nghề.

The FastAPI app is used only during the build. The exported site contains
HTML, static assets and pre-computed JSON responses; it does not need Python
at runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from laban.config import ROOT, STATIC_DIR
from laban.taxonomy import load_roles, load_skills
from laban.web import app


PAGES = {
    "/": "index.html",
    "/ky-nang": "ky-nang/index.html",
    "/vi-tri": "vi-tri/index.html",
    "/nguon": "nguon/index.html",
    "/tin-hieu-cong-dong": "tin-hieu-cong-dong/index.html",
    "/bao-cao": "bao-cao/index.html",
    "/cntt": "cntt/index.html",
    "/sach-lat": "sach-lat/index.html",
    "/case-study-cv": "case-study-cv/index.html",
}


def q(value: object) -> str:
    return quote(str(value), safe="")


def key_for(path: str, params: dict | None = None) -> str:
    pairs = sorted(
        (k, str(v))
        for k, v in (params or {}).items()
        if v is not None and str(v) != ""
    )
    query = "&".join(f"{q(k)}={q(v)}" for k, v in pairs)
    return path + ("?" + query if query else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "_site"), help="thư mục đầu ra")
    parser.add_argument("--base-url", default="/labannghe/", help="đường dẫn gốc trên GitHub Pages")
    parser.add_argument("--repo-url", default="https://github.com/ktzung/labannghe")
    parser.add_argument("--site-url", default="https://ktzung.github.io/labannghe/")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    api_dir = out / "api-static"
    if out.exists():
        shutil.rmtree(out)
    api_dir.mkdir(parents=True)
    shutil.copytree(STATIC_DIR, out / "static", dirs_exist_ok=True)

    files: dict[str, str] = {}

    def add(path: str, params: dict | None = None) -> dict:
        key = key_for(path, params)
        if key in files:
            return {}
        response = client.get(path, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"{key} -> HTTP {response.status_code}: {response.text[:200]}")
        payload = response.json()
        name = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] + ".json"
        (api_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        files[key] = name
        return payload

    scopes = ("vn", "global", "all")
    windows = (7, 30, 90)
    forums = ("all", "95", "91", "42", "90")
    skill_ids = sorted(load_skills()[0])
    role_ids = sorted(r["id"] for r in load_roles())

    with TestClient(app) as client:
        for scope in scopes:
            for days in windows:
                base = {"scope": scope, "days": days}
                add("/api/overview", base)
                add("/api/roles", base)
                add("/api/it", base)
                add("/api/export", base)
                add("/api/skills", {**base, "role": "all", "limit": 300, "kind": "skill"})
                add("/api/skills", {**base, "role": "all", "limit": 120, "kind": "knowledge"})

        for days in windows:
            for forum in forums:
                add("/api/social/overview", {"days": days, "forum": forum})

        for skill_id in skill_ids:
            path = "/api/skill/" + q(skill_id)
            for scope in scopes:
                for days in windows:
                    add(path, {"scope": scope, "days": days})

        for role_id in role_ids:
            path = "/api/role/" + q(role_id)
            for scope in scopes:
                for days in windows:
                    add(path, {"scope": scope, "days": days})

        add("/api/method")
        add("/api/health")

        export_key = key_for("/api/export", {"scope": "vn", "days": 30})
        export_file = files[export_key]

        for route, target in PAGES.items():
            response = client.get(route)
            if response.status_code != 200:
                raise RuntimeError(f"{route} -> HTTP {response.status_code}")
            html = response.text.replace('="/', '="' + args.base_url)
            html = html.replace(
                '<script src="' + args.base_url + 'static/app.js',
                '<script src="' + args.base_url + 'static/snapshot.js" defer></script>\n'
                '<script src="' + args.base_url + 'static/app.js',
            )
            html = html.replace(
                'href="' + args.base_url + 'api/export?scope=vn&amp;days=30"',
                'href="' + args.base_url + "api-static/" + export_file + '"',
            )
            target_path = out / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(html, encoding="utf-8")

    manifest = {
        "root": args.base_url,
        "repo_url": args.repo_url,
        "site_url": args.site_url,
        "captured": date.today().strftime("%d/%m/%Y"),
        "files": files,
    }
    (out / "static" / "snapshot.js").write_text(
        "window.LABAN_STATIC = "
        + json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Đã tạo {len(files)} phản hồi API trong {api_dir}")
    print(f"Site: {out}")
    print(f"Pages: {args.site_url}")


if __name__ == "__main__":
    main()
