#!/usr/bin/env python3
"""Проактивность Стива — пишет владельцу первым, только при важном.

Вызывается в конце каждого цикла. Дедупликация через store.notifications:
  • hot_leads    — без cooldown, hash по составу id (новые горячие = всегда важно)
  • bounce_series— cooldown 12ч, hash по кол-ву bounce
  • queue_empty  — cooldown 24ч
  • budget_low   — cooldown 24ч

Самодельный steve_proactive.json упразднён: единый журнал в agent.db.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import env as _env  # noqa: F401
from core.store import Store


def _hash(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _push(text: str) -> bool:
    try:
        from telegram.notify import notify
        return notify(text) > 0
    except Exception:
        return False


def run(*, store: Store | None = None) -> dict:
    store = store or Store()
    store.init()
    fired: list[str] = []

    stats = store.stats()

    # 1) Handoff владельцу. Дедуп — навсегда по lead_id + типу события,
    # а не по скользящему top-20: CRM обновляет updated_at и переставляет
    # старые лиды в окне, хотя нового события не было.
    hot_statuses = {"hot", "escalated", "replied", "meeting", "proposal"}
    try:
        hot = [
            lead for lead in store.list_leads(limit=5000)
            if (lead.get("status") or "") in hot_statuses
        ]
    except Exception:
        hot = []

    marker_key = "proactive:handoff_v2_initialized"
    initialized = not store.should_notify(marker_key, "1", cooldown_hours=0)
    if not initialized:
        # Миграция без повторной рассылки уже переданных 42 лидов.
        for lead in hot:
            kind = "interest" if (lead.get("profile") or {}).get("interest_confirmed") else "priority"
            store.record_notification(f"proactive:handoff:{lead['id']}:{kind}", "seen")
        store.record_notification(marker_key, "1")
    else:
        new_hot = []
        for lead in hot:
            kind = "interest" if (lead.get("profile") or {}).get("interest_confirmed") else "priority"
            key = f"proactive:handoff:{lead['id']}:{kind}"
            if store.should_notify(key, "seen", cooldown_hours=0):
                new_hot.append((lead, kind, key))
        for lead, kind, key in new_hot[:5]:
            if kind == "interest":
                title = "📣 <b>Стив:</b> новый входящий интерес — нужен ответ сегодня:"
            else:
                title = "📣 <b>Стив:</b> новая приоритетная компания — нужен личный выход:"
            try:
                from workers.escalate import format_contacts
                body = title + "\n\n" + format_contacts(lead)
            except Exception:
                body = title + f"\n\n• {lead.get('name', '?')}"
            if _push(body):
                store.record_notification(key, "seen")
                fired.append("confirmed_interest" if kind == "interest" else "priority_handoff")

    # 2) Серия hard bounce за последними циклами → доставляемость.
    recent_bounces = 0
    try:
        recent = store.recent_audit("imap", "bounce_hard", limit=10) \
            if hasattr(store, "recent_audit") else []
        recent_bounces = len(recent)
    except Exception:
        pass
    if recent_bounces >= 3:
        bounce_hash = _hash(recent_bounces)
        if store.should_notify("proactive:bounce_series", bounce_hash, cooldown_hours=12):
            if _push(
                f"📣 <b>Стив:</b> поймал {recent_bounces} жёстких отказов почты (hard bounce). "
                "Подчистил адреса, чтобы не жечь домен. Если их много — обновим контакты в базе."
            ):
                store.record_notification("proactive:bounce_series", bounce_hash)
                fired.append("bounce_series")

    # 3) База нужных лидов кончается.
    queue = None
    try:
        from orchestrator.outreach import outreach_candidates
        queue = len(outreach_candidates(store, limit=50))
    except Exception:
        pass
    if queue is not None and queue <= 5:
        queue_hash = _hash(queue)
        if store.should_notify("proactive:queue_empty", queue_hash, cooldown_hours=24):
            if _push(
                f"📣 <b>Стив:</b> очередь на холодный аутрич почти пуста ({queue}). "
                "Новых писем не будет, пока contact enrichment не найдёт проверенные "
                "адреса закупок/корпоративные контакты."
            ):
                store.record_notification("proactive:queue_empty", queue_hash)
                fired.append("queue_empty")

    # 4) Бюджет Стива на исходе.
    try:
        from core.budget import summary as steve_budget
        sb = steve_budget()
        if sb["remaining_usd"] <= sb["budget_usd"] * 0.15:
            budget_hash = _hash(round(sb["remaining_usd"], 2))
            if store.should_notify("proactive:budget_low", budget_hash, cooldown_hours=24):
                if _push(
                    f"📣 <b>Стив:</b> мой бюджет на исходе — осталось ${sb['remaining_usd']:.2f} из "
                    f"${sb['budget_usd']:.0f}. Дальше работаю по уже принятой стратегии, "
                    "но новых глубоких разборов до конца месяца почти не будет."
                ):
                    store.record_notification("proactive:budget_low", budget_hash)
                    fired.append("budget_low")
    except Exception:
        pass

    return {"fired": fired, "hot": len(hot), "queue": queue, "stats_leads": stats.get("leads")}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
