#!/usr/bin/env python3
"""Bulk repair of two classes of stale/fabricated content found in the
2026-07-03 external audit (see data/audit_reconcile.md). Deterministic,
no LLM. Designed to be run ONCE from Composer as an explicit bulk step —
per CLAUDE.md this is exactly the kind of "Bulk без явного Current step"
that must not run silently from the daily pipeline.

Two independent, separately-gated fixes:

  A) STALE SKU-COUNT TEXT ("77 SKU" / "77 товаров" / "77 наименований" / …)
     baked into the body of ~400 already-published static pages (geo, blog,
     private-label, export, ar/kk/az locales). The live catalog is 72 SKUs
     (see public/products.json -> totalProducts, kept in sync by
     scripts/reconcile_sku_count.py for the small set of files it covers —
     this script covers everything else). Safe, mechanical text substitution
     with a fixed set of known phrase patterns; does not touch numbers that
     are not the total-catalog-count (e.g. price digits, addresses, dates).

  B) FABRICATED aggregateRating IN JSON-LD (~440 pages). Real customer
     reviews do not exist for this catalog — the numbers ("4.8/5, 24 ratings"
     etc.) were invented by a page generator and violate the halal/brand
     honesty rule (CLAUDE.md §5: "Никаких выдуманных отзывов/рейтингов") and
     Google's structured-data policy (fabricated ratings = manual-action
     risk). scripts/fix_schema.py and data/invariants.json already guard the
     GENERATOR from re-adding this; this script is the one-time cleanup of
     EXISTING pages that predate that guard. Removes the aggregateRating
     object entirely (does not fabricate a "0 reviews" substitute — absence
     is honest, a fake zero is not better).

Usage:
    python3 scripts/bulk_fix_stale_content.py --dry-run          # report only
    python3 scripts/bulk_fix_stale_content.py --fix-sku-text     # apply (A)
    python3 scripts/bulk_fix_stale_content.py --fix-ratings      # apply (B)
    python3 scripts/bulk_fix_stale_content.py --fix-sku-text --fix-ratings

Always run --dry-run first and read the counts before applying. After
applying, run scripts/fix_pages.py + scripts/qa_pages.py --quarantine
(the standard QA gate) before committing, per pepperoni-infra.mdc.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
PRODUCTS_JSON = PUBLIC / "products.json"


def get_live_sku_count() -> int:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    n = data.get("totalProducts")
    if not isinstance(n, int) or n <= 0:
        n = len(data.get("products", []))
    if not n:
        raise SystemExit("bulk_fix_stale_content: could not determine live SKU count")
    return n


def iter_content_files():
    # HTML + a few text surfaces that still bake in whole-catalog counts.
    # Skip quarantine (regenerated separately).
    for p in PUBLIC.rglob("*.html"):
        if "_quarantine" in p.parts or p.name.startswith("_removed_"):
            continue
        yield p
    for p in PUBLIC.rglob("*.txt"):
        if "_quarantine" in p.parts:
            continue
        yield p


# ---------------------------------------------------------------------------
# (A) Stale "77 SKU" text
# ---------------------------------------------------------------------------

def ru_tovar(n: int) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} товар"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return f"{n} товара"
    return f"{n} товаров"


STATE_FILE = ROOT / "data" / "sku_count_state.json"
# Historic whole-catalog totals that still appear in published HTML.
BASE_STALE_COUNTS = {72, 77}


def stale_counts(live_n: int) -> list[int]:
    """Counts to rewrite → live_n. Excludes the live total itself."""
    olds = set(BASE_STALE_COUNTS)
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for key in ("previous", "current"):
                v = st.get(key)
                if isinstance(v, int) and v > 0:
                    olds.add(v)
        except Exception:
            pass
    olds.discard(live_n)
    return sorted(olds, reverse=True)


def _naimenovanie(n: int) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} наименование"
    if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
        return f"{n} наименования"
    return f"{n} наименований"


def sku_text_rules(n: int) -> list[tuple[re.Pattern, str]]:
    """Narrow patterns for stale whole-catalog counts (72/77/previous).

    Deliberately does NOT use a generic \\d+ SKU pattern — that would also
    rewrite unrelated numbers (e.g. MOQ "308 kg per SKU").
    """
    rules: list[tuple[re.Pattern, str]] = []
    for old in stale_counts(n):
        rules.extend([
            (re.compile(rf"\b{old}\+?\s*SKUs?\b"), f"{n} SKUs"),
            (re.compile(rf"\b{old}-SKU\b"), f"{n}-SKU"),
            (re.compile(rf"\b{old}\s*halal SKU\b", re.I), f"{n} halal SKU"),
            (re.compile(rf"\b{old}\s*Halal SKU\b"), f"{n} Halal SKU"),
            (re.compile(rf"\b{old}\s*SKU\s*халяль"), f"{n} SKU халяль"),
            (re.compile(rf"\b{old}\s*SKU\s*өнімдер"), f"{n} SKU өнімдер"),
            (re.compile(rf"\b{old}\s+товар(?:ов|а)?\b"), ru_tovar(n)),
            (re.compile(rf"\b{old}\s+наименован(?:ий|ия|ие)\b"), _naimenovanie(n)),
            (re.compile(rf"\b{old}\s*SKU\b"), f"{n} SKU"),
        ])
    return rules


def scan_sku_text(files) -> dict[Path, int]:
    rules = sku_text_rules(get_live_sku_count())
    hits: dict[Path, int] = {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        count = 0
        for pattern, _repl in rules:
            count += len(pattern.findall(text))
        if count:
            hits[f] = count
    return hits


def fix_sku_text(files) -> Counter:
    n = get_live_sku_count()
    rules = sku_text_rules(n)
    stats = Counter()
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        original = text
        for pattern, repl in rules:
            text = pattern.sub(repl, text)
        if text != original:
            f.write_text(text, encoding="utf-8")
            stats["files_changed"] += 1
    return stats


# ---------------------------------------------------------------------------
# (B) Fabricated aggregateRating
# ---------------------------------------------------------------------------

# Matches a JSON-LD aggregateRating object with or without a preceding comma,
# on a single line (all generated JSON-LD in this codebase is minified/inline).
RATING_PATTERN = re.compile(
    r',?\s*"aggregateRating"\s*:\s*\{\s*"@type"\s*:\s*"AggregateRating"[^{}]*\}'
)


def scan_ratings(files) -> dict[Path, int]:
    hits: dict[Path, int] = {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        count = len(RATING_PATTERN.findall(text))
        if count:
            hits[f] = count
    return hits


def fix_ratings(files) -> Counter:
    stats = Counter()
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        original = text
        text = RATING_PATTERN.sub("", text)
        # Also strip a lone top-level "review" array if present alongside
        # (same fabrication family); harmless no-op if absent.
        text = re.sub(r',?\s*"review"\s*:\s*\[[^\[\]]*\]', "", text)
        if text != original:
            # Validate every JSON-LD blob on the page still parses before
            # writing — refuse to leave broken JSON on a live page.
            broken = False
            for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
                try:
                    json.loads(m.group(1))
                except json.JSONDecodeError:
                    broken = True
                    break
            if broken:
                stats["skipped_would_break_json"] += 1
                continue
            f.write_text(text, encoding="utf-8")
            stats["files_changed"] += 1
    return stats


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report counts only, write nothing")
    ap.add_argument("--fix-sku-text", action="store_true", help="apply fix (A): stale SKU-count text")
    ap.add_argument("--fix-ratings", action="store_true", help="apply fix (B): fabricated aggregateRating")
    args = ap.parse_args()

    if not (args.dry_run or args.fix_sku_text or args.fix_ratings):
        ap.print_help()
        return 1

    n = get_live_sku_count()
    print(f"Live SKU count: {n}")
    print(f"Stale counts to rewrite: {stale_counts(n)}\n")

    files = list(iter_content_files())
    print(f"Scanning {len(files)} files under public/ …\n")

    if args.dry_run or args.fix_sku_text:
        hits = scan_sku_text(files)
        total = sum(hits.values())
        print(f"[A] Stale SKU-count text: {len(hits)} files, {total} occurrences")
        for f, c in sorted(hits.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {c:3d}  {f.relative_to(ROOT)}")
        if len(hits) > 10:
            print(f"    … and {len(hits) - 10} more files")
        print()
        if args.fix_sku_text:
            stats = fix_sku_text(list(hits.keys()))
            print(f"[A] Applied: {stats['files_changed']} files patched\n")

    if args.dry_run or args.fix_ratings:
        hits = scan_ratings(files)
        total = sum(hits.values())
        print(f"[B] Fabricated aggregateRating: {len(hits)} files, {total} occurrences")
        for f, c in sorted(hits.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {c:3d}  {f.relative_to(ROOT)}")
        if len(hits) > 10:
            print(f"    … and {len(hits) - 10} more files")
        print()
        if args.fix_ratings:
            stats = fix_ratings(list(hits.keys()))
            print(f"[B] Applied: {stats['files_changed']} files patched, "
                  f"{stats['skipped_would_break_json']} skipped (would break JSON)\n")

    if args.dry_run:
        print("Dry run only — nothing was written. Re-run with --fix-sku-text "
              "and/or --fix-ratings to apply.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
