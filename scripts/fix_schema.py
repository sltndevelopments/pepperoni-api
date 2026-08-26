#!/usr/bin/env python3
"""Deterministic Product JSON-LD repair (no LLM).

Keeps fields backed by the canonical catalog and removes merchant policies that
were previously invented to silence optional GSC warnings:
  ERROR   Missing field "image"                    → page og:image / brand fallback
  WARNING Missing field "description"              → page meta description
  REMOVE  shippingDetails / hasMerchantReturnPolicy → buyer-specific, not facts
  WARNING Missing field "priceCurrency" (in offers)
          → Product.offers / AggregateOffer: add priceCurrency (default RUB)
          → OfferCatalog thin Offer{itemOffered:Product} without price:
            convert to ListItem (not a shoppable Offer — no invented prices;
            GSC was flagging these catalog wrappers as Product offers)
  REMOVE  invalid gtin/gtin8/gtin12/gtin13/gtin14 values

review/aggregateRating are intentionally NOT touched: we have no real review
corpus and fabricated ratings violate Google policy (manual-action risk).
Those two warnings are cosmetic (rich-result enhancement unavailable), not errors.

Idempotent: re-running on an already-repaired page changes nothing. Designed to
run after every generation step in seo-agent-vps.sh and via the bot command
«почини schema».
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
SITE = "https://pepperoni.tatar"
FALLBACK_IMAGE = f"{SITE}/images/pepperoni-halal.png"

LD_RE = re.compile(r'(<script[^>]*application/ld\+json[^>]*>)(.*?)(</script>)',
                   re.S | re.I)
OG_IMAGE_RE = re.compile(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', re.I)
OG_IMAGE_RE2 = re.compile(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image', re.I)
META_DESC_RE = re.compile(r'name=["\']description["\'][^>]*content=["\']([^"\']+)', re.I)
META_DESC_RE2 = re.compile(r'content=["\']([^"\']+)["\'][^>]*name=["\']description', re.I)


def _absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return SITE + url
    return url


def _first(html: str, *regexes) -> str:
    for rx in regexes:
        m = rx.search(html)
        if m:
            return m.group(1).strip()
    return ""


def _iter_offer_dicts(offers):
    """Yield enrichable Offer dicts. AggregateOffer is skipped: Google merchant
    listings require a single Offer; shipping/return fields don't apply there."""
    nodes = offers if isinstance(offers, list) else [offers]
    for o in nodes:
        if isinstance(o, dict) and o.get("@type", "Offer") != "AggregateOffer":
            yield o


def _valid_gtin(value, expected_length: int | None = None) -> bool:
    digits = str(value or "").strip()
    if not digits.isdigit():
        return False
    allowed = {expected_length} if expected_length else {8, 12, 13, 14}
    if len(digits) not in allowed:
        return False
    payload = [int(char) for char in digits]
    check = payload.pop()
    total = sum(
        digit * (3 if (len(payload) - index) % 2 else 1)
        for index, digit in enumerate(payload)
    )
    return (10 - total % 10) % 10 == check


def enrich_product(node: dict, page_image: str, page_desc: str) -> bool:
    changed = False
    for key, length in (
        ("gtin", None), ("gtin8", 8), ("gtin12", 12),
        ("gtin13", 13), ("gtin14", 14),
    ):
        if key in node and not _valid_gtin(node[key], length):
            node.pop(key, None)
            changed = True
    img = node.get("image")
    if not img or (isinstance(img, list) and not any(img)):
        if page_image:
            node["image"] = _absolutize(page_image)
            changed = True
    elif isinstance(img, str) and img.startswith("/"):
        node["image"] = _absolutize(img)
        changed = True
    if not node.get("description") and page_desc:
        node["description"] = page_desc
        changed = True
    for offer in _iter_offer_dicts(node.get("offers")):
        if "shippingDetails" in offer:
            offer.pop("shippingDetails", None)
            changed = True
        if "hasMerchantReturnPolicy" in offer:
            offer.pop("hasMerchantReturnPolicy", None)
            changed = True
    return changed


def _types(node: dict) -> list:
    t = node.get("@type")
    if isinstance(t, list):
        return t
    return [t] if t else []


def _has_price_currency(offer: dict) -> bool:
    if offer.get("priceCurrency"):
        return True
    spec = offer.get("priceSpecification")
    if isinstance(spec, dict) and spec.get("priceCurrency"):
        return True
    if isinstance(spec, list):
        return any(isinstance(s, dict) and s.get("priceCurrency") for s in spec)
    return False


def _is_thin_catalog_offer(offer: dict) -> bool:
    """Offer that only wraps a Product — no price, not a real shoppable offer."""
    keys = set(offer.keys()) - {"@type"}
    if keys != {"itemOffered"}:
        return False
    if any(k in offer for k in ("price", "lowPrice", "highPrice", "priceSpecification")):
        return False
    io = offer.get("itemOffered")
    if isinstance(io, dict) and "Product" in _types(io):
        return True
    if isinstance(io, list) and any(
        isinstance(x, dict) and "Product" in _types(x) for x in io
    ):
        return True
    return False


def fix_offer_currency(node, stats: dict) -> bool:
    """Ensure every Offer touching Product has priceCurrency, without inventing prices.

    - Thin OfferCatalog wrappers (Offer → itemOffered Product, no price) become
      ListItem{item: Product}. GSC was treating them as Product offers missing
      priceCurrency; converting removes the false shoppable Offer.
    - Real Product.offers / AggregateOffer / priced Offer: set priceCurrency=RUB
      when missing (site catalog is RUB-primary).
    """
    changed = False
    if isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, dict) and any(
                t in ("Offer", "AggregateOffer") for t in _types(item)
            ):
                if not _has_price_currency(item):
                    if _is_thin_catalog_offer(item):
                        node[i] = {"@type": "ListItem", "item": item["itemOffered"]}
                        stats["offer_to_listitem"] += 1
                        changed = True
                        # still walk the product inside
                        if fix_offer_currency(node[i], stats):
                            changed = True
                        continue
                    item["priceCurrency"] = "RUB"
                    stats["currency_added"] += 1
                    changed = True
            if fix_offer_currency(item, stats):
                changed = True
        return changed
    if not isinstance(node, dict):
        return False
    if any(t in ("Offer", "AggregateOffer") for t in _types(node)):
        if not _has_price_currency(node):
            # Dict Offer (Product.offers / LocalBusiness.makesOffer) — нельзя
            # превратить в ListItem; ставим валюту, цену не выдумываем.
            node["priceCurrency"] = "RUB"
            stats["currency_added"] += 1
            changed = True
    for k, v in list(node.items()):
        if isinstance(v, (dict, list)):
            if fix_offer_currency(v, stats):
                changed = True
    return changed


def _walk_nodes(data):
    """Yield all dict nodes incl. @graph members and top-level lists."""
    stack = data if isinstance(data, list) else [data]
    for node in stack:
        if isinstance(node, dict):
            yield node
            for sub in node.get("@graph") or []:
                if isinstance(sub, dict):
                    yield sub


def process_file(path: Path, stats: dict | None = None) -> bool:
    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    # Product snippets OR OfferCatalog wrappers that GSC attributes to Product.
    if (
        '"Product"' not in html
        and "'Product'" not in html
        and "OfferCatalog" not in html
    ):
        return False
    page_image = _first(html, OG_IMAGE_RE, OG_IMAGE_RE2) or FALLBACK_IMAGE
    page_desc = _first(html, META_DESC_RE, META_DESC_RE2)
    local_stats = stats if stats is not None else {
        "offer_to_listitem": 0,
        "currency_added": 0,
    }

    changed = False

    def repl(m):
        nonlocal changed
        try:
            data = json.loads(m.group(2))
        except (json.JSONDecodeError, ValueError):
            return m.group(0)
        block_changed = False
        for node in _walk_nodes(data):
            if "Product" in _types(node):
                if enrich_product(node, page_image, page_desc):
                    block_changed = True
        if fix_offer_currency(data, local_stats):
            block_changed = True
        if not block_changed:
            return m.group(0)
        changed = True
        return m.group(1) + json.dumps(data, ensure_ascii=False,
                                       separators=(",", ":")) + m.group(3)

    new_html = LD_RE.sub(repl, html)
    if changed:
        path.write_text(new_html, encoding="utf-8")
    return changed


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    files = sorted(PUBLIC.rglob("*.html"))
    if only:
        files = [f for f in files if only in str(f)]
    stats = {"offer_to_listitem": 0, "currency_added": 0}
    touched = 0
    for f in files:
        if process_file(f, stats):
            touched += 1
    summary = (
        f"schema-fix: {len(files)} страниц просканировано, {touched} обогащено"
        f" (Offer→ListItem={stats['offer_to_listitem']},"
        f" priceCurrency+={stats['currency_added']})"
    )
    print(f"✅ {summary}")
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        import daily_ledger
        daily_ledger.append_event("done", summary)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
