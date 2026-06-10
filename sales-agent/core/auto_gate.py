"""
Opus (или правила) решает исходящее: send / hold / escalate.

escalate — лид уже тёплый → не слать холодняк, уведомить владельца.
send     — рутинный холодный аутрич, матрица can/cannot ок.
hold     — редко, только при сомнении Opus.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.autonomy import hot_statuses, load_autonomy
from core.llm import brain_available, call_opus
from kb.loader import KnowledgeBase

HOLD_MARKERS = re.compile(
    r"гарантир|100%|без\s+огранич|любой\s+объём|свинин|куриц[аы]\s+в\s+панир|наггетс",
    re.I,
)


def _lookalike_of(lead: dict) -> int:
    p = lead.get("profile") or {}
    la = p.get("lookalike")
    if isinstance(la, dict) and la.get("lookalike_score"):
        try:
            return int(float(str(la["lookalike_score"]).replace(",", ".")))
        except Exception:
            pass
    # плоская колонка из CRM-таблицы (после crm-pull)
    flat = p.get("lookalike_score")
    if flat:
        try:
            return int(float(str(flat).replace(",", ".")))
        except Exception:
            pass
    return 0


def decide_outbound(draft: dict, lead: dict, fit_check: dict) -> dict:
    """
    Возвращает {action: send|hold|escalate, reason, decided_by: opus|rules}.

    Rules-first: очевидные случаи решаются без LLM (≈80–90% вызовов).
    Fable (effort=low) — только для пограничных.
    """
    cfg = load_autonomy()
    if not cfg.get("autonomy", {}).get("enabled", True):
        return {"action": "hold", "reason": "autonomy_disabled", "decided_by": "rules"}

    if fit_check and not fit_check.get("ok", True):
        return {
            "action": "hold",
            "reason": "fit_blocked: " + str(fit_check.get("blocked_reasons", []))[:200],
            "decided_by": "rules",
        }

    status = (lead.get("status") or "new").lower()
    if status in hot_statuses():
        return {
            "action": "escalate",
            "reason": f"лид уже тёплый (status={status}) — на владельца, не холодняк",
            "decided_by": "rules",
        }

    body = (draft.get("body") or "") + " " + (draft.get("subject") or "")
    if HOLD_MARKERS.search(body):
        return {
            "action": "hold",
            "reason": "рискованные формулировки в тексте",
            "decided_by": "rules",
        }

    # ── Rules-first: однозначные случаи не тратят Fable ──
    tier = lead.get("tier", "—")
    score = lead.get("fit_score") or 0
    la = _lookalike_of(lead)
    revenue = (lead.get("profile") or {}).get("revenue_mln_rub") or 0
    try:
        revenue = float(str(revenue).replace(",", ".") or 0)
    except Exception:
        revenue = 0

    # крупняк (>1 млрд) — стратегическое решение, пусть смотрит Fable
    big_fish = revenue >= 1000

    if not big_fish:
        if tier in ("S", "A") and score >= 70 and la >= 45:
            return {
                "action": "send",
                "reason": f"однозначный аутрич: tier={tier} score={score} lookalike={la}",
                "decided_by": "rules",
            }
        if score < 50:
            return {"action": "hold", "reason": f"низкий score={score}", "decided_by": "rules"}

    # ── Пограничный случай → Fable (effort=low) ──
    if cfg.get("autonomy", {}).get("opus_approves_outbound") and brain_available():
        return _opus_decide(draft, lead, fit_check)

    return _rules_decide(draft, lead, fit_check)


def _rules_decide(draft: dict, lead: dict, fit_check: dict) -> dict:
    tier = lead.get("tier", "—")
    score = lead.get("fit_score") or 0
    la = _lookalike_of(lead)
    if tier in ("S", "A") and score >= 60 and la >= 45:
        return {
            "action": "send",
            "reason": f"аутрич tier={tier} score={score} lookalike={la}",
            "decided_by": "rules",
        }
    if tier == "S" or score >= 70:
        return {
            "action": "send",
            "reason": f"рутинный аутрич tier={tier} score={score}",
            "decided_by": "rules",
        }
    if score >= 60 and fit_check.get("can_proceed_to_draft"):
        return {"action": "send", "reason": "fit ok, score>=60", "decided_by": "rules"}
    return {"action": "hold", "reason": f"низкий score={score}", "decided_by": "rules"}


GATE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["send", "hold", "escalate"]},
        "reason": {"type": "string"},
    },
    "required": ["action", "reason"],
}


def _opus_decide(draft: dict, lead: dict, fit_check: dict) -> dict:
    kb = KnowledgeBase()
    profile = lead.get("profile") or {}
    # Стабильный system (кэшируется между вызовами), переменное — в prompt
    system = (
        "Ты гейт автономных продаж halal-производителя. "
        "Реши исходящее B2B-действие.\n"
        "send — рутинное первое письмо холодному лиду, текст не обещает лишнего\n"
        "escalate — лид тёплый/важный, владелец должен звонить лично (не слать автописьмо)\n"
        "hold — сомнение в тексте или фите\n"
        "Не разрешай send если текст обещает то, чего нет в НЕ МОЖЕМ. "
        "escalate для Tier S с явным интересом или крупных (выручка >1млрд).\n\n"
        + kb.context_for_prompt(8)
    )
    prompt = f"""Лид: {lead.get('name')} | tier {lead.get('tier')} | score {lead.get('fit_score')} | status {lead.get('status')}
Регион: {lead.get('region')} | ИНН: {lead.get('inn')}
Сигнал: {(profile.get('sausage_evidence') or profile.get('score_reasons') or '')[:200]}

Тема: {(draft.get('subject') or '')[:120]}
Текст (начало): {(draft.get('body') or '')[:400]}

Фит: {json.dumps(fit_check, ensure_ascii=False)[:300]}
"""
    try:
        raw, usage = call_opus(
            prompt, system=system, max_tokens=300,
            effort="low", json_schema=GATE_SCHEMA,
        )
        data = json.loads(raw) if raw.strip().startswith("{") else None
        if data is None:
            m = re.search(r"\{[^{}]+\}", raw, re.S)
            data = json.loads(m.group()) if m else {}
        action = data.get("action", "send")
        if action not in ("send", "hold", "escalate"):
            action = "send"
        return {
            "action": action,
            "reason": str(data.get("reason", ""))[:300],
            "decided_by": "opus",
            "cost_usd": usage.get("cost_usd"),
        }
    except Exception as e:
        return _rules_decide(draft, lead, fit_check) | {"opus_error": str(e)[:100]}
