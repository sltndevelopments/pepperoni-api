#!/usr/bin/env python3
"""Commercial pulse — north-star checkpoint while experiments are measuring.

Read-only. No page edits. Surfaces for the 3 active operator experiments:
  • days left until measure_at
  • GSC for exact query+page (may be empty = not ranking yet)
  • GSC for query site-wide (demand / cannibalization)
  • leads 7d / 21d, optionally matched to experiment landing pages

Usage:
  python3 scripts/commercial_pulse.py           # print report
  python3 scripts/commercial_pulse.py --json    # machine-readable
  python3 scripts/commercial_pulse.py --telegram  # post via notification_router
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "seo_data.db"
EXPERIMENTS = DATA / "operator_experiments.json"
LEADS = DATA / "leads.json"
WINDOW = 28


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_experiments() -> list[dict]:
    rows = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("experiments", [])
    return [r for r in rows if r.get("status") == "measuring"]


def _gsc_conn() -> sqlite3.Connection | None:
    if not DB.exists():
        return None
    return sqlite3.connect(str(DB))


def _page_variants(page: str) -> list[str]:
    page = page or ""
    out = [page]
    if page.startswith("/"):
        out += [
            f"https://pepperoni.tatar{page}",
            f"https://pepperoni.tatar{page}/",
        ]
    return out


def _gsc_query_page(conn: sqlite3.Connection, query: str, page: str) -> dict:
    pages = _page_variants(page)
    ph = ",".join("?" for _ in pages)
    row = conn.execute(
        f"""SELECT SUM(impressions), SUM(clicks),
                   SUM(position*impressions)*1.0/NULLIF(SUM(impressions),0)
            FROM gsc_queries
            WHERE query = ? AND page IN ({ph})
              AND date >= date('now','-{WINDOW} days')""",
        (query, *pages),
    ).fetchone()
    impr = int(row[0] or 0) if row else 0
    clicks = int(row[1] or 0) if row else 0
    pos = round(float(row[2]), 1) if row and row[2] is not None else None
    return {"impr": impr, "clicks": clicks, "position": pos}


def _gsc_query_sitewide(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        f"""SELECT page, SUM(impressions) AS impr, SUM(clicks) AS clicks,
                   SUM(position*impressions)*1.0/NULLIF(SUM(impressions),0) AS pos
            FROM gsc_queries
            WHERE query = ? AND date >= date('now','-{WINDOW} days')
            GROUP BY page
            ORDER BY impr DESC
            LIMIT ?""",
        (query, limit),
    ).fetchall()
    out = []
    for page, impr, clicks, pos in rows:
        path = page or ""
        if "pepperoni.tatar" in path:
            path = "/" + path.split("pepperoni.tatar/", 1)[-1]
        out.append({
            "page": path,
            "impr": int(impr or 0),
            "clicks": int(clicks or 0),
            "position": round(float(pos), 1) if pos is not None else None,
        })
    return out


def _leads_stats(experiment_pages: set[str]) -> dict:
    try:
        data = json.loads(LEADS.read_text(encoding="utf-8"))
        leads = data.get("leads") or []
    except Exception:
        return {"7d": 0, "21d": 0, "commercial_7d": 0, "on_exp_pages_21d": 0, "last_at": None}

    now = _now()
    cut7 = now - timedelta(days=7)
    cut21 = now - timedelta(days=21)
    n7 = n21 = comm7 = on_exp = 0
    last_at = None
    for lead in leads:
        try:
            at = datetime.fromisoformat(str(lead.get("at", "")).replace("Z", "+00:00"))
        except Exception:
            continue
        if last_at is None or at > last_at:
            last_at = at
        if at >= cut21:
            n21 += 1
            landing = (lead.get("landing_page") or "").rstrip("/")
            if any(landing.endswith(p.rstrip("/")) or p.rstrip("/") in landing
                   for p in experiment_pages if p):
                on_exp += 1
        if at >= cut7:
            n7 += 1
            if lead.get("intent") == "commercial":
                comm7 += 1
    return {
        "7d": n7,
        "21d": n21,
        "commercial_7d": comm7,
        "on_exp_pages_21d": on_exp,
        "last_at": last_at.isoformat() if last_at else None,
    }


def build_pulse() -> dict:
    exps = _load_experiments()
    conn = _gsc_conn()
    pages = {e.get("page", "") for e in exps}
    leads = _leads_stats(pages)
    gsc_max = None
    if conn:
        try:
            gsc_max = conn.execute("SELECT max(date) FROM gsc_queries").fetchone()[0]
        except Exception:
            pass

    items = []
    for e in exps:
        query = e.get("query") or ""
        page = e.get("page") or ""
        baseline = e.get("baseline") or {}
        measure_at = e.get("measure_at") or ""
        try:
            mdt = datetime.fromisoformat(measure_at.replace("Z", "+00:00"))
            days_left = max(0, int((mdt - _now()).total_seconds() // 86400))
        except Exception:
            days_left = None

        exact = {"impr": 0, "clicks": 0, "position": None}
        sitewide: list[dict] = []
        if conn and query:
            exact = _gsc_query_page(conn, query, page)
            sitewide = _gsc_query_sitewide(conn, query)

        base_pos = baseline.get("position")
        delta = None
        if exact.get("position") is not None and base_pos is not None:
            delta = round(float(base_pos) - float(exact["position"]), 1)

        items.append({
            "id": e.get("id"),
            "query": query,
            "page": page,
            "days_left": days_left,
            "measure_at": measure_at[:10],
            "baseline_position": base_pos,
            "baseline_impr_90d": baseline.get("impr_90d"),
            "exact": exact,
            "delta_vs_baseline": delta,
            "sitewide_top": sitewide,
            "flag": (
                "not_ranking_yet"
                if exact["impr"] == 0
                else ("improved" if (delta is not None and delta >= 3)
                      else ("worse" if (delta is not None and delta <= -3)
                            else "watching"))
            ),
        })

    if conn:
        conn.close()

    return {
        "generated_at": _now().isoformat(),
        "gsc_data_through": gsc_max,
        "window_days": WINDOW,
        "leads": leads,
        "experiments": items,
        "north_star": "leads + commercial GSC vs kazandelikates; no geo farm",
    }


def format_report(pulse: dict) -> str:
    lines = [
        "🎯 <b>Commercial pulse</b> (north star)",
        f"<i>{pulse['generated_at'][:10]}</i> · GSC data → {pulse.get('gsc_data_through') or '—'}",
        "",
        "<b>Лиды</b>",
        f"  7д: {pulse['leads']['7d']} (commercial {pulse['leads']['commercial_7d']}) · "
        f"21д: {pulse['leads']['21d']} · на exp-страницах: {pulse['leads']['on_exp_pages_21d']}",
        "",
        "<b>Эксперименты (measuring)</b>",
    ]
    for it in pulse["experiments"]:
        exact = it["exact"]
        flag = {
            "not_ranking_yet": "⏳ страница ещё не в выдаче по запросу",
            "improved": "✅ лучше baseline ≥3 поз.",
            "worse": "⚠ хуже baseline ≥3 поз.",
            "watching": "👀 смотрим",
        }.get(it["flag"], it["flag"])
        lines.append(
            f"• <b>{it['query']}</b> → <code>{it['page']}</code>\n"
            f"  до замера: {it['days_left']}д ({it['measure_at']}) · {flag}\n"
            f"  exact: pos={exact['position'] if exact['position'] is not None else '—'} "
            f"impr={exact['impr']} clicks={exact['clicks']} "
            f"(baseline pos={it['baseline_position']})"
        )
        if it["sitewide_top"]:
            top = it["sitewide_top"][0]
            lines.append(
                f"  сейчас клики/показы уходят на: <code>{top['page']}</code> "
                f"pos={top['position']} impr={top['impr']}"
            )
        lines.append("")
    lines.append("Не трогать exp-страницы до measure_at. Max 3 эксперимента.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()
    pulse = build_pulse()
    if args.json:
        print(json.dumps(pulse, ensure_ascii=False, indent=2))
    else:
        report = format_report(pulse)
        print(report)
        if args.telegram:
            try:
                from notification_router import emit
                emit("digest", "commercial_pulse", report,
                     dedupe_key=f"commercial_pulse:{pulse['generated_at'][:10]}")
            except Exception as exc:
                print(f"telegram emit failed: {exc}", file=sys.stderr)
                return 1
    # Always write snapshot for weekly_sync / brain
    out = DATA / "commercial_pulse.json"
    out.write_text(json.dumps(pulse, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
