from __future__ import annotations

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
from model import PIPELINE, STATUSES, TERMINAL
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
        # idempotent
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
        tos = [__import__("json").loads(e["detail"]).get("to") for e in events if e["action"] == "status"]
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
        with patch("scheduler.send_to_work_chat", return_value=1) as to_work, patch(
            "scheduler._broadcast", return_value=1
        ) as broadcast:
            r1 = check_72h_distributor(self.store)
            self.assertEqual(r1["arbi_alerts"], 1)
            # сразу повтор — не дублируем
            r2 = check_72h_distributor(self.store)
            self.assertEqual(r2["arbi_alerts"], 0)
            # состарить пинг на 25ч → владелец
            self.store.set_meta(
                f"stuck72:{lead['id']}",
                (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
            )
            r3 = check_72h_distributor(self.store)
            self.assertEqual(r3["owner_alerts"], 1)
        self.assertEqual(to_work.call_count, 1)
        self.assertGreaterEqual(broadcast.call_count, 1)

    def test_digest_contains_sections(self) -> None:
        lead = self.store.create_lead(source="call", company="A")
        self.store.set_status(lead["id"], "contacted")
        text = build_weekly_digest(self.store)
        self.assertIn("ОТЧЁТ ЗА НЕДЕЛЮ", text)
        self.assertIn("ЗАСТРЯЛО", text)
        self.assertIn("КОНВЕРСИЯ", text)
        self.assertIn("Пришло новых", text)


if __name__ == "__main__":
    unittest.main()
