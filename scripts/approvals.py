#!/usr/bin/env python3
"""
Shared action queue for high-impact agent actions — FULL AUTONOMY MODE.

Historically this was a human-in-the-loop approval queue. The owner granted the
Brain (Claude Fable) full trust, so every request is now AUTO-APPROVED at
creation: agents queue an action, the next pipeline pass executes it via
take_approved(). The git-tracked file (data/approvals.json) remains as an
audit trail, and Telegram gets an informational "decided & scheduled" ping
instead of an approval ask.

Status lifecycle: approved → done (after execution).  ("pending"/"rejected"
remain readable for old entries.)

Idempotency: each request has a stable `key`; requesting the same key twice does
not create duplicates while one is still approved-but-unexecuted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
APPROVALS_FILE = DATA / "approvals.json"


def _load() -> list:
    try:
        return json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(rows: list) -> None:
    DATA.mkdir(exist_ok=True)
    APPROVALS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def request(key: str, title: str, detail: str = "", action: str = "",
            payload: dict | None = None, risk: str = "high",
            requested_by: str = "agent") -> bool:
    """Queue an action — AUTO-APPROVED (full-autonomy mode). Returns True if new."""
    rows = _load()
    for a in rows:
        if a.get("key") == key and a.get("status") in ("pending", "approved"):
            return False  # already queued / waiting to execute
    rows.append({
        "key": key,
        "title": title,
        "detail": detail,
        "action": action,
        "payload": payload or {},
        "risk": risk,
        "requested_by": requested_by,
        "status": "approved",
        "auto_approved": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(rows)
    _notify_auto_decision(title, detail, risk, requested_by)
    return True


def auto_approve_pending() -> int:
    """One-time migration: flip any legacy 'pending' entries to 'approved'."""
    rows = _load()
    n = 0
    for a in rows:
        if a.get("status") == "pending":
            a["status"] = "approved"
            a["auto_approved"] = True
            n += 1
    if n:
        _save(rows)
    return n


def _notify_auto_decision(title: str, detail: str, risk: str, requested_by: str) -> None:
    """Informational ping: the system decided and will execute on the next pass."""
    try:
        from telegram_notify import notify
    except Exception:
        return
    text = (
        f"<b>🤖 Fable решил</b> [{risk}]\n"
        f"{title}\n"
        f"<i>{detail[:300]}</i>\n\n"
        f"Инициатор: {requested_by}. Выполнится автоматически в ближайший цикл."
    )
    notify(text)


def take_approved(action: str | None = None) -> list:
    """Return approved items (optionally filtered by action) and mark them done.

    The caller is responsible for actually performing the work; this just hands
    over the approved payloads exactly once and flips their status to 'done'."""
    rows = _load()
    out = []
    changed = False
    for a in rows:
        if a.get("status") == "approved" and (action is None or a.get("action") == action):
            out.append(dict(a))
            a["status"] = "done"
            a["executed_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
    if changed:
        _save(rows)
    return out


def pending() -> list:
    return [a for a in _load() if a.get("status") == "pending"]


def notify_pending() -> int:
    """Full-autonomy mode: flip legacy pendings to approved, no asks sent."""
    n = auto_approve_pending()
    print(f"auto-approved {n} legacy pending item(s); approvals are autonomous now")
    return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "notify":
        print(f"notified {notify_pending()} batch(es)")
    elif len(sys.argv) >= 3 and sys.argv[1] == "request":
        created = request(key=sys.argv[2], title=" ".join(sys.argv[3:]) or sys.argv[2])
        print("created" if created else "already-queued")
    else:
        for a in _load():
            print(f"[{a['status']}] {a.get('key')}: {a.get('title')}")
