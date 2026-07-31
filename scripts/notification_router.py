#!/usr/bin/env python3
"""Single routing policy for owner notifications.

Only emergencies and explicit owner decisions interrupt immediately. Confirmed
results and routine facts are buffered for the weekly Owner Brief.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from telegram_notify import STATE_DIR
except Exception:
    STATE_DIR = Path(__file__).resolve().parent.parent / "data"

STATE = STATE_DIR / "notification_router.json"
DEDUPE_HOURS = {"emergency": 2, "action": 24, "result": 24, "info": 24}


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"sent": {}}


def _save(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _duplicate(key: str, severity: str) -> bool:
    if not key:
        return False
    state = _load()
    raw = state.get("sent", {}).get(key)
    if not raw:
        return False
    try:
        seen = datetime.fromisoformat(raw)
        return datetime.now(timezone.utc) - seen < timedelta(
            hours=DEDUPE_HOURS.get(severity, 24)
        )
    except Exception:
        return False


def _remember(key: str) -> None:
    if not key:
        return
    state = _load()
    sent = state.setdefault("sent", {})
    sent[key] = datetime.now(timezone.utc).isoformat()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    state["sent"] = {
        k: v for k, v in sent.items()
        if _parse(v) is not None and _parse(v) >= cutoff
    }
    _save(state)


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def emit(
    severity: str,
    category: str,
    text: str,
    *,
    dedupe_key: str = "",
) -> bool:
    if severity not in {"emergency", "action", "result", "info"}:
        raise ValueError(f"unsupported severity: {severity}")
    key = dedupe_key or f"{severity}:{category}:{text[:80]}"
    if _duplicate(key, severity):
        print(f"notification suppressed (duplicate): {key}")
        return False

    if severity == "emergency":
        from telegram_notify import notify_emergency
        sent = notify_emergency(text) > 0
    elif severity == "action":
        from telegram_notify import notify
        sent = notify(f"🆘 <b>Нужно решение</b>\n\n{text}") > 0
    else:
        from daily_ledger import append_event
        append_event("done" if severity == "result" else "info", text)
        sent = True

    if sent:
        _remember(key)
    return sent
