#!/usr/bin/env python3
"""Build the locked SEO/AI/Metrika trust-reset baseline from source data."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "seo_data.db"
AI = DATA / os.environ.get(
    "AI_BASELINE_FILE", "buyer_baseline_2026-08-26.json")
OUT = ROOT / os.environ.get(
    "TRUST_RESET_BASELINE_OUT",
    "data/trust_reset_baseline_2026-08-26.json",
)


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def search_baselines() -> dict:
    conn = sqlite3.connect(str(DB))
    latest_gsc = conn.execute(
        "SELECT MAX(date) FROM gsc_queries").fetchone()[0]
    if not latest_gsc:
        raise SystemExit("GSC baseline missing")
    gsc_start = (date.fromisoformat(latest_gsc) - timedelta(days=27)).isoformat()
    gsc = conn.execute(
        """SELECT COALESCE(SUM(clicks), 0),
                  COALESCE(SUM(impressions), 0),
                  COALESCE(
                    SUM(position * impressions) / NULLIF(SUM(impressions), 0),
                    0
                  ),
                  COUNT(DISTINCT query),
                  COUNT(DISTINCT page)
           FROM gsc_queries WHERE date >= ?""",
        (gsc_start,),
    ).fetchone()
    latest_yandex = conn.execute(
        "SELECT MAX(date) FROM yandex_queries").fetchone()[0]
    if not latest_yandex:
        raise SystemExit("Yandex Webmaster baseline missing")
    yandex = conn.execute(
        """SELECT COALESCE(SUM(clicks), 0),
                  COALESCE(SUM(impressions), 0),
                  COUNT(DISTINCT query)
           FROM yandex_queries WHERE date = ?""",
        (latest_yandex,),
    ).fetchone()
    conn.close()

    gsc_clicks, gsc_impressions, gsc_position, gsc_queries, gsc_pages = gsc
    ya_clicks, ya_impressions, ya_queries = yandex
    return {
        "google_search_console": {
            "window": {"start": gsc_start, "end": latest_gsc, "days": 28},
            "clicks": int(gsc_clicks),
            "impressions": int(gsc_impressions),
            "ctr": round(gsc_clicks / gsc_impressions, 6) if gsc_impressions else 0,
            "weighted_position": round(float(gsc_position), 2),
            "distinct_queries": int(gsc_queries),
            "distinct_pages": int(gsc_pages),
            "scope": "non-anonymized query×page×country×device rows returned by the GSC API",
            "caveat": "Do not compare this partial query-level total with the aggregate Search Console UI total.",
        },
        "yandex_webmaster": {
            "window_end": latest_yandex,
            "window_days": 30,
            "clicks": int(ya_clicks),
            "impressions": int(ya_impressions),
            "ctr": round(ya_clicks / ya_impressions, 6) if ya_impressions else 0,
            "distinct_queries": int(ya_queries),
            "scope": "popular-query aggregate for the exact verified https://pepperoni.tatar host",
        },
    }


def ai_baseline() -> dict:
    payload = json.loads(AI.read_text(encoding="utf-8"))
    summary: dict[str, dict] = {}
    for layer in payload.get("layers") or []:
        records = [
            row.get("layers", {}).get(layer, {})
            for row in payload.get("rows") or []
        ]
        ok = [record for record in records if record.get("status") == "ok"]
        hits = [record for record in ok if record.get("kd_present") is True]
        ranks = [
            int(record["rank"]) for record in hits
            if isinstance(record.get("rank"), int)
        ]
        summary[layer] = {
            "prompts": len(records),
            "ok": len(ok),
            "errors": len(records) - len(ok),
            "hits": len(hits),
            "hit_rate": round(len(hits) / len(ok), 4) if ok else None,
            "top3": sum(rank <= 3 for rank in ranks),
            "rank1": sum(rank == 1 for rank in ranks),
            "average_rank_when_present": (
                round(sum(ranks) / len(ranks), 2) if ranks else None
            ),
        }
    return {
        "captured_at": payload.get("ts"),
        "panel": "fixed 20 buyer prompts; search-grounded layers only",
        "layers": summary,
        "source_file": str(AI.relative_to(ROOT)),
    }


def main() -> int:
    metrika = load("metrika.json")
    manifest = load("index_manifest.json")
    retire = load("url_consolidation_map.json")
    experiments = json.loads(
        (DATA / "operator_experiments.json").read_text(encoding="utf-8"))
    legacy_experiments = load("ab_tests.json").get("ab_tests", [])
    authority = load("authority_program.json")
    active_experiments = [
        {"source": "operator_experiments", "id": row["id"]}
        for row in experiments
        if row.get("status") in {"active", "measuring"}
    ]
    active_experiments.extend(
        {
            "source": "ab_tests",
            "id": row.get("query") or row.get("variant_url"),
        }
        for row in legacy_experiments
        if row.get("status") == "ab_running"
    )
    payload = {
        "version": 1,
        "locked_at": "2026-08-26",
        "purpose": "Pre-publication baseline for the 213-URL SEO and AI trust reset.",
        "search": search_baselines(),
        "analytics": {
            "window_days": metrika.get("days"),
            "fetched_at": metrika.get("fetched_at"),
            "visits": metrika.get("totals", {}).get("visits"),
            "search_visits": next(
                (
                    row.get("visits")
                    for row in metrika.get("sources", [])
                    if row.get("source") == "Search engine traffic"
                ),
                None,
            ),
            "all_site_goal_completions": metrika.get("leads", {}).get("total_leads"),
            "qualified_organic_b2b_leads": None,
            "attribution_status": (
                "Not yet measurable: auto-goal completions are not equivalent "
                "to qualified organic B2B enquiries."
            ),
        },
        "ai_search": ai_baseline(),
        "index_policy": {
            "keep": manifest.get("counts", {}).get("keep"),
            "retired": manifest.get("counts", {}).get("retired"),
            "redirect_301": retire.get("counts", {}).get("301"),
            "gone_410": retire.get("counts", {}).get("410"),
            "noindex": retire.get("counts", {}).get("noindex"),
            "city_product_indexable": retire.get("policy", {}).get(
                "city_product_indexable"),
            "languages_indexable": retire.get("policy", {}).get(
                "languages_indexable"),
        },
        "experiments": {
            "active": active_experiments,
            "active_count": len(active_experiments),
            "max_active": 3,
        },
        "authority": {
            "cycle": authority.get("cycle", {}).get("id"),
            "new_domains_published": authority.get(
                "scoreboard", {}).get("new_domains_published"),
            "target": authority.get("goal", {}).get("new_independent_domains"),
            "international_target": authority.get(
                "goal", {}).get("international_domains_min"),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"trust-reset baseline: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
