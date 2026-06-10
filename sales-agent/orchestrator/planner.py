"""
Планировщик цикла: observe → plan → dispatch.
Opus подключается позже для strategy.tasks; сейчас — rule-based план.
"""
from __future__ import annotations

from typing import Any


def observe(state: dict) -> dict:
    """Снимок состояния контура."""
    return {
        "stats": state.get("stats", {}),
        "unprocessed_signals": state.get("unprocessed_signals", []),
        "pending_approvals": state.get("pending_approvals", 0),
        "tier_s_leads_without_draft": state.get("tier_s_no_draft", 0),
    }


def plan(observation: dict, *, max_drafts: int = 5) -> list[dict]:
    """Список задач для воркеров."""
    tasks: list[dict] = []
    stats = observation.get("stats", {})

    if stats.get("unprocessed_signals", 0) > 0:
        tasks.append({"worker": "process_signals", "priority": 1})

    if stats.get("inbox_messages", 0) > 0:
        tasks.append({"worker": "scan_interest", "priority": 1})

    if observation.get("tier_s_leads_without_draft", 0) > 0:
        n = min(max_drafts, observation["tier_s_leads_without_draft"])
        tasks.append({"worker": "draft_outreach", "count": n, "priority": 2})

    # Периодически — заглушка тендеров
    tasks.append({"worker": "tender_scan_stub", "priority": 10})

    tasks.sort(key=lambda t: t.get("priority", 99))
    return tasks


def reflect(plan: list[dict], results: list[dict]) -> dict:
    return {
        "tasks_planned": len(plan),
        "tasks_done": len(results),
        "results": results,
    }
