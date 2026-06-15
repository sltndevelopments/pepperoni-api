#!/usr/bin/env python3
"""
Shared action queue for high-impact agent actions.

Two modes coexist:

  FULL AUTONOMY (default) — request() auto-approves at creation. Used for
  edits to existing pages (title rewrites, schema fixes, link repairs, etc.).
  Telegram gets an informational ping, not a question.

  NEW-PAGE GATE — request_new_page() puts the action in "pending" and sends a
  Telegram message asking the owner to approve via /approve <key> or reject
  via /reject <key>. Used ONLY when a new SEO page is about to be created by
  the brain. Other agents (sales-agent uses its own SQLite store) are NOT
  affected.

  NEW_PAGE_ACTIONS — the exact action strings that trigger the gate. Everything
  else stays auto-approved.

Status lifecycle:
  pending  → approved (owner types /approve) or rejected (/reject)
  approved → done (after execution by a generator)
  approved (auto) → done (auto-approved actions, no human step)

Idempotency: request_new_page() returns the *current* status for an existing
key, so generators can always check the latest state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
APPROVALS_FILE = DATA / "approvals.json"

# Actions that require owner approval before a new page is written to disk.
# Everything NOT in this set stays auto-approved (existing-page edits, sales-agent, etc.)
NEW_PAGE_ACTIONS = frozenset({
    "create_landing",
    "geo_page",
    "blog_post",
    "pl_page",
    "new_page",
})


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


def get_status(key: str) -> str | None:
    """Return the current status of an approval entry, or None if not found."""
    for a in _load():
        if a.get("key") == key:
            return a.get("status")
    return None


def request_new_page(key: str, title: str, detail: str = "", action: str = "",
                     payload: dict | None = None,
                     requested_by: str = "agent") -> str:
    """Queue a NEW-PAGE creation for owner approval.

    Returns the current status string so the caller can decide immediately:
      "approved"  — already approved, go build it
      "pending"   — waiting for owner answer, skip this run
      "rejected"  — owner said no, skip permanently
      "queued"    — just created as pending, Telegram question sent

    Idempotent: calling again for an existing key never duplicates the entry.
    """
    rows = _load()
    for a in rows:
        if a.get("key") == key:
            return a.get("status", "pending")  # return current state, no dup

    rows.append({
        "key": key,
        "title": title,
        "detail": detail,
        "action": action,
        "payload": payload or {},
        "risk": "medium",
        "requested_by": requested_by,
        "status": "pending",
        "auto_approved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(rows)
    _notify_pending_page(key, title, detail, requested_by)
    return "queued"


def approve(key: str) -> bool:
    """Flip a pending entry to approved. Returns True if found and changed."""
    rows = _load()
    for a in rows:
        if a.get("key") == key and a.get("status") == "pending":
            a["status"] = "approved"
            a["decided_at"] = datetime.now(timezone.utc).isoformat()
            _save(rows)
            return True
    return False


def reject(key: str) -> bool:
    """Flip a pending entry to rejected. Returns True if found and changed."""
    rows = _load()
    for a in rows:
        if a.get("key") == key and a.get("status") == "pending":
            a["status"] = "rejected"
            a["decided_at"] = datetime.now(timezone.utc).isoformat()
            _save(rows)
            return True
    return False


def get_approved_new_pages(action: str | None = None) -> list:
    """Return approved new-page entries (optionally filtered by action) and mark done.

    Mirrors take_approved() but restricted to NEW_PAGE_ACTIONS entries that went
    through the human-approval gate (auto_approved=False).
    """
    rows = _load()
    out = []
    changed = False
    for a in rows:
        if a.get("status") != "approved":
            continue
        if a.get("auto_approved"):
            continue  # skip auto-approved edits — handled by take_approved()
        if action is not None and a.get("action") != action:
            continue
        out.append(dict(a))
        a["status"] = "done"
        a["executed_at"] = datetime.now(timezone.utc).isoformat()
        changed = True
    if changed:
        _save(rows)
    return out


def _notify_pending_page(key: str, title: str, detail: str, requested_by: str) -> None:
    """Ask the owner to approve a new page via Telegram."""
    try:
        from telegram_notify import notify
    except Exception:
        return
    text = (
        f"<b>📋 Новая страница ждёт одобрения</b>\n"
        f"{title}\n"
        f"<i>{detail[:300]}</i>\n\n"
        f"Инициатор: {requested_by}\n\n"
        f"✅ Одобрить: <code>/approve {key}</code>\n"
        f"❌ Отклонить: <code>/reject {key}</code>"
    )
    notify(text)


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
    elif len(sys.argv) >= 3 and sys.argv[1] == "approve":
        print("approved" if approve(sys.argv[2]) else "not-found-or-not-pending")
    elif len(sys.argv) >= 3 and sys.argv[1] == "reject":
        print("rejected" if reject(sys.argv[2]) else "not-found-or-not-pending")
    else:
        for a in _load():
            print(f"[{a['status']}] {a.get('key')}: {a.get('title')}")
