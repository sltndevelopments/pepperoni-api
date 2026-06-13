"""
Планировщик цикла: observe → plan → dispatch.
Opus подключается позже для strategy.tasks; сейчас — rule-based план.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Shared agent bus lives in the repo-root scripts/ dir (used by Fable too).
_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "scripts"))
try:
    import agent_bus  # type: ignore
except Exception:
    agent_bus = None  # type: ignore


def observe(state: dict) -> dict:
    """Снимок состояния контура + входящие задачи с общей шины (от Fable/handoff)."""
    bus_tasks = []
    if agent_bus is not None:
        try:
            bus_tasks = agent_bus.inbox("steve", status="pending")
        except Exception:
            bus_tasks = []
    return {
        "stats": state.get("stats", {}),
        "unprocessed_signals": state.get("unprocessed_signals", []),
        "pending_approvals": state.get("pending_approvals", 0),
        "tier_s_leads_without_draft": state.get("tier_s_no_draft", 0),
        "bus_tasks": bus_tasks,
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

    # Warm leads handed off from Fable/listener via the shared bus take priority:
    # a real commercial lead beats cold prospecting.
    warm = [t for t in observation.get("bus_tasks", [])
            if t.get("type") == "warm_lead_followup"]
    if warm:
        tasks.append({"worker": "handle_warm_leads", "priority": 0,
                      "bus_task_ids": [t["id"] for t in warm]})

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
