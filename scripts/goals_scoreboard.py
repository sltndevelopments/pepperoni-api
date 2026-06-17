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
from typing import Any
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
DB = DATA / "seo_data.db"
OUT = DATA / "goals.json"
METRIKA = DATA / "metrika.json"

# Thresholds for gap classification (tuned for early-stage traffic):
CTR_GAP_MIN_IMPRESSIONS = 30   # at least 30 impressions in 28d
CTR_GAP_MAX_CLICKS = 2         # ≤2 clicks → title/snippet problem
CONV_GAP_MIN_CLICKS = 3        # at least 3 clicks → people arrived, didn't convert

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

# Target export markets (GSC uses ISO-3166 alpha-3 lowercase country codes).
TARGET_COUNTRIES = {
    "rus": "Россия", "kaz": "Казахстан", "blr": "Беларусь", "arm": "Армения",
    "aze": "Азербайджан", "kgz": "Кыргызстан", "tjk": "Таджикистан",
    "geo": "Грузия", "are": "ОАЭ", "sau": "Сауд. Аравия", "kwt": "Кувейт",
    "bhr": "Бахрейн", "omn": "Оман", "yem": "Йемен", "qat": "Катар",
    "egy": "Египет",
}


def _rows(conn, sql, args=()):
    try:
        return conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []


def country_scoreboard(conn, cutoff: str) -> list:
    """Per-target-country visibility: impressions/clicks/avg position (28d)."""
    rows = _rows(conn, """
        SELECT lower(country), SUM(impressions), SUM(clicks),
               SUM(position*impressions)/MAX(SUM(impressions),1)
        FROM gsc_queries WHERE date >= ? GROUP BY lower(country)
    """, (cutoff,))
    by_code = {r[0]: r for r in rows if r[0]}
    out = []
    for code, name in TARGET_COUNTRIES.items():
        r = by_code.get(code)
        out.append({
            "country": name, "code": code,
            "impressions_28d": int(r[1]) if r else 0,
            "clicks_28d": int(r[2]) if r else 0,
            "position_28d": round(r[3], 1) if r and r[3] else None,
        })
    return out


def _load_inquiries_by_page() -> dict[str, dict]:
    """Load per-page inquiry counts from metrika.json (written by fetch_metrika.py).

    Returns: {"/geo/pepperoni-kazan": {"28d": 2, "7d": 1}, ...}
    Empty dict if metrika.json is absent or has no inquiry data yet.
    """
    try:
        m = json.loads(METRIKA.read_text(encoding="utf-8"))
        return m.get("inquiries_by_page") or {}
    except Exception:
        return {}


def _match_inquiries(pages_for_query: list[str],
                     inq: dict[str, dict]) -> int:
    """Sum 28d inquiries across all landing pages that serve a given query.

    pages_for_query: list of URLs from GSC (full URLs like https://pepperoni.tatar/foo
                     or plain paths /foo).
    inq: {path: {"28d": N, "7d": M}} from Metrika — paths like /foo.
    Normalises GSC URLs → paths and matches against Metrika paths.
    """
    from urllib.parse import urlparse
    total = 0
    seen: set[str] = set()
    for p in pages_for_query:
        # Extract path from full URL if needed.
        if p.startswith("http"):
            path = urlparse(p).path
        else:
            path = p
        norm = path.rstrip("/") or "/"
        if norm in seen:
            continue
        seen.add(norm)
        total += inq.get(norm, {}).get("28d", 0)
    return total


def main() -> int:
    goals = []
    gsc_extra = []
    countries = []
    inq = _load_inquiries_by_page()  # {path: {"28d": N, "7d": M}}

    if DB.exists():
        conn = sqlite3.connect(DB)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")
        week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        countries = country_scoreboard(conn, cutoff)

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
            # Landing pages that rank for this query (for inquiry matching).
            pages_for_q = [r[0] for r in _rows(conn, """
                SELECT DISTINCT page FROM gsc_queries
                WHERE date >= ? AND lower(query)=lower(?) AND page IS NOT NULL
            """, (cutoff, q))]

            impr   = int((r28[0][0] if r28 else 0) or 0)
            clicks = int((r28[0][1] if r28 else 0) or 0)
            pos28  = r28[0][2] if r28 and r28[0][2] else None
            pos7   = r7[0][0] if r7 and r7[0][0] else None
            inquiries_28d = _match_inquiries(pages_for_q, inq)

            # ── Gap classification ───────────────────────────────────────────
            # ctr_gap:        impressions but almost no clicks → fix title/snippet
            # conversion_gap: people clicked in but didn't contact → fix CTA/intent
            ctr_gap = (
                impr >= CTR_GAP_MIN_IMPRESSIONS
                and clicks <= CTR_GAP_MAX_CLICKS
            )
            conversion_gap = (
                clicks >= CONV_GAP_MIN_CLICKS
                and inquiries_28d == 0
            )

            goals.append({
                "query":          q,
                "seed":           q in SEED_QUERIES,
                "impressions_28d": impr,
                "clicks_28d":     clicks,
                "inquiries_28d":  inquiries_28d,
                "position_28d":   round(pos28, 1) if pos28 else None,
                "position_7d":    round(pos7, 1) if pos7 else None,
                "trend":          (round(pos28 - pos7, 1) if pos28 and pos7 else None),
                "gap_to_1":       (round(max(0.0, (pos7 or pos28) - 1.0), 1)
                                   if (pos7 or pos28) else None),
                "achieved":       bool((pos7 or pos28) and (pos7 or pos28) <= 1.3),
                "ctr_gap":        ctr_gap,
                "conversion_gap": conversion_gap,
            })
        conn.close()
    else:
        goals = [{"query": q, "seed": True, "position_28d": None, "position_7d": None,
                  "trend": None, "gap_to_1": None, "achieved": False,
                  "impressions_28d": 0, "clicks_28d": 0,
                  "inquiries_28d": 0, "ctr_gap": False, "conversion_gap": False}
                 for q in SEED_QUERIES]

    tracked = [g for g in goals if g["gap_to_1"] is not None]

    # ── Summary stats ─────────────────────────────────────────────────────────
    ctr_gaps       = [g for g in goals if g.get("ctr_gap")]
    conversion_gaps = [g for g in goals if g.get("conversion_gap")]
    # Top converting: pages with ≥1 inquiry, sorted by inquiries desc.
    top_converting = sorted(
        [{"path": p, **v} for p, v in inq.items() if v.get("28d", 0) > 0],
        key=lambda x: -x["28d"]
    )[:10]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": ("Позиция №1 в Google/Яндекс по каждому целевому запросу (RU+EN) "
                    "и цитирование ИИ-ассистентами. "
                    "Real KPI = квалифицированные заявки (inquiries_28d)."),
        "achieved":             sum(1 for g in goals if g["achieved"]),
        "tracked":              len(tracked),
        "total":                len(goals),
        "ctr_gaps_count":       len(ctr_gaps),
        "conversion_gaps_count": len(conversion_gaps),
        "top_converting":       top_converting,
        "goals":                sorted(goals, key=lambda g: (
                                    g["gap_to_1"] is None,
                                    -(g["impressions_28d"] or 0)
                                )),
        "countries":            countries,
    }
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ctr_n  = len(ctr_gaps)
    conv_n = len(conversion_gaps)
    inq_total = sum(g["inquiries_28d"] for g in goals)
    print(f"goals: {out['achieved']}/{out['total']} at #1, {len(tracked)} tracked, "
          f"inquiries_28d={inq_total}, ctr_gaps={ctr_n}, conversion_gaps={conv_n} → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
