#!/usr/bin/env python3
"""Product.offers on /products/kd-* and /en/products/kd-* have itemCondition + url."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
ORIGIN = "https://pepperoni.tatar"
ORG_ID = "https://pepperoni.tatar/#organization"

fail = 0
LD_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def products(html: str) -> list[dict]:
    found = []
    for raw in LD_RE.findall(html):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            nodes = data["@graph"]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Product":
                found.append(node)
    return found


def main() -> int:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep = [e for e in man.get("entries") or [] if e.get("status") == "keep"]
    check(len(keep) == 250, f"keep stays 250 (got {len(keep)})")
    rows = [
        e for e in keep
        if e.get("file", "").startswith("products/kd-")
        or e.get("file", "").startswith("en/products/kd-")
    ]
    check(bool(rows), "keep list includes product cards")
    for entry in rows:
        rel = entry["file"]
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        prods = products(html)
        check(len(prods) == 1, f"{rel} has one Product")
        if not prods:
            continue
        offer = prods[0].get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        canon = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', html, re.I)
        canonical = canon.group(1) if canon else f"{ORIGIN}/{rel.replace('.html', '')}"
        check(offer.get("itemCondition") == "https://schema.org/NewCondition",
              f"{rel} offers.itemCondition is NewCondition")
        check(offer.get("url") == canonical, f"{rel} offers.url == canonical")
        check("priceValidUntil" not in offer, f"{rel} has no invented priceValidUntil")
        check("shippingDetails" not in offer, f"{rel} has no invented shippingDetails")
        check("hasMerchantReturnPolicy" not in offer,
              f"{rel} has no invented hasMerchantReturnPolicy")
        orgs = [
            n for raw in LD_RE.findall(html)
            for n in ([json.loads(raw.strip())] if raw.strip().startswith("{") else [])
            if isinstance(n, dict) and n.get("@type") == "Organization"
        ]
        if orgs:
            check(orgs[0].get("@id") == ORG_ID, f"{rel} Organization @id is canonical")
    ru_src = (ROOT / "scripts" / "gen-ru-products.py").read_text(encoding="utf-8")
    en_src = (ROOT / "scripts" / "gen-en-products.py").read_text(encoding="utf-8")
    check("itemCondition" in ru_src and "itemCondition" in en_src,
          "both product generators emit itemCondition")
    check('"url":"https://pepperoni.tatar/products/{slug}"' in ru_src.replace(" ", "")
          or "pepperoni.tatar/products/{slug}" in ru_src,
          "RU generator offer url is the page canonical")
    check("pepperoni.tatar/en/products/{slug}" in en_src,
          "EN generator offer url is the page canonical")
    if fail:
        print(f"test_product_offer_fields: {fail} FAIL")
        return 1
    print("test_product_offer_fields: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
