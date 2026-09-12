#!/usr/bin/env python3
"""Gate: every private-label (СТМ) minimum-run figure on the site must be the
owner-approved one — «от 5 тонн» (decision 2026-09-12, open-questions §4).

Before this gate the site carried invented minimums: 100 kg, 200 kg, 300 kg,
500 kg, 1000 kg, «2–5 т/мес», «500 кг/мес (пилот)». The class is "a mass
figure inside a private-label sentence", so that is what is scanned — in the
published pages AND in the sources that regenerate them (product overrides,
generator scripts, landing i18n).

Usage: python3 scripts/check_stm_min_run.py [--quiet]   → exit 1 on any hit.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CTX = re.compile(
    r"стм|private[- ]?label|white[- ]?label|own[- ]brand|под ваш\w* бренд|your brand|"
    r"контрактн\w* производств|contract manufactur|тираж|production run|per run|oem|"
    r"минимальн\w* пилот|серийн\w* объ[её]м|pilot batch|serial (?:supply|volume)|пилот от|pilot from|"
    r"buyer.s branding|your branding|custom packaging|branded (?:retail|sleeve|vacuum|pack)|под брендом заказчика|логотип\w* заказчика",
    re.I,
)
MASS = re.compile(r"(?<![\d,.])(\d[\d\s,.]{0,5})\s*(кг|kg|тонн\w*|т(?![а-яё])|tonnes?|tons?|t(?![a-z]))(?![а-яё\w])", re.I)
ALLOWED = re.compile(r"^\s*5\s*(тонн|т|tonnes?|tons?|t)\s*$", re.I)
# Pack/portion sizes are not minimum runs: «фасовка 0,5–5 кг», «10 kg box».
PACK_CTX = re.compile(r"фасовк|упаковк|pack|box|короб|case|sleeve|vacuum|вакуум|log|порци|slice|нарезк|вес изделия", re.I)
# «от 0,5 до 5 кг», «0.5–5 kg», «from 1 to 20 kg» are pack-size ranges, not runs.
RANGE = re.compile(r"(от|from|аз)?\s*\d[\d,.]*(?:\s*кг|\s*kg)?(?:-d[əe]n)?\s*(до|to|то|dan|–|-|—)\s*\d[\d,.]*\s*(кг|kg|г|g)(?:-d[əe]k| gacha)?\b", re.I)

SCAN_DIRS = [
    ("public", ("*.html", "*.txt", "*.md")),
    ("data/product_overrides", ("*.html",)),
    ("scripts", ("*.py",)),
    ("data", ("pepperoni_landing_i18n*.json",)),
]
SKIP_PARTS = {"1", "2", "3", "4", "5", "_quarantine_stale_syrokopch", "node_modules", "site"}
SKIP_NAMES = {"check_stm_min_run.py", "fix_moq_100kg.py"}


def sentences(text: str):
    text = re.sub(r"<[^>]+>", " ", text)
    for s in re.split(r"(?<=[.!?…])\s+|\n+|(?<=</li>)|\||[{}\[\]]", text):
        if s.strip():
            yield s


def scan_file(path: Path) -> list[tuple[str, str]]:
    hits = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return hits
    for sent in sentences(text):
        if not CTX.search(sent):
            continue
        for m in MASS.finditer(sent):
            figure = f"{m.group(1).strip()} {m.group(2)}"
            if ALLOWED.match(figure):
                continue
            window = sent[max(0, m.start() - 60): m.end() + 30]
            if RANGE.search(sent[max(0, m.start() - 25): m.end()]) and PACK_CTX.search(window):
                continue
            if PACK_CTX.search(window) and not re.search(r"минимал|minimum|moq|от\s*\d|from\s*\d|start", window, re.I):
                continue
            hits.append((figure, re.sub(r"\s+", " ", sent.strip())[:180]))
            break
    return hits


def main() -> int:
    quiet = "--quiet" in sys.argv
    total = 0
    for rel, globs in SCAN_DIRS:
        base = ROOT / rel
        for g in globs:
            for p in sorted(base.rglob(g)):
                if p.name.endswith(".bak") or p.name in SKIP_NAMES:
                    continue
                if set(p.relative_to(ROOT).parts) & SKIP_PARTS:
                    continue
                for figure, sent in scan_file(p):
                    total += 1
                    if not quiet:
                        print(f"{p.relative_to(ROOT)}: [{figure}] {sent}")
    print(f"check_stm_min_run: {total} non-approved private-label minimum figure(s) (approved: от 5 тонн)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
