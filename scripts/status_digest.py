#!/usr/bin/env python3
"""Daily status digest → Telegram (@KDSEOSiteBot via telegram_notify.notify).

Collects REAL numbers from repo/VPS files — never invented stats.
Separate from daily_ledger.flush_digest() (routine events) and notify_emergency().

Usage:
    python3 scripts/status_digest.py --dry-run
    python3 scripts/status_digest.py --send          # one-shot test
    python3 scripts/status_digest.py --daily         # send at most once/calendar day UTC
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
QUARANTINE = DATA / "quarantine"
NEXT_TASK = ROOT / "instructions" / "next-task.md"
STATE_FILE = DATA / "status_digest_last.json"

sys.path.insert(0, str(ROOT / "scripts"))


def _count_geo_pages() -> int:
    n = 0
    for p in PUBLIC.rglob("geo"):
        if p.is_dir():
            n += len(list(p.glob("*.html")))
    return n


def _quarantine_snapshot() -> dict:
    """Live queue vs historical rejects — never conflate the two."""
    try:
        from quarantine_report import build_report, summary_line
        report = build_report()
        return {
            "current": report["current_files"],
            "historical_rejects": report["historical_reject_hold_events"],
            "unique_paths": report["unique_rejected_paths"],
            "summary": summary_line(report),
        }
    except Exception:
        try:
            current = len(list(QUARANTINE.rglob("*.html")))
        except Exception:
            current = 0
        return {
            "current": current,
            "historical_rejects": 0,
            "unique_paths": 0,
            "summary": f"карантин сейчас {current}",
        }


def _gate_period(hours: int = 24) -> dict:
    try:
        import page_reviewer
        log_path = page_reviewer.GATE_LOG
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:
        return {"pass": 0, "reject": 0, "hold": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    tick = [
        e for e in log
        if e.get("ts", "") >= cutoff and "tmp" not in e.get("path", "")
    ]
    return {
        "pass": sum(1 for e in tick if e.get("verdict") == "pass"),
        "reject": sum(1 for e in tick if e.get("verdict") == "reject"),
        "hold": sum(1 for e in tick if e.get("verdict") == "hold"),
    }


def _budget_today() -> tuple[float, float]:
    try:
        from claude_client import today_spend_usd, LLM_DAILY_BUDGET_USD
        return today_spend_usd(), float(LLM_DAILY_BUDGET_USD)
    except Exception:
        return 0.0, 5.0


def _outcomes_summary() -> dict:
    try:
        d = json.loads((DATA / "outcomes.json").read_text(encoding="utf-8"))
        return d.get("summary") or {}
    except Exception:
        return {}


def _last_commit() -> tuple[str, str]:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%h %s"],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        line = (r.stdout or "").strip()
        if not line:
            return "?", "?"
        parts = line.split(" ", 1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    except Exception:
        return "?", "?"


def _owner_waiting() -> list[str]:
    if not NEXT_TASK.exists():
        return []
    text = NEXT_TASK.read_text(encoding="utf-8")
    items: list[str] = []
    for line in text.splitlines():
        if "ЖДУТ ВЛАДЕЛЬЦА" in line.upper() or "ждёт владельца" in line.lower():
            items.append(line.strip().lstrip("- ").lstrip("0123456789. "))
    return items[:5]


def _ledger_pending() -> dict:
    try:
        import daily_ledger
        return daily_ledger.get_pending()
    except Exception:
        return {}


def _bot_info() -> str:
    import os
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return "TELEGRAM_BOT_TOKEN не задан"
    try:
        import urllib.request
        from telegram_notify import open_telegram_url, API
        req = urllib.request.Request(f"{API}/getMe")
        with open_telegram_url(req, 20) as r:
            d = json.loads(r.read())
        if d.get("ok"):
            return "@" + d.get("result", {}).get("username", "?")
    except Exception as e:
        return f"getMe failed: {e}"
    return "?"


def build_digest() -> str:
    today = date.today().isoformat()
    geo_total = _count_geo_pages()
    q = _quarantine_snapshot()
    gate = _gate_period(24)
    spent, cap = _budget_today()
    outcomes = _outcomes_summary()
    commit_hash, commit_msg = _last_commit()
    waiting = _owner_waiting()
    pending = _ledger_pending()

    lines = [
        f"📊 <b>Статус pepperoni.tatar</b> · {today}",
        "",
        f"🌍 GEO опубликовано: <b>{geo_total}</b> стр.",
        f"📦 Карантин сейчас: <b>{q['current']}</b> "
        f"(reject за период {q['historical_rejects']}, "
        f"уник. {q['unique_paths']})",
        f"🚦 Гейт 24ч: ✅{gate['pass']} / 🚧{gate['reject']} / ⏸{gate['hold']}",
        f"💰 LLM сегодня: <b>${spent:.2f}</b> / ${cap:.0f}",
    ]

    if outcomes:
        lines.append(
            f"📈 Исходы: ↑{outcomes.get('improved', 0)} "
            f"→{outcomes.get('flat', 0)} ↓{outcomes.get('worse', 0)} "
            f"⏳{outcomes.get('pending', 0)}"
        )

    lines.extend([
        "",
        f"🔧 Последний коммит: <code>{commit_hash}</code> {commit_msg[:80]}",
    ])

    if pending.get("pending_needs_help"):
        lines.append(
            f"🆘 В ledger (needs_help): {pending['pending_needs_help']}"
        )

    if waiting:
        lines.append("")
        lines.append("👤 <b>Ждёт владельца:</b>")
        for w in waiting:
            lines.append(f"• {w[:120]}")

    lines.append("")
    lines.append("<i>Автономный дайджест · @KDSEOSiteBot</i>")
    return "\n".join(lines)


def _already_sent_today() -> bool:
    try:
        st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return st.get("last_sent_date") == date.today().isoformat()
    except Exception:
        return False


def _mark_sent() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"last_sent_date": date.today().isoformat(),
                    "sent_at": datetime.now(timezone.utc).isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_digest(*, force: bool = False) -> int:
    if not force and _already_sent_today():
        print("already sent today — skip")
        return 0
    from telegram_notify import notify
    n = notify(build_digest())
    if n > 0:
        _mark_sent()
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Status digest → Telegram")
    ap.add_argument("--dry-run", action="store_true", help="Print digest, do not send")
    ap.add_argument("--send", action="store_true", help="Send once (test)")
    ap.add_argument("--daily", action="store_true", help="Send if not yet sent today")
    ap.add_argument("--verify-bot", action="store_true", help="Print bot username from getMe")
    args = ap.parse_args()

    if args.verify_bot:
        print("bot:", _bot_info())
        return 0

    msg = build_digest()
    if args.dry_run:
        print(msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", ""))
        return 0

    if args.send:
        n = send_digest(force=True)
        print(f"sent to {n} chat(s)")
        return 0 if n > 0 else 1

    if args.daily:
        n = send_digest(force=False)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
