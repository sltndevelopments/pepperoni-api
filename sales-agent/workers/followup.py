"""Один безопасный follow-up по доставленному холодному письму.

Повтор разрешён только для procurement/corporate адресов, если спустя заданное
число дней нет входящего ответа. Больше одного follow-up агент не создаёт.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import agent_profile as ap
from core.gate import Gate
from core.store import Store
from channels.email import pick_recipient
from prospecting.contact_research import is_buyer_contact
from workers.draft_outreach import _signature


def followup_candidates(
    store: Store,
    *,
    min_days: int = 5,
    allowed_quality: set[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    allowed_quality = allowed_quality or {"procurement", "corporate"}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=min_days)).isoformat()
    result: list[dict] = []

    with store._conn() as conn:
        rows = conn.execute(
            """SELECT l.*, d.id AS first_draft_id, d.subject AS first_subject,
                      d.created_at AS first_sent_at, d.fit_check AS first_fit_check
               FROM leads l
               JOIN drafts d ON d.lead_id=l.id
               WHERE l.status='contacted'
                 AND d.status='sent'
                 AND d.sequence_step=0
                 AND d.created_at<=?
                 AND NOT EXISTS (
                   SELECT 1 FROM drafts f
                   WHERE f.lead_id=l.id AND f.sequence_step>0
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM threads t
                   JOIN messages m ON m.thread_id=t.id
                   WHERE t.lead_id=l.id AND m.direction='in'
                 )
               ORDER BY d.created_at ASC
               """,
            (cutoff,),
        ).fetchall()

    from core.store import _row_lead

    for row in rows:
        lead = _row_lead(row)
        profile = lead.get("profile") or {}
        try:
            import json
            sent_meta = json.loads(row["first_fit_check"] or "{}")
        except Exception:
            sent_meta = {}
        has_send_snapshot = bool(sent_meta.get("sent_at"))
        if has_send_snapshot:
            recipient = sent_meta.get("recipient_email")
            quality = sent_meta.get("recipient_quality")
        else:
            recipient = pick_recipient(profile)
            quality = ap.get(profile, "email_quality")
        if quality not in allowed_quality:
            continue
        if not is_buyer_contact(recipient, quality):
            continue
        # Для старых писем нет send-time snapshot; разрешаем fallback только
        # если текущий адрес был проверен contact research.
        if has_send_snapshot:
            if not sent_meta.get("recipient_verified"):
                continue
        elif not ap.get(profile, "email_verified"):
            continue
        lead["_first_draft_id"] = row["first_draft_id"]
        lead["_first_subject"] = row["first_subject"]
        lead["_first_sent_at"] = row["first_sent_at"]
        lead["_first_recipient"] = recipient
        lead["_first_quality"] = quality
        result.append(lead)
        if len(result) >= limit:
            break
    return result


def send_due_followups(
    *,
    store: Store | None = None,
    min_days: int = 5,
    allowed_quality: set[str] | None = None,
    limit: int = 2,
    dry_run: bool = False,
) -> dict:
    store = store or Store()
    gate = Gate(store)
    candidates = followup_candidates(
        store,
        min_days=min_days,
        allowed_quality=allowed_quality,
        limit=limit,
    )
    if dry_run:
        return {"candidates": len(candidates), "sent": 0, "failed": 0, "dry_run": True}

    sent = 0
    failed = 0
    for lead in candidates:
        subject = lead.get("_first_subject") or "Сотрудничество — Казанские Деликатесы"
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        body = (
            "Добрый день!\n\n"
            "Возвращаюсь к письму ниже. Подскажите, пожалуйста, кто у вас отвечает "
            "за закупки мясных начинок, замороженной выпечки или СТМ? "
            "Если направление сейчас неактуально, достаточно коротко ответить — "
            "больше напоминать не буду.\n\n"
            f"{_signature()}"
        )
        draft_id = store.create_draft(
            lead["id"],
            "email",
            body,
            subject=subject,
            sequence_step=1,
            sequence_id=lead["_first_draft_id"],
            fit_check={
                "ok": True,
                "can_proceed_to_draft": True,
                "recipient_email": lead["_first_recipient"],
                "recipient_quality": lead["_first_quality"],
                "recipient_verified": True,
            },
            status="draft",
        )
        outbound = gate.process_draft_outbound(
            draft_id,
            actor="followup",
            send_now=True,
            dry_run=dry_run,
        )
        if ((outbound or {}).get("send") or {}).get("ok"):
            sent += 1
        else:
            failed += 1

    store.audit(
        "followup",
        "cycle",
        detail={"candidates": len(candidates), "sent": sent, "failed": failed, "dry_run": dry_run},
    )
    return {"candidates": len(candidates), "sent": sent, "failed": failed}
