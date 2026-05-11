#!/usr/bin/env python3
"""Generate a Google Merchant Center / OpenAI Commerce-compatible product feed.

Outputs:
  public/products-feed.csv   — GMC CSV (tab-separated, GMC standard)
  public/products-feed.xml   — RSS 2.0 / Google Merchant XML feed
  public/products-feed.json  — Schema.org ItemList for AI crawlers (Bing, Perplexity, ChatGPT)

Sources:
  public/products.json        — live catalog (77 SKUs)
  scripts/translations.json   — RU → EN translation map for names, categories, sections
"""
from __future__ import annotations
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = PUBLIC / "products.json"
TRANSLATIONS = ROOT / "scripts" / "translations.json"

BASE_URL = "https://pepperoni.tatar"
BRAND = "Kazan Delicacies"
COUNTRY = "RU"
CURRENCY = "RUB"

# Google taxonomy IDs — https://www.google.com/basepages/producttype/taxonomy.en-US.txt
TAXONOMY = {
    "Заморозка":              ("420",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Meat"),
    "Охлаждённая продукция":  ("420",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Meat"),
    "Выпечка":                ("1876", "Food, Beverages & Tobacco > Food Items > Bakery"),
}
# More specific overrides per category
CATEGORY_TAXONOMY = {
    "Пепперони (вар-коп, конина, сырокоп)": ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Пепперони вар-коп":                    ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Пепперони сырокопчёный":               ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Пепперони":                            ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Сосиски, сардельки":                   ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Сосиски гриль для хот-догов":          ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Вареные":                              ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Копченые":                             ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Премиум Казылык":                      ("5740", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Sausages"),
    "Ветчины":                              ("431",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Lunch & Deli Meats"),
    "Котлеты для бургеров":                 ("420",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Meat"),
    "Топпинги":                             ("420",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Meat"),
    "Мясные заготовки":                     ("420",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Meat"),
    "Грудка куриная":                       ("431",  "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Lunch & Deli Meats"),
    "Национальная татарская выпечка":       ("1876", "Food, Beverages & Tobacco > Food Items > Bakery"),
}

# Default placeholder image when product has no specific image
DEFAULT_IMAGE = "https://pepperoni.tatar/images/logo.png"

OG_BY_SECTION = {
    "Заморозка":             "https://pepperoni.tatar/og-default-en.png",
    "Охлаждённая продукция": "https://pepperoni.tatar/og-pepperoni-en.png",
    "Выпечка":               "https://pepperoni.tatar/og-bakery-en.png",
}


def load():
    products = json.loads(DATA.read_text(encoding="utf-8")).get("products", [])
    tr = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    return products, tr


def t_product(name_ru: str, tr: dict) -> str:
    if not name_ru:
        return ""
    key = name_ru.strip().lower()
    out = tr.get("products", {}).get(key)
    if out:
        return out
    # Try without trailing weight bracket
    base = re.sub(r"\s*\([^)]*\)\s*$", "", name_ru).strip().lower()
    out = tr.get("products", {}).get(base)
    if out:
        return out
    return name_ru  # fall back to RU


def t_category(cat_ru: str, tr: dict) -> str:
    if not cat_ru:
        return ""
    return tr.get("categories", {}).get(cat_ru, cat_ru)


def t_section(sec_ru: str, tr: dict) -> str:
    return tr.get("sections", {}).get(sec_ru, sec_ru)


def parse_seo(s: str):
    """Parse seoDescriptionEN: 'Title | Headline | Tagline | Long'."""
    if not s:
        return (None, None, None, None)
    parts = [p.strip() for p in s.split("|")]
    while len(parts) < 4:
        parts.append("")
    return parts[0], parts[1], parts[2], parts[3]


def derive_title(p: dict, tr: dict) -> str:
    """Build a GMC-compliant title (≤150 chars, EN).

    GMC ranks titles with brand + key attribute + product highly. We aim for
    ~50-130 chars: "Halal {NAME} ({WEIGHT}) — Kazan Delicacies".
    """
    seo_title, _, _, _ = parse_seo(p.get("seoDescriptionEN", ""))
    name_en = seo_title or t_product(p.get("name", ""), tr)
    name_en = re.sub(r"\s+", " ", name_en).strip()

    # Halal prefix (skip if already present)
    halal_prefix = "" if re.search(r"\bhalal\b", name_en, re.I) else "Halal "
    title = f"{halal_prefix}{name_en}"

    # If still short, append weight and section
    weight = p.get("weight", "")
    needs_weight = weight and weight not in title and "(" not in title
    if len(title) < 60 and needs_weight:
        title = f"{title} ({weight} kg)"

    # Append brand suffix unless already obviously branded
    brand_suffix = f" — {BRAND}"
    if BRAND.lower() not in title.lower() and len(title) + len(brand_suffix) <= 150:
        title = f"{title}{brand_suffix}"

    return title[:150]


def derive_description(p: dict, tr: dict) -> str:
    """Build a GMC-compliant description (≥150, ≤5000 chars, EN)."""
    seo_title, headline, tagline, long_desc = parse_seo(p.get("seoDescriptionEN", ""))
    chunks = []
    if long_desc and len(long_desc) >= 50:
        chunks.append(long_desc)
    elif headline and tagline:
        chunks.append(headline)
        chunks.append(tagline)
    # Add structured attributes when SEO description is thin
    if sum(len(c) for c in chunks) < 150:
        name_en = derive_title(p, tr)
        cat_en = t_category(p.get("category", ""), tr)
        sec_en = t_section(p.get("section", ""), tr)
        weight = p.get("weight", "")
        shelf = p.get("shelfLife", "")
        storage = p.get("storage", "")
        chunks.append(
            f"{name_en} — halal {cat_en.lower()} from Kazan Delicacies, {sec_en.lower()} category."
        )
        if weight:
            chunks.append(f"Net weight: {weight} kg.")
        if shelf:
            shelf_clean = shelf.replace("суток", "days").replace("сутки", "days").replace("месяцев", "months")
            chunks.append(f"Shelf life: {shelf_clean}.")
        if storage:
            chunks.append(f"Storage: {storage}.")
    # Halal + sourcing pitch — always include for AI parsing
    chunks.append(
        "HALAL certified #614A/2024 (DUM RT). HACCP & ISO 22000. "
        "100% pork-free. Wholesale from Kazan (Tatarstan, Russia). EXW Kazan / DC Lyubertsy."
    )
    desc = " ".join(c for c in chunks if c).strip()
    # Clean double-spaces and ensure 150-5000 char window
    desc = re.sub(r"\s+", " ", desc)
    if len(desc) < 150:
        desc += (" Suitable for pizzerias, HoReCa, fuel-station street food, retail chains, "
                 "and distributors. Live pricing at api.pepperoni.tatar.")
    return desc[:5000]


def derive_link(p: dict) -> str:
    sku = p.get("sku", "").lower()
    return f"{BASE_URL}/en/products/{sku}"


def derive_link_ru(p: dict) -> str:
    sku = p.get("sku", "").lower()
    return f"{BASE_URL}/products/{sku}"


def derive_image(p: dict) -> str:
    return (p.get("imageMain")
            or p.get("image")
            or OG_BY_SECTION.get(p.get("section"), "")
            or DEFAULT_IMAGE)


def derive_additional_images(p: dict) -> list:
    out = []
    for k in ("imagePack", "imageSlice"):
        v = p.get(k)
        if v and v != p.get("imageMain") and v != p.get("image"):
            out.append(v)
    return out[:10]  # GMC limit


def derive_price(p: dict) -> str:
    """RUB price WITH VAT. Format: '290.00 RUB'."""
    pr = (p.get("offers") or {}).get("price")
    if not pr:
        return ""
    try:
        v = float(str(pr).replace(",", "."))
        return f"{v:.2f} {CURRENCY}"
    except Exception:
        return f"{pr} {CURRENCY}"


def derive_price_no_vat(p: dict) -> str:
    pr = (p.get("offers") or {}).get("priceExclVAT")
    if not pr:
        return ""
    try:
        v = float(str(pr).replace(",", "."))
        return f"{v:.2f} {CURRENCY}"
    except Exception:
        return ""


def derive_taxonomy(p: dict):
    cat = p.get("category", "")
    sec = p.get("section", "")
    if cat in CATEGORY_TAXONOMY:
        return CATEGORY_TAXONOMY[cat]
    if sec in TAXONOMY:
        return TAXONOMY[sec]
    return ("420", "Food, Beverages & Tobacco > Food Items > Meat & Poultry > Meat")


def derive_product_type(p: dict, tr: dict) -> str:
    sec = t_section(p.get("section", ""), tr)
    cat = t_category(p.get("category", ""), tr)
    name = derive_title(p, tr)
    parts = [x for x in (sec, cat, name) if x]
    return " > ".join(parts)


def derive_custom_labels(p: dict, tr: dict) -> dict:
    package = p.get("packageType", "")
    package_en = tr.get("packageTypes", {}).get(package, package)
    return {
        "custom_label_0": "halal",
        "custom_label_1": t_section(p.get("section", ""), tr).lower().replace(" products", ""),
        "custom_label_2": t_category(p.get("category", ""), tr),
        "custom_label_3": package_en,
        "custom_label_4": "halal-#614A/2024",
    }


def build_row(p: dict, tr: dict) -> dict:
    google_cat_id, google_cat_path = derive_taxonomy(p)
    return {
        "id": p.get("sku", ""),
        "title": derive_title(p, tr),
        "description": derive_description(p, tr),
        "link": derive_link(p),
        "image_link": derive_image(p),
        "additional_image_link": ",".join(derive_additional_images(p)),
        "availability": "in_stock",
        "price": derive_price(p),
        "sale_price": "",
        "brand": BRAND,
        "gtin": p.get("barcode", ""),
        "mpn": p.get("articleNumber", "") or p.get("sku", ""),
        "condition": "new",
        "identifier_exists": "yes" if p.get("barcode") else "no",
        "google_product_category": google_cat_id,
        "product_type": derive_product_type(p, tr),
        "shipping": f"{COUNTRY}:::0.00 {CURRENCY}",
        "shipping_weight": (p.get("weight", "") + " kg") if p.get("weight") else "",
        "tax": f"{COUNTRY}:20:y",
        "multipack": p.get("qtyPerBox", ""),
        "is_bundle": "no",
        "age_group": "adult",
        "adult": "no",
        "country_of_origin": "RU",
        "manufacturer": BRAND,
        **derive_custom_labels(p, tr),
    }


# ----------------------------------------------------------------------
# CSV output (Google Merchant Center TSV)
# ----------------------------------------------------------------------
def write_csv(rows: list, path: Path):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                           quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            # GMC discourages newlines in description
            r2 = {k: re.sub(r"[\r\n\t]+", " ", str(v)) for k, v in r.items()}
            w.writerow(r2)
    print(f"OK CSV (TSV)  {path} — {len(rows)} rows, {path.stat().st_size//1024} KB")


# ----------------------------------------------------------------------
# XML output (RSS 2.0 / Google Merchant)
# ----------------------------------------------------------------------
def write_xml(rows: list, path: Path):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">',
        '  <channel>',
        f'    <title>Kazan Delicacies — Halal Catalog (EN)</title>',
        f'    <link>{BASE_URL}/en/</link>',
        f'    <description>Halal pepperoni, sausages, kazylyk, Tatar pastries — wholesale catalog feed.</description>',
        f'    <language>en-us</language>',
        f'    <pubDate>{now}</pubDate>',
    ]
    for r in rows:
        addl = [x.strip() for x in r["additional_image_link"].split(",") if x.strip()]
        lines.append("    <item>")
        lines.append(f"      <g:id>{escape(r['id'])}</g:id>")
        lines.append(f"      <title>{escape(r['title'])}</title>")
        lines.append(f"      <description>{escape(r['description'])}</description>")
        lines.append(f"      <link>{escape(r['link'])}</link>")
        lines.append(f"      <g:image_link>{escape(r['image_link'])}</g:image_link>")
        for a in addl:
            lines.append(f"      <g:additional_image_link>{escape(a)}</g:additional_image_link>")
        lines.append(f"      <g:availability>{r['availability']}</g:availability>")
        lines.append(f"      <g:price>{escape(r['price'])}</g:price>")
        lines.append(f"      <g:brand>{escape(r['brand'])}</g:brand>")
        if r["gtin"]:
            lines.append(f"      <g:gtin>{escape(r['gtin'])}</g:gtin>")
        if r["mpn"]:
            lines.append(f"      <g:mpn>{escape(r['mpn'])}</g:mpn>")
        lines.append(f"      <g:condition>{r['condition']}</g:condition>")
        lines.append(f"      <g:identifier_exists>{r['identifier_exists']}</g:identifier_exists>")
        lines.append(f"      <g:google_product_category>{r['google_product_category']}</g:google_product_category>")
        lines.append(f"      <g:product_type>{escape(r['product_type'])}</g:product_type>")
        lines.append(f"      <g:shipping><g:country>RU</g:country><g:price>0.00 {CURRENCY}</g:price></g:shipping>")
        if r["shipping_weight"]:
            lines.append(f"      <g:shipping_weight>{escape(r['shipping_weight'])}</g:shipping_weight>")
        lines.append(f"      <g:tax><g:country>RU</g:country><g:rate>20</g:rate><g:tax_ship>y</g:tax_ship></g:tax>")
        if r["multipack"]:
            lines.append(f"      <g:multipack>{escape(str(r['multipack']))}</g:multipack>")
        lines.append(f"      <g:age_group>{r['age_group']}</g:age_group>")
        lines.append(f"      <g:adult>{r['adult']}</g:adult>")
        for i, key in enumerate(("custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4")):
            v = r.get(key, "")
            if v:
                lines.append(f"      <g:custom_label_{i}>{escape(str(v))}</g:custom_label_{i}>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK XML  {path} — {len(rows)} items, {path.stat().st_size//1024} KB")


# ----------------------------------------------------------------------
# JSON output (Schema.org ItemList for AI crawlers)
# ----------------------------------------------------------------------
def write_json(rows: list, products: list, path: Path):
    item_list = []
    for r, p in zip(rows, products):
        offer = (p.get("offers") or {})
        item_list.append({
            "@type": "Product",
            "@id": f"{BASE_URL}/en/products/{p['sku'].lower()}#product",
            "sku": r["id"],
            "mpn": r["mpn"],
            "gtin13": r["gtin"] if r["gtin"] else None,
            "name": r["title"],
            "description": r["description"],
            "image": [r["image_link"]] + [x.strip() for x in r["additional_image_link"].split(",") if x.strip()],
            "url": r["link"],
            "brand": {"@type": "Brand", "name": BRAND},
            "manufacturer": {
                "@type": "Organization",
                "name": BRAND,
                "url": "https://kazandelikates.tatar",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "ul. Agrarnaya, 2",
                    "addressLocality": "Kazan",
                    "addressRegion": "Tatarstan",
                    "postalCode": "420059",
                    "addressCountry": "RU",
                },
            },
            "countryOfOrigin": "RU",
            "category": r["product_type"],
            "hasCertification": {
                "@type": "Certification",
                "name": "Halal",
                "identifier": "614A/2024",
                "issuedBy": {
                    "@type": "Organization",
                    "name": "Muslim Spiritual Board of the Republic of Tatarstan (DUM RT)",
                    "url": "https://dumrt.ru",
                },
            },
            "offers": {
                "@type": "Offer",
                "url": r["link"],
                "priceCurrency": offer.get("priceCurrency", CURRENCY),
                "price": offer.get("price"),
                "priceExclVAT": offer.get("priceExclVAT"),
                "availability": offer.get("availability", "https://schema.org/InStock"),
                "itemCondition": "https://schema.org/NewCondition",
                "seller": {"@type": "Organization", "name": BRAND, "url": "https://kazandelikates.tatar"},
                "exportPrices": offer.get("exportPrices"),
                "shippingDetails": {
                    "@type": "OfferShippingDetails",
                    "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "RU"},
                    "shippingRate": {"@type": "MonetaryAmount", "value": "0.00", "currency": CURRENCY},
                    "shippingOrigin": {
                        "@type": "DefinedRegion",
                        "addressLocality": "Kazan",
                        "addressCountry": "RU",
                    },
                    "deliveryTime": {
                        "@type": "ShippingDeliveryTime",
                        "handlingTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 3, "unitCode": "DAY"},
                    },
                },
            },
            "additionalProperty": [
                {"@type": "PropertyValue", "name": "halal", "value": True},
                {"@type": "PropertyValue", "name": "section", "value": p.get("section", "")},
                {"@type": "PropertyValue", "name": "category", "value": p.get("category", "")},
                {"@type": "PropertyValue", "name": "shelfLife", "value": p.get("shelfLife", "")},
                {"@type": "PropertyValue", "name": "storage", "value": p.get("storage", "")},
                {"@type": "PropertyValue", "name": "hsCode", "value": p.get("hsCode", "")},
                {"@type": "PropertyValue", "name": "weight_kg", "value": p.get("weight", "")},
                {"@type": "PropertyValue", "name": "minOrder_boxes", "value": p.get("minOrder", "")},
                {"@type": "PropertyValue", "name": "diameter_mm", "value": p.get("diameter", "")},
                {"@type": "PropertyValue", "name": "casing", "value": p.get("casing", "")},
                {"@type": "PropertyValue", "name": "packageType", "value": p.get("packageType", "")},
            ],
        })

    out = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "@id": f"{BASE_URL}/products-feed.json",
        "name": "Kazan Delicacies — Halal Product Catalog Feed",
        "description": "Machine-readable feed of 77 halal SKUs (sausages, pepperoni, kazylyk, ham, Tatar pastries) from Kazan Delicacies LLC. Compatible with Google Merchant Center, OpenAI Commerce, Bing Shopping, Perplexity Shopping.",
        "url": f"{BASE_URL}/products-feed.json",
        "inLanguage": "en",
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "publisher": {
            "@type": "Organization",
            "name": BRAND,
            "url": "https://kazandelikates.tatar",
            "logo": "https://pepperoni.tatar/images/logo.png",
        },
        "numberOfItems": len(item_list),
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": p} for i, p in enumerate(item_list)
        ],
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK JSON  {path} — {len(item_list)} products, {path.stat().st_size//1024} KB")


def main():
    products, tr = load()
    rows = [build_row(p, tr) for p in products]

    write_csv(rows, PUBLIC / "products-feed.csv")
    write_xml(rows, PUBLIC / "products-feed.xml")
    write_json(rows, products, PUBLIC / "products-feed.json")

    # Sanity stats
    short_titles = sum(1 for r in rows if len(r["title"]) < 30)
    short_descs = sum(1 for r in rows if len(r["description"]) < 150)
    no_image = sum(1 for r in rows if r["image_link"] in ("", DEFAULT_IMAGE, ""))
    no_gtin = sum(1 for r in rows if not r["gtin"])
    no_price = sum(1 for r in rows if not r["price"])
    print(f"\nFeed health:")
    print(f"  Short titles (<30 char): {short_titles}/{len(rows)}")
    print(f"  Short descs  (<150 char): {short_descs}/{len(rows)}")
    print(f"  Missing image  (fallback): {no_image}/{len(rows)}")
    print(f"  Missing GTIN              : {no_gtin}/{len(rows)}")
    print(f"  Missing price             : {no_price}/{len(rows)}")


if __name__ == "__main__":
    main()
