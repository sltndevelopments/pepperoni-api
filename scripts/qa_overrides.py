#!/usr/bin/env python3
"""QA the DeepSeek-generated per-SKU override files.

Checks each data/product_overrides/<sku>.html (+ .en.html) for:
  • structure: contains <div class="section-block"> + <h2 class="section-title">
  • no leftover markdown fences (``` ) or stray <html>/<head>/<style>/<script>
  • halal consistency: no pork/свинина, no alcohol, no 'no pork' redundancy
  • no hallucinated/invented certifications or numbers beyond our real claims
  • word count in a sane band (300–1600)
  • product name from products.json is actually mentioned (relevance / not generic)

Prints a per-file report and a summary. Exit code 1 if any FAIL.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "product_overrides"
ITEMS = json.load(open(ROOT / "public" / "products.json", encoding="utf-8"))
ITEMS = ITEMS if isinstance(ITEMS, list) else ITEMS.get("products", [])
BY_SKU = {it.get("sku", "").lower(): it for it in ITEMS}

# Things that must NOT appear (halal / hallucination guards).
FORBIDDEN = [
    (r"свинин", "pork mention (RU)"),
    (r"\bpork\b", "pork mention (EN)"),
    (r"сало\b", "lard mention"),
    (r"\bбекон", "bacon mention"),
    (r"\bвин[оа]\b|\bалкогол|\bпив[оа]\b|\balcohol|\bwine\b|\bbeer\b", "alcohol mention"),
    (r"без свинины|нет свинины|no pork", "redundant 'no pork'"),
    (r"```", "markdown code fence"),
    (r"<html|<head|<body|<!doctype", "full-document tags"),
    (r"<style|<script", "style/script injected"),
    # invented certs we don't claim:
    (r"\bГОСТ\s?Р?\s?\d", "invented GOST number"),
    (r"\bEU organic|\bUSDA|\bкошер|\bkosher", "wrong/foreign cert"),
]

# Suspicious invented specifics (years/percentages that look fabricated).
SUSPICIOUS = [
    (r"\b(19|20)\d{2}\s*год", "specific year claim — verify"),
    (r"\b\d{2,3}\s*%", "percentage claim — verify"),
    (r"\bпремия|\bнаград|\baward|\bwinner", "award claim — verify"),
]


def check(path: Path, sku: str) -> tuple[str, list[str], list[str]]:
    html = path.read_text(encoding="utf-8")
    errs: list[str] = []
    warns: list[str] = []
    low = html.lower()

    if "section-block" not in html or "section-title" not in html:
        errs.append("missing section-block/section-title structure")
    for pat, label in FORBIDDEN:
        if re.search(pat, low, re.I):
            errs.append(label)
    for pat, label in SUSPICIOUS:
        if re.search(pat, html, re.I):
            warns.append(label)

    text = re.sub(r"<[^>]+>", " ", html)
    wc = len(re.findall(r"\w+", text))
    if wc < 300:
        errs.append(f"too short ({wc}w)")
    elif wc > 1600:
        warns.append(f"very long ({wc}w)")

    # relevance: product name tokens should appear
    item = BY_SKU.get(sku, {})
    name = (item.get("name") or "").lower()
    name_tokens = [t for t in re.findall(r"[а-яёa-z]{4,}", name) if t not in
                   ("шт", "для", "под")]
    if name_tokens and not any(t in low for t in name_tokens):
        warns.append("product name not referenced (generic?)")

    verdict = "FAIL" if errs else ("WARN" if warns else "OK")
    return verdict, errs, warns


def main() -> int:
    files = sorted(OUT.glob("*.html"))
    if not files:
        print("no override files found")
        return 1
    n_ok = n_warn = n_fail = 0
    for f in files:
        sku = f.name.replace(".en.html", "").replace(".html", "")
        verdict, errs, warns = check(f, sku)
        if verdict == "FAIL":
            n_fail += 1
            print(f"  FAIL {f.name}: {', '.join(errs)}")
        elif verdict == "WARN":
            n_warn += 1
            print(f"  WARN {f.name}: {', '.join(warns)}")
        else:
            n_ok += 1
    print(f"\nSUMMARY: {len(files)} files — OK={n_ok} WARN={n_warn} FAIL={n_fail}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
