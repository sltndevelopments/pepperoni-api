#!/usr/bin/env python3
"""Strip shoppable Product offers from geo landings (GMC crawl source).

Geo pages are marketing landings, not SKU cards. Product+Offer with a local
currency (MYR etc.) gets ingested by Merchant Center «Found by Google» as
ghost offers (frh-ipoh-2024, pep-kl-2024, …) outside the 64-SKU feed.

Idempotent. Default: only pages whose Product offers use currencies in
--currencies (default MYR). Use --all-geo-currencies to strip every geo Offer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
LD_RE = re.compile(
    r'(<script[^>]*application/ld\+json[^>]*>)(.*?)(</script>)', re.S | re.I
)


def is_product(node: dict) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return "Product" in types


def offer_currencies(offers) -> set[str]:
    out: set[str] = set()
    if isinstance(offers, dict):
        c = offers.get("priceCurrency")
        if c:
            out.add(str(c).upper())
        for o in offers.get("offers") or []:
            if isinstance(o, dict) and o.get("priceCurrency"):
                out.add(str(o["priceCurrency"]).upper())
    elif isinstance(offers, list):
        for o in offers:
            if isinstance(o, dict) and o.get("priceCurrency"):
                out.add(str(o["priceCurrency"]).upper())
    return out


def strip_product_offers(node, currencies: set[str] | None, stats: dict) -> bool:
    """Return True if anything changed."""
    changed = False
    if isinstance(node, list):
        for x in node:
            if strip_product_offers(x, currencies, stats):
                changed = True
        return changed
    if not isinstance(node, dict):
        return False

    if is_product(node) and "offers" in node:
        curs = offer_currencies(node.get("offers"))
        # Strip when: all-geo mode, or offer currency intersects target set.
        should = currencies is None or bool(curs & currencies)
        if should:
            del node["offers"]
            stats["offers_removed"] += 1
            changed = True
            # Drop invented SKUs that become GMC offerIds
            sku = str(node.get("sku") or "")
            if sku and not re.fullmatch(r"KD-\d{3}", sku, re.I):
                node.pop("sku", None)
                stats["sku_cleared"] += 1

    if "@graph" in node:
        if strip_product_offers(node["@graph"], currencies, stats):
            changed = True
    for k, v in list(node.items()):
        if k == "@graph":
            continue
        if isinstance(v, (dict, list)):
            if strip_product_offers(v, currencies, stats):
                changed = True
    return changed


def process_file(path: Path, currencies: set[str] | None, dry_run: bool) -> dict:
    html = path.read_text(encoding="utf-8", errors="replace")
    stats = {"offers_removed": 0, "sku_cleared": 0, "blocks": 0}
    out_parts: list[str] = []
    last = 0
    file_changed = False

    for m in LD_RE.finditer(html):
        out_parts.append(html[last : m.start()])
        prefix, raw, suffix = m.group(1), m.group(2), m.group(3)
        try:
            data = json.loads(raw)
        except Exception:
            out_parts.append(m.group(0))
            last = m.end()
            continue
        if strip_product_offers(data, currencies, stats):
            file_changed = True
            stats["blocks"] += 1
            new_raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            out_parts.append(prefix + new_raw + suffix)
        else:
            out_parts.append(m.group(0))
        last = m.end()

    if not file_changed:
        return stats

    out_parts.append(html[last:])
    if not dry_run:
        path.write_text("".join(out_parts), encoding="utf-8")
    stats["file_changed"] = 1
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--currencies",
        default="MYR",
        help="Comma-separated offer currencies to strip (default MYR). "
        "Use ALL to strip every geo Product offer.",
    )
    ap.add_argument(
        "--paths",
        nargs="*",
        help="Optional explicit files; default: public/**/geo/**.html",
    )
    args = ap.parse_args()

    if args.currencies.strip().upper() == "ALL":
        currencies: set[str] | None = None
    else:
        currencies = {c.strip().upper() for c in args.currencies.split(",") if c.strip()}

    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        files = sorted(PUBLIC.rglob("geo/**/*.html"))

    total = {"files": 0, "offers_removed": 0, "sku_cleared": 0}
    for f in files:
        if not f.is_file():
            continue
        # Pre-filter: skip files without Product / target currency text
        text = f.read_text(encoding="utf-8", errors="replace")
        if "Product" not in text:
            continue
        if currencies is not None and not any(c in text for c in currencies):
            continue
        st = process_file(f, currencies, args.dry_run)
        if st.get("file_changed") or st["offers_removed"]:
            total["files"] += 1
            total["offers_removed"] += st["offers_removed"]
            total["sku_cleared"] += st["sku_cleared"]
            print(f"{'DRY ' if args.dry_run else ''}{f.relative_to(ROOT)} "
                  f"offers-{st['offers_removed']} sku-{st['sku_cleared']}")

    print(
        f"\nSummary: files={total['files']} offers_removed={total['offers_removed']} "
        f"sku_cleared={total['sku_cleared']} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    # Fix accidental walrus in LD_RE — rewrite cleanly below if import fails
    raise SystemExit(main())
