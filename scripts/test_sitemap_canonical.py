#!/usr/bin/env python3
"""Regression test: sitemap URLs must not hit a canonical redirect.

Background (SEO audit 2026-09-09): sitemap.xml listed `https://pepperoni.tatar/en`
while nginx 301s `/en` → `/en/` and the page declares canonical `/en/`. The
generator (`build_index_manifest.clean_url` / `rebuild_sitemap.html_to_url`)
stripped the trailing slash from every directory index, including the locale
root. This test pins the rule for both the generator functions and the
published XML.

Run:  python3 scripts/test_sitemap_canonical.py
"""
from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_index_manifest as bim  # noqa: E402
import rebuild_sitemap as rs  # noqa: E402

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "xhtml": "http://www.w3.org/1999/xhtml"}


class CleanUrlRules(unittest.TestCase):
    def test_locale_root_keeps_trailing_slash(self):
        self.assertEqual(bim.clean_url("en/index.html"), "/en/")
        self.assertEqual(rs.html_to_url(rs.PUBLIC / "en" / "index.html"),
                         "https://pepperoni.tatar/en/")

    def test_site_root(self):
        self.assertEqual(bim.clean_url("index.html"), "/")
        self.assertEqual(rs.html_to_url(rs.PUBLIC / "index.html"),
                         "https://pepperoni.tatar/")

    def test_other_directory_indexes_have_no_slash(self):
        self.assertEqual(bim.clean_url("products/index.html"), "/products")
        self.assertEqual(bim.clean_url("en/products/index.html"), "/en/products")
        self.assertEqual(rs.html_to_url(rs.PUBLIC / "products" / "index.html"),
                         "https://pepperoni.tatar/products")

    def test_plain_pages_have_no_slash(self):
        self.assertEqual(bim.clean_url("pepperoni.html"), "/pepperoni")
        self.assertEqual(bim.clean_url("en/blog/kazylyk.html"), "/en/blog/kazylyk")

    def test_policy_checker_flags_both_directions(self):
        errs = rs.check_trailing_slash_policy([
            "https://pepperoni.tatar/",
            "https://pepperoni.tatar/en/",
            "https://pepperoni.tatar/en",
            "https://pepperoni.tatar/products/",
            "https://pepperoni.tatar/products",
        ])
        self.assertEqual(len(errs), 2)
        self.assertTrue(any("/en (expected" in e for e in errs))
        self.assertTrue(any("/products/" in e for e in errs))


class PublishedSitemap(unittest.TestCase):
    def setUp(self):
        self.tree = ET.parse(ROOT / "public" / "sitemap.xml")

    def _urls(self):
        locs = [e.text for e in self.tree.iterfind(".//sm:loc", NS)]
        alts = [e.get("href") for e in self.tree.iterfind(".//xhtml:link", NS)]
        return locs, alts

    def test_no_bare_en_anywhere(self):
        locs, alts = self._urls()
        self.assertNotIn("https://pepperoni.tatar/en", locs)
        self.assertNotIn("https://pepperoni.tatar/en", alts)
        self.assertIn("https://pepperoni.tatar/en/", locs)

    def test_trailing_slash_policy_holds(self):
        locs, alts = self._urls()
        self.assertEqual(rs.check_trailing_slash_policy(locs + alts), [])

    def test_manifest_matches(self):
        import json
        manifest = json.loads((ROOT / "data" / "index_manifest.json").read_text())
        by_file = {row["file"]: row["url"] for row in manifest["entries"]}
        self.assertEqual(by_file.get("en/index.html"), "/en/")
        self.assertEqual(by_file.get("index.html"), "/")


if __name__ == "__main__":
    unittest.main(verbosity=1)
