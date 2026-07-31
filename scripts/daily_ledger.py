#!/usr/bin/env python3
"""Owner-Brief event ledger — «signal, not noise» Telegram discipline.

All routine scripts call append_event() instead of notify(). Once per week
flush_digest() assembles a single Telegram message with
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
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
LEDGER_FILE = DATA / "daily_ledger.json"

Category = Literal["done", "info", "needs_help", "emergency"]


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
    # Producers may retry every few hours. Keep one identical event per day.
    today = datetime.now(timezone.utc).date().isoformat()
    if any(
        e.get("cat") == category
        and e.get("txt") == text[:400]
        and str(e.get("ts", "")).startswith(today)
        for e in state["events"]
    ):
        return
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
    elif category == "needs_help":
        try:
            from notification_router import emit
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            emit("action", "owner_decision", text,
                 dedupe_key=f"needs-help:{digest}")
        except Exception as e:
            print(f"⚠️  ledger action notify failed: {e}")


def flush_digest() -> bool:
    """Send one weekly Owner Brief and clear delivered routine events.

    The daily pipeline may call this safely; it sends only if seven days elapsed.

    Returns True if digest was sent, False if already sent today.
    """
    today = date.today().isoformat()
    state = _load()

    last = state.get("last_flush_date")
    if last:
        try:
            if (date.today() - date.fromisoformat(last)).days < 7:
                return False
        except ValueError:
            pass

    events = state.get("events", [])

    done_lines: list[str] = []
    help_lines: list[str] = []

    for ev in events:
        cat = ev.get("cat", "done")
        txt = ev.get("txt", "")
        if cat in ("done", "info"):
            done_lines.append(f"• {txt}")
        elif cat == "needs_help":
            help_lines.append(f"• {txt}")
        # emergency events were already sent immediately — skip in digest

    parts: list[str] = [f"📋 <b>KD Site Brain — недельный Owner Brief</b>", ""]
    try:
        from weekly_sync import build_report
        parts.append(build_report())
        parts.append("")
    except Exception as e:
        print(f"weekly report unavailable: {e}")

    parts.append("📈 <b>Подтверждённые результаты и факты:</b>")
    if done_lines:
        parts.extend(done_lines[:12])
    else:
        parts.append("• Новых подтверждённых результатов нет.")

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

    if sent:
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
