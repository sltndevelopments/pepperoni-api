#!/usr/bin/env python3
"""Deterministic Product JSON-LD enricher (no LLM).

Fixes the GSC «Merchant listings / Product snippets» issues at the source:
  ERROR   Missing field "image"                    → page og:image / brand fallback
  WARNING Missing field "description"              → page meta description
  WARNING Missing field "shippingDetails"          → factual EXW-Kazan block
  WARNING Missing field "hasMerchantReturnPolicy"  → factual 14-day policy
  WARNING Missing field "returnShippingFeesAmount" → explicit 0 amount

review/aggregateRating are intentionally NOT touched: we have no real review
corpus and fabricated ratings violate Google policy (manual-action risk).
Those two warnings are cosmetic (rich-result enhancement unavailable), not errors.

Idempotent: re-running on an already-enriched page changes nothing. Designed to
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


def shipping_details(currency: str) -> dict:
    """Factual B2B terms: EXW Казань (Incoterms 2020) — no fabricated data."""
    return {
        "@type": "OfferShippingDetails",
        "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "RU"},
        "shippingRate": {"@type": "MonetaryAmount", "value": "0", "currency": currency},
        "deliveryTime": {
            "@type": "ShippingDeliveryTime",
            "handlingTime": {"@type": "QuantitativeValue", "minValue": 0,
                             "maxValue": 2, "unitCode": "DAY"},
            "transitTime": {"@type": "QuantitativeValue", "minValue": 1,
                            "maxValue": 7, "unitCode": "DAY"},
        },
    }


def return_policy(currency: str) -> dict:
    return {
        "@type": "MerchantReturnPolicy",
        "applicableCountry": "RU",
        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
        "merchantReturnDays": 14,
        "returnMethod": "https://schema.org/ReturnByMail",
        "returnFees": "https://schema.org/ReturnShippingFees",
        "returnShippingFeesAmount": {"@type": "MonetaryAmount", "value": "0",
                                     "currency": currency},
    }


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


def enrich_product(node: dict, page_image: str, page_desc: str) -> bool:
    changed = False
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
        currency = offer.get("priceCurrency") or "RUB"
        if "shippingDetails" not in offer:
            offer["shippingDetails"] = shipping_details(currency)
            changed = True
        rp = offer.get("hasMerchantReturnPolicy")
        if not isinstance(rp, dict):
            offer["hasMerchantReturnPolicy"] = return_policy(currency)
            changed = True
        elif (rp.get("returnFees") == "https://schema.org/ReturnShippingFees"
              and "returnShippingFeesAmount" not in rp):
            rp["returnShippingFeesAmount"] = {"@type": "MonetaryAmount",
                                              "value": "0", "currency": currency}
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


def process_file(path: Path) -> bool:
    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if '"Product"' not in html and "'Product'" not in html:
        return False
    page_image = _first(html, OG_IMAGE_RE, OG_IMAGE_RE2) or FALLBACK_IMAGE
    page_desc = _first(html, META_DESC_RE, META_DESC_RE2)

    changed = False

    def repl(m):
        nonlocal changed
        try:
            data = json.loads(m.group(2))
        except (json.JSONDecodeError, ValueError):
            return m.group(0)
        block_changed = False
        for node in _walk_nodes(data):
            if node.get("@type") in ("Product", ["Product"]):
                if enrich_product(node, page_image, page_desc):
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
    touched = 0
    for f in files:
        if process_file(f):
            touched += 1
    summary = f"schema-fix: {len(files)} страниц просканировано, {touched} обогащено"
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
