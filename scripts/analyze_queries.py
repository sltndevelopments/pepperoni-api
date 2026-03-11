#!/usr/bin/env python3
"""
Analyze search queries in DB and generate a list of SEO opportunities.
Types:
  quick_growth — position 4-20, impressions > 30 (candidate for title/content improvement)
  low_ctr      — position 1-5, CTR < 3% (needs title rewrite)
  new_query    — high impression query with no matching page
  commercial   — commercial intent query with position > 10

Writes rows to `opportunities` table (status='new').
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

KNOWN_PAGES = {
    "https://pepperoni.tatar/",
    "https://pepperoni.tatar/pepperoni",
    "https://pepperoni.tatar/pepperoni-optom",
    "https://pepperoni.tatar/pepperoni-dlya-pizzerii",
    "https://pepperoni.tatar/pepperoni-dlya-horeca",
    "https://pepperoni.tatar/pepperoni-private-label",
    "https://pepperoni.tatar/pepperoni-v-narezke",
}

COMMERCIAL_KEYWORDS = [
    "купить", "оптом", "поставщик", "цена", "цены",
    "заказать", "доставка", "халяль", "pizzeria", "пиццерия",
    "private label", "стм", "b2b", "хорека", "horeca",
]


def already_exists(conn, query: str, opp_type: str) -> bool:
    row = conn.execute(
        "SELECT id FROM opportunities WHERE query=? AND type=? AND status IN ('new','in_progress','done')",
        (query, opp_type),
    ).fetchone()
    return row is not None


def analyze_gsc(conn, created_at: str) -> int:
    rows = conn.execute("""
        SELECT query, page, AVG(position) as pos, SUM(impressions) as impr, AVG(ctr) as ctr
        FROM gsc_queries
        WHERE date >= date('now', '-30 days')
        GROUP BY query, page
        HAVING impr > 15
        ORDER BY impr DESC
        LIMIT 2000
    """).fetchall()

    added = 0
    for row in rows:
        query = row["query"]
        page  = row["page"] or ""
        pos   = row["pos"]
        impr  = int(row["impr"])
        ctr   = row["ctr"]

        # quick_growth: pos 4-20, impressions > 30
        if 4 <= pos <= 20 and impr > 30:
            if not already_exists(conn, query, "quick_growth"):
                conn.execute(
                    """INSERT INTO opportunities
                       (created_at, type, source, query, page, position, impressions, ctr, status)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (created_at, "quick_growth", "gsc", query, page, pos, impr, ctr, "new"),
                )
                added += 1

        # low_ctr: pos 1-5, ctr < 3%
        if 1 <= pos <= 5 and ctr < 0.03:
            if not already_exists(conn, query, "low_ctr"):
                conn.execute(
                    """INSERT INTO opportunities
                       (created_at, type, source, query, page, position, impressions, ctr, status)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (created_at, "low_ctr", "gsc", query, page, pos, impr, ctr, "new"),
                )
                added += 1

        # commercial_gap: commercial keyword, pos > 10
        ql = query.lower()
        if pos > 10 and any(kw in ql for kw in COMMERCIAL_KEYWORDS):
            if not already_exists(conn, query, "commercial_gap"):
                conn.execute(
                    """INSERT INTO opportunities
                       (created_at, type, source, query, page, position, impressions, ctr, status)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (created_at, "commercial_gap", "gsc", query, page, pos, impr, ctr, "new"),
                )
                added += 1

    return added


def analyze_yandex(conn, created_at: str) -> int:
    rows = conn.execute("""
        SELECT query, AVG(position) as pos, SUM(impressions) as impr
        FROM yandex_queries
        WHERE date >= date('now', '-30 days')
        GROUP BY query
        HAVING impr > 20
        ORDER BY impr DESC
        LIMIT 1000
    """).fetchall()

    added = 0
    for row in rows:
        query = row["query"]
        pos   = row["pos"]
        impr  = int(row["impr"])

        if 4 <= pos <= 20 and impr > 20:
            if not already_exists(conn, query, "quick_growth"):
                conn.execute(
                    """INSERT INTO opportunities
                       (created_at, type, source, query, page, position, impressions, ctr, status)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (created_at, "quick_growth", "yandex", query, None, pos, impr, 0.0, "new"),
                )
                added += 1

    return added


def main():
    init_db()
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    gsc_added = analyze_gsc(conn, now)
    ya_added  = analyze_yandex(conn, now)

    conn.commit()
    conn.close()

    total = gsc_added + ya_added
    print(f"✅ Found {total} new opportunities (GSC: {gsc_added}, Yandex: {ya_added})")

    return total


if __name__ == "__main__":
    main()
