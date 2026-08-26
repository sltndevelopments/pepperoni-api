from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


aio = load_module("yaratu_aio", "yaratu/scripts/aio_visibility.py")
nudge = load_module("yaratu_nudge", "yaratu/scripts/nudge_indexing.py")


class AioMeasurementTests(unittest.TestCase):
    def test_fixed_panel_has_balanced_twenty_questions(self):
        panel = aio.load_panel()
        self.assertEqual(20, len(panel["questions"]))
        buckets = {}
        for item in panel["questions"]:
            key = (item["language"], item["audience"])
            buckets[key] = buckets.get(key, 0) + 1
        self.assertEqual(
            {("ru", "b2c"): 5, ("en", "b2c"): 5, ("ru", "b2b"): 5, ("en", "b2b"): 5},
            buckets,
        )
        text = " ".join(item["text"] for item in panel["questions"]).lower()
        self.assertNotIn("здорового питания", text)
        self.assertNotIn("health-focused", text)
        self.assertIn("магазина халяльных продуктов", text)
        self.assertIn("halal-focused retailer", text)

    def test_model_defaults_match_repository_contour(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual("gpt-5.6", aio.LAYERS["openai_search"]["default_model"])
            self.assertEqual("gemini-3.7-flash", aio.LAYERS["gemini_memory"]["default_model"])
            self.assertEqual("gemini-3.7-flash", aio.LAYERS["gemini_search"]["default_model"])

    def test_provider_failure_is_null_not_zero(self):
        panel = aio.load_panel()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=False):
            result = aio.run_layer(
                "openai_memory",
                panel["questions"],
                asker=lambda _question: ("", "synthetic provider failure"),
            )
        self.assertEqual("fail", result["status"])
        self.assertIsNone(result["score"])
        self.assertIsNone(result["cited"])

    def test_live_answers_produce_score(self):
        panel = aio.load_panel()
        answers = iter(
            [("Yaratu — https://yaratu.com/", None)] * 5
            + [("Other brands", None)] * 15
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=False):
            result = aio.run_layer(
                "openai_memory",
                panel["questions"],
                asker=lambda _question: next(answers),
            )
        self.assertEqual("ok", result["status"])
        self.assertEqual(0.25, result["score"])
        self.assertEqual(5, result["cited"])

    def test_dry_run_writes_skip_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "baseline.json"
            code = aio.main([
                "--dry-run",
                "--layers", "openai_memory,gemini_search",
                "--output", str(output),
            ])
            snapshot = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertTrue(snapshot["dry_run"])
        self.assertTrue(all(layer["status"] == "skip" for layer in snapshot["layers"].values()))
        self.assertTrue(all(layer["score"] is None for layer in snapshot["layers"].values()))


class NudgeTests(unittest.TestCase):
    def test_dry_run_has_all_channels_and_no_network(self):
        with mock.patch.object(nudge, "_request", side_effect=AssertionError("network called")):
            code = nudge.main([
                "--domain", "yaratu.com",
                "--gsc-property", "sc-domain:yaratu.com",
                "--sitemap-url", "https://yaratu.com/sitemap.xml",
                "--hot-url", "https://yaratu.com/",
                "--dry-run",
            ])
        self.assertEqual(0, code)

    def test_google_indexing_is_disabled_without_opt_in(self):
        skipped = nudge._entry("skip", error="test")
        with (
            mock.patch.object(nudge, "submit_google_hot", side_effect=AssertionError("must stay disabled")),
            mock.patch.object(nudge, "submit_gsc_sitemap", return_value=skipped),
            mock.patch.object(nudge, "submit_yandex_hot", return_value={**skipped, "items": []}),
            mock.patch.object(nudge, "submit_yandex_sitemap", return_value=skipped),
            mock.patch.object(nudge, "submit_indexnow", return_value=skipped),
        ):
            code = nudge.main([
                "--domain", "yaratu.com",
                "--gsc-property", "sc-domain:yaratu.com",
                "--sitemap-url", "https://yaratu.com/sitemap.xml",
                "--hot-url", "https://yaratu.com/",
            ])
        self.assertEqual(0, code)

    def test_yandex_url_queue_uses_canonical_trailing_slash(self):
        with mock.patch.object(nudge, "_request", return_value=(202, None)) as request:
            result = nudge.submit_yandex_hot(
                "42", "https:yaratu.com:443", "token", ["https://yaratu.com/"]
            )
        self.assertEqual("ok", result["status"])
        self.assertTrue(request.call_args.args[1].endswith("/recrawl/queue/"))

    def test_yandex_sitemap_recrawl_requires_exact_registration(self):
        listing = {
            "sitemaps": [
                {"sitemap_id": "sm-1", "sitemap_url": "https://yaratu.com/sitemap.xml"}
            ]
        }
        with (
            mock.patch.object(nudge, "_get_json", return_value=(listing, 200, None)),
            mock.patch.object(nudge, "_request", return_value=(202, None)) as request,
        ):
            result = nudge.submit_yandex_sitemap(
                "42", "https:yaratu.com:443", "token", "https://yaratu.com/sitemap.xml"
            )
        self.assertEqual("ok", result["status"])
        self.assertTrue(request.call_args.args[1].endswith("/sitemaps/sm-1/recrawl"))

    def test_yandex_sitemap_skips_when_not_registered(self):
        with (
            mock.patch.object(nudge, "_get_json", return_value=({"sitemaps": []}, 200, None)),
            mock.patch.object(nudge, "_request", side_effect=AssertionError("must not submit")),
        ):
            result = nudge.submit_yandex_sitemap(
                "42", "https:yaratu.com:443", "token", "https://yaratu.com/sitemap.xml"
            )
        self.assertEqual("skip", result["status"])
        self.assertIn("not registered", result["error"])

    def test_rejects_cross_domain_hot_url(self):
        code = nudge.main([
            "--domain", "yaratu.com",
            "--gsc-property", "sc-domain:yaratu.com",
            "--sitemap-url", "https://yaratu.com/sitemap.xml",
            "--hot-url", "https://example.com/",
            "--dry-run",
        ])
        self.assertEqual(2, code)

    def test_json_contract_files_parse(self):
        for name in (
            "aio_baseline.schema.json",
            "conversion_event.schema.json",
            "measurement_30_60_90.schema.json",
            "expansion_policy.json",
        ):
            json.loads((ROOT / "yaratu" / "data" / name).read_text(encoding="utf-8"))


class WorkflowTests(unittest.TestCase):
    def test_scheduled_run_never_invokes_indexing(self):
        workflow = (
            ROOT / ".github" / "workflows" / "yaratu-aio-visibility.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(1, workflow.count("python yaratu/scripts/nudge_indexing.py"))
        self.assertNotIn("--google-indexing", workflow)
        self.assertNotIn("Check indexing plan", workflow)
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && "
            "github.event.inputs.run_indexing == 'true'",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
