#!/usr/bin/env python3
"""Guard against hardcoded product-count text drifting from the live catalog.

Why: on 2026-07-03/05 several files (public/.well-known/ai-meta.json,
public/openapi.yaml, public/faq.html, public/search.html,
public/blog/api.html, and — worse — a literal "77" baked into
scripts/sync-sheets.py's llms.txt generator function) kept saying "77
SKU/товаров/products" for days after the live catalog shrank to 72. Nobody
noticed until a manual audit. This script makes that class of drift
mechanically detectable instead of relying on the next audit to catch it.

What it does: scans public/**/*.{html,json,yaml,txt} and scripts/**/*.py for
numbers immediately adjacent to SKU-count vocabulary (SKU, товар(-ов/-а),
product(s), халяль товар) that do NOT match products.json's live
totalProducts. Known-correct numbers (prices, phone digits, dates, weights)
are excluded by requiring the count word directly before/after the number.

This is a detector, not a fixer — unlike reconcile_sku_count.py it doesn't
know how to safely rewrite arbitrary prose, so it just flags mismatches for
a human/agent to fix by hand or extend reconcile_sku_count.py's TARGETS.

Usage:
  python3 scripts/check_stale_counts.py            # scan + report
  python3 scripts/check_stale_counts.py --check    # same, exit 1 if any found (CI)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
PRODUCTS_JSON = PUBLIC / "products.json"

# Directories we never want to scan (archived/legacy, third-party, generated
# binary-ish artifacts, or things already covered by reconcile_sku_count.py).
SKIP_DIR_PARTS = {"node_modules", ".git", "1", "2", "3", "4", "5"}

# File globs to scan.
GLOBS = ["**/*.html", "**/*.json", "**/*.yaml", "**/*.yml", "**/*.txt"]

# Count-vocabulary words that make a nearby number "count-like". Case
# sensitive for RU (declension varies), case-insensitive for EN.
RU_WORDS = r"(?:SKU|SKUs|товар(?:ов|а|ы)?|наименовани[йяе])"
# Negative lookahead for "-" excludes CSS-class false positives like
# "h-100 product-card" / "col-6 product-grid".
EN_WORDS = r"(?:SKUs?|products?)(?!-)"

# Number immediately before/after a count word, with a space (not glued to
# other digits/letters, so prices like "68.77" or phones don't match).
PATTERNS = [
    re.compile(rf"(?<!\d)(\d{{1,4}})\s+{RU_WORDS}\b"),
    re.compile(rf"\b{RU_WORDS}\s*[:—-]?\s*(\d{{1,4}})(?!\d)"),
    re.compile(rf"(?<![\d-])(\d{{1,4}})\s+{EN_WORDS}\b", re.I),
    re.compile(rf'"product_count"\s*:\s*(\d{{1,4}})'),
]

# "numberOfItems" appears both for the whole-catalog ItemList/OfferCatalog
# AND for per-section OfferCatalog sub-lists (e.g. "Заморозка": 20 items) —
# only the former should equal totalProducts. Skip matches whose nearby
# context names a section, since those are legitimate sub-counts.
SECTION_NAMES = ("Заморозка", "Охлаждённая продукция", "Выпечка",
                  "Frozen Products", "Refrigerated Products", "Bakery")
NUMBER_OF_ITEMS_RE = re.compile(r'"numberOfItems"\s*:\s*(\d{1,4})')

# Substrings that make an otherwise-matching number a false positive (e.g.
# legitimate "N countries" multi-country feed descriptions, years, etc.)
# handled ad hoc — anything under 1000 that isn't close to totalProducts or
# a known multiplier is still flagged for human triage.


def get_live_count() -> int:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    n = data.get("totalProducts") or len(data.get("products", []))
    if not n:
        raise SystemExit("check_stale_counts: could not determine live SKU count")
    return n


def iter_files():
    for glob in GLOBS:
        for path in PUBLIC.glob(glob):
            if any(part in SKIP_DIR_PARTS for part in path.relative_to(PUBLIC).parts):
                continue
            yield path
    for path in SCRIPTS.glob("*.py"):
        yield path


def find_mismatches(n: int) -> list[tuple[Path, int, str]]:
    valid = {n, n * 7, n * 8}  # n*7/n*8 = multi-currency/multi-country feed item counts
    findings = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        seen_lines = set()
        all_patterns = PATTERNS + [NUMBER_OF_ITEMS_RE]
        for pattern in all_patterns:
            for m in pattern.finditer(text):
                num = int(m.group(1))
                if num in valid:
                    continue
                # Ignore tiny numbers (per-section counts like "9 SKU" for a
                # category page are legitimate and not the whole-catalog
                # count) — only flag numbers plausibly claiming to be the
                # *whole* catalog (within a loose band around historical
                # sizes) to avoid false positives on category sub-counts.
                if num < 20:
                    continue
                # Markdown section headers like "### Заморозка (20 товаров)"
                # are legitimate per-section sub-counts, not catalog totals.
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line_text = text[line_start:line_end if line_end != -1 else None]
                if line_text.lstrip().startswith("#") and any(
                        sec in line_text for sec in SECTION_NAMES):
                    continue
                # Skip numberOfItems entries whose nearby preceding context
                # names a specific section — those are legitimate sub-counts.
                if pattern is NUMBER_OF_ITEMS_RE:
                    context_before = text[max(0, m.start() - 80):m.start()]
                    if any(sec in context_before for sec in SECTION_NAMES):
                        continue
                line_no = text.count("\n", 0, m.start()) + 1
                if (path, line_no) in seen_lines:
                    continue
                seen_lines.add((path, line_no))
                snippet = text[max(0, m.start() - 40):m.end() + 20].replace("\n", " ")
                findings.append((path, line_no, snippet.strip()))
    return findings


def main() -> int:
    check_only = "--check" in sys.argv
    n = get_live_count()
    print(f"Live SKU count (products.json.totalProducts): {n}")

    findings = find_mismatches(n)
    if not findings:
        print("check_stale_counts: no stale product-count mentions found")
        return 0

    print(f"check_stale_counts: {len(findings)} potential stale count(s) found:\n")
    for path, line_no, snippet in sorted(findings):
        rel = path.relative_to(ROOT)
        print(f"  {rel}:{line_no}: ...{snippet}...")

    if check_only:
        print("\ncheck_stale_counts --check: mismatches found (see above)")
        return 1
    print("\nNote: this script only detects drift — fix by hand or extend "
          "reconcile_sku_count.py's TARGETS, then rerun to confirm clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
