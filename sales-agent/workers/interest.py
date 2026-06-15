"""
Детект заинтересованных: входящие, ответы, сигналы Opus.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.autonomy import load_autonomy
from core.llm import brain_available, call_haiku
from core.store import Store
from workers.escalate import escalate_to_owner
from workers.triage import triage_inbound

POSITIVE_REPLY = re.compile(
    r"интересн|готов|давайте|пришлите|прайс|образец|встреч|звоните|перезвон|"
    r"да[,!\s]|согласен|актуальн|рассмотр|хотим|нужн[оа]",
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
        triage = triage_inbound(msg, store)

        channel = msg.get("channel") or ""

        # Форм-заявка с сайта — это прямое обращение клиента: всегда поднимаем
        # владельцу (даже если в тексте нет ключевых слов).
        if channel == "email_form" and triage.get("temperature") != "reject":
            lead_id = msg.get("lead_id")
            body = (msg.get("body") or "")[:800]
            if lead_id:
                r = escalate_to_owner(lead_id, "📝 заявка с сайта", context=body, store=store)
            else:
                r = _escalate_unknown(body, "📝 заявка с сайта (форма)", triage, store)
            results.append({"message_id": msg.get("id"), "triage": triage, **r})
            if msg.get("id"):
                store.patch_message_meta(msg["id"], {"interest_scanned": True})
            continue

        if channel in ANALYTICS_CHANNELS:
            intents = set(triage.get("intents") or [])
            # нет явного интереса купить НАШЕ — молча в аналитику, не беспокоим
            if not (intents & BUYING_INTENTS) or triage.get("temperature") == "reject":
                store.add_signal("analytics", f"inbound_{channel}", {"body": (msg.get("body") or "")[:500], "triage": triage})
                if msg.get("id"):
                    store.patch_message_meta(msg["id"], {"interest_scanned": True, "analytics_only": True})
                continue

        if not _is_interested_triage(triage):
            continue

        lead_id = msg.get("lead_id")
        body = (msg.get("body") or "")[:800]
        reason = f"входящее: {', '.join(triage.get('intents') or [])} · {triage.get('temperature')}"

        if not lead_id and brain_available():
            lead_id = _guess_lead_from_text(body, store)

        if lead_id:
            from core.exclusions import is_excluded
            lead = store.get_lead(lead_id) or {}
            if is_excluded(lead)[0]:
                store.patch_message_meta(msg["id"], {"interest_scanned": True, "skipped": "excluded"})
                continue
            r = escalate_to_owner(lead_id, reason, context=body, store=store)
        else:
            r = _escalate_unknown(body, reason, triage, store)

        results.append({"message_id": msg.get("id"), "triage": triage, **r})
        store.audit("interest", "inbox_escalation", "message", msg.get("id"), r)
        if msg.get("id"):
            store.patch_message_meta(msg["id"], {"interest_scanned": True})

    return results


def check_reply_text(text: str, lead_id: str, *, store: Store | None = None) -> dict | None:
    """Если в тексте явный интерес — эскалация."""
    if not POSITIVE_REPLY.search(text):
        return None
    return escalate_to_owner(
        lead_id,
        "явный интерес в переписке",
        context=text[:800],
        store=store,
    )


def _guess_lead_from_text(text: str, store: Store) -> str | None:
    leads = store.list_leads(limit=100)
    text_l = text.lower()
    for l in leads:
        name = (l.get("name") or "").lower()
        if len(name) > 8 and name[:20] in text_l:
            return l["id"]
        inn = l.get("inn") or ""
        if inn and inn in text:
            return l["id"]
    return None


def _escalate_unknown(body: str, reason: str, triage: dict, store: Store) -> dict:
    """Входящее без привязки к лиду — всё равно шлём владельцу."""
    try:
        from telegram.notify import notify
        from workers.escalate import format_contacts

        extra = ""
        if brain_available():
            try:
                # извлечение полей — задача Haiku, не Fable ($1 vs $5+thinking за MTok)
                raw, _ = call_haiku(
                    f"Извлеки из текста: компания, контакт, телефон, email. JSON keys: company, contact, phone, email.\n{body[:600]}",
                    max_tokens=150,
                )
                extra = f"\n\n<i>Извлечено:</i> {raw[:300]}"
            except Exception:
                pass

        text = (
            f"<b>🔥 Входящий без лида в базе</b>\n"
            f"<b>Почему:</b> {reason}\n\n"
            f"{body[:600]}{extra}"
        )
        n = notify(text)
        try:
            from workers.forward_important import forward_to_owner
            forward_to_owner("Входящее без лида", body[:2000] + extra, category="inbound")
        except Exception:
            pass
    except Exception:
        n = 0
    store.add_signal("interest", "unknown_inbound", {"body": body[:500], "triage": triage})
    return {"ok": True, "unknown": True, "telegram_sent": n}


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
