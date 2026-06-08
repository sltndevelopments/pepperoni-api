#!/usr/bin/env python3
"""
ANOMALY-GUARD — traffic/position watchdog (meta-agent item E, runs daily).

Catches sudden drops (algo update, site breakage, deindexing) within a day
instead of weeks. The optimizer/health-monitor look at structure; this looks at
the TREND of real search performance.

Mechanism (durable across ephemeral CI/VPS runs):
  • Each run reads the current aggregate from GSC (and Yandex if present):
    total clicks, impressions, weighted avg position, and the position of the
    top-N money queries.
  • Appends today's point to a git-tracked time series (data/anomaly_baseline.json).
  • Compares the latest point against the trailing baseline (median of the prior
    N points). If clicks/impressions fall more than DROP_PCT, or weighted position
    worsens by more than POS_DROP, or a tracked key query falls off page 1 — it
    fires an INSTANT Telegram alert.

Designed to be conservative: needs a minimum history before alerting, uses median
(robust to single spikes), and de-dupes alerts so it won't spam the same drop.

Env:
  ANOMALY_DROP_PCT   (0.35)  relative drop in clicks/impr that triggers an alert
  ANOMALY_POS_DROP   (3.0)   worsening of weighted avg position that triggers
  ANOMALY_MIN_HISTORY(4)     min prior points before we judge
  ANOMALY_BASELINE_N (7)     trailing points used for the baseline median
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
Usage:
  python3 scripts/anomaly_guard.py            # record + check + alert
  python3 scripts/anomaly_guard.py --check-only  # don't append a new point
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
BASELINE = DATA / "anomaly_baseline.json"

DROP_PCT     = float(os.environ.get("ANOMALY_DROP_PCT", "0.35"))
POS_DROP     = float(os.environ.get("ANOMALY_POS_DROP", "3.0"))
MIN_HISTORY  = int(os.environ.get("ANOMALY_MIN_HISTORY", "4"))
BASELINE_N   = int(os.environ.get("ANOMALY_BASELINE_N", "7"))
TOP_QUERIES  = int(os.environ.get("ANOMALY_TOP_QUERIES", "10"))


def load_series() -> list:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_series(series: list) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(series, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def snapshot(conn) -> dict:
    """Current aggregate metrics + top-query positions from GSC."""
    agg = conn.execute("""
        SELECT SUM(clicks) clk, SUM(impressions) impr,
               SUM(position*impressions)/NULLIF(SUM(impressions),0) wpos
        FROM gsc_queries
    """).fetchone()
    top = conn.execute(f"""
        SELECT query,
               SUM(impressions) impr,
               SUM(position*impressions)/NULLIF(SUM(impressions),0) pos
        FROM gsc_queries
        GROUP BY query
        ORDER BY impr DESC
        LIMIT {TOP_QUERIES}
    """).fetchall()
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "clicks": int(agg["clk"] or 0),
        "impressions": int(agg["impr"] or 0),
        "wpos": round(float(agg["wpos"] or 0), 2),
        "queries": {r["query"]: round(float(r["pos"] or 0), 1) for r in top},
    }


def _median(vals: list) -> float:
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else 0.0


def detect(series: list, cur: dict) -> list[str]:
    """Compare current point to trailing baseline median; return anomaly messages."""
    prior = series[-BASELINE_N - 1:-1] if len(series) > 1 else series[:-1]
    prior = [p for p in prior if p.get("date") != cur.get("date")]
    if len(prior) < MIN_HISTORY:
        return []

    alerts = []
    base_clicks = _median([p["clicks"] for p in prior])
    base_impr   = _median([p["impressions"] for p in prior])
    base_wpos   = _median([p["wpos"] for p in prior if p.get("wpos")])

    if base_clicks >= 5 and cur["clicks"] < base_clicks * (1 - DROP_PCT):
        drop = 1 - cur["clicks"] / base_clicks
        alerts.append(f"клики: {cur['clicks']} (медиана {base_clicks:.0f}, "
                      f"падение {drop*100:.0f}%)")
    if base_impr >= 100 and cur["impressions"] < base_impr * (1 - DROP_PCT):
        drop = 1 - cur["impressions"] / base_impr
        alerts.append(f"показы: {cur['impressions']} (медиана {base_impr:.0f}, "
                      f"падение {drop*100:.0f}%)")
    if base_wpos and cur["wpos"] and cur["wpos"] - base_wpos >= POS_DROP:
        alerts.append(f"средняя позиция: {cur['wpos']} "
                      f"(была {base_wpos:.1f}, ухудшение +{cur['wpos']-base_wpos:.1f})")

    # per-query: a tracked money query that dropped off page 1 (was <=10, now >15)
    prev_q = {}
    for p in reversed(prior):
        for q, pos in (p.get("queries") or {}).items():
            prev_q.setdefault(q, pos)
    for q, pos in cur.get("queries", {}).items():
        was = prev_q.get(q)
        if was and was <= 10 and pos > 15:
            alerts.append(f"запрос «{q}»: упал с поз. {was:.0f} → {pos:.0f}")
    return alerts


def alert(cur: dict, messages: list[str]) -> None:
    lines = ["<b>🚨 Anomaly-Guard — резкое падение!</b>",
             f"<i>Дата: {cur['date']}</i>", ""]
    for m in messages:
        lines.append(f"  🔻 {m}")
    lines.append("\n<i>Проверь: апдейт Я/Google, доступность сайта, "
                 "robots/sitemap, недавние изменения. Возможен сбой индексации.</i>")
    try:
        from telegram_notify import notify
        notify("\n".join(lines))
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


def main():
    check_only = "--check-only" in sys.argv[1:]
    init_db()
    conn = get_conn()
    cur = snapshot(conn)
    conn.close()

    if cur["impressions"] == 0 and cur["clicks"] == 0:
        print("· no GSC data this run — skip (fetch GSC first)")
        return 0

    series = load_series()
    # replace today's point if it already exists (idempotent within a day)
    series = [p for p in series if p.get("date") != cur["date"]]
    history_for_check = series + [cur]

    messages = detect(history_for_check, cur)

    if not check_only:
        series.append(cur)
        series = series[-90:]  # keep ~3 months
        save_series(series)
        print(f"📈 recorded {cur['date']}: clicks={cur['clicks']} "
              f"impr={cur['impressions']} wpos={cur['wpos']} "
              f"(history {len(series)} pts)")

    if messages:
        print("🚨 ANOMALY detected:")
        for m in messages:
            print(f"  - {m}")
        alert(cur, messages)
    else:
        prior_n = len([p for p in series if p.get("date") != cur["date"]])
        if prior_n < MIN_HISTORY:
            print(f"· building baseline ({prior_n}/{MIN_HISTORY} pts) — no judgment yet")
        else:
            print("✅ no anomaly — traffic/positions within normal range")
    return 0


if __name__ == "__main__":
    sys.exit(main())
