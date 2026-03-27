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
# Order matters: more specific prefixes must come before shorter ones
PRODUCT_MAP = {
    # Pepperoni — specific types first
    "pepperoni-govyadina": ["kd-015", "kd-016", "kd-017", "kd-018"],  # beef pepperoni
    "pepperoni-kurica":    ["kd-015", "kd-016", "kd-017", "kd-018"],  # chicken (same line)
    "pepperoni-konina":    ["kd-014"],                                  # horse meat pepperoni
    "pepperoni-miks":      ["kd-015", "kd-014", "kd-017"],             # mixed pepperoni
    "pepperoni":           ["kd-014", "kd-015", "kd-016", "kd-017", "kd-018"],  # all pepperoni
    # Other products
    "kotlety-dlya-burgerov": ["kd-009", "kd-010"],                     # burger patties
    "sosiki-dlya-hotdog":    ["kd-001", "kd-002", "kd-003", "kd-004", "kd-005"],  # hot dog sausages
    "kazylyk":               ["kd-057", "kd-058"],                     # kazylyk
    "vetchina":              ["kd-036", "kd-037", "kd-038", "kd-039"],  # ham
    "sosiki":                ["kd-019", "kd-020", "kd-021", "kd-022"],  # chilled sausages
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
    # Check longer prefixes first to avoid "pepperoni" matching "pepperoni-govyadina"
    for prefix in sorted(PRODUCT_MAP.keys(), key=len, reverse=True):
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

    slug = path.stem
    product_type = get_product_type(slug)
    if not product_type:
        return False

    skus = PRODUCT_MAP[product_type]

    if lang == "en":
        block = build_products_block_en(skus)
    else:
        block = build_products_block_ru(skus)

    # Remove existing geo-products block if present (to replace with correct one)
    html = re.sub(r'\n?<section class="geo-products">.*?</section>\n?', '', html, flags=re.DOTALL)

    # Inject before CTA, </main>, or before <footer>
    if '<div class="cta-block">' in html:
        html = html.replace('<div class="cta-block">', block + '<div class="cta-block">', 1)
    elif "</main>" in html:
        html = html.replace("</main>", block + "</main>", 1)
    elif "<footer" in html:
        html = html.replace("<footer", block + "<footer", 1)
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
