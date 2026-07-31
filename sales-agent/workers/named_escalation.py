"""
Именной поток (Поток 2): исследовать ЛПР и эскалировать владельцу с досье.

Не отправляет письма. Максимум `limit` эскалаций за вызов (owner-требование:
1–2 за цикл, не шторм из 12 досье разом), плюс недельный кулдаун поверх
cycle-лимита через уже существующий `owner_escalated_at`.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import agent_profile as ap
from core.store import Store
from orchestrator.outreach import named_escalation_candidates
from prospecting.contact_research import research_contacts, apply_research_to_lead
from workers.escalate import escalate_to_owner

OWNER_NAME = __import__("os").environ.get("OWNER_NAME", "Ринат Султанов")
OWNER_PHONE = __import__("os").environ.get("OWNER_PHONE", "+7 927 429-72-20")
OWNER_EMAIL = __import__("os").environ.get("OWNER_EMAIL", "kam@kazandelikates.tatar")

_ESCALATION_COOLDOWN_DAYS = 7

# Известные публичные порталы поставщиков — если сеть в списке, упомянуть
# как альтернативный канал. Не выдумывать URL для сетей, которых тут нет.
_SUPPLIER_PORTALS = {
    "магнит": "портал поставщиков Магнит (b2b.magnit.ru) — часто быстрее холодного email",
    "перекрёсток": "портал поставщиков X5 (supplier.x5.ru)",
    "перекресток": "портал поставщиков X5 (supplier.x5.ru)",
}


def _lpr_query(lead: dict, pitch: str, segment: str) -> str:
    name = lead.get("name", "")
    return (
        f"Найди ФИО и должность категорийного менеджера или ответственного за "
        f"закупки готовой еды/кулинарии/замороженных полуфабрикатов в компании "
        f"«{name}» (сегмент: {segment}). Нужен email или LinkedIn для делового "
        f"обращения. Если это крупная сеть — укажи, есть ли у неё портал "
        f"поставщиков (b2b-платформа для подачи КП). Только факты, кратко."
    )


def _find_lpr(lead: dict, pitch: str, segment: str) -> dict:
    """Perplexity: ЛПР + канал выхода. Возвращает {name, email, phone, note}."""
    try:
        from pplx_client import pplx_search
    except ImportError:
        return {"name": None, "email": None, "phone": None, "note": "pplx недоступен"}

    try:
        text, _ = pplx_search(_lpr_query(lead, pitch, segment), max_tokens=400, timeout=60)
    except Exception as e:
        return {"name": None, "email": None, "phone": None, "note": f"pplx error: {str(e)[:100]}"}

    if not text:
        return {"name": None, "email": None, "phone": None, "note": "пусто от Perplexity"}

    import re
    email_m = re.search(r"[\w.\-+]{2,30}@[\w\-]+\.[a-z]{2,6}", text)
    return {
        "name": None,  # ФИО из свободного текста ненадёжно парсить регуляркой — отдаём текст целиком
        "email": email_m.group(0) if email_m else None,
        "phone": None,
        "note": text[:600],
    }


def _draft_first_touch(lead: dict, pitch: str) -> str:
    """Короткий текст первого касания под конкретный SKU-оффер сети.

    Пустой pitch → явная пометка, не выдуманный оффер (owner-правило).
    """
    name = lead.get("name", "цель")
    if not pitch:
        return (
            f"⚠️ SKU-оффер не задан для «{name}» — заполни поле `pitch` в "
            f"config/named_targets.yaml перед первым касанием. Черновик не "
            f"сгенерирован, чтобы не придумывать оффер."
        )
    return (
        f"Тема: Halal-поставки для {name}\n\n"
        f"Здравствуйте!\n\n"
        f"Казанские Деликатесы (pepperoni.tatar) — halal-производитель полного "
        f"цикла в Казани. Конкретное предложение: {pitch}.\n\n"
        f"Халяль (ДУМ РТ), ХАССП, ISO 22000:2018, готовы к пилотной поставке "
        f"под ваш формат. Подскажите, куда направить КП с образцами?\n\n"
        f"С уважением,\n{OWNER_NAME}\n{OWNER_PHONE}\n{OWNER_EMAIL}"
    )


def _channel_note(lead: dict) -> str:
    name = (lead.get("name") or "").lower()
    for key, note in _SUPPLIER_PORTALS.items():
        if key in name:
            return note
    return "email/телефон (портал поставщика не известен для этой сети — уточнить вручную)"


def _cooldown_ok(profile: dict) -> bool:
    ts = ap.get(profile, "owner_escalated_at")
    if not ts:
        return True
    try:
        prev = datetime.fromisoformat(str(ts))
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - prev > timedelta(days=_ESCALATION_COOLDOWN_DAYS)
    except Exception:
        return True


def escalate_named_targets(store: Store | None = None, *, limit: int = 2) -> dict:
    """Исследовать и эскалировать до `limit` именных целей за вызов."""
    store = store or Store()
    store.init()

    candidates = named_escalation_candidates(store, limit=50)
    escalated, skipped_cooldown = 0, 0

    for lead in candidates:
        if escalated >= limit:
            break

        profile = dict(lead.get("profile") or {})
        if not _cooldown_ok(profile):
            skipped_cooldown += 1
            continue

        pitch = profile.get("pitch_hint") or ap.get(profile, "pitch_hint") or ""
        segment = profile.get("segment") or ""

        # Контакты сайта/email — дешёвый путь, уже есть в contact_research.
        research = research_contacts(lead, deep=True)
        apply_research_to_lead(lead, research, store=store, deep=True)

        lpr = _find_lpr(lead, pitch, segment)
        if lpr.get("email") and not profile.get("lpr_email"):
            profile["lpr_email"] = lpr["email"]
        channel_note = _channel_note(lead)
        draft_text = _draft_first_touch(lead, pitch)

        context = (
            f"Сегмент: {segment}\n"
            f"Канал выхода: {channel_note}\n"
            f"ЛПР (Perplexity): {lpr.get('note') or 'не найден'}\n\n"
            f"--- Draft первого касания ---\n{draft_text}"
        )

        # Сохраняем досье до handoff; canonical escalation timestamp поставит
        # единый escalate_to_owner только после формирования сообщения.
        store.upsert_lead(
            lead["name"], lead_id=lead["id"],
            inn=lead.get("inn"), region=lead.get("region"),
            tier=lead.get("tier"), fit_score=lead.get("fit_score") or 0,
            status="escalated", source=lead.get("source"),
            profile=profile,
        )

        result = escalate_to_owner(
            lead["id"], "named_target_researched",
            context=context, store=store,
        )
        # escalate_to_owner переводит статус в "hot" — вернуть на "escalated"
        # (именной поток не должен смешиваться с обычными hot-лидами по холодному аутричу).
        fresh = store.get_lead(lead["id"]) or {}
        if (fresh.get("status") or "") == "hot":
            store.upsert_lead(
                fresh["name"], lead_id=fresh["id"],
                inn=fresh.get("inn"), region=fresh.get("region"),
                tier=fresh.get("tier"), fit_score=fresh.get("fit_score") or 0,
                status="escalated", source=fresh.get("source"),
                profile=fresh.get("profile"),
            )

        if result.get("ok"):
            escalated += 1

    return {"escalated": escalated, "candidates_seen": len(candidates),
             "skipped_cooldown": skipped_cooldown}


if __name__ == "__main__":
    import json
    print(json.dumps(escalate_named_targets(), ensure_ascii=False, indent=2))
