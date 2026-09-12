#!/usr/bin/env python3
"""Gate: the wholesale minimum order on the site is ONE PALLET — for every
category (owner decision 2026-09-12: «Минимальный заказ — паллет … для всех»).

Before this gate the pages carried a zoo of invented minimums: «от 20 кг»,
«от 1 коробки (2,5 кг)», «от 50 штук», «Minimum order from 20 kg», «MOQ 100 kg»,
«200–300 штук». The class is "a minimum-order / wholesale sentence that quotes a
kg / box / piece figure", so that is what is scanned — in the published pages
and in the sources that regenerate them (generator scripts, landing i18n).
Private-label runs («от 5 тонн») are a different fact with their own gate
(check_stm_min_run.py) and are ignored here.

Usage: python3 scripts/check_wholesale_moq.py [--quiet]   → exit 1 on any hit.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CTX = re.compile(
    r"минимальн\w*\s+(?:оптов\w+\s+)?(?:заказ|парти|объ[её]м)|мин\.\s*заказ|"
    r"minimum\s+(?:wholesale\s+)?order|min(?:\.|imum)?\s*order|moq|"
    r"оптов\w*\s+(?:партии|закупк\w*|поставк\w*|покупател\w*)\s+(?:—\s*)?от\s*\d|"
    r"wholesale\s+(?:supply\s+|orders?\s+)?from\s+\d|оптом\s+от\s+\d|opt\w*\s+from\s+\d",
    re.I,
)
FIGURE = re.compile(
    r"(?<![\d,.])(\d[\d\s,.]{0,4})\s*(кг|kg|шт\.?|штук|pcs|pieces|короб\w*|коробк\w*|box(?:es)?|case?s?|"
    r"упаковк\w*|packs?|блок\w*)(?![а-яёa-z])|"
    r"(?:от|from)\s+(?:1|одн\w+|one|a)\s+(?:коробк\w*|короб\w*|box|case|упаковк\w*|pack)",
    re.I,
)
ALLOW = re.compile(r"паллет|pallet|тонн|tonnes?|\btons?\b", re.I)

SCAN = [
    ("public", ("*.html", "*.txt", "*.md")),
    ("scripts", ("*.py", "*.mjs")),
    ("data", ("pepperoni_landing_i18n*.json",)),
]
SKIP_PARTS = {"1", "2", "3", "4", "5", "node_modules", "site", "quarantine", "_quarantine_stale_syrokopch"}
SKIP_NAMES = {"check_wholesale_moq.py", "check_stm_min_run.py", "fix_moq_100kg.py", "fix_pages.py",
              "generate_geo_bulk.py", "bulk_fix_stale_content.py"}  # quote bad figures as prohibitions


def sentences(text: str):
    text = re.sub(r"<[^>]+>", " ", text)
    for s in re.split(r"(?<=[.!?…])\s+|\n+|\||[{}\[\]]", text):
        if s.strip():
            yield s


def scan(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    hits = []
    for sent in sentences(text):
        if not CTX.search(sent):
            continue
        m = FIGURE.search(sent)
        if not m:
            continue
        # «одна паллета (сборная …)» / «по 6 шт в коробе» inside an allowed sentence
        window = sent[max(0, m.start() - 80): m.end() + 40]
        if ALLOW.search(window):
            continue
        hits.append(re.sub(r"\s+", " ", sent.strip())[:170])
    return hits


def main() -> int:
    quiet = "--quiet" in sys.argv
    total = 0
    for rel, globs in SCAN:
        for g in globs:
            for p in sorted((ROOT / rel).rglob(g)):
                if p.name in SKIP_NAMES or set(p.relative_to(ROOT).parts) & SKIP_PARTS:
                    continue
                for h in scan(p):
                    total += 1
                    if not quiet:
                        print(f"{p.relative_to(ROOT)}: {h}")
    print(f"check_wholesale_moq: {total} non-pallet minimum-order figure(s) (canon: одна паллета / one pallet)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
