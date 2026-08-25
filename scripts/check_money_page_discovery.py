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
    llm_sitemap = {
        loc.text.strip()
        for loc in ET.parse(PUBLIC / "sitemap-llms.xml").findall(
            ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )
        if loc.text
    }
    well_known = (PUBLIC / ".well-known" / "llms.txt").read_text(encoding="utf-8")
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

    homepage = (PUBLIC / "index.html").read_text(encoding="utf-8")
    for path in ("/pepperoni", "/jerky"):
        if f'href="{path}"' not in homepage:
            fail(f"homepage missing internal link to {path}", failures)

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
