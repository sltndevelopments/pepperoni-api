#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import experiment_registry
import fix_attempts
import notification_router
import outcome_tracker
import repair_outcomes
import seo_brain
import strategy_control
import worker_tick_notify


class StrategyContractTests(unittest.TestCase):
    def valid_strategy(self) -> dict:
        return {
            "focus_products": [],
            "focus_langs": ["ru", "en"],
            "geo_daily_target": 0,
            "blog_weekly_target": 0,
            "new_blog_topics": [],
            "pl_oem_topics": [],
            "questions": [],
            "proactive_message": "",
            "notes": "repair",
            "report_to_owner": "No new work.",
        }

    def test_valid_contract_and_incomplete_fail_closed(self):
        valid = self.valid_strategy()
        self.assertEqual([], seo_brain.strategy_contract_errors(valid))
        valid.pop("geo_daily_target")
        self.assertTrue(seo_brain.strategy_contract_errors(valid))

    def test_executor_coverage(self):
        accepted = set(seo_brain.STRATEGY_SCHEMA["properties"])
        classified = (
            seo_brain.STRATEGY_CONSUMED_FIELDS
            | seo_brain.STRATEGY_ENGINEERING_FIELDS
        )
        self.assertEqual(accepted, classified)


class ControlPlaneTests(unittest.TestCase):
    def test_repair_mode_blocks_generation(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            state = base / "operator_state.json"
            strategy = base / "strategy.json"
            experiments = base / "operator_experiments.json"
            state.write_text(json.dumps({"mode": "repair"}))
            strategy.write_text(json.dumps({"generated_at": "2099-01-01T00:00:00+00:00"}))
            experiments.write_text("[]")
            with (
                mock.patch.object(strategy_control, "STATE", state),
                mock.patch.object(strategy_control, "STRATEGY", strategy),
                mock.patch.object(strategy_control, "EXPERIMENTS", experiments),
                mock.patch.object(strategy_control, "gsc_age_days", return_value=0),
            ):
                allowed, blockers = strategy_control.generation_allowed()
            self.assertFalse(allowed)
            self.assertTrue(any("mode=repair" in b for b in blockers))

    def test_both_cron_contours_gate_before_generators(self):
        worker = (ROOT / "scripts/seo-worker.sh").read_text()
        daily = (ROOT / "scripts/seo-agent-vps.sh").read_text()
        for source in (worker, daily):
            gate = source.index("strategy_control.py --check-generation")
            self.assertLess(gate, source.index("generate_from_strategy.py"))
            self.assertLess(gate, source.index("generate_geo_bulk.py"))
        geo = (ROOT / "scripts/generate_geo_bulk.py").read_text()
        self.assertIn('geo_daily_target", "")).strip() == "0"', geo)


class ExperimentRegistryTests(unittest.TestCase):
    def test_dedupe_and_three_active_limit(self):
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "experiments.json"
            registry.write_text("[]")
            with mock.patch.object(experiment_registry, "REGISTRY", registry):
                first = experiment_registry.start(
                    query="pepperoni", page="/pepperoni",
                    hypothesis="CTR improves", change_type="title_meta",
                    baseline={"ctr": 0.01},
                )
                self.assertTrue(first["baseline"])
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    experiment_registry.start(
                        query="PEPPERONI", page="https://pepperoni.tatar/pepperoni/",
                        hypothesis="other", change_type="cta",
                    )
                for n in (2, 3):
                    experiment_registry.start(
                        query=f"q{n}", page=f"/p{n}",
                        hypothesis="h", change_type="internal_links",
                    )
                with self.assertRaisesRegex(ValueError, "limit"):
                    experiment_registry.start(
                        query="q4", page="/p4",
                        hypothesis="h", change_type="cta",
                    )

    def test_query_position_is_page_specific(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE gsc_queries "
            "(date TEXT, query TEXT, page TEXT, position REAL, impressions INTEGER)"
        )
        conn.execute(
            "INSERT INTO gsc_queries VALUES "
            "(date('now'), 'pepperoni', '/a', 5, 10)"
        )
        conn.execute(
            "INSERT INTO gsc_queries VALUES "
            "(date('now'), 'pepperoni', '/b', 50, 100)"
        )
        pos, impressions = outcome_tracker._current_pos(conn, "pepperoni", "/a")
        conn.close()
        self.assertEqual((5.0, 10), (pos, impressions))

    def test_same_failure_is_counted_once(self):
        with tempfile.TemporaryDirectory() as td:
            attempts = Path(td) / "fix_attempts.json"
            with mock.patch.object(fix_attempts, "ATTEMPTS_FILE", attempts):
                first = fix_attempts.increment(
                    "pepperoni halal", "not_indexed", failure_id="exp-1"
                )
                second = fix_attempts.increment(
                    "pepperoni halal", "not_indexed", failure_id="exp-1"
                )
            self.assertEqual(1, first["attempts"])
            self.assertEqual(1, second["attempts"])

    def test_repair_mode_does_not_create_repair_actions(self):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td)
            outcomes = data / "outcomes.json"
            outcomes.write_text(json.dumps({
                "failing": [{
                    "query": "pepperoni halal",
                    "page": "https://pepperoni.tatar/pepperoni",
                    "verdict": "not_indexed",
                }]
            }))
            (data / "operator_state.json").write_text(json.dumps({"mode": "repair"}))
            with (
                mock.patch.object(repair_outcomes, "DATA", data),
                mock.patch.object(repair_outcomes, "OUTCOMES", outcomes),
            ):
                result = repair_outcomes.repair()
            self.assertEqual(1, result["repair_mode_skipped"])
            self.assertEqual(0, result["queued_for_fable"])


class NotificationTests(unittest.TestCase):
    def test_empty_worker_tick_sends_nothing(self):
        with (
            mock.patch.object(worker_tick_notify, "_gate_since",
                              return_value={"pass": 0, "reject": 0, "hold": 0,
                                            "sample_reasons": []}),
            mock.patch.object(worker_tick_notify, "_today_spend", return_value=(0.0, 1.0)),
            mock.patch.object(worker_tick_notify, "build_message", return_value="tick"),
            mock.patch.object(
                sys, "argv",
                ["worker_tick_notify.py", "--since", "2026-07-19T00:00:00Z",
                 "--pushed", "0"],
            ),
            mock.patch("notification_router.emit") as emit,
        ):
            self.assertEqual(0, worker_tick_notify.main())
            emit.assert_not_called()

    def test_action_and_emergency_send_once(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "router.json"
            with (
                mock.patch.object(notification_router, "STATE", state),
                mock.patch("telegram_notify.notify", return_value=1) as notify,
                mock.patch("telegram_notify.notify_emergency", return_value=1) as emergency,
            ):
                self.assertTrue(notification_router.emit(
                    "action", "approval", "Approve?", dedupe_key="approval:1"
                ))
                self.assertFalse(notification_router.emit(
                    "action", "approval", "Approve?", dedupe_key="approval:1"
                ))
                self.assertTrue(notification_router.emit(
                    "emergency", "pipeline", "Down", dedupe_key="pipeline:1"
                ))
                self.assertFalse(notification_router.emit(
                    "emergency", "pipeline", "Down", dedupe_key="pipeline:1"
                ))
                self.assertEqual(1, notify.call_count)
                self.assertEqual(1, emergency.call_count)


if __name__ == "__main__":
    unittest.main()
