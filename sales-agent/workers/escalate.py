"""
Эскалация заинтересованных лидов владельцу: контакты в Telegram.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.autonomy import load_autonomy
from core.store import Store


def format_contacts(lead: dict) -> str:
    from core import agent_profile as ap

    p = lead.get("profile") or {}
    lines = [
        f"<b>{lead.get('name', '?')}</b>",
        f"Tier <b>{lead.get('tier', '—')}</b> · score {lead.get('fit_score', 0)} · {lead.get('status', 'new')}",
    ]
    if lead.get("region"):
        lines.append(f"📍 {lead['region']}")
    if lead.get("inn"):
        lines.append(f"ИНН <code>{lead['inn']}</code>")
    if p.get("director"):
        lines.append(f"👤 {p['director']}")
    if p.get("phones"):
        lines.append(f"📞 {p['phones']}")
    email = ap.get(p, "email_best") or p.get("emails")
    if email:
        lines.append(f"✉️ {email}")
    site = ap.get(p, "contact_site") or p.get("sites") or p.get("website")
    if site:
        lines.append(f"🌐 {site}")
    rev = p.get("revenue_mln_rub") or p.get("revenue_mln") or p.get("gainSum") or p.get("revenue")
    if rev:
        lines.append(f"💰 выручка: {rev} млн ₽")
    if p.get("sausage_evidence"):
        lines.append(f"<i>Сигнал: {p['sausage_evidence'][:160]}</i>")
    return "\n".join(lines)


def escalate_to_owner(
    lead_id: str,
    reason: str,
    *,
    context: str = "",
    store: Store | None = None,
    force: bool = False,
    confirmed_interest: bool = False,
) -> dict:
    """Передать лида владельцу, честно разделяя интерес и приоритет."""
    store = store or Store()
    lead = store.get_lead(lead_id)
    if not lead:
        return {"ok": False, "error": "lead_not_found"}

    profile = dict(lead.get("profile") or {})
    now = datetime.now(timezone.utc).isoformat()

    interest_upgrade = confirmed_interest and not profile.get("interest_confirmed")
    if profile.get("escalated_at") and not force and not interest_upgrade:
        return {"ok": True, "skipped": "already_escalated", "lead_id": lead_id}

    owner = load_autonomy().get("escalation", {}).get("owner_name", "Ринат")
    profile["escalated_at"] = now
    profile["escalation_reason"] = reason[:500]
    profile["owner"] = owner
    if confirmed_interest:
        profile["interest_confirmed"] = True
    if context:
        profile["last_context"] = context[:1000]

    store.upsert_lead(
        lead["name"],
        lead_id=lead_id,
        inn=lead.get("inn"),
        region=lead.get("region"),
        tier=lead.get("tier"),
        fit_score=lead.get("fit_score") or 0,
        status="hot",
        source=lead.get("source"),
        profile=profile,
    )

    heading = (
        "🔥 Входящий интерес — ответь сегодня"
        if confirmed_interest
        else "🎯 Приоритетная компания — нужен личный выход"
    )
    text = (
        f"<b>{heading}</b>\n"
        f"{format_contacts(lead)}\n\n"
        f"<b>Почему:</b> {reason[:400]}"
    )
    if context:
        text += f"\n\n<i>{context[:500]}</i>"
    text += f"\n\n<i>→ позвони лично или ответь с sales@</i>"

    sent = 0
    if load_autonomy().get("escalation", {}).get("notify_telegram", True):
        try:
            from telegram.notify import notify
            sent = notify(text)
        except Exception:
            pass
    if sent:
        kind = "interest" if confirmed_interest else "priority"
        store.record_notification(f"proactive:handoff:{lead_id}:{kind}", "seen")

    email_fwd = {}
    try:
        from workers.forward_important import forward_to_owner
        plain = (
            f"{lead.get('name')}\n"
            f"ИНН: {lead.get('inn')}\n"
            f"Регион: {lead.get('region')}\n"
            f"Тел: {(profile.get('phones') or '')}\n"
            f"Email: {(profile.get('emails') or '')}\n\n"
            f"Причина: {reason}\n\n{context}"
        )
        email_fwd = forward_to_owner(
            lead.get("name", "лид"),
            plain,
            category="hot_lead",
            meta={"lead_id": lead_id},
        )
    except Exception as e:
        email_fwd = {"ok": False, "error": str(e)[:100]}

    store.audit(
        "escalate", "hot_lead", "lead", lead_id,
        {"reason": reason, "telegram_sent": sent, "email_fwd": email_fwd},
    )
    return {
        "ok": True,
        "lead_id": lead_id,
        "telegram_sent": sent,
        "email_forwarded": email_fwd.get("ok"),
        "status": "hot",
        "interest_confirmed": confirmed_interest,
    }
