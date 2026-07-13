from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core import agent_profile as ap
from core.gate import Gate
from core.store import Store
from crm.google_sync import _lead_row_from_db, load_schema
from orchestrator.outreach import outreach_candidates, outreach_diagnostics
from orchestrator.proactive import run as proactive_run
from prospecting.contact_research import label_profile_emails
from prospecting.enrich_contacts import _needs_enrich
from workers.followup import followup_candidates
from workers.interest import (
    _escalate_unknown,
    _unknown_contact,
    recover_untracked_warm_inbound,
    scan_inbox,
)
from workers.escalate import escalate_to_owner
from workers.draft_outreach import draft_cold_email
from workers.triage import triage_inbound


class SalesFunnelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "agent.db")
        self.store.init()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _lead(self, name: str, *, quality: str, tier: str = "B", la: int = 48, status: str = "new") -> str:
        return self.store.upsert_lead(
            name,
            tier=tier,
            fit_score=100,
            status=status,
            profile={
                "emails": f"buyer@{name.lower().replace(' ', '')}.ru",
                "_agent": {
                    "email_best": f"buyer@{name.lower().replace(' ', '')}.ru",
                    "email_quality": quality,
                    "email_verified": True,
                    "lookalike": {"lookalike_score": la},
                },
            },
        )

    def test_outreach_accepts_b_corporate_but_rejects_generic(self) -> None:
        good = self._lead("Good Bakery", quality="corporate")
        self._lead("Generic Bakery", quality="generic")
        self.store.upsert_lead(
            "HR Bakery",
            tier="B",
            fit_score=100,
            status="new",
            profile={
                "emails": "hr@hrbakery.ru",
                "_agent": {
                    "email_best": "hr@hrbakery.ru",
                    "email_quality": "corporate",
                    "lookalike": {"lookalike_score": 48},
                },
            },
        )

        ids = {lead["id"] for lead in outreach_candidates(self.store, limit=20)}

        self.assertEqual(ids, {good})

    def test_imported_email_is_labeled_but_not_verified(self) -> None:
        profile = {"emails": "info@example.ru,buyer@example.ru"}

        self.assertTrue(label_profile_emails(profile))
        self.assertEqual(ap.get(profile, "email_best"), "buyer@example.ru")
        self.assertEqual(ap.get(profile, "email_quality"), "procurement")
        self.assertFalse(ap.get(profile, "email_verified"))

    def test_failed_enrichment_uses_short_retry(self) -> None:
        recent = datetime.now(timezone.utc).isoformat()
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        lead_id = self.store.upsert_lead(
            "Retry Bakery",
            inn="1234567890",
            status="new",
            profile={
                "emails": "info@retry.ru",
                "_agent": {
                    "email_best": "info@retry.ru",
                    "email_quality": "generic",
                    "email_verified": True,
                    "contact_last_attempt_at": recent,
                },
            },
        )
        lead = self.store.get_lead(lead_id)
        self.assertFalse(_needs_enrich(lead))
        lead["profile"]["_agent"]["contact_last_attempt_at"] = old
        self.assertTrue(_needs_enrich(lead))

    def test_cancelled_draft_does_not_block_outreach(self) -> None:
        lead_id = self._lead("Retry Draft Bakery", quality="corporate")
        draft_id = self.store.create_draft(
            lead_id, "email", "old", status="cancelled", sequence_step=0
        )
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        with self.store._conn() as conn:
            conn.execute(
                "UPDATE drafts SET created_at=?, updated_at=? WHERE id=?",
                (old, old, draft_id),
            )

        ids = {lead["id"] for lead in outreach_candidates(self.store, limit=20)}
        self.assertIn(lead_id, ids)
        self.assertEqual(outreach_diagnostics(self.store)["counts"]["eligible"], 1)

    def test_proactive_migrates_old_handoffs_then_notifies_new_once(self) -> None:
        self._lead("Old Priority", quality="corporate", tier="S", la=100, status="hot")
        pushed: list[str] = []
        with patch("orchestrator.proactive._push", side_effect=lambda text: pushed.append(text) or True):
            first = proactive_run(store=self.store)
            self.assertNotIn("priority_handoff", first["fired"])
            self.assertFalse(any("Old Priority" in text for text in pushed))

            self._lead("New Priority", quality="corporate", tier="S", la=100, status="hot")
            second = proactive_run(store=self.store)
            third = proactive_run(store=self.store)

        self.assertIn("priority_handoff", second["fired"])
        self.assertEqual(third["fired"], [])
        self.assertEqual(len([text for text in pushed if "New Priority" in text]), 1)

    def test_supplier_offer_is_not_a_price_request(self) -> None:
        with patch("core.llm.brain_available", return_value=False):
            result = triage_inbound(
                {
                    "id": "m1",
                    "subject": "Информационное коммерческое предложение",
                    "body": "Мы производим барьерные пленки и готовы предложить решения. Вышлите ТЗ.",
                },
                self.store,
            )
        self.assertIn("supplier_offer", result["intents"])
        self.assertNotIn("price_request", result["intents"])
        self.assertEqual(result["temperature"], "cold")

    def test_supplier_commercial_offer_without_product_terms_stays_cold(self) -> None:
        with patch("core.llm.brain_available", return_value=False):
            result = triage_inbound(
                {
                    "id": "m2",
                    "subject": "Коммерческое предложение",
                    "body": "Направляем коммерческое предложение, наш прайс во вложении.",
                },
                self.store,
            )
        self.assertIn("supplier_offer", result["intents"])
        self.assertNotIn("price_request", result["intents"])
        self.assertEqual(result["temperature"], "cold")

    def test_live_inbox_supplier_offer_is_analytics_only(self) -> None:
        message_id = self.store.add_inbound(
            "email",
            "Направляем коммерческое предложение, наш прайс во вложении.",
            meta={"from": "seller@example.ru"},
        )
        with patch("core.llm.brain_available", return_value=False), patch(
            "workers.interest.escalate_to_owner"
        ) as escalate:
            result = scan_inbox(self.store)
        self.assertEqual(result, [])
        escalate.assert_not_called()
        message = next(m for m in self.store.inbox(10) if m["id"] == message_id)
        self.assertIn('"analytics_only": true', message["meta"])

    def test_unknown_warm_inbound_becomes_persistent_lead(self) -> None:
        body = (
            "Нас заинтересовала ваша продукция. Мы сеть ресторанов Чизерия.\n"
            "Пришлите прайс. Телефон 89178513364, Ольга."
        )
        contact = _unknown_contact(body, {"meta": '{"from":"olga@example.ru"}'})
        self.assertEqual(contact["company"], "Чизерия")
        self.assertEqual(contact["email"], "olga@example.ru")

        with patch(
            "workers.interest.escalate_to_owner",
            return_value={"ok": True, "telegram_sent": 1},
        ):
            result = _escalate_unknown(
                body,
                "входящее: price_request · warm",
                {"intents": ["price_request"], "temperature": "warm"},
                self.store,
                message={"meta": '{"from":"olga@example.ru"}'},
            )

        lead = self.store.get_lead(result["lead_id"])
        self.assertIsNotNone(lead)
        self.assertEqual(lead["source"], "inbound")
        self.assertTrue(lead["profile"]["interest_confirmed"])

    def test_unknown_contact_accepts_single_restaurant_name(self) -> None:
        contact = _unknown_contact(
            "Ресторан Чизерия, пришлите прайс. Телефон 89178513364",
            {"meta": '{"from":"olga@example.ru"}'},
        )
        self.assertEqual(contact["company"], "Чизерия")

    def test_followup_requires_quality_age_and_no_reply(self) -> None:
        lead_id = self._lead("Follow Bakery", quality="corporate", status="contacted")
        draft_id = self.store.create_draft(
            lead_id,
            "email",
            "Первое письмо",
            subject="Поставка",
            sequence_step=0,
            status="sent",
            fit_check={
                "ok": True,
                "recipient_email": "legacy-field@example.ru",
                "recipient_quality": "corporate",
            },
        )
        old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        with self.store._conn() as conn:
            conn.execute("UPDATE drafts SET created_at=? WHERE id=?", (old, draft_id))

        self.assertEqual(len(followup_candidates(self.store, min_days=5)), 1)

        self.store.add_inbound("email", "Спасибо, неактуально", lead_id=lead_id)
        self.assertEqual(followup_candidates(self.store, min_days=5), [])

    def test_recover_old_warm_inbound_skips_supplier_offer(self) -> None:
        warm_id = self.store.add_inbound(
            "email_info",
            "Мы сеть ресторанов Чизерия. Хотим сотрудничать, пришлите прайс. 89178513364",
            meta={"from": "olga@example.ru", "interest_scanned": True},
        )
        self.store.add_inbound(
            "email_info",
            "Мы производим упаковочную пленку и готовы предложить коммерческое предложение.",
            meta={"from": "supplier@example.ru", "interest_scanned": True},
        )
        self.store.add_inbound(
            "email_info",
            "Из Тюмени\nпятница, 10 июля от Казанские Деликатесы\nА можно по прайс?",
            meta={"from": "reply@example.ru", "interest_scanned": True},
        )
        with patch(
            "workers.interest.escalate_to_owner",
            return_value={"ok": True, "telegram_sent": 1},
        ):
            recovered = recover_untracked_warm_inbound(self.store)

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["message_id"], warm_id)

    def test_recover_retries_stale_missing_lead_reference(self) -> None:
        message_id = self.store.add_inbound(
            "email_info",
            "Мы сеть ресторанов Чизерия. Хотим сотрудничать, пришлите прайс. 89178513364",
            meta={
                "from": "olga@example.ru",
                "interest_scanned": True,
                "warm_lead_recovered": True,
                "recovered_lead_id": "missing-lead",
            },
        )
        with patch(
            "workers.interest.escalate_to_owner",
            return_value={"ok": True, "telegram_sent": 1},
        ):
            recovered = recover_untracked_warm_inbound(self.store)

        self.assertEqual([item["message_id"] for item in recovered], [message_id])
        self.assertIsNotNone(self.store.get_lead(recovered[0]["lead_id"]))

    def test_direct_escalation_marks_proactive_handoff_seen(self) -> None:
        lead_id = self._lead("Interested Bakery", quality="corporate")
        with patch("telegram.notify.notify", return_value=1), patch(
            "workers.forward_important.forward_to_owner",
            return_value={"ok": True},
        ):
            result = escalate_to_owner(
                lead_id,
                "входящий прайс",
                store=self.store,
                confirmed_interest=True,
            )

        self.assertTrue(result["interest_confirmed"])
        self.assertFalse(
            self.store.should_notify(
                f"proactive:handoff:{lead_id}:interest",
                "seen",
                cooldown_hours=0,
            )
        )

    def test_escalation_uses_canonical_namespace_and_deduplicates(self) -> None:
        lead_id = self._lead("Canonical Bakery", quality="corporate")
        with patch("telegram.notify.notify", return_value=1), patch(
            "workers.forward_important.forward_to_owner",
            return_value={"ok": True},
        ):
            first = escalate_to_owner(lead_id, "крупная компания", store=self.store)
            second = escalate_to_owner(lead_id, "повтор", store=self.store)

        profile = self.store.get_lead(lead_id)["profile"]
        self.assertTrue(first["ok"])
        self.assertEqual(second["skipped"], "already_escalated")
        self.assertTrue(ap.get(profile, "owner_escalated_at"))
        self.assertEqual(ap.get(profile, "escalation_reason"), "крупная компания")

        crm_row = _lead_row_from_db(self.store.get_lead(lead_id), load_schema())
        schema = load_schema()
        keys = [c["key"] for c in schema["tabs"]["leads"]["columns"]]
        self.assertEqual(crm_row[keys.index("escalation_reason")], "крупная компания")

    def test_legacy_escalation_fields_migrate_before_crm_pull(self) -> None:
        profile = {
            "escalated_at": "2026-07-01T10:00:00+00:00",
            "escalation_reason": "старый handoff",
            "owner_escalated_at": "2026-07-01T10:00:00+00:00",
        }
        ap.migrate_legacy(profile)

        self.assertEqual(ap.get(profile, "escalation_reason"), "старый handoff")
        self.assertTrue(ap.is_escalated(profile))

    def test_inbound_source_survives_crm_refresh(self) -> None:
        lead_id = self.store.upsert_lead(
            "Входящий лид: Чизерия", source="inbound", status="replied"
        )
        self.store.upsert_lead(
            "Входящий лид: Чизерия",
            lead_id=lead_id,
            source="crm_sheet_api",
            status="new",
        )
        self.assertEqual(self.store.get_lead(lead_id)["source"], "inbound")

    def test_successful_send_persists_recipient_snapshot(self) -> None:
        lead_id = self._lead("Snapshot Bakery", quality="corporate")
        draft_id = self.store.create_draft(
            lead_id,
            "email",
            "Первое письмо",
            subject="Поставка",
            status="approved",
            fit_check={"ok": True, "can_proceed_to_draft": True},
        )
        with patch("channels.email.send_email", return_value={"ok": True}):
            result = Gate(self.store)._send_one_draft(draft_id)

        self.assertTrue(result["ok"])
        fit = self.store.get_draft(draft_id)["fit_check"]
        self.assertEqual(fit["recipient_email"], "buyer@snapshotbakery.ru")
        self.assertEqual(fit["recipient_quality"], "corporate")
        self.assertTrue(fit["sent_at"])
        self.assertTrue(fit["track_token"])

    def test_cold_draft_dry_run_never_calls_smtp(self) -> None:
        lead_id = self._lead("Dry Run Bakery", quality="corporate", tier="B", la=48)
        with patch(
            "workers.draft_outreach._llm_draft",
            return_value=("Тест", "Безопасный тестовый текст"),
        ), patch("core.auto_gate.brain_available", return_value=False), patch(
            "channels.email.send_email"
        ) as send:
            result = draft_cold_email(
                lead_id,
                store=self.store,
                auto_submit=True,
                dry_run=True,
            )

        send.assert_not_called()
        self.assertTrue(result["outbound"]["send"]["dry_run"])
        self.assertNotEqual(self.store.get_draft(result["draft_id"])["status"], "sent")

    def test_cycle_dry_run_has_no_external_actions(self) -> None:
        cycle_module = importlib.import_module("orchestrator.run_cycle")
        with patch.object(cycle_module, "Store", return_value=self.store), patch.object(
            cycle_module, "apply_lookalike_scores"
        ) as lookalike, patch(
            "channels.imap_inbox.fetch_inbox"
        ) as fetch_mail, patch(
            "prospecting.bounce_recovery.recover"
        ) as bounce, patch(
            "workers.named_escalation.escalate_named_targets"
        ) as named, patch(
            "crm.google_sync.crm_sync"
        ) as crm, patch(
            "orchestrator.proactive.run"
        ) as proactive:
            result = cycle_module.run_cycle(dry_run_send=True, max_drafts=3)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["external_actions"], 0)
        lookalike.assert_not_called()
        fetch_mail.assert_not_called()
        bounce.assert_not_called()
        named.assert_not_called()
        crm.assert_not_called()
        proactive.assert_not_called()


if __name__ == "__main__":
    unittest.main()
