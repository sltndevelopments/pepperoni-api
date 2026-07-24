from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from digest import build_weekly_digest
from ingest import ingest_text, parse_card
from keyboards import distributor_keyboard, lost_keyboard, main_keyboard
from model import (
    PIPELINE,
    POINT_STATUS_ACTIVE,
    POINT_STATUS_AT_RISK,
    POINT_STATUS_CHURNED,
    STATUSES,
    TERMINAL,
    format_actor,
    point_status_from_last_order,
)
from scheduler import check_72h_distributor
from store import Store


CALL_CARD = """📞 Новая заявка — Казанские Деликатесы

Тип: 🛒 Хочет купить продукцию
Компания: Пицца Рулит
Контакт: Иван
Телефон: +7 999 111-22-33
Город: Москва
Запрос: халяльная пепперони
Объём: 50 кг/нед

ID звонка: CA123abc
"""


class MoscowLeadsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")
        self.store.init()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_all_required_statuses_present(self) -> None:
        required = {
            "new", "contacted", "samples_sent", "meeting_done",
            "passed_to_distributor", "first_shipment", "repeat_shipment",
            "won", "lost", "no_demand",
        }
        self.assertTrue(required.issubset(set(STATUSES)))
        self.assertEqual(PIPELINE[0], "new")
        self.assertIn("lost", TERMINAL)

    def test_ingest_call_card(self) -> None:
        lead = ingest_text(CALL_CARD, store=self.store)
        self.assertIsNotNone(lead)
        self.assertEqual(lead["status"], "new")
        self.assertEqual(lead["source"], "call")
        self.assertEqual(lead["company"], "Пицца Рулит")
        self.assertTrue(lead["id"].startswith("LEAD-"))
        again = ingest_text(CALL_CARD, store=self.store)
        self.assertEqual(again["id"], lead["id"])

    def test_site_form_card(self) -> None:
        text = (
            "🌐 Заявка с сайта (форма)\n"
            "Имя: Ольга\n"
            "Телефон: +79991234567\n"
            "Сообщение: нужен прайс на пепперони\n"
        )
        parsed = parse_card(text)
        self.assertEqual(parsed["source"], "site")
        lead = ingest_text(text, store=self.store)
        self.assertEqual(lead["contact"], "Ольга")

    def test_full_path_new_to_first_shipment(self) -> None:
        lead = self.store.create_lead(
            source="manual", company="Тест", city="Москва", request="пепперони"
        )
        lid = lead["id"]
        for st, kw in [
            ("contacted", {}),
            ("samples_sent", {}),
            ("meeting_done", {}),
            ("passed_to_distributor", {"distributor": "GFC"}),
            ("first_shipment", {}),
        ]:
            lead = self.store.set_status(lid, st, **kw)
            self.assertEqual(lead["status"], st)
        events = self.store.events(lid)
        tos = [json.loads(e["detail"]).get("to") for e in events if e["action"] == "status"]
        self.assertEqual(
            tos,
            ["contacted", "samples_sent", "meeting_done", "passed_to_distributor", "first_shipment"],
        )

    def test_inline_keyboards_callback_prefix(self) -> None:
        kb = main_keyboard(42)
        flat = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
        self.assertTrue(any(c == "ml:42:contacted" for c in flat))
        self.assertTrue(any(c == "ml:42:dist_menu" for c in flat))
        self.assertTrue(any(c == "ml:42:lost_menu" for c in flat))
        dist = distributor_keyboard(42)
        dflat = [b["callback_data"] for row in dist["inline_keyboard"] for b in row]
        self.assertIn("ml:42:dist:GFC", dflat)
        self.assertIn("ml:42:dist:SweetLife", dflat)
        lost = lost_keyboard(42)
        lflat = [b["callback_data"] for row in lost["inline_keyboard"] for b in row]
        self.assertIn("ml:42:lost:price", lflat)

    def test_72h_alerts_arbi_then_owner(self) -> None:
        lead = self.store.create_lead(source="manual", company="Stuck Co")
        old = (datetime.now(timezone.utc) - timedelta(hours=80)).isoformat()
        with self.store._conn() as conn:
            conn.execute(
                "UPDATE leads SET status='passed_to_distributor', distributor='GFC', "
                "status_changed_at=?, updated_at=? WHERE id=?",
                (old, old, lead["id"]),
            )
        with patch("scheduler.send_to_arbi", return_value=1) as to_arbi, patch(
            "scheduler._broadcast", return_value=1
        ) as broadcast:
            r1 = check_72h_distributor(self.store)
            self.assertEqual(r1["arbi_alerts"], 1)
            r2 = check_72h_distributor(self.store)
            self.assertEqual(r2["arbi_alerts"], 0)
            self.store.set_meta(
                f"stuck72:{lead['id']}",
                (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
            )
            r3 = check_72h_distributor(self.store)
            self.assertEqual(r3["owner_alerts"], 1)
        self.assertEqual(to_arbi.call_count, 1)
        self.assertGreaterEqual(broadcast.call_count, 1)

    def test_digest_contains_akb_sections(self) -> None:
        lead = self.store.create_lead(source="call", company="A")
        self.store.set_status(lead["id"], "contacted")
        text = build_weekly_digest(self.store)
        self.assertIn("ОТЧЁТ ЗА НЕДЕЛЮ", text)
        self.assertIn("АКБ", text)
        self.assertIn("ЗОНА РИСКА", text)
        self.assertIn("SELL-OUT", text)
        self.assertIn("ЗАСТРЯЛО", text)
        self.assertEqual(POINT_STATUS_CHURNED, "churned")

    def test_point_status_lifecycle(self) -> None:
        now = datetime(2026, 7, 23, tzinfo=timezone.utc)
        active_at = (now - timedelta(days=10)).isoformat()
        risk_at = (now - timedelta(days=35)).isoformat()
        churn_at = (now - timedelta(days=70)).isoformat()
        self.assertEqual(point_status_from_last_order(active_at, now=now), POINT_STATUS_ACTIVE)
        self.assertEqual(point_status_from_last_order(risk_at, now=now), POINT_STATUS_AT_RISK)
        self.assertEqual(point_status_from_last_order(churn_at, now=now), POINT_STATUS_CHURNED)

        lead = self.store.create_lead(
            source="manual", company="Пицца Тест", city="Москва", request="пепперони"
        )
        self.store.set_status(lead["id"], "contacted", actor="telegram:1:test")
        self.store.set_status(lead["id"], "meeting_done", actor="telegram:1:test")
        self.store.set_status(
            lead["id"], "passed_to_distributor", distributor="GFC", actor="telegram:1:test"
        )
        lead = self.store.set_status(
            lead["id"], "first_shipment", actor="telegram:1:test"
        )
        point = self.store.find_point_by_name("Пицца Тест", "Москва")
        self.assertIsNotNone(point)
        self.assertEqual(point["status"], POINT_STATUS_ACTIVE)
        self.assertGreaterEqual(point["orders_count"], 1)

        # состарить last_order → at_risk
        with self.store._conn() as conn:
            conn.execute(
                "UPDATE points SET last_order_at=?, first_order_at=? WHERE id=?",
                (risk_at, risk_at, point["id"]),
            )
        point = self.store.get_point(point["id"])
        # get_point uses utcnow — force via helper
        st = point_status_from_last_order(point["last_order_at"], now=now)
        self.assertEqual(st, POINT_STATUS_AT_RISK)

    def test_sellout_and_contact_log(self) -> None:
        p = self.store.create_point(
            name="Шаурма №1", segment="фастфуд", city="Москва", distributor="GFC"
        )
        rec = self.store.log_contact(
            contact_type="visit",
            result="order",
            actor="telegram:42:arbi",
            point_id=p["id"],
        )
        self.assertTrue(rec["productive"])
        p2 = self.store.get_point(p["id"])
        self.assertEqual(p2["status"], POINT_STATUS_ACTIVE)
        self.assertEqual(p2["orders_count"], 1)

        so = self.store.upsert_sellout(
            distributor="GFC", month="2026-06", kg=1200, points_count=18, actor="telegram:42:arbi"
        )
        self.assertEqual(so["kg"], 1200)
        text = build_weekly_digest(self.store)
        self.assertIn("GFC", text)
        self.assertIn("1200", text)

    def test_format_actor_from_user(self) -> None:
        self.assertEqual(
            format_actor({"id": 123, "username": "arbi_msk"}),
            "telegram:123:arbi_msk",
        )
        self.assertEqual(format_actor({"id": 1}), "telegram:1:noname")
        self.assertEqual(format_actor(None), "telegram")

    def test_allowed_user_ids_constant_exists(self) -> None:
        from tg import ALLOWED_USER_IDS, user_allowed
        self.assertTrue(hasattr(sys.modules["tg"], "ALLOWED_USER_IDS"))
        # пустой список = все разрешены
        self.assertTrue(user_allowed(999999))


if __name__ == "__main__":
    unittest.main()
