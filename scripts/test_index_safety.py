#!/usr/bin/env python3
"""Guards for allowlist safety and the Metrika snippet. No network."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
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
        slash_only = "location = /halal/ { return 301 https://pepperoni.tatar/halal; }\n"
        self.assertEqual(
            index_safety.nginx_keep_conflicts(slash_only, {"/halal"}),
            [],
        )

    def test_installed_snippets_do_not_hit_keep(self):
        hits = index_safety.check_nginx_install()
        self.assertEqual([], hits, hits)

    def test_redirect_snippets_are_classified(self):
        files = {p.name for p in (ROOT / "deploy" / "nginx").glob("*-redirects.conf")}
        managed = {
            name for name in index_safety.NGINX_INSTALL if name.endswith("-redirects.conf")
        }
        manual = set(index_safety.NGINX_MANUAL_REDIRECTS)
        overlap = sorted(managed & manual)
        missing = sorted(files - managed - manual)
        extra = sorted((managed | manual) - files)
        self.assertEqual([], overlap, overlap)
        self.assertEqual([], missing, missing)
        self.assertEqual([], extra, extra)
        self.assertIn("pepperoni-halyal-redirects.conf", managed)
        self.assertNotIn(
            "pepperoni-halyal-redirects.conf", index_safety.nginx_include_names()
        )
        self.assertEqual(
            index_safety.NGINX_INCLUDE_MARKER, "pepperoni-halyal-redirects.conf"
        )

    def test_apply_script_uses_shared_list_and_rolls_back(self):
        text = (ROOT / "scripts" / "apply_nginx_trust_reset.sh").read_text(encoding="utf-8")
        self.assertIn("from index_safety import NGINX_INSTALL", text)
        self.assertIn("patch_site_includes", text)
        self.assertIn("nginx -t", text)
        self.assertIn("systemctl reload nginx", text)
        self.assertLess(text.index("nginx -t"), text.index("systemctl reload nginx"))
        self.assertIn("rolled back", text)
        self.assertIn("rollback", text)
        self.assertIn('readlink -f', text)
        self.assertIn("cp -aL", text)
        self.assertIn("SITE_REAL", text)

    def test_cases_noindex_repeats_server_headers(self):
        snippet = (ROOT / "deploy" / "nginx" / "security-headers.csp.snippet").read_text(
            encoding="utf-8"
        )
        csp_line = next(
            line.strip()
            for line in snippet.splitlines()
            if line.startswith("add_header Content-Security-Policy")
        )
        csp_value = re.search(r'add_header\s+Content-Security-Policy\s+"([^"]*)"', csp_line).group(1)
        server = {
            "Strict-Transport-Security": "max-age=31536000",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": csp_value,
        }
        expected = {**server, "X-Robots-Tag": "noindex, nofollow"}
        text = (ROOT / "deploy" / "nginx" / "cases-noindex.conf").read_text(encoding="utf-8")
        self.assertIn(csp_line, text)
        header_re = re.compile(r'add_header\s+(\S+)\s+"([^"]*)"\s+always;')
        bodies = re.findall(r"location\s+[^{]+\{(.*?)\}", text, re.S)
        self.assertEqual(len(bodies), 2, bodies)
        for body in bodies:
            got = dict(header_re.findall(body))
            self.assertEqual(got, expected)

    def test_symlink_site_rollback_restores_real_file(self):
        script = ROOT / "scripts" / "apply_nginx_trust_reset.sh"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            real = work / "real.conf"
            site = work / "site"
            real.write_text("ORIGINAL\n", encoding="utf-8")
            site.symlink_to(real)
            proc = subprocess.run(
                ["bash", str(script), "--symlink-rollback-test", str(work)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(site.is_symlink())
            self.assertEqual(site.resolve(), real.resolve())
            self.assertEqual(real.read_text(encoding="utf-8"), "ORIGINAL\n")

    def test_patch_site_includes_keeps_single_halyal_include(self):
        src = "\n".join([
            "server {",
            "    include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;",
            "    include /etc/nginx/snippets/jerky-redirects.conf;",
            "    include /etc/nginx/snippets/test1-noindex.conf;",
            "}",
            "",
        ])
        out = index_safety.patch_site_includes(src)
        includes = re.findall(r"include /etc/nginx/snippets/([^;]+);", out)
        self.assertEqual(includes.count("pepperoni-halyal-redirects.conf"), 1)
        self.assertEqual(len(includes), len(set(includes)), includes)
        self.assertIn("cases-noindex.conf", includes)
        self.assertNotIn("test1-noindex.conf", includes)
        self.assertEqual(includes[0], "pepperoni-halyal-redirects.conf")
        self.assertEqual(
            includes[1:], list(index_safety.nginx_include_names())
        )

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
