#!/usr/bin/env python3
"""Telegram «кино» после seo-worker tick — короткий ping в @KDSEOSiteBot.

Routine ticks: immediate notify (не daily_ledger — тот раз в день).
ЧП по-прежнему через notify_emergency / daily_ledger emergency.

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


def _quarantine_count() -> int:
    try:
        return len(list(QUARANTINE.glob("*.html")))
    except Exception:
        return 0


def _today_spend() -> tuple[float, float]:
    try:
        from claude_client import today_spend_usd, LLM_DAILY_BUDGET_USD
        return today_spend_usd(), float(LLM_DAILY_BUDGET_USD)
    except Exception:
        return 0.0, 5.0


def build_message(*, since: str, pushed: int, log_hint: str = "") -> str:
    g = _gate_since(since)
    spent, cap = _today_spend()
    q = _quarantine_count()
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    if pushed > 0:
        ship = f"📄 <b>+{pushed}</b> → main"
    else:
        ship = "📄 без новых коммитов"

    lines = [
        f"⚙️ <b>Worker tick</b> {now}",
        ship,
        f"🚦 гейт (тик): ✅{g['pass']} / 🚧{g['reject']} / ⏸{g['hold']}",
        f"📦 карантин: {q} стр.",
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

    try:
        from telegram_notify import notify
        n = notify(msg)
        if n == 0:
            print("⏭ worker_tick_notify: no recipients (open @KDSEOSiteBot on VPS once)")
            return 0
        return 0
    except Exception as e:
        print(f"⚠️ worker_tick_notify failed: {e}", file=sys.stderr)
        return 0  # non-fatal for worker


if __name__ == "__main__":
    raise SystemExit(main())
