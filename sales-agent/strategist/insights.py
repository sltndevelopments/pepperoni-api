"""Слой 5: проактивный стратег — кластеры спроса (Opus при наличии ключа)."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.llm import brain_available, call_opus
from core.store import Store
from kb.loader import KnowledgeBase


def cluster_demand(store: Store | None = None, *, use_opus: bool = True) -> dict:
    """Кластер Tier S по регионам; Opus — текст рекомендации."""
    store = store or Store()
    leads = store.list_leads(limit=500)
    regions = Counter(l.get("region") or "?" for l in leads if l.get("tier") == "S")
    top = regions.most_common(5)
    insight: dict = {"tier_s_by_region": top, "recommendation": None, "opus": False}

    if top and top[0][1] >= 3:
        insight["recommendation"] = (
            f"Кластер спроса: {top[0][0]} — {top[0][1]} Tier S лидов. "
            "Рекомендую пилотный заход в регион."
        )

    if use_opus and brain_available() and top:
        kb = KnowledgeBase()
        prompt = (
            f"Tier S лиды по регионам: {dict(top)}\n"
            f"Всего лидов в базе: {len(leads)}\n"
            "Одним абзацем: куда бить на этой неделе и почему (фикс-база Астрахань)."
        )
        try:
            text, usage = call_opus(prompt, system=kb.context_for_prompt(8), max_tokens=600)
            insight["recommendation"] = text.strip()
            insight["opus"] = True
            insight["cost_usd"] = usage.get("cost_usd")
        except Exception as e:
            insight["opus_error"] = str(e)[:200]

    store.add_signal("strategist", "cluster_insight", insight)
    return insight
