#!/usr/bin/env python3
"""Gates for private /cases/<slug> consent drafts."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from qa_pages import _visible_words  # noqa: E402

SLUGS = ("gfc", "sweet-life", "tatneft", "aslam-ompk")
PUBLIC_HREFS = (
    'href="/cases/gfc"',
    'href="/cases/sweet-life"',
    'href="/cases/tatneft"',
    'href="/cases/aslam-ompk"',
    "href='https://pepperoni.tatar/cases/gfc'",
)

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    manifest = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    keep_files = {
        row["file"] for row in manifest.get("entries") or []
        if isinstance(row, dict) and row.get("status") == "keep" and row.get("file")
    }

    retire = json.loads((ROOT / "data" / "url_consolidation_map.json").read_text(encoding="utf-8"))
    retire_by_file = {e["file"]: e for e in retire.get("entries") or []}

    sitemap = (ROOT / "public" / "sitemap.xml").read_text(encoding="utf-8")
    robots = (ROOT / "public" / "robots.txt").read_text(encoding="utf-8")
    check("Disallow: /cases/" in robots, "robots.txt disallows /cases/")
    ua_blocks = re.split(r"(?=^User-agent:)", robots, flags=re.M)
    named = [b for b in ua_blocks if re.match(r"User-agent:\s+\S+", b)]
    missing_ua = []
    for block in named:
        name = re.match(r"User-agent:\s+(\S+)", block).group(1)
        if "Disallow: /cases/" not in block:
            missing_ua.append(name)
    check(not missing_ua, f"every User-agent group disallows /cases/ (missing: {missing_ua})")

    for slug in SLUGS:
        rel = f"cases/{slug}.html"
        path = ROOT / "public" / rel
        check(path.is_file(), f"{rel} exists")
        html = path.read_text(encoding="utf-8")
        check(re.search(r'name="robots" content="noindex, nofollow"', html),
              f"{rel} noindex,nofollow")
        check(rel not in keep_files, f"{rel} not in index allowlist")
        check(f"/cases/{slug}" not in sitemap and f"cases/{slug}" not in sitemap,
              f"{rel} not in sitemap")
        row = retire_by_file.get(rel)
        check(bool(row) and row.get("status") == "noindex",
              f"{rel} is noindex in url_consolidation_map")
        check("/assets/kd-landing.css" in html and "kd-topbar" in html,
              f"{rel} uses shared landing chrome")
        check(len(re.findall(r"<h1\b", html, re.I)) == 1, f"{rel} one H1")
        check(_visible_words(html) >= 250, f"{rel} >= 250 visible words")
        check("[УТОЧНИТЬ:" in html, f"{rel} has placeholders for missing facts")
        check("tel:+79872170202" in html, f"{rel} canonical phone")
        check("info@kazandelikates.tatar" in html, f"{rel} canonical email")

    # Fact anchors
    gfc = (ROOT / "public/cases/gfc.html").read_text(encoding="utf-8")
    check("gfc_pepperoni_240111" in gfc and "gfc-russia.ru" in gfc, "GFC registry id + URL")
    sl = (ROOT / "public/cases/sweet-life.html").read_text(encoding="utf-8")
    check("sweet_life_pepperoni_118665" in sl and "swlife.ru/118665" in sl,
          "Sweet Life registry id + URL")
    tat = (ROOT / "public/cases/tatneft.html").read_text(encoding="utf-8")
    check("evidence_registry.json" in tat and "сосиски" in tat, "Tatneft cites public pages")
    aslam = (ROOT / "public/cases/aslam-ompk.html").read_text(encoding="utf-8")
    check("пепперони в этой линейке нет" in aslam or "пепперони нет" in aslam,
          "Aslam page keeps the no-pepperoni fact")
    check("private_label_min_run_5t" in aslam, "Aslam STM min is factory term, sourced")
    check('href="https://aslamhalal.com/"' in aslam
          and 'target="_blank"' in aslam and 'rel="noopener"' in aslam,
          "Aslam page links brand site aslamhalal.com")
    check('"url": "https://aslamhalal.com/"' in aslam
          or '"url":"https://aslamhalal.com/"' in aslam,
          "Aslam client Organization JSON-LD has url")
    check('"sameAs"' in aslam and "aslamhalal.com" in aslam,
          "Aslam client Organization JSON-LD has sameAs")

    # Not linked from public HTML except the drafts themselves
    for path in (ROOT / "public").rglob("*.html"):
        rel = str(path.relative_to(ROOT / "public"))
        if rel.startswith("cases/"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for href in PUBLIC_HREFS:
            if href in text:
                check(False, f"public {rel} links {href}")
                break
        else:
            continue
    check(True, "no public page links to private case URLs")

    # Not in llms
    for name in ("llms.txt", "llms-full.txt", "en/llms.txt", "en/llms-full.txt"):
        p = ROOT / "public" / name
        if not p.exists():
            continue
        blob = p.read_text(encoding="utf-8")
        check("/cases/gfc" not in blob and "/cases/tatneft" not in blob,
              f"{name} does not list private cases")

    if fail:
        print(f"test_case_pages: {fail} FAIL")
        return 1
    print("test_case_pages: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
