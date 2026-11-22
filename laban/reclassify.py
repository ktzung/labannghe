from __future__ import annotations

import json

from .company import classify_company_type
from .db import connect, init_db
from .geo import parse_locations
from .taxonomy import classify_role, company_tier, detect_level, extract_facets


def run(verbose: bool = True) -> int:
    conn = connect()
    init_db(conn)
    rows = conn.execute(
        """SELECT id, title, category, tags, description, requirements,
                  company, region, location
           FROM jobs ORDER BY id"""
    ).fetchall()
    changed = 0
    for row in rows:
        tags = json.loads(row["tags"] or "[]")
        description = row["description"] or ""
        requirements = row["requirements"] or ""
        role = classify_role(row["title"], row["category"] or "", tags, description)
        level = detect_level(row["title"])
        facets = extract_facets(row["title"], tags, requirements, description)
        company_type = classify_company_type(row["company"] or "", row["region"] or "GLOBAL")
        locations = parse_locations(row["location"] or "") if row["region"] == "VN" else []
        conn.execute(
            """UPDATE jobs SET role=?, level=?, company_type=?, company_tier=?
               WHERE id=?""",
            (role, level, company_type, company_tier(row["company"] or ""), row["id"]),
        )
        conn.execute("DELETE FROM job_skills WHERE job_id=?", (row["id"],))
        facets_rows = [
            (row["id"], item, weight, "skill")
            for item, weight in facets["skills"].items()
        ]
        facets_rows.extend(
            (row["id"], item, weight, "knowledge")
            for item, weight in facets["knowledge"].items()
        )
        if facets_rows:
            conn.executemany(
                "INSERT OR REPLACE INTO job_skills(job_id, skill_id, weight, kind) VALUES(?,?,?,?)",
                facets_rows,
            )
        conn.execute("DELETE FROM job_locations WHERE job_id=?", (row["id"],))
        if locations:
            conn.executemany(
                "INSERT OR IGNORE INTO job_locations(job_id, city) VALUES(?,?)",
                [(row["id"], city) for city in locations],
            )
        changed += 1
    conn.commit()
    conn.close()
    if verbose:
        print("Đã phân loại lại %d tin: nghề, kỹ năng, địa bàn và loại hình doanh nghiệp." % changed)
    return changed


def main(argv=None):
    run()


if __name__ == "__main__":
    main()
