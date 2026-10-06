#!/usr/bin/env python3
"""Guards for allowlist safety and the Metrika snippet. No network."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import index_safety  # noqa: E402
import metrika_snippet  # noqa: E402
from render_static_catalog import replace_live_sku_list  # noqa: E402


class SafetyTests(unittest.TestCase):
    def test_keep_file_blocks_without_confirm(self):
        keep = {"halal.html": "/halal"}
        self.assertTrue(
            index_safety.block_if_keep(
                "quarantine", "public/halal.html", keep=keep, confirm=False
            )
        )
        self.assertFalse(
            index_safety.block_if_keep(
                "quarantine", "public/halal.html", keep=keep, confirm=True
            )
        )
        self.assertFalse(
            index_safety.block_if_keep(
                "delete", "public/geo/old.html", keep=keep, confirm=False
            )
        )

    def test_nginx_exact_and_prefix(self):
        text = "\n".join([
            "location = /halal { return 301 https://pepperoni.tatar/; }",
            "location = /old-page { return 410; }",
            "location ^~ /geo/ { return 410; }",
            "location ^~ /export/ { return 410; }",
        ])
        hits = index_safety.nginx_keep_conflicts(
            text, {"/halal", "/pepperoni", "/export/kazakhstan"}
        )
        self.assertIn("301 /halal", hits)
        self.assertTrue(any("/export/kazakhstan" in h for h in hits))
        self.assertFalse(any("old-page" in h for h in hits))
        self.assertFalse(any("/pepperoni" in h and "geo" in h for h in hits))

    def test_installed_snippets_do_not_hit_keep(self):
        hits = index_safety.check_nginx_install()
        self.assertEqual([], hits, hits)

    def test_metrika_insert_once(self):
        html = "<html><head></head><body><h1>x</h1></body></html>"
        once = metrika_snippet.ensure_metrika_html(html)
        twice = metrika_snippet.ensure_metrika_html(once)
        self.assertEqual(1, metrika_snippet.init_count(once))
        self.assertEqual(once, twice)
        self.assertEqual(1, once.count("gtm.js?id="))
        self.assertEqual(1, once.count("ns.html?id=GTM-W2Q5S8HF"))

    def test_metrika_does_not_touch_existing_init(self):
        html = (
            "<html><head></head><body>"
            '<script>ym(107064141,"init",{clickmap:true});</script>'
            "</body></html>"
        )
        out = metrika_snippet.ensure_metrika_html(html, with_gtm=False)
        self.assertEqual(html, out)

    def test_about_sku_list_drops_surplus_closes(self):
        html = (
            '<div class="card"><p class="cat-desc"></p>'
            '<div class="live-sku-list" data-section="Заморозка">'
            '<div class="sku-grid"><a href="/products/kd-013">Пепперони</a></div>'
            "</div></div></div></div>\n"
            '<p style="margin-top:12px">links</p></div>'
        )
        block = (
            '<div class="live-sku-list" data-section="Заморозка">'
            '<div class="sku-grid"><a href="/products/kd-013">Пепперони</a></div></div>'
        )
        fixed = replace_live_sku_list(html, "Заморозка", block)
        self.assertEqual(fixed.count("<div"), fixed.count("</div>"))
        self.assertIn("Пепперони", fixed)
        self.assertIn("links", fixed)
        self.assertEqual(fixed, replace_live_sku_list(fixed, "Заморозка", block))


if __name__ == "__main__":
    unittest.main()
