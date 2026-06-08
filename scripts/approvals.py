#!/usr/bin/env python3
"""
Shared approval queue for high-impact agent actions (human-in-the-loop).

Any agent can request approval for a risky action (deleting pages, removing a
section, large structural changes). The action is queued in a git-tracked file
(data/approvals.json) and surfaced in Telegram ("✅ Аппрувы"), where the owner
approves/rejects. On its next run the requesting agent calls take_approved() to
execute only what was explicitly approved.

Status lifecycle: pending → approved | rejected → done (after execution).

Idempotency: each request has a stable `key`; requesting the same key twice does
not create duplicates while one is still pending/approved.
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
    """Queue an action for approval. Returns True if newly created."""
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
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(rows)
    return True


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


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "request":
        created = request(key=sys.argv[2], title=" ".join(sys.argv[3:]) or sys.argv[2])
        print("created" if created else "already-queued")
    else:
        for a in _load():
            print(f"[{a['status']}] {a.get('key')}: {a.get('title')}")
