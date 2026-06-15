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

    # 1) Горячие лиды — главный повод: передать владельцу.
    # Нет cooldown — новые лиды всегда важны; hash по составу id.
    hot = []
    try:
        hot = store.list_hot_leads(5)
    except Exception:
        hot = []
    if hot:
        hot_hash = _hash(*sorted(l["id"] for l in hot))
        if store.should_notify("proactive:hot_leads", hot_hash, cooldown_hours=0):
            lines = ["📣 <b>Стив:</b> есть заинтересованные — забирай на личные переговоры:"]
            for r in hot:
                try:
                    from workers.escalate import format_contacts
                    lines.append("\n" + format_contacts(r))
                except Exception:
                    lines.append(f"\n• {r.get('name', '?')}")
            if _push("\n".join(lines)):
                store.record_notification("proactive:hot_leads", hot_hash)
                fired.append("hot_leads")

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
                "Беру свежие сегменты из реестров — но дай знать, если есть приоритет по нишам/сетям."
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
