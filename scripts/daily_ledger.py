#!/usr/bin/env python3
"""Daily event ledger — «signal, not noise» Telegram discipline.

All routine scripts call append_event() instead of notify(). Once per day
(first pipeline run) flush_digest() assembles a single Telegram message with
two sections:

  ✅ Done autonomously — numbers of pages built, links fixed, schema patched, etc.
  🆘 Needs attention — stuck tasks, brain questions, strategic decisions.

Emergencies (deploy failure, reviewer down, brand violation) bypass the ledger
and call notify_emergency() for immediate delivery.

Storage: data/daily_ledger.json  (git-tracked so brain sees it in digest)
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
LEDGER_FILE = DATA / "daily_ledger.json"

Category = Literal["done", "needs_help", "emergency"]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"events": [], "last_flush_date": ""}


def _save(state: dict) -> None:
    DATA.mkdir(exist_ok=True)
    LEDGER_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def append_event(category: Category, text: str) -> None:
    """Buffer a routine event. category='done'|'needs_help'|'emergency'.

    emergency events are ALSO sent immediately via notify_emergency().
    """
    state = _load()
    state.setdefault("events", [])
    state["events"].append({
        "ts":  datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cat": category,
        "txt": text[:400],
    })
    _save(state)
    if category == "emergency":
        try:
            from telegram_notify import notify_emergency
            notify_emergency(text)
        except Exception as e:
            print(f"⚠️  ledger emergency notify failed: {e}")


def flush_digest() -> bool:
    """Send the daily digest and clear the ledger.

    Guard: only fires ONCE per calendar day (UTC).  Every subsequent call on
    the same day returns False without sending.  This means the 3-hourly cron
    just calls flush_digest() unconditionally — the first run sends, the rest
    are silent no-ops.

    Returns True if digest was sent, False if already sent today.
    """
    today = date.today().isoformat()
    state = _load()

    if state.get("last_flush_date") == today:
        return False  # already flushed today

    events = state.get("events", [])

    done_lines: list[str] = []
    help_lines: list[str] = []

    for ev in events:
        cat = ev.get("cat", "done")
        txt = ev.get("txt", "")
        if cat == "done":
            done_lines.append(f"• {txt}")
        elif cat == "needs_help":
            help_lines.append(f"• {txt}")
        # emergency events were already sent immediately — skip in digest

    parts: list[str] = [f"📋 <b>Fable — дайджест {today}</b>", ""]

    parts.append("✅ <b>Сделано автономно:</b>")
    if done_lines:
        parts.extend(done_lines[:30])  # cap display at 30 lines
    else:
        parts.append("• Активности не было.")

    parts.append("")
    parts.append("🆘 <b>Нужна помощь / решение:</b>")
    if help_lines:
        parts.extend(help_lines[:15])
    else:
        parts.append("• Решений не требуется.")

    msg = "\n".join(parts)

    try:
        from telegram_notify import notify
        notify(msg)
        sent = True
    except Exception as e:
        print(f"⚠️  flush_digest send failed: {e}")
        sent = False

    # Clear events, record flush date regardless of send success
    # (avoids repeated spam if notify is temporarily broken)
    state["events"] = []
    state["last_flush_date"] = today
    _save(state)
    return sent


def get_pending() -> dict:
    """Return ledger state for brain digest (read-only snapshot)."""
    state = _load()
    events = state.get("events", [])
    done   = [e["txt"] for e in events if e.get("cat") == "done"]
    help_  = [e["txt"] for e in events if e.get("cat") == "needs_help"]
    emerg  = [e["txt"] for e in events if e.get("cat") == "emergency"]
    return {
        "last_flush": state.get("last_flush_date", "never"),
        "pending_done":       len(done),
        "pending_needs_help": len(help_),
        "pending_emergency":  len(emerg),
        "sample_needs_help":  help_[:3],
    }


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "flush":
        sent = flush_digest()
        print("sent" if sent else "already_flushed_today")
    elif cmd == "status":
        print(json.dumps(get_pending(), ensure_ascii=False, indent=2))
    elif cmd == "test":
        append_event("done", "тест: построено 5 страниц")
        append_event("needs_help", "тест: застряла задача strengthen_landing/kz-001")
        print("test events appended — run with 'flush' to send")
