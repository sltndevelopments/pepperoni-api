from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.store import Store
from orchestrator.outreach import outreach_candidates
from orchestrator.proactive import run as proactive_run
from workers.followup import followup_candidates
from workers.interest import _escalate_unknown, _unknown_contact, recover_untracked_warm_inbound
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

    def test_followup_requires_quality_age_and_no_reply(self) -> None:
        lead_id = self._lead("Follow Bakery", quality="corporate", status="contacted")
        draft_id = self.store.create_draft(
            lead_id,
            "email",
            "Первое письмо",
            subject="Поставка",
            sequence_step=0,
            status="sent",
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


if __name__ == "__main__":
    unittest.main()
