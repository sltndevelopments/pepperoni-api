#!/usr/bin/env python3
"""Agent Bus — the shared "nervous system" of the multi-agent company.

A single git-tracked JSON ledger (data/agent_bus.json) that ALL agents read and
write: Fable (strategy/SEO brain), Steve (sales/SDR), and the workers. It is the
one place where one agent hands a task to another (Orchestrator-Worker handoff)
and where escalations and statuses live (Observability).

Deliberately NOT LangGraph: for 3-7 agents a typed JSON bus with explicit fields
is simpler, cheaper, fully transparent, and trivially debuggable — which is what
Fable approved for this small/mid B2B case.

Task lifecycle:
  pending → in_progress → done
                       ↘ escalated (needs owner)  ↘ failed

Schema (data/agent_bus.json):
{
  "tasks": [{
     "id","from","to","type","payload",
     "status","trigger","note",
     "created_at","updated_at","claimed_by"
  }],
  "seq": <int>,            # monotonic id counter
  "updated_at": "..."
}

Both repos import this module. Fable runs from scripts/ (sys.path includes it);
Steve adds REPO_ROOT/scripts to sys.path (see sales-agent integration).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUS = DATA / "agent_bus.json"

VALID_STATUS = {"pending", "in_progress", "done", "escalated", "failed"}
# How long a non-terminal task may sit before it is considered "stuck".
STUCK_HOURS = float(os.environ.get("BUS_STUCK_HOURS", "24"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    try:
        d = json.loads(BUS.read_text())
    except Exception:
        d = {}
    d.setdefault("tasks", [])
    d.setdefault("seq", 0)
    return d


def _save(d: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    d["updated_at"] = _now()
    BUS.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def post(frm: str, to: str, type_: str, payload: dict | None = None,
         trigger: str = "", note: str = "", dedup_key: str | None = None) -> str:
    """Create a task from one agent to another. Returns task id.

    dedup_key: if given, an existing OPEN (pending/in_progress) task with the
    same (to, type, dedup_key) is not duplicated — returns its id instead.
    """
    d = _load()
    if dedup_key is not None:
        for t in d["tasks"]:
            if (t.get("to") == to and t.get("type") == type_
                    and t.get("payload", {}).get("_dedup") == dedup_key
                    and t.get("status") in ("pending", "in_progress")):
                return t["id"]
    d["seq"] += 1
    tid = f"t-{datetime.now(timezone.utc):%Y%m%d}-{d['seq']:04d}"
    payload = dict(payload or {})
    if dedup_key is not None:
        payload["_dedup"] = dedup_key
    d["tasks"].append({
        "id": tid, "from": frm, "to": to, "type": type_,
        "payload": payload, "status": "pending", "trigger": trigger,
        "note": note, "created_at": _now(), "updated_at": _now(),
        "claimed_by": None,
    })
    _save(d)
    return tid


def inbox(agent: str, status: str = "pending") -> list:
    """Tasks addressed TO `agent` with the given status (open work)."""
    d = _load()
    return [t for t in d["tasks"]
            if t.get("to") == agent and t.get("status") == status]


def claim(task_id: str, agent: str) -> bool:
    d = _load()
    for t in d["tasks"]:
        if t["id"] == task_id and t.get("status") == "pending":
            t["status"] = "in_progress"
            t["claimed_by"] = agent
            t["updated_at"] = _now()
            _save(d)
            return True
    return False


def update(task_id: str, status: str, note: str = "") -> bool:
    if status not in VALID_STATUS:
        raise ValueError(f"bad status {status!r}")
    d = _load()
    for t in d["tasks"]:
        if t["id"] == task_id:
            t["status"] = status
            if note:
                t["note"] = note
            t["updated_at"] = _now()
            _save(d)
            return True
    return False


def stuck(hours: float | None = None) -> list:
    """Non-terminal tasks older than `hours` — candidates for escalation."""
    hours = STUCK_HOURS if hours is None else hours
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    out = []
    for t in _load()["tasks"]:
        if t.get("status") in ("pending", "in_progress"):
            try:
                ts = datetime.fromisoformat(t["updated_at"]).timestamp()
            except Exception:
                continue
            if ts < cutoff:
                out.append(t)
    return out


def digest(agent: str | None = None) -> dict:
    """Compact view for an agent's prompt: open work + recent flow + health."""
    d = _load()
    tasks = d["tasks"]
    open_for = [
        {"id": t["id"], "from": t["from"], "type": t["type"],
         "status": t["status"], "note": (t.get("note") or "")[:120],
         "payload": {k: v for k, v in t.get("payload", {}).items() if k != "_dedup"}}
        for t in tasks
        if (agent is None or t.get("to") == agent)
        and t.get("status") in ("pending", "in_progress")
    ][-15:]
    by_status: dict = {}
    for t in tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    return {
        "open_for_me": open_for,
        "by_status": by_status,
        "stuck_count": len(stuck()),
        "total": len(tasks),
    }


def escalate_stuck(hours: float | None = None) -> dict:
    """Find stuck tasks, mark them escalated, and alert the owner in Telegram.

    Observability + escalation rules: a task that sits pending/in_progress past
    the threshold is surfaced to the human instead of silently rotting. Each
    task is escalated only once (status flips to 'escalated').
    """
    items = stuck(hours)
    if not items:
        return {"escalated": 0}
    d = _load()
    lines = ["⚠️ <b>Зависшие задачи в шине агентов</b>",
             "<i>Не двигаются дольше нормы — нужно решение.</i>", ""]
    n = 0
    for s in items:
        for t in d["tasks"]:
            if t["id"] == s["id"] and t["status"] != "escalated":
                t["status"] = "escalated"
                t["updated_at"] = _now()
                n += 1
                lines.append(f"• <b>{t['from']}→{t['to']}</b> {t['type']} "
                             f"({t['id']})\n  {(t.get('note') or '')[:120]}")
    if n:
        _save(d)
        try:
            sys_path_inserted = str(ROOT / "scripts")
            import sys as _sys
            if sys_path_inserted not in _sys.path:
                _sys.path.insert(0, sys_path_inserted)
            from telegram_notify import notify
            notify("\n".join(lines))
        except Exception:
            pass
    return {"escalated": n}


def gc(keep_done_days: int = 14) -> int:
    """Drop terminal tasks older than N days to keep the bus small."""
    cutoff = datetime.now(timezone.utc).timestamp() - keep_done_days * 86400
    d = _load()
    before = len(d["tasks"])
    kept = []
    for t in d["tasks"]:
        if t.get("status") in ("done", "failed"):
            try:
                if datetime.fromisoformat(t["updated_at"]).timestamp() < cutoff:
                    continue
            except Exception:
                pass
        kept.append(t)
    d["tasks"] = kept
    _save(d)
    return before - len(kept)


def main() -> int:
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--gc":
        print(f"gc removed {gc()} task(s)")
    elif args and args[0] == "--escalate":
        print(f"escalated {escalate_stuck()['escalated']} stuck task(s)")
    elif args and args[0] == "--stuck":
        for t in stuck():
            print(f"STUCK {t['id']} {t['from']}→{t['to']} {t['type']} ({t['status']})")
    else:
        print(json.dumps(digest(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
