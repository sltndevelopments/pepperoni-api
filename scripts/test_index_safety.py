#!/usr/bin/env python3
"""Unit tests for PHASE 1 allowlist safety rails."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import analytics_snippets as an  # noqa: E402
import index_safety as safety  # noqa: E402


class AnalyticsIdempotent(unittest.TestCase):
    def test_count_init_ignores_reachgoal(self):
        html = (
            '<html><body>'
            'ym(107064141,"reachGoal","click_phone")'
            f'{an.METRIKA_SCRIPT}'
            "</body></html>"
        )
        self.assertEqual(an.count_metrika_inits(html), 1)

    def test_inject_does_not_double(self):
        html = f"<html><body>hi</body></html>"
        once, added = an.inject_metrika(html)
        self.assertTrue(added)
        self.assertEqual(an.count_metrika_inits(once), 1)
        twice, added2 = an.inject_metrika(once)
        self.assertFalse(added2)
        self.assertEqual(an.count_metrika_inits(twice), 1)

    def test_inject_gtm_idempotent(self):
        html = "<html><head></head><body></body></html>"
        once, added = an.inject_gtm(html)
        self.assertTrue(added)
        self.assertTrue(an.has_gtm(once))
        twice, added2 = an.inject_gtm(once)
        self.assertFalse(added2)
        self.assertEqual(once.count(an.GTM_ID), twice.count(an.GTM_ID))

    def test_delayed_pepperoni_pattern_counts_as_one(self):
        html = (
            "<html><body><script>s.onload=function(){"
            "ym(107064141,'init',{clickmap:true});"
            "}</script></body></html>"
        )
        self.assertEqual(an.count_metrika_inits(html), 1)
        out, added = an.inject_metrika(html)
        self.assertFalse(added)
        self.assertEqual(out, html)


class KeepLookup(unittest.TestCase):
    def test_manifest_has_keep_urls(self):
        files = safety.keep_files()
        urls = safety.keep_urls()
        self.assertIn("halal.html", files)
        self.assertIn("/halal", urls)
        self.assertIn("pepperoni.html", files)
        self.assertTrue(safety.is_keep_file(ROOT / "public" / "halal.html"))
        self.assertTrue(safety.is_keep_url("https://pepperoni.tatar/halal"))
        self.assertTrue(safety.is_keep_url("/products/kd-013"))

    def test_owner_override_default_off(self):
        env = os.environ.copy()
        env.pop("ALLOW_AB_NOINDEX", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(safety.owner_override("ALLOW_AB_NOINDEX"))
        with mock.patch.dict(os.environ, {"ALLOW_AB_NOINDEX": "1"}):
            self.assertTrue(safety.owner_override("ALLOW_AB_NOINDEX"))


class QuarantineProtect(unittest.TestCase):
    def test_protect_keep_does_not_require_move(self):
        path = ROOT / "public" / "halal.html"
        with mock.patch.object(safety, "restore_from_git", return_value=True), \
             mock.patch.object(safety, "alert"):
            blocked = safety.protect_keep_from_quarantine(path, ["fake gost"])
        self.assertTrue(blocked)

    def test_protect_skips_unknown_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brand-new-geo.html"
            p.write_text("<html></html>", encoding="utf-8")
            with mock.patch.object(safety, "alert"):
                blocked = safety.protect_keep_from_quarantine(p, ["thin"])
        self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
