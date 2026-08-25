#!/usr/bin/env python3
"""Deterministic discovery gate for the /pepperoni and /jerky money pages."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from indexing_hot_urls import load_hot_urls

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
ORIGIN = "https://pepperoni.tatar"
MONEY_PAGES = (
    ("/pepperoni", PUBLIC / "pepperoni.html"),
    ("/en/pepperoni", PUBLIC / "en" / "pepperoni.html"),
    ("/jerky", PUBLIC / "jerky.html"),
    ("/en/jerky", PUBLIC / "en" / "jerky.html"),
)


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"FAIL {message}")


def check() -> int:
    failures: list[str] = []
    hot = set(load_hot_urls())
    sitemap_text = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
    sitemap_root = ET.parse(PUBLIC / "sitemap.xml").getroot()
    sm = "http://www.sitemaps.org/schemas/sitemap/0.9"
    xhtml = "http://www.w3.org/1999/xhtml"
    sitemap_entries = {}
    for node in sitemap_root.findall(f"{{{sm}}}url"):
        loc = node.find(f"{{{sm}}}loc")
        if loc is not None and loc.text:
            sitemap_entries[loc.text.strip()] = {
                link.attrib.get("hreflang"): link.attrib.get("href")
                for link in node.findall(f"{{{xhtml}}}link")
            }
    llm_sitemap = {
        loc.text.strip()
        for loc in ET.parse(PUBLIC / "sitemap-llms.xml").findall(
            ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )
        if loc.text
    }
    well_known = (PUBLIC / ".well-known" / "llms.txt").read_text(encoding="utf-8")
    llms_full = (PUBLIC / "llms-full.txt").read_text(encoding="utf-8")
    ai_meta = json.loads(
        (PUBLIC / ".well-known" / "ai-meta.json").read_text(encoding="utf-8")
    )
    ai_meta_urls = {
        item.get("url")
        for item in ai_meta.get("datasets", [])
        if isinstance(item, dict)
    }

    for path, html_path in MONEY_PAGES:
        url = ORIGIN + path
        if not html_path.exists():
            fail(f"missing page {html_path.relative_to(ROOT)}", failures)
            continue
        html = html_path.read_text(encoding="utf-8")
        if f'<link rel="canonical" href="{url}">' not in html:
            fail(f"{path}: canonical mismatch", failures)
        if not re.search(
            r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'][^"\']*index',
            html,
            re.I,
        ):
            fail(f"{path}: missing index robots directive", failures)
        if f"<loc>{url}</loc>" not in sitemap_text:
            fail(f"{path}: absent from sitemap.xml", failures)
        if url not in hot:
            fail(f"{path}: absent from indexing hot URLs", failures)
        if url not in llm_sitemap:
            fail(f"{path}: absent from sitemap-llms.xml", failures)
        if url not in well_known:
            fail(f"{path}: absent from .well-known/llms.txt", failures)

    for url in (f"{ORIGIN}/pepperoni", f"{ORIGIN}/jerky"):
        if url not in ai_meta_urls:
            fail(f"{url}: absent from ai-meta datasets", failures)

    if "### Джерки — канонические URL" not in llms_full:
        fail("llms-full.txt missing dedicated jerky canonical block", failures)

    homepage = (PUBLIC / "index.html").read_text(encoding="utf-8")
    for path in ("/pepperoni", "/jerky"):
        if f'href="{path}"' not in homepage:
            fail(f"homepage missing internal link to {path}", failures)

    pepperoni_locales = ("ru", "en", "kk", "uz", "az", "hy", "ka", "ky", "tg")
    expected_alternates = {
        lang: (
            f"{ORIGIN}/pepperoni"
            if lang == "ru"
            else f"{ORIGIN}/{lang}/pepperoni"
        )
        for lang in pepperoni_locales
    }
    expected_alternates["x-default"] = f"{ORIGIN}/en/pepperoni"
    for page_url in {expected_alternates[lang] for lang in pepperoni_locales}:
        if sitemap_entries.get(page_url) != expected_alternates:
            fail(f"{page_url}: incomplete or conflicting hreflang cluster", failures)

    for path in (PUBLIC / "jerky.html", PUBLIC / "en" / "jerky.html"):
        html = path.read_text(encoding="utf-8")
        if '<meta name="keywords"' not in html:
            fail(f"{path.relative_to(ROOT)}: keywords metadata missing", failures)

    required_redirects = {
        "/jerky.html": "/jerky",
        "/jerky/": "/jerky",
        "/en/jerky.html": "/en/jerky",
        "/en/jerky/": "/en/jerky",
    }
    vercel = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    vercel_redirects = {
        item.get("source"): item.get("destination")
        for item in vercel.get("redirects", [])
        if isinstance(item, dict)
    }
    nginx = (ROOT / "deploy" / "nginx" / "jerky-redirects.conf").read_text(
        encoding="utf-8"
    )
    for source, destination in required_redirects.items():
        if vercel_redirects.get(source) != destination:
            fail(f"Vercel redirect missing: {source} -> {destination}", failures)
        pattern = (
            rf"location\s*=\s*{re.escape(source)}\s*\{{"
            rf"[^}}]*return\s+301\s+https://pepperoni\.tatar{re.escape(destination)};"
        )
        if not re.search(pattern, nginx, re.S):
            fail(f"nginx redirect missing: {source} -> {destination}", failures)

    if failures:
        print(f"money-page-discovery: {len(failures)} failure(s)")
        return 1
    print(
        "money-page-discovery: OK — 4 canonicals in sitemap, hot push, "
        "AI sitemap and discovery manifests"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
