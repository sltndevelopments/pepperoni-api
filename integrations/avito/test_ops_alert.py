import unittest
from unittest.mock import MagicMock

from integrations.avito.worker import OpsAlert


class OpsAlertTest(unittest.TestCase):
    def test_blip_under_five_minutes_is_silent(self) -> None:
        clock = {"t": 0.0}
        tg = MagicMock()
        alert = OpsAlert(tg, now=lambda: clock["t"], hold_seconds=300)
        alert.note_failure("HTTP 500")
        clock["t"] = 299
        alert.note_failure("HTTP 500")
        alert.note_success()
        tg.send.assert_not_called()

    def test_down_after_hold_then_one_recovery(self) -> None:
        clock = {"t": 1000.0}
        tg = MagicMock()
        alert = OpsAlert(tg, now=lambda: clock["t"], hold_seconds=300)
        alert.note_failure("HTTP 500")
        clock["t"] = 1299
        alert.note_failure("HTTP 500")
        tg.send.assert_not_called()
        clock["t"] = 1300
        alert.note_failure("HTTP 500")
        tg.send.assert_called_once()
        self.assertIn("затупил", tg.send.call_args[0][0])
        clock["t"] = 1400
        alert.note_failure("HTTP 500")
        tg.send.assert_called_once()
        alert.note_success()
        self.assertEqual(tg.send.call_count, 2)
        self.assertIn("ожил", tg.send.call_args[0][0])
        alert.note_success()
        self.assertEqual(tg.send.call_count, 2)

    def test_new_blip_after_recovery_stays_silent(self) -> None:
        clock = {"t": 0.0}
        tg = MagicMock()
        alert = OpsAlert(tg, now=lambda: clock["t"], hold_seconds=300)
        alert.note_failure("HTTP 500")
        clock["t"] = 300
        alert.note_failure("HTTP 500")
        clock["t"] = 400
        alert.note_success()
        clock["t"] = 410
        alert.note_failure("HTTP 500")
        clock["t"] = 500
        alert.note_success()
        self.assertEqual(tg.send.call_count, 2)


if __name__ == "__main__":
    unittest.main()
