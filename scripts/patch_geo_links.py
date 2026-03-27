#!/usr/bin/env python3
"""
Add relevant product page links to geo pages.
Each geo page gets a "Products" block with 3-5 links to matching product SKUs.
This passes SEO weight from geo pages to product pages.

Run: python scripts/patch_geo_links.py
"""

import json
import re
from pathlib import Path

PUBLIC   = Path(__file__).parent.parent / "public"
PRODUCTS = json.loads((PUBLIC / "products.json").read_text())["products"]

# Map geo page slug prefix → matching product SKUs
PRODUCT_MAP = {
    "pepperoni": ["kd-026", "kd-027", "kd-028", "kd-029", "kd-030"],  # pepperoni line
    "kotlety-dlya-burgerov": ["kd-009", "kd-010"],                     # burger patties
    "sosiki-dlya-hotdog": ["kd-001", "kd-002", "kd-003", "kd-004", "kd-005"],  # hot dog sausages
    "kazylyk": ["kd-057", "kd-058"],                                   # kazylyk
    "vetchina": ["kd-036", "kd-037", "kd-038", "kd-039"],             # ham
    "sosiki": ["kd-019", "kd-020", "kd-021", "kd-022"],               # chilled sausages
}

# Build SKU → product name map
SKU_NAMES = {p["sku"].lower(): p["name"] for p in PRODUCTS}
SKU_NAMES_EN = {}
for p in PRODUCTS:
    sku = p["sku"].lower()
    en_desc = p.get("seoDescriptionEN", "")
    if en_desc:
        short = en_desc.split("|")[0].strip()
        if short:
            SKU_NAMES_EN[sku] = short[:60]
    if sku not in SKU_NAMES_EN:
        SKU_NAMES_EN[sku] = p["name"][:60]


def get_product_type(slug: str):
    for prefix in PRODUCT_MAP:
        if slug.startswith(prefix):
            return prefix
    return None


def build_products_block_ru(skus: list[str]) -> str:
    items = []
    for sku in skus:
        name = SKU_NAMES.get(sku, sku)
        items.append(f'<li><a href="/products/{sku}">{name}</a></li>')
    return (
        '\n<section class="geo-products">'
        '<h2>Продукты в каталоге</h2>'
        f'<ul>{"".join(items)}</ul>'
        '</section>\n'
    )


def build_products_block_en(skus: list[str]) -> str:
    items = []
    for sku in skus:
        name = SKU_NAMES_EN.get(sku, sku)
        items.append(f'<li><a href="/en/products/{sku}">{name}</a></li>')
    return (
        '\n<section class="geo-products">'
        '<h2>Products in Catalog</h2>'
        f'<ul>{"".join(items)}</ul>'
        '</section>\n'
    )


GEO_PRODUCTS_CSS = """
.geo-products{max-width:800px;margin:2rem auto;padding:1.2rem 1.5rem;background:var(--green-light,#e8f5e9);border-radius:10px}
.geo-products h2{font-size:1.2rem;color:var(--green,#1b7a3d);margin-bottom:.8rem}
.geo-products ul{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:.5rem}
.geo-products li a{display:inline-block;padding:.3rem .8rem;background:#fff;border:1px solid var(--green,#1b7a3d);border-radius:6px;color:var(--green,#1b7a3d);font-size:.9rem;text-decoration:none}
.geo-products li a:hover{background:var(--green,#1b7a3d);color:#fff}
"""


def patch_geo_file(path: Path, lang: str = "ru") -> bool:
    html = path.read_text(encoding="utf-8")

    if "geo-products" in html:
        return False  # already patched

    slug = path.stem
    product_type = get_product_type(slug)
    if not product_type:
        return False

    skus = PRODUCT_MAP[product_type]

    if lang == "en":
        block = build_products_block_en(skus)
    else:
        block = build_products_block_ru(skus)

    # Inject before CTA or before </main>
    if '<div class="cta-block">' in html:
        html = html.replace('<div class="cta-block">', block + '<div class="cta-block">', 1)
    elif "</main>" in html:
        html = html.replace("</main>", block + "</main>", 1)
    else:
        return False

    # Add CSS
    if ".geo-products" not in html:
        html = html.replace("</style>", GEO_PRODUCTS_CSS + "</style>", 1)

    path.write_text(html, encoding="utf-8")
    return True


def main():
    patched = 0

    for path in sorted((PUBLIC / "geo").glob("*.html")):
        if patch_geo_file(path, "ru"):
            patched += 1

    # EN geo pages if they exist
    en_geo = PUBLIC / "en" / "geo"
    if en_geo.exists():
        for path in sorted(en_geo.glob("*.html")):
            if patch_geo_file(path, "en"):
                patched += 1

    print(f"✅ Geo pages patched with product links: {patched}")


if __name__ == "__main__":
    main()
