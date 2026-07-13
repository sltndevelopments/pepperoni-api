"""
Детект заинтересованных: входящие, ответы, сигналы Opus.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.autonomy import load_autonomy
from core.llm import brain_available
from core.store import Store
from workers.escalate import escalate_to_owner
from workers.triage import triage_inbound

POSITIVE_REPLY = re.compile(
    r"интересн|готов|давайте|пришлите|прайс|образец|встреч|звоните|перезвон|"
    r"да[,!\s]|согласен|актуальн|рассмотр|хотим|нужн[оа]",
    re.I,
)
QUOTE_SPLIT = re.compile(
    r"(?:\r?\n)(?:[-_]{2,}\s*(?:original|исходн)|from:|от:|"
    r".{0,80}\bот\s+Казанские\s+Деликатесы\b)",
    re.I,
)
EXPLICIT_BUYER = re.compile(
    r"нас\s+заинтересовал|интересует\s+ваш|хотим\s+(?:с\s+вами\s+)?сотруднич|"
    r"(?:можно|пришлите|прошу|нужен)\b.{0,40}\bпрайс|сколько\s+стоит|"
    r"(?:дать|дайте|пришлите)\b.{0,40}\bобразец|хотим\s+(?:купить|заказать)",
    re.I | re.S,
)
SELLER_OFFER = re.compile(
    r"я\s+представляю\s+(?:компанию|инвестицион)|мы\s+(?:производим|поставляем)|"
    r"направляю\s+(?:вам\s+)?презентац|готовы\s+предложить|"
    r"производител[ья]\s+(?:пл[её]нок|упаковк|лент|добавок|сырья)|"
    r"(?:нашем|нашего)\s+стенд[ае]\s+на\s+выставк",
    re.I,
)


def _is_interested_triage(triage: dict) -> bool:
    cfg = load_autonomy()
    esc = cfg.get("escalation", {})
    temp = triage.get("temperature", "cold")
    if temp in esc.get("hot_temperatures", ["hot", "warm"]):
        return True
    intents = set(triage.get("intents") or [])
    warm = set(esc.get("warm_intents", []))
    if intents & warm and temp != "reject":
        return True
    return triage.get("suggest_escalate", False)


def _fresh_body(body: str) -> str:
    """Только новое сообщение, без процитированной переписки ниже."""
    match = QUOTE_SPLIT.search(body)
    return body[:match.start()] if match else body


def scan_inbox(store: Store | None = None, limit: int = 30) -> list[dict]:
    """Проверить входящие, эскалировать заинтересованных."""
    store = store or Store()
    results = []
    # Каналы пассивного сбора: группа лидов и info@. Их Стив копит для
    # аналитики и НЕ дёргает владельца, кроме настоящего покупательского
    # интента к нашей продукции (цена/образец/опт/сосиски в тесте).
    ANALYTICS_CHANNELS = {"telegram_group", "email_info"}
    BUYING_INTENTS = {"price_request", "sample_request", "sausage_in_dough"}

    for msg in store.inbox(limit, unprocessed_interest=True):
        fresh_body = _fresh_body(msg.get("body") or "")
        triage = triage_inbound({**msg, "body": fresh_body}, store)

        channel = msg.get("channel") or ""
        intents = set(triage.get("intents") or [])

        # Поставщик продаёт нам, а не покупает у нас. Один и тот же guard
        # действует и для live inbox, и для исторического recovery.
        if SELLER_OFFER.search(fresh_body) or "supplier_offer" in intents:
            store.add_signal(
                "analytics",
                f"inbound_{channel or 'unknown'}",
                {"body": fresh_body[:500], "triage": triage, "seller_offer": True},
            )
            if msg.get("id"):
                store.patch_message_meta(
                    msg["id"],
                    {"interest_scanned": True, "analytics_only": True, "seller_offer": True},
                )
            continue

        # Форм-заявка с сайта — это прямое обращение клиента: всегда поднимаем
        # владельцу (даже если в тексте нет ключевых слов).
        if channel == "email_form" and triage.get("temperature") != "reject":
            lead_id = msg.get("lead_id")
            body = fresh_body[:800]
            if lead_id:
                r = escalate_to_owner(
                    lead_id,
                    "📝 заявка с сайта",
                    context=body,
                    store=store,
                    confirmed_interest=True,
                )
            else:
                r = _escalate_unknown(body, "📝 заявка с сайта (форма)", triage, store, message=msg)
            results.append({"message_id": msg.get("id"), "triage": triage, **r})
            if msg.get("id"):
                store.patch_message_meta(msg["id"], {"interest_scanned": True})
            continue

        if channel in ANALYTICS_CHANNELS:
            # нет явного интереса купить НАШЕ — молча в аналитику, не беспокоим
            if not (intents & BUYING_INTENTS) or triage.get("temperature") == "reject":
                store.add_signal("analytics", f"inbound_{channel}", {"body": (msg.get("body") or "")[:500], "triage": triage})
                if msg.get("id"):
                    store.patch_message_meta(msg["id"], {"interest_scanned": True, "analytics_only": True})
                continue

        if not _is_interested_triage(triage):
            if msg.get("id"):
                store.patch_message_meta(msg["id"], {"interest_scanned": True, "not_interested": True})
            continue

        lead_id = msg.get("lead_id")
        body = fresh_body[:800]
        reason = f"входящее: {', '.join(triage.get('intents') or [])} · {triage.get('temperature')}"

        if not lead_id and brain_available():
            lead_id = _guess_lead_from_text(body, store)

        if lead_id:
            from core.exclusions import is_excluded
            lead = store.get_lead(lead_id) or {}
            if is_excluded(lead)[0]:
                store.patch_message_meta(msg["id"], {"interest_scanned": True, "skipped": "excluded"})
                continue
            r = escalate_to_owner(
                lead_id, reason, context=body, store=store, confirmed_interest=True
            )
        else:
            r = _escalate_unknown(body, reason, triage, store, message=msg)

        results.append({"message_id": msg.get("id"), "triage": triage, **r})
        store.audit("interest", "inbox_escalation", "message", msg.get("id"), r)
        if msg.get("id"):
            store.patch_message_meta(msg["id"], {"interest_scanned": True})

    return results


def recover_untracked_warm_inbound(
    store: Store | None = None,
    *,
    limit: int = 5,
) -> list[dict]:
    """Разово восстановить старые warm-входящие, которые уведомили, но не создали лид.

    Использует только детерминированный triage, чтобы не тратить LLM на историю.
    """
    store = store or Store()
    recovered: list[dict] = []
    for msg in store.inbox(500):
        if msg.get("lead_id"):
            continue
        try:
            meta = json.loads(msg.get("meta") or "{}")
        except Exception:
            meta = {}
        if meta.get("warm_lead_recovered"):
            continue
        fresh_body = _fresh_body(msg.get("body") or "")
        if not EXPLICIT_BUYER.search(fresh_body) or SELLER_OFFER.search(fresh_body):
            continue
        triage = triage_inbound({**msg, "body": fresh_body}, store, use_llm=False)
        if not _is_interested_triage(triage):
            continue
        body = fresh_body[:800]
        reason = f"восстановленное входящее: {', '.join(triage.get('intents') or [])} · {triage.get('temperature')}"
        result = _escalate_unknown(body, reason, triage, store, message=msg)
        store.patch_message_meta(
            msg["id"],
            {"warm_lead_recovered": True, "recovered_lead_id": result.get("lead_id")},
        )
        recovered.append({"message_id": msg["id"], **result})
        if len(recovered) >= limit:
            break
    return recovered


def check_reply_text(text: str, lead_id: str, *, store: Store | None = None) -> dict | None:
    """Если в тексте явный интерес — эскалация."""
    if not POSITIVE_REPLY.search(text):
        return None
    return escalate_to_owner(
        lead_id,
        "явный интерес в переписке",
        context=text[:800],
        store=store,
        confirmed_interest=True,
    )


def _guess_lead_from_text(text: str, store: Store) -> str | None:
    leads = store.list_leads(limit=5000)
    text_l = text.lower()
    for l in leads:
        name = (l.get("name") or "").lower()
        if len(name) > 8 and name[:20] in text_l:
            return l["id"]
        inn = l.get("inn") or ""
        if inn and inn in text:
            return l["id"]
    return None


def _unknown_contact(body: str, message: dict | None = None) -> dict:
    """Извлечь только явно присутствующие контактные поля без выдумывания."""
    meta = {}
    if message:
        raw_meta = message.get("meta") or {}
        try:
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
        except Exception:
            meta = {}
    email = str(meta.get("from") or "")
    phone_match = re.search(r"(?:\+?7|8)[\s()\-]*\d[\d\s()\-]{8,16}\d", body)
    company_match = re.search(
        r"(?:(?:мы\s+)?сеть\s+(?:ресторанов|кафе|пекарен|магазинов)|"
        r"(?:ресторан|кафе|пекарня|магазин|компания))\s+"
        r"[«\"]?([^\n\r,.]{2,60})",
        body,
        re.I,
    )
    company = company_match.group(1).strip(" «»\"") if company_match else ""
    return {
        "company": company,
        "phone": phone_match.group(0).strip() if phone_match else "",
        "email": email if "@" in email else "",
    }


def _escalate_unknown(
    body: str,
    reason: str,
    triage: dict,
    store: Store,
    *,
    message: dict | None = None,
) -> dict:
    """Тёплое входящее становится лидом и получает отслеживаемый handoff."""
    contact = _unknown_contact(body, message)
    label = contact["company"] or contact["email"] or contact["phone"] or "без контакта"
    lead_name = f"Входящий лид: {label}"[:120]
    profile = {
        "emails": contact["email"],
        "phones": contact["phone"],
        "last_context": body[:1000],
        "inbound_reason": reason[:500],
        "interest_confirmed": True,
    }
    lead_id = store.upsert_lead(
        lead_name,
        status="replied",
        source="inbound",
        profile=profile,
    )
    handoff = escalate_to_owner(
        lead_id,
        reason,
        context=body,
        store=store,
        confirmed_interest=True,
    )

    # Telegram и email-forward уже выполнены единым handoff в escalate_to_owner.
    n = handoff.get("telegram_sent", 0)
    store.add_signal(
        "interest",
        "inbound_lead_created",
        {"lead_id": lead_id, "body": body[:500], "triage": triage},
    )
    return {"ok": True, "lead_id": lead_id, "created": True, "telegram_sent": n}


def scan_contacted_for_replies(store: Store | None = None) -> list[dict]:
    """
    Лиды в статусе contacted — если в профиле есть reply_snippet с позитивом, эскалация.
    (Заготовка под IMAP; пока — ручной инбокс / сигналы.)
    """
    store = store or Store()
    out = []
    for lead in store.list_leads(status="contacted", limit=50):
        snippet = (lead.get("profile") or {}).get("reply_snippet", "")
        if snippet:
            r = check_reply_text(snippet, lead["id"], store=store)
            if r:
                out.append(r)
    return out
