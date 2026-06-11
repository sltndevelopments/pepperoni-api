#!/usr/bin/env python3
"""Проактивность Стива — он сам пишет владельцу первым, но только при важном.

Вызывается в конце каждого цикла. Стив смотрит на свежие сигналы воронки и шлёт
📣-сообщение в Telegram ТОЛЬКО когда есть повод:
  • горячий лид (заинтересованный ЛПР) — передать владельцу с контактами
  • всплеск ответов на рассылку
  • серия hard bounce — проблема доставляемости
  • база нужных лидов кончается
  • бюджет Стива подходит к концу

Анти-спам: на каждый тип повода — кулдаун (data/steve_proactive.json), чтобы не
дёргать владельца по одному и тому же поводу чаще, чем раз в N часов.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import env as _env  # noqa: F401
from core.store import Store

STATE = ROOT / "data" / "steve_proactive.json"

COOLDOWN_HOURS = {
    "hot": 1,
    "replies": 6,
    "bounce": 12,
    "base_low": 24,
    "budget": 24,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _due(state: dict, key: str) -> bool:
    last = state.get(key)
    if not last:
        return True
    try:
        prev = datetime.fromisoformat(last)
    except Exception:
        return True
    return (_now() - prev).total_seconds() >= COOLDOWN_HOURS.get(key, 12) * 3600


def _push(text: str) -> bool:
    try:
        from telegram.notify import notify
        return notify(text) > 0
    except Exception:
        return False


def run(*, store: Store | None = None) -> dict:
    store = store or Store()
    store.init()
    state = _load()
    fired: list[str] = []

    stats = store.stats()

    # 1) Горячие лиды — главный повод: передать владельцу
    hot = []
    try:
        hot = store.list_hot_leads(5)
    except Exception:
        hot = []
    if hot and _due(state, "hot"):
        lines = ["📣 <b>Стив:</b> есть заинтересованные — забирай на личные переговоры:"]
        for r in hot:
            try:
                from workers.escalate import format_contacts
                lines.append("\n" + format_contacts(r))
            except Exception:
                lines.append(f"\n• {r.get('name', '?')}")
        if _push("\n".join(lines)):
            state["hot"] = _now().isoformat()
            fired.append("hot")

    # 2) Серия hard bounce за последние циклы → доставляемость
    try:
        recent = store.recent_audit("imap", "bounce_hard", limit=10) \
            if hasattr(store, "recent_audit") else []
    except Exception:
        recent = []
    if len(recent) >= 3 and _due(state, "bounce"):
        if _push(
            f"📣 <b>Стив:</b> поймал {len(recent)} жёстких отказов почты (hard bounce). "
            "Подчистил адреса, чтобы не жечь домен. Если их много — обновим контакты в базе."
        ):
            state["bounce"] = _now().isoformat()
            fired.append("bounce")

    # 3) База нужных лидов кончается
    try:
        from orchestrator.outreach import outreach_candidates
        queue = len(outreach_candidates(store, limit=50))
    except Exception:
        queue = None
    if queue is not None and queue <= 5 and _due(state, "base_low"):
        if _push(
            f"📣 <b>Стив:</b> очередь на холодный аутрич почти пуста ({queue}). "
            "Беру свежие сегменты из реестров — но дай знать, если есть приоритет по нишам/сетям."
        ):
            state["base_low"] = _now().isoformat()
            fired.append("base_low")

    # 4) Бюджет Стива на исходе
    try:
        from core.budget import summary as steve_budget
        sb = steve_budget()
        if sb["remaining_usd"] <= sb["budget_usd"] * 0.15 and _due(state, "budget"):
            if _push(
                f"📣 <b>Стив:</b> мой бюджет на исходе — осталось ${sb['remaining_usd']:.2f} из "
                f"${sb['budget_usd']:.0f}. Дальше работаю по уже принятой стратегии, "
                "но новых глубоких разборов до конца месяца почти не будет."
            ):
                state["budget"] = _now().isoformat()
                fired.append("budget")
    except Exception:
        pass

    _save(state)
    return {"fired": fired, "hot": len(hot), "queue": queue, "stats_leads": stats.get("leads")}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
