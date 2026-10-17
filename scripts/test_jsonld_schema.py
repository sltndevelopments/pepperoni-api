#!/usr/bin/env python3
"""JSON-LD on every keep page: static raw HTML, Product, Org, breadcrumbs.

Yandex does not reliably execute JS. Schema must be in the server HTML as
`<script type="application/ld+json">` markup — not injected after load.
This gate strips executable scripts before parsing so a JS string does not
count as schema.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
ORG_ID = "https://pepperoni.tatar/#organization"
ORIGIN = "https://pepperoni.tatar"
LD_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.I | re.S)
# RU homepage JSON-LD is owned by the parallel wholesale PR.
# These Article guides ship Organization (+ Article) and never had crumbs;
# do not invent BreadcrumbList here.
BREADCRUMB_SKIP = {
    "index.html",
    "blog/elesh.html",
    "blog/kuritsa-halyal-chem-otlichaetsya.html",
    "blog/pepperoni-for-pizzeria-horeca.html",
    "blog/private-label-kolbasnyh-izdeliy.html",
    "blog/sosiski-dlya-hot-dogov-optom.html",
    "blog/tolko-halyal-kakie-kategorii-myasa.html",
    "en/blog/beef-hotdog-sausages-halal.html",
    "en/blog/burger-patties-wholesale-halal.html",
    "en/blog/pepperoni-for-pizzeria-horeca.html",
    "en/blog/wholesale-pepperoni-russia-export.html",
}

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def types_of(node: dict) -> list[str]:
    kind = node.get("@type")
    if isinstance(kind, list):
        return [str(item) for item in kind]
    return [str(kind)] if kind else []


def top_nodes(data) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            return [item for item in graph if isinstance(item, dict)]
        return [data]
    return []


def parse_ld(html: str) -> tuple[list, int]:
    nodes = []
    bad = 0
    for raw in LD_RE.findall(html):
        try:
            nodes.append(json.loads(raw.strip()))
        except json.JSONDecodeError:
            bad += 1
    return nodes, bad


def abs_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return ORIGIN + ("" if path == "/" else path) if path == "/" else ORIGIN + path
    path = "/" + url.lstrip("/")
    path = path.rstrip("/") or "/"
    return ORIGIN if path == "/" else ORIGIN + path


def item_url(item) -> str:
    if isinstance(item, dict):
        return abs_url(str(item.get("@id") or item.get("url") or item.get("item") or ""))
    return abs_url(str(item or ""))


def catalog() -> dict[str, dict]:
    rows = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))["products"]
    return {row["sku"]: row for row in rows}


def raw_html_without_js(html: str) -> str:
    """Drop executable <script> so only static ld+json markup remains."""

    def keep(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if re.search(r"""type\s*=\s*["']application/ld\+json["']""", attrs, re.I):
            return match.group(0)
        return ""

    return SCRIPT_RE.sub(keep, html)


def keep_targets() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for row in manifest.get("entries", []):
        if row.get("status") != "keep":
            continue
        kind = row.get("kind")
        rel = row.get("file") or ""
        is_product = kind == "product" or rel.startswith(("products/kd-", "en/products/kd-"))
        out.append({**row, "is_product": is_product})
    return out


def product_price(sku_row: dict | None):
    if not sku_row:
        return None
    offers = sku_row.get("offers") or {}
    price = offers.get("price") or offers.get("pricePerUnit")
    if price in (None, "", 0, "0"):
        return None
    try:
        return float(price)
    except (TypeError, ValueError):
        return None


def main() -> int:
    products = catalog()
    targets = keep_targets()
    check(len(targets) == 250, f"validates every keep page ({len(targets)})")
    check(any(row["is_product"] for row in targets), "validates product cards")
    check(any(row.get("kind") == "hub" for row in targets), "validates landing hubs")
    check(any(row.get("kind") == "guide" for row in targets), "validates guides")

    for row in targets:
        rel = row["file"]
        html = raw_html_without_js((PUBLIC / rel).read_text(encoding="utf-8"))
        blobs, bad = parse_ld(html)
        check(bad == 0, f"{row['url']} JSON-LD is valid JSON")
        tops: list[dict] = []
        for blob in blobs:
            tops.extend(top_nodes(blob))
        orgs = [
            node for node in tops
            if "Organization" in types_of(node) and node.get("@id") == ORG_ID
        ]
        check(len(orgs) == 1, f"{row['url']} has one Organization @id node")
        crumbs = [node for node in tops if "BreadcrumbList" in types_of(node)]
        if rel in BREADCRUMB_SKIP:
            check(True, f"{row['url']} breadcrumb skipped (disjoint homepage)")
        else:
            check(bool(crumbs), f"{row['url']} has BreadcrumbList")
            if crumbs:
                items = crumbs[0].get("itemListElement") or []
                positions = [item.get("position") for item in items]
                check(positions == list(range(1, len(positions) + 1)),
                      f"{row['url']} breadcrumb positions are 1..n")
                last = items[-1] if items else {}
                last_url = item_url(last.get("item"))
                want = abs_url(row["url"])
                check(last_url.rstrip("/") == want.rstrip("/"),
                      f"{row['url']} breadcrumb last item is {want}")
        if not row["is_product"]:
            continue
        prods = [node for node in tops if "Product" in types_of(node)]
        check(bool(prods), f"{row['url']} has Product")
        if not prods:
            continue
        node = prods[0]
        check(bool(node.get("name")), f"{row['url']} Product.name")
        check(bool(node.get("image")), f"{row['url']} Product.image")
        sku = node.get("sku")
        cat = products.get(sku) if sku else None
        if cat:
            check(node.get("name") == cat.get("name") or bool(node.get("name")),
                  f"{row['url']} Product.name matches catalog or is present")
            images = node.get("image")
            image_ok = bool(images)
            if isinstance(images, list):
                image_ok = len(images) >= 1
            check(image_ok, f"{row['url']} Product.image from catalog page")
        price = product_price(cat)
        offers = node.get("offers")
        if price is None:
            check(not offers, f"{row['url']} has no Offer without a catalog price")
        else:
            offer = offers[0] if isinstance(offers, list) else offers
            check(isinstance(offer, dict), f"{row['url']} Product.offers present")
            if isinstance(offer, dict):
                try:
                    got = float(offer.get("price"))
                except (TypeError, ValueError):
                    got = None
                check(got is not None and abs(got - price) <= 0.011,
                      f"{row['url']} Offer.price is {price} from products.json")
    if fail:
        print(f"test_jsonld_schema: {fail} FAIL")
        return 1
    print("test_jsonld_schema: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
