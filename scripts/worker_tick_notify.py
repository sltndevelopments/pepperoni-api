#!/usr/bin/env python3
"""Emit only actionable worker outcomes; green ticks stay silent.

Usage (from seo-worker.sh):
    python3 scripts/worker_tick_notify.py --since 2026-06-21T15:00:00+00:00 --pushed 4
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GATE_LOG = ROOT / "data" / "page_gate_log.json"
QUARANTINE = ROOT / "data" / "quarantine"


def _gate_since(since_iso: str) -> dict:
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {"pass": 0, "reject": 0, "hold": 0, "sample_reasons": []}
    since = since_iso.strip()
    tick = [e for e in log if e.get("ts", "") >= since and "tmp" not in e.get("path", "")]
    reasons: list[str] = []
    for e in tick:
        if e.get("verdict") in ("reject", "hold"):
            reasons.extend(e.get("reasons", [])[:1])
    return {
        "pass": sum(1 for e in tick if e.get("verdict") == "pass"),
        "reject": sum(1 for e in tick if e.get("verdict") == "reject"),
        "hold": sum(1 for e in tick if e.get("verdict") == "hold"),
        "sample_reasons": reasons[:2],
    }


def _quarantine_snapshot() -> dict:
    try:
        from quarantine_report import build_report
        report = build_report()
        return {
            "current": report["current_files"],
            "historical_rejects": report["historical_reject_hold_events"],
        }
    except Exception:
        try:
            return {"current": len(list(QUARANTINE.rglob("*.html"))),
                    "historical_rejects": 0}
        except Exception:
            return {"current": 0, "historical_rejects": 0}


def _today_spend() -> tuple[float, float]:
    try:
        from claude_client import today_spend_usd, LLM_DAILY_BUDGET_USD
        return today_spend_usd(), float(LLM_DAILY_BUDGET_USD)
    except Exception:
        return 0.0, 5.0


def build_message(*, since: str, pushed: int, log_hint: str = "") -> str:
    g = _gate_since(since)
    spent, cap = _today_spend()
    q = _quarantine_snapshot()
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    # Green/no-ship ticks are suppressed in main(); if we get here there is
    # either a ship or a gate/budget signal — never a bare "без коммитов" ping.
    if pushed > 0:
        ship = f"📄 <b>+{pushed}</b> → main"
    else:
        ship = "📄 тик без публикации (есть сигнал гейта/бюджета)"

    lines = [
        f"⚙️ <b>Worker tick</b> {now}",
        ship,
        f"🚦 гейт (тик): ✅{g['pass']} / 🚧{g['reject']} / ⏸{g['hold']}",
        f"📦 карантин сейчас: {q['current']} "
        f"(reject за период {q['historical_rejects']})",
        f"💰 ${spent:.2f} сегодня (лимит ${cap:.0f})",
    ]
    if g["sample_reasons"]:
        r = " · ".join(g["sample_reasons"])[:120]
        lines.append(f"↳ {r}")
    if log_hint:
        lines.append(f"<i>{log_hint[:80]}</i>")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="ISO timestamp tick start (UTC)")
    ap.add_argument("--pushed", type=int, default=0, help="Files pushed this tick")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    msg = build_message(since=args.since, pushed=args.pushed)
    if args.dry_run:
        print(msg)
        return 0

    gate = _gate_since(args.since)
    spent, cap = _today_spend()
    if args.pushed <= 0 and gate["reject"] == 0 and gate["hold"] == 0 and spent < cap * 0.8:
        print("⏭ worker_tick_notify: green/no-result tick suppressed")
        return 0

    try:
        from notification_router import emit
        if gate["hold"] > 0:
            emit("emergency", "reviewer_hold", msg,
                 dedupe_key=f"worker-hold:{datetime.now(timezone.utc):%Y-%m-%d}")
        elif gate["reject"] > 0 or spent >= cap * 0.8:
            emit("action", "worker_attention", msg,
                 dedupe_key=f"worker-action:{datetime.now(timezone.utc):%Y-%m-%d}")
        else:
            emit("result", "worker_publish", msg,
                 dedupe_key=f"worker-result:{args.since}")
        return 0
    except Exception as e:
        print(f"⚠️ worker_tick_notify failed: {e}", file=sys.stderr)
        return 0  # non-fatal for worker


if __name__ == "__main__":
    raise SystemExit(main())
