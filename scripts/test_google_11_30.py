#!/usr/bin/env python3
"""Exact-query wording on Google 11–30 landings outside the wholesale hubs."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CSV_PATH = ROOT / "docs" / "seo" / "google-11-30-2026-10-17.csv"
WHOLESALE = {
    "/sosiski-dlya-hotdog",
    "/kotlety-dlya-burgerov",
    "/vetchina-optom",
    "/pepperoni",
    "/sosiski-halyal-optom",
    "/dlya-horeca",
    "/en/pepperoni",
}

# query → (url, must appear in title or H1 or lead/FAQ)
QUERIES = [
    ("татарская колбаса из конины", "kazylyk.html"),
    ("конская колбаса название у татар", "blog/kazylyk.html"),
    ("what is halal pepperoni made of", "en/blog/what-is-halal-pepperoni.html"),
    ("is pepperoni halal", "en/blog/what-is-halal-pepperoni.html"),
    ("эчпочмак это", "blog/echpochmak.html"),
    ("элеш это", "blog/elesh.html"),
    ("что такое эчпочмак", "blog/echpochmak.html"),
    ("губадия это", "blog/echpochmak.html"),
    ("что такое эчпочмак в казани", "blog/echpochmak.html"),
    ("что значит курица халяль", "halal.html"),
    ("поставки мяса в рестораны", "pepperoni-dlya-pizzerii.html"),
    ("размеры пиццы", "pepperoni-dlya-pizzerii.html"),
    ("контрактное производство печенья", "kontraktnoe-proizvodstvo.html"),
]

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def visible(html: str) -> str:
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    parts = [
        title.group(1) if title else "",
        re.sub(r"<[^>]+>", " ", h1.group(1)) if h1 else "",
        html,
    ]
    return re.sub(r"\s+", " ", " ".join(parts)).lower()


def main() -> int:
    check(CSV_PATH.is_file(), "CSV report exists")
    if CSV_PATH.is_file():
        rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
        check(rows and {"query", "gsc_pos", "url", "old_title", "new_title", "old_h1", "new_h1"}
              <= set(rows[0]), "CSV has required columns")
        for row in rows:
            check(row["url"] not in WHOLESALE, f"CSV row not a wholesale hub: {row['query']}")
            check("казанские деликатесы" not in row["query"].lower()
                  or "brand" in row.get("query", ""),
                  f"no brand-intent row: {row['query']}")
    for query, rel in QUERIES:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        check(query.lower() in visible(html), f"{rel} contains «{query}»")
        check("халяль бургер" not in html.lower(), f"{rel} has no burger-halal claim")
    if fail:
        print(f"test_google_11_30: {fail} FAIL")
        return 1
    print("test_google_11_30: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
