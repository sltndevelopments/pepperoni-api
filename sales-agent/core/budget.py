#!/usr/bin/env python3
"""Отдельный кошелёк Стива — $20/мес, независимо от мозга сайта (Fable).

Расход Стива уже тегируется в общем леджере data/llm_costs.json как `sales:*`
(см. core/llm._source_tag). Этот модуль считает потраченное Стивом за текущий
месяц из этих тегов и сравнивает с его собственным лимитом
STEVE_MONTHLY_BUDGET_USD (по умолчанию $20).

Kill switch: если Стив исчерпал свои $20 — стратег-цикл «перестаёт думать»
(brain_allowed() == False), но крон-циклы, отправка по уже принятой стратегии и
обработка входящих/bounce продолжают работать. Лимит Fable при этом не трогается.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from core import env as _env  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent

STEVE_BUDGET_USD = float(os.environ.get("STEVE_MONTHLY_BUDGET_USD", "20"))


def _ledger_path() -> Path:
    for p in (REPO / "data" / "llm_costs.json", REPO / "repo" / "data" / "llm_costs.json"):
        if p.exists():
            return p
    return REPO / "data" / "llm_costs.json"


def _month_node() -> dict:
    try:
        led = json.loads(_ledger_path().read_text(encoding="utf-8"))
        return led.get(date.today().strftime("%Y-%m"), {}) or {}
    except Exception:
        return {}


def spent_this_month() -> float:
    """Сумма по всем тегам sales:* за текущий месяц."""
    node = _month_node()
    total = 0.0
    for name, n in (node.get("scripts") or {}).items():
        if name.startswith("sales"):
            total += float(n.get("usd") or 0.0)
    return round(total, 4)


def remaining() -> float:
    return max(0.0, STEVE_BUDGET_USD - spent_this_month())


def brain_allowed() -> bool:
    """True, если у Стива остался бюджет на размышления этот месяц."""
    return remaining() > 0


def summary() -> dict:
    spent = spent_this_month()
    return {
        "budget_usd": STEVE_BUDGET_USD,
        "spent_usd": spent,
        "remaining_usd": round(STEVE_BUDGET_USD - spent, 4),
        "allowed": spent < STEVE_BUDGET_USD,
    }


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=1))
