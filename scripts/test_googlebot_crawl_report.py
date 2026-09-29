#!/usr/bin/env python3
"""Fixture: verified Googlebot is counted; a spoofed UA from another IP is not."""
from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

import googlebot_crawl_report as report

RANGES = Path(__file__).resolve().parent.parent / "data" / "googlebot_ip_ranges.json"
UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def line(ip: str, path: str, status: int, ua: str = UA) -> str:
    return (
        f'{ip} - - [28/Sep/2026:01:02:03 +0000] "GET {path} HTTP/1.1" '
        f'{status} 100 "-" "{ua}"'
    )


class GooglebotCrawlReportTest(unittest.TestCase):
    def test_verified_hits_counted_and_spoof_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            public = root / "public"
            logs.mkdir()
            public.mkdir()
            (public / "page.html").write_text(
                '<a href="/missing.html">x</a><img src="https://pepperoni.tatar/img/ok.jpg">',
                encoding="utf-8",
            )
            (logs / "access.log").write_text(
                "\n".join([
                    line("66.249.66.1", "/geo/kazan", 410),
                    line("66.249.66.1", "/missing.html", 404),
                    line("203.0.113.5", "/secret.env", 404),
                    line("66.249.66.1", "/health", 200, ua="Python-urllib/3.12"),
                ]) + "\n",
                encoding="utf-8",
            )
            gz_body = line("66.249.66.2", "/blog/old", 410) + "\n"
            with gzip.open(logs / "access.log.2.gz", "wt", encoding="utf-8") as handle:
                handle.write(gz_body)

            built = report.build_report(logs, public, RANGES)

        self.assertEqual(built["verified_requests"], 3)
        self.assertEqual(built["excluded_googlebot_ua_outside_ranges"], 1)
        self.assertEqual(built["status_totals"]["410"], 2)
        self.assertEqual(built["status_totals"]["404"], 1)
        self.assertEqual(built["status_totals"]["200"], 0)
        self.assertEqual(built["gone_by_segment"], {"/geo": 1, "/blog": 1})
        self.assertEqual(built["days"]["2026-09-28"]["410"], 2)
        self.assertEqual(len(built["not_found"]), 1)
        self.assertEqual(built["not_found"][0]["path"], "/missing.html")
        self.assertTrue(built["not_found"][0]["linked_from_public"])
        self.assertEqual(built["not_found"][0]["mark"], "есть ссылка в public/")
        self.assertIn("no $host", built["note"])
        self.assertNotIn("/secret.env", json_paths(built))

    def test_unlinked_404_is_marked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            logs.mkdir()
            (logs / "access.log").write_text(
                line("66.249.66.1", "/ads.txt", 404) + "\n",
                encoding="utf-8",
            )
            built = report.build_report(logs, root / "missing-public", RANGES)
        self.assertEqual(built["not_found"][0]["mark"], "ссылок нет")
        self.assertFalse(built["not_found"][0]["linked_from_public"])


def json_paths(built: dict) -> str:
    return " ".join(item["path"] for item in built["not_found"])


if __name__ == "__main__":
    unittest.main()
