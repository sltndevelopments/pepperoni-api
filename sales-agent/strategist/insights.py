"""Слой 5: Стив-стратег — мозг зама по продажам.

Раз в цикл (или по кнопке) Стив читает воронку, думает голосом своей личности с
учётом памяти (принципы/решения/OKR/факты) и выдаёт СТРУКТУРИРОВАННУЮ стратегию:
куда бить, что записать в память, какие аналитические инструменты себе построить.
Результат сохраняется в data/steve_strategy.json — его подхватывает toolsmith.

Бюджет: думает только пока у Стива остался его месячный лимит ($20). Исчерпан →
стратег молчит (kill switch), остальной цикл (аутрич/входящие/bounce) работает.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import budget as steve_budget
from core import memory
from core.llm import brain_available, call_opus
from core.store import Store
from kb.loader import KnowledgeBase

STRATEGY_FILE = ROOT / "data" / "steve_strategy.json"

STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "focus": {"type": "string"},
        "attack_plan": {"type": "array", "items": {"type": "string"}},
        "report_to_owner": {"type": "string"},
        "memory_ops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "update", "remove"]},
                    "section": {"type": "string",
                                "enum": ["principles", "decisions", "okr", "facts"]},
                    "text": {"type": "string"},
                    "objective": {"type": "string"},
                    "why": {"type": "string"},
                    "id": {"type": "string"},
                },
                "required": ["action", "section"],
            },
        },
        "propose_tools": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "spec": {"type": "string"},
                    "model": {"type": "string", "enum": ["haiku", "sonnet", "opus"]},
                    "version": {"type": "integer"},
                },
                "required": ["name", "purpose"],
            },
        },
        "run_tools": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["focus", "attack_plan", "report_to_owner"],
}


def _funnel(store: Store) -> dict:
    leads = store.list_leads(limit=500)
    by_status = Counter((l.get("status") or "new") for l in leads)
    by_tier = Counter((l.get("tier") or "—") for l in leads)
    tier_s_region = Counter(l.get("region") or "?" for l in leads if l.get("tier") == "S")
    return {
        "total_leads": len(leads),
        "by_status": dict(by_status),
        "by_tier": dict(by_tier),
        "tier_s_by_region": tier_s_region.most_common(5),
        "stats": store.stats(),
    }


def think(*, store: Store | None = None) -> dict:
    """Полный стратег-цикл Стива со структурированным выводом."""
    store = store or Store()

    if not brain_available():
        return {"skipped": "llm_unavailable"}
    if not steve_budget.brain_allowed():
        return {"skipped": "steve_budget_exhausted",
                "budget": steve_budget.summary()}

    kb = KnowledgeBase()
    funnel = _funnel(store)
    try:
        from brain.toolsmith import _registry
        toolbox = list((_registry().get("tools") or {}).keys())
    except Exception:
        toolbox = []

    from core.persona import block as persona_block
    system = (
        persona_block()
        + "\n\nТы выдаёшь стратегию СТРОГО как JSON по схеме. В report_to_owner — "
        "1–3 коротких человеческих абзаца голосом Стива (что с воронкой и деньгами "
        "и что делаешь). В memory_ops — что записать/обновить в памяти (новые "
        "принципы, решения, факты, корректировка OKR). В propose_tools — какие "
        "аналитические инструменты тебе построить в своей песочнице (только чтение "
        "данных продаж). В run_tools — какие уже готовые инструменты прогнать.\n\n"
        + kb.context_for_prompt(10)
    )
    prompt = (
        f"Воронка сейчас: {json.dumps(funnel, ensure_ascii=False)}\n"
        f"Мои инструменты: {toolbox}\n\n"
        "Дай стратегию на ближайшие 2 недели как зам по продажам: фокус, план "
        "атаки (кого и как брать, как наполнять базу нужными ЛПР), что записать в "
        "память, какие инструменты построить/прогнать."
    )

    try:
        raw, usage = call_opus(prompt, system=system, max_tokens=2500,
                               effort="medium", json_schema=STRATEGY_SCHEMA)
        strat = json.loads(raw) if raw.strip().startswith("{") else {}
    except Exception as e:
        return {"error": str(e)[:200]}

    # применить операции с памятью
    mem_results = []
    try:
        mem_results = memory.apply_ops(strat.get("memory_ops") or [])
    except Exception as e:
        mem_results = [f"memory_error: {str(e)[:120]}"]

    # сохранить стратегию для toolsmith
    try:
        STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)
        STRATEGY_FILE.write_text(json.dumps(strat, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    except Exception:
        pass

    store.add_signal("strategist", "steve_plan", {
        "focus": strat.get("focus"),
        "report": (strat.get("report_to_owner") or "")[:2000],
    })

    return {
        "focus": strat.get("focus"),
        "attack_plan": strat.get("attack_plan", []),
        "report_to_owner": strat.get("report_to_owner", ""),
        "memory_ops": mem_results,
        "propose_tools": [t.get("name") for t in (strat.get("propose_tools") or [])],
        "run_tools": strat.get("run_tools", []),
        "cost_usd": usage.get("cost_usd"),
        "budget": steve_budget.summary(),
    }


def cluster_demand(store: Store | None = None, *, use_opus: bool = True) -> dict:
    """Обратная совместимость: лёгкий кластерный взгляд без полного цикла."""
    store = store or Store()
    leads = store.list_leads(limit=500)
    regions = Counter(l.get("region") or "?" for l in leads if l.get("tier") == "S")
    top = regions.most_common(5)
    insight: dict = {"tier_s_by_region": top, "recommendation": None}
    if top and top[0][1] >= 3:
        insight["recommendation"] = (
            f"Кластер спроса: {top[0][0]} — {top[0][1]} Tier S лидов."
        )
    store.add_signal("strategist", "cluster_insight", insight)
    return insight
