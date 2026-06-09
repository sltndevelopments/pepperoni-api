#!/usr/bin/env python3
"""Goals scoreboard — formalizes the mission "be #1 for every target query".

Combines a curated seed list of must-win commercial queries with the top
real-demand queries from GSC, and for each computes: current avg position,
7-day trend, and distance to #1. Writes data/goals.json (git-tracked) which
feeds the brain digest and the Telegram «🎯 Цели» button.

No LLM, no network — pure SQLite read. Safe to run daily.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
DB = DATA / "seo_data.db"
OUT = DATA / "goals.json"

# Must-win queries: the commercial core of the business. Position here is the
# definition of success, regardless of what GSC currently shows demand for.
SEED_QUERIES = [
    "пепперони оптом",
    "халяль пепперони",
    "пепперони халяль оптом",
    "сосиска в тесте оптом",
    "сосиски для хот-догов оптом",
    "котлеты для бургеров оптом",
    "казылык купить оптом",
    "халяль колбаса оптом",
    "контрактное производство мясных изделий",
    "мясные полуфабрикаты под СТМ",
    "татарская выпечка оптом",
    "чак-чак оптом",
    "halal pepperoni wholesale",
    "halal sausages supplier russia",
]

MAX_GSC_EXTRA = 10  # top demand queries auto-added from GSC


def _rows(conn, sql, args=()):
    try:
        return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []


def main() -> int:
    goals = []
    gsc_extra = []
    if DB.exists():
        conn = sqlite3.connect(DB)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")
        week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        # Top real-demand queries (28d) not already in the seed list.
        seed_low = {q.lower() for q in SEED_QUERIES}
        for q, impr in _rows(conn, """
            SELECT query, SUM(impressions) FROM gsc_queries
            WHERE date >= ? GROUP BY query ORDER BY SUM(impressions) DESC LIMIT 40
        """, (cutoff,)):
            if q.lower() not in seed_low and len(gsc_extra) < MAX_GSC_EXTRA:
                gsc_extra.append(q)

        for q in SEED_QUERIES + gsc_extra:
            r28 = _rows(conn, """
                SELECT SUM(impressions), SUM(clicks),
                       SUM(position*impressions)/MAX(SUM(impressions),1)
                FROM gsc_queries WHERE date >= ? AND lower(query)=lower(?)
            """, (cutoff, q))
            r7 = _rows(conn, """
                SELECT SUM(position*impressions)/MAX(SUM(impressions),1)
                FROM gsc_queries WHERE date >= ? AND lower(query)=lower(?)
            """, (week, q))
            impr = (r28[0][0] if r28 else 0) or 0
            clicks = (r28[0][1] if r28 else 0) or 0
            pos28 = r28[0][2] if r28 and r28[0][2] else None
            pos7 = r7[0][0] if r7 and r7[0][0] else None
            goals.append({
                "query": q,
                "seed": q in SEED_QUERIES,
                "impressions_28d": int(impr),
                "clicks_28d": int(clicks),
                "position_28d": round(pos28, 1) if pos28 else None,
                "position_7d": round(pos7, 1) if pos7 else None,
                "trend": (round(pos28 - pos7, 1) if pos28 and pos7 else None),  # + = improving
                "gap_to_1": (round(max(0.0, (pos7 or pos28) - 1.0), 1)
                             if (pos7 or pos28) else None),
                "achieved": bool((pos7 or pos28) and (pos7 or pos28) <= 1.3),
            })
        conn.close()
    else:
        goals = [{"query": q, "seed": True, "position_28d": None, "position_7d": None,
                  "trend": None, "gap_to_1": None, "achieved": False,
                  "impressions_28d": 0, "clicks_28d": 0} for q in SEED_QUERIES]

    tracked = [g for g in goals if g["gap_to_1"] is not None]
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "Позиция №1 в Google/Яндекс по каждому целевому запросу (RU+EN) и цитирование ИИ-ассистентами",
        "achieved": sum(1 for g in goals if g["achieved"]),
        "tracked": len(tracked),
        "total": len(goals),
        "goals": sorted(goals, key=lambda g: (g["gap_to_1"] is None,
                                              -(g["impressions_28d"] or 0))),
    }
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"goals: {out['achieved']}/{out['total']} at #1, {len(tracked)} tracked -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
