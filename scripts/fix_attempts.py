#!/usr/bin/env python3
"""Fix-Attempts SSOT — tracks consecutive repair failures per query/page.

Persisted to data/fix_attempts.json (git-tracked, survives deploys).

Anti-cycle logic:
  • Each failing repair increments the counter for that query.
  • After MAX_FIX_ATTEMPTS consecutive failures the entry is marked abandoned=True.
  • An abandoned entry is NOT re-queued for repair; instead a needs_help event
    is emitted to the owner.
  • Reset back to zero happens on two triggers:
      Trigger A (auto): a new experiment with applied_at > abandon_date appears
                        for the same query (brain chose a fresh approach).
      Trigger B (manual): /unblock <query> Telegram command.

Usage (programmatic):
    from fix_attempts import increment, reset, is_abandoned, abandoned_list
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ATTEMPTS_FILE = DATA / "fix_attempts.json"

MAX_FIX_ATTEMPTS = 2


def _load() -> dict:
    try:
        return json.loads(ATTEMPTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"failed_queries": {}}


def _save(data: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    ATTEMPTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _key(query: str) -> str:
    return query.strip().lower()


def increment(query: str, verdict: str = "", failure_id: str = "") -> dict:
    """Count one distinct failed experiment for a query.

    Re-reading the same outcome is idempotent when ``failure_id`` is supplied.
    """
    data = _load()
    fq = data.setdefault("failed_queries", {})
    k = _key(query)
    entry = fq.get(k, {})
    seen = entry.setdefault("seen_failure_ids", [])
    if failure_id and failure_id in seen:
        return dict(entry)

    entry["attempts"] = entry.get("attempts", 0) + 1
    entry["last_verdict"] = verdict
    entry["last_attempt"] = datetime.now(timezone.utc).isoformat()
    if failure_id:
        seen.append(failure_id)
        entry["seen_failure_ids"] = seen[-20:]

    newly_abandoned = False
    if entry["attempts"] >= MAX_FIX_ATTEMPTS and not entry.get("abandoned"):
        entry["abandoned"] = True
        entry["abandon_date"] = datetime.now(timezone.utc).isoformat()
        entry["abandon_reason"] = (
            f"{MAX_FIX_ATTEMPTS} consecutive failing repairs — needs owner decision"
        )
        newly_abandoned = True

    fq[k] = entry
    _save(data)

    if newly_abandoned:
        msg = (
            f"🔁 Анти-цикл: «{query}» — {MAX_FIX_ATTEMPTS} провала подряд "
            f"(вердикт: {verdict}). Авторемонт ОСТАНОВЛЕН.\n"
            f"Возможные причины: технический блок, неверный интент страницы, "
            f"конкурент с принципиально лучшим контентом. "
            f"Сброс: /unblock {query.strip()}"
        )
        try:
            from daily_ledger import append_event
            append_event("needs_help", msg)
        except Exception as e:
            print(f"⚠️  daily_ledger unavailable: {e}")

    return dict(entry)


def reset(query: str, reason: str = "") -> None:
    """Reset (unblock) an entry — removes it so next failure starts fresh."""
    data = _load()
    fq = data.get("failed_queries", {})
    k = _key(query)
    removed = fq.pop(k, None)
    _save(data)
    if removed:
        msg = f"✅ Анти-цикл сброшен: «{query}»{' — ' + reason if reason else ''}"
        print(msg)
        try:
            from daily_ledger import append_event
            append_event("done", msg)
        except Exception:
            pass


def is_abandoned(query: str) -> bool:
    """Return True if this query has been abandoned after repeated failures."""
    data = _load()
    entry = data.get("failed_queries", {}).get(_key(query), {})
    return bool(entry.get("abandoned"))


def abandoned_list() -> list[dict]:
    """Return all currently abandoned queries."""
    data = _load()
    out = []
    for q, entry in data.get("failed_queries", {}).items():
        if entry.get("abandoned"):
            out.append({"query": q, **entry})
    return out


def mark_low_priority(query: str, reason: str = "no_search_demand") -> None:
    """Mark a query as low_priority — brain will not touch it in autonomous mode.

    Use for queries with no realistic search demand (wrong language, misspelling,
    overly specific long-tail with zero GSC impressions over 60+ days).

    Unlike abandon (3-failure anti-cycle), low_priority is a deliberate owner
    decision — it does NOT emit needs_help and is NOT reset by Trigger A/B.
    Removal requires explicit fix_attempts.reset() call.
    """
    data = _load()
    fq = data.setdefault("failed_queries", {})
    k = _key(query)
    entry = fq.get(k, {})
    entry["status"] = "low_priority"
    entry["low_priority_reason"] = reason
    entry["low_priority_at"] = datetime.now(timezone.utc).isoformat()
    # Ensure it's also flagged abandoned so is_abandoned() returns True (skip in repair)
    entry["abandoned"] = True
    entry["abandon_reason"] = f"low_priority: {reason}"
    fq[k] = entry
    _save(data)
    msg = f"⏭ low_priority: «{query}» — {reason} (не будет в авторемонте)"
    print(msg)
    try:
        from daily_ledger import append_event
        append_event("done", msg)
    except Exception:
        pass


def is_low_priority(query: str) -> bool:
    """Return True if this query is explicitly marked as low_priority."""
    data = _load()
    entry = data.get("failed_queries", {}).get(_key(query), {})
    return entry.get("status") == "low_priority"


def check_trigger_a(query: str) -> bool:
    """Trigger A: auto-reset if a newer experiment exists for this query.

    Call from repair_outcomes after discovering a new experiment entry.
    Returns True if the entry was reset.
    Low_priority entries are immune to Trigger A — they require explicit /unblock.
    """
    if not is_abandoned(query):
        return False
    if is_low_priority(query):
        return False  # low_priority is owner decision, not auto-resettable
    data = _load()
    k = _key(query)
    entry = data.get("failed_queries", {}).get(k, {})
    abandon_date = entry.get("abandon_date", "")
    if not abandon_date:
        return False

    # Check experiments.json for a newer entry under this query
    try:
        experiments = json.loads(
            (DATA / "experiments.json").read_text(encoding="utf-8")
        )
        for exp in experiments:
            if _key(exp.get("query", "")) == k:
                applied_at = exp.get("applied_at", "")
                if applied_at and applied_at > abandon_date:
                    reset(query, reason="new experiment detected (Trigger A)")
                    return True
    except Exception:
        pass
    return False
