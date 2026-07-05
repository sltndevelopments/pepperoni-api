"""
Жёсткий гейт перед всем исходящим.

Внутреннее (обогащение, скоринг, черновики) — свободно.
Необратимое (email, WA, TG, тендер, звонок-задача) — только через approvals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from . import env as _env  # noqa: F401
from .store import Store
from .types import GateAction, INTERNAL_ACTIONS

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CAPABILITIES_PATH = ROOT / "config" / "capabilities.yaml"


class Gate:
    def __init__(self, store: Store | None = None):
        self.store = store or Store()
        self._capabilities = self._load_capabilities()

    def _load_capabilities(self) -> dict:
        try:
            return yaml.safe_load(CAPABILITIES_PATH.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def is_outbound(self, action: str) -> bool:
        return action not in INTERNAL_ACTIONS

    def check_fit(self, requested_products: list[str], lead_context: str = "") -> dict:
        """
        Сверка запроса клиента с матрицей can/cannot.
        Возвращает {ok, blocked_reasons, matched_can, score_adjustment}.
        """
        text = " ".join(requested_products + [lead_context]).lower()
        blocked = []
        matched = []

        for item in self._capabilities.get("cannot_produce", []):
            for kw in item.get("keywords", []):
                if kw.lower() in text:
                    blocked.append({"id": item["id"], "label": item["label"], "reason": item.get("reason", "")})

        for item in self._capabilities.get("can_produce", []):
            for kw in item.get("keywords", []):
                if kw.lower() in text:
                    matched.append({"id": item["id"], "label": item["label"]})
                    break

        ok = len(blocked) == 0
        score_adj = 20 * len(matched) - 50 * len(blocked)
        min_fit = (self._capabilities.get("scoring") or {}).get("min_fit_for_draft", 60)

        return {
            "ok": ok,
            "blocked_reasons": blocked,
            "matched_can": matched,
            "score_adjustment": score_adj,
            "min_fit_for_draft": min_fit,
            "can_proceed_to_draft": ok and score_adj >= 0,
        }

    def process_draft_outbound(
        self,
        draft_id: str,
        *,
        actor: str = "agent",
        send_now: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """
        Автономный гейт: Opus → send / escalate / hold.
        send: авто-аппрув и отправка (без участия человека).
        escalate: контакты владельцу, письмо не уходит.
        """
        from core.auto_gate import decide_outbound
        from core.autonomy import is_autonomous, load_autonomy
        from workers.escalate import escalate_to_owner

        draft = self.store.get_draft(draft_id)
        if not draft:
            return {"ok": False, "error": "draft_not_found"}

        lead = self.store.get_lead(draft["lead_id"]) or {}
        fit = draft.get("fit_check") or {}

        if not is_autonomous():
            aid = self.submit_draft_for_approval(draft_id, actor=actor)
            return {"ok": bool(aid), "action": "manual_approval", "approval_id": aid}

        decision = decide_outbound(draft, lead, fit)
        action = decision.get("action", "hold")
        self.store.audit(actor, f"auto_gate_{action}", "draft", draft_id, decision)

        if action == "escalate":
            self.store.update_draft_status(draft_id, "cancelled")
            esc = escalate_to_owner(
                draft["lead_id"],
                decision.get("reason", "opus escalate"),
                context=(draft.get("subject") or "") + "\n" + (draft.get("body") or "")[:400],
                store=self.store,
            )
            return {"ok": True, "action": "escalate", "decision": decision, "escalation": esc}

        if action == "hold":
            cfg = load_autonomy()
            if cfg.get("manual_hold", {}).get("enabled"):
                aid = self.submit_draft_for_approval(draft_id, actor=actor)
                return {"ok": True, "action": "hold", "approval_id": aid, "decision": decision}
            self.store.update_draft_status(draft_id, "cancelled")
            return {"ok": True, "action": "hold", "cancelled": True, "decision": decision}

        # send — авто-аппрув Opus
        channel = draft.get("channel", "email")
        action_map = {
            "email": GateAction.SEND_EMAIL.value,
            "whatsapp": GateAction.SEND_WHATSAPP.value,
            "telegram": GateAction.SEND_TELEGRAM.value,
            "phone_task": GateAction.CREATE_PHONE_TASK.value,
        }
        gate_action = action_map.get(channel, GateAction.SEND_EMAIL.value)
        title = f"[auto] {channel}: {draft.get('lead_name', '?')}"
        payload = {
            "draft_id": draft_id,
            "auto": True,
            "decision": decision,
        }
        approval_id = self.store.create_approval(
            draft_id, gate_action, title,
            decision.get("reason", ""),
            payload,
        )
        decided_by = decision.get("decided_by", "opus")
        self.approve(approval_id, decided_by=decided_by)

        result = {"ok": True, "action": "send", "decision": decision, "approval_id": approval_id}
        if send_now:
            sent = self._send_one_draft(draft_id, dry_run=dry_run)
            result["send"] = sent
        return result

    def submit_draft_for_approval(
        self,
        draft_id: str,
        *,
        actor: str = "agent",
    ) -> str | None:
        """Черновик → очередь аппрува. Возвращает approval_id."""
        draft = self.store.get_draft(draft_id)
        if not draft:
            return None

        channel = draft["channel"]
        action_map = {
            "email": GateAction.SEND_EMAIL.value,
            "whatsapp": GateAction.SEND_WHATSAPP.value,
            "telegram": GateAction.SEND_TELEGRAM.value,
            "phone_task": GateAction.CREATE_PHONE_TASK.value,
        }
        action = action_map.get(channel, GateAction.SEND_EMAIL.value)

        fit = draft.get("fit_check") or {}
        if fit and not fit.get("ok", True):
            self.store.audit(actor, "gate_blocked", "draft", draft_id, {
                "reason": "fit_check_failed",
                "blocked": fit.get("blocked_reasons"),
            })
            self.store.update_draft_status(draft_id, "cancelled")
            return None

        title = f"{channel}: {draft.get('lead_name', '?')}"
        detail = (draft.get("subject") or "")[:200]
        payload = {
            "draft_id": draft_id,
            "lead_id": draft["lead_id"],
            "channel": channel,
            "subject": draft.get("subject"),
            "body_preview": (draft.get("body") or "")[:500],
        }

        approval_id = self.store.create_approval(draft_id, action, title, detail, payload)
        self.store.audit(actor, "submitted_for_approval", "approval", approval_id, payload)
        self._notify_telegram(title, detail, draft_id)
        return approval_id

    def approve(self, approval_id: str, *, decided_by: str = "human") -> dict | None:
        result = self.store.decide_approval(approval_id, True, decided_by)
        if result:
            self.store.audit(decided_by, "approved", "approval", approval_id)
        return result

    def reject(self, approval_id: str, *, decided_by: str = "human", reason: str = "") -> dict | None:
        result = self.store.decide_approval(approval_id, False, decided_by)
        if result:
            self.store.audit(decided_by, "rejected", "approval", approval_id, {"reason": reason})
        return result

    def _send_one_draft(self, draft_id: str, *, dry_run: bool = False) -> dict:
        draft = self.store.get_draft(draft_id)
        if not draft or draft.get("status") not in ("approved",):
            # may already be sent
            if draft and draft.get("status") == "sent":
                return {"ok": True, "already_sent": True}
            return {"ok": False, "error": "draft_not_approved"}

        from channels.email import pick_recipient, send_email

        record = {
            "draft_id": draft_id,
            "channel": draft.get("channel"),
            "lead_id": draft.get("lead_id"),
            "dry_run": dry_run,
        }
        if dry_run:
            self.store.audit("gate", "would_send", "draft", draft_id, record)
            return record

        channel = draft.get("channel", "")
        if channel == "email":
            lead = self.store.get_lead(draft["lead_id"]) or {}
            to = pick_recipient(lead.get("profile") or {})
            if not to:
                record["error"] = "no_recipient_email"
                self.store.audit("gate", "send_failed", "draft", draft_id, record)
                return record
            try:
                track_token = self.store.create_email_open_token(draft_id, draft.get("lead_id"))
            except Exception:
                track_token = None
            result = send_email(
                to,
                draft.get("subject") or "Сотрудничество — Казанские Деликатесы",
                draft.get("body") or "",
                dry_run=False,
                track_token=track_token,
            )
            record.update(result)
            if result.get("ok"):
                self.store.mark_draft_sent(draft_id)
                self.store.audit("gate", "sent", "draft", draft_id, record)
                try:
                    self.store.add_outbound(
                        draft.get("lead_id"), "email",
                        draft.get("body") or "",
                        subject=draft.get("subject"),
                        meta={"draft_id": draft_id},
                    )
                except Exception as e:
                    self.store.audit("gate", "outbound_log_failed", "draft", draft_id, {"error": str(e)[:200]})
                if (lead.get("status") or "new") == "new":
                    self.store.upsert_lead(
                        lead["name"],
                        lead_id=lead["id"],
                        status="contacted",
                        inn=lead.get("inn"),
                        region=lead.get("region"),
                        tier=lead.get("tier"),
                        fit_score=lead.get("fit_score") or 0,
                        source=lead.get("source"),
                        profile=lead.get("profile"),
                    )
            else:
                self.store.audit("gate", "send_failed", "draft", draft_id, record)
            return record

        if channel == "phone_task":
            record["note"] = "phone_task_created"
            self.store.mark_draft_sent(draft_id)
            self.store.audit("gate", "phone_task", "draft", draft_id, record)
            return record

        record["error"] = f"channel_not_wired:{channel}"
        self.store.audit("gate", "send_skipped", "draft", draft_id, record)
        return record

    def execute_approved(self, *, dry_run: bool = True) -> list[dict]:
        """Остаточная очередь (ручной hold). Автономный режим шлёт в process_draft_outbound."""
        approved = self.store.take_approved_for_send()
        executed = []
        for draft in approved:
            r = self._send_one_draft(draft["id"], dry_run=dry_run)
            executed.append(r)
        return executed

    def _notify_telegram(self, title: str, detail: str, draft_id: str) -> None:
        try:
            from telegram.notify import notify
            n = notify(
                f"<b>📤 Нужен аппрув</b>\n{title}\n<i>{detail[:300]}</i>\n\n"
                f"draft: <code>{draft_id}</code>\n"
                f"Ответь в @KDSalesManagerBot: <code>одобрить 1</code>"
            )
            if not n:
                print("[gate] telegram notify: no recipients yet — log into @KDSalesManagerBot")
        except Exception as e:
            print(f"[gate] telegram notify failed: {e}")
