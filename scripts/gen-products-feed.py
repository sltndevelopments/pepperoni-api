#!/usr/bin/env python3
"""Generate a Google Merchant Center / OpenAI Commerce-compatible product feed.

Outputs:
  public/products-feed.csv   — GMC CSV (tab-separated, GMC standard)
  public/products-feed.xml   — RSS 2.0 / Google Merchant XML feed
  public/products-feed.json  — Schema.org ItemList for AI crawlers (Bing, Perplexity, ChatGPT)
  public/products-feed-openai.csv / .csv.gz / .tsv.gz — OpenAI Commerce (tab-separated UTF-8; .tsv.gz per file-upload overview)
  public/openai-commerce-kazan-delicacies.tsv.gz — stable snapshot path (same bytes; SFTP overwrite per overview)

Sources:
  public/products.json        — live catalog (77 SKUs)
  scripts/translations.json   — RU → EN translation map for names, categories, sections
"""
from __future__ import annotations
import csv
import gzip
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = PUBLIC / "products.json"
TRANSLATIONS = ROOT / "scripts" / "translations.json"

BASE_URL = "https://pepperoni.tatar"
BRAND = "Kazan Delicacies"
COUNTRY = "RU"
CURRENCY = "RUB"

# OpenAI Commerce best practices — stable feed click attribution (same params every snapshot).
# https://developers.openai.com/commerce/guides/best-practices
OPENAI_FEED_UTM: tuple[tuple[str, str], ...] = (
    ("utm_source", "openai"),
    ("utm_medium", "feed"),
    ("utm_campaign", "pepperoni_commerce"),
)

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
    "Заморозка":             "https://pepperoni.tatar/og-pepperoni-en.png",
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


def cleanse_description(text: str) -> str:
    """Remove sodium nitrite/nitrate mentions to avoid GMC false-positive flagging."""
    import re as _re
    # Remove full ingredient-like phrases mentioning nitrite/nitrate
    text = _re.sub(
        r"\([^)]*(?:нитрит|нитрат|nitrit|nitrat)[^)]*\)",
        "(curing salt)", text, flags=_re.IGNORECASE,
    )
    text = _re.sub(
        r"[^.]*?(?:нитрит|нитрат|nitrit|nitrat)[^.]*?\.?\s*",
        "", text, flags=_re.IGNORECASE,
    )
    # Clean up double spaces
    text = _re.sub(r"\s{2,}", " ", text)
    return text.strip()


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
    if sum(len(c) for c in chunks) < 500:
        name_en = derive_title(p, tr)
        cat_en = t_category(p.get("category", ""), tr)
        sec_en = t_section(p.get("section", ""), tr)
        weight = p.get("weight", "")
        shelf = p.get("shelfLife", "")
        storage = p.get("storage", "")
        diameter = p.get("diameter", "")
        casing = p.get("casing", "")
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
        if diameter:
            chunks.append(f"Diameter: {diameter} mm.")
        if casing:
            casing_en = casing.lower().strip()
            if casing_en in ("без оболочки", "без оболоччки"):
                casing_en = "casingless"
            elif casing_en == "есть":
                casing_en = "natural casing"
            chunks.append(f"Casing: {casing_en}.")
    # Halal + sourcing pitch — always include for AI parsing
    chunks.append(
        "HALAL certified #614A/2024 by the Muslim Spiritual Board of the Republic of Tatarstan (DUM RT). "
        "HACCP and ISO 22000 certified production facility. 100% pork-free, made from premium halal meats "
        "(beef, turkey, chicken, horse). Wholesale manufacturer direct from Kazan, Tatarstan, Russia. "
        "Shipment options: EXW Kazan warehouse or DC Lyubertsy (Moscow region)."
    )
    desc = " ".join(c for c in chunks if c).strip()
    # Clean double-spaces and ensure 500-5000 char window
    desc = re.sub(r"\s+", " ", desc)
    desc = cleanse_description(desc)
    if len(desc) < 500:
        desc += (" Suitable for pizzerias, HoReCa, gas-station street food concepts, retail chains, "
                 "cash-and-carry distributors, and foodservice operators. Ideal for hot dogs, pizza toppings, "
                 "sandwiches, burgers, and national cuisine applications. Wholesale pricing available. "
                 "Live prices and export quotes at api.pepperoni.tatar.")
    return desc[:5000]


def derive_link(p: dict) -> str:
    sku = p.get("sku", "").lower()
    return f"{BASE_URL}/en/products/{sku}"


def safe_shopping_url(url: str) -> str:
    """Percent-encode path (by segment) and query; keep already-% encoded paths intact."""
    if not url or not isinstance(url, str):
        return url
    u = url.strip()
    low = u.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return u
    p = urlsplit(u)
    path = p.path
    if "%" not in path:
        path = "/".join(quote(seg, safe="") if seg else seg for seg in path.split("/"))
    q = urlencode(parse_qsl(p.query, keep_blank_values=True), doseq=True)
    return urlunsplit((p.scheme, p.netloc, path, q, p.fragment))


def with_openai_feed_attribution(product_url: str) -> str:
    """Product landing URL + stable UTM block (OpenAI: feed attribution)."""
    base = safe_shopping_url(product_url.strip())
    p = urlsplit(base)
    merged = dict(parse_qsl(p.query, keep_blank_values=True))
    for k, v in OPENAI_FEED_UTM:
        merged[k] = v
    ordered = sorted(merged.items(), key=lambda kv: kv[0])
    q = urlencode(ordered, doseq=True)
    return urlunsplit((p.scheme, p.netloc, p.path, q, p.fragment))


def derive_link_ru(p: dict) -> str:
    sku = p.get("sku", "").lower()
    return f"{BASE_URL}/products/{sku}"


def normalize_weight(weight: str) -> str:
    """Normalize weight to 'X.XX kg' format."""
    if not weight:
        return ""
    w = str(weight).strip().lower()
    w = w.replace(",", ".")
    # Extract numeric value
    import re
    m = re.match(r"([\d.]+)\s*(g|г|kg|кг)?", w)
    if not m:
        return ""
    val = float(m.group(1))
    unit = m.group(2)
    if unit in ("g", "г"):
        val = val / 1000
    return f"{val:.3f} kg"


def normalize_image_url(url: str) -> str | None:
    if not url or url == "0":
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("v") and "/" in url:
        return f"https://res.cloudinary.com/duygfl3vz/image/upload/{url}"
    return None


def derive_image(p: dict) -> str:
    return (normalize_image_url(p.get("imageMain"))
            or normalize_image_url(p.get("image"))
            or OG_BY_SECTION.get(p.get("section"), "")
            or DEFAULT_IMAGE)


def derive_additional_images(p: dict) -> list:
    out = []
    main = p.get("imageMain")
    primary = p.get("image")
    for k in ("imagePack", "imageSlice"):
        v = normalize_image_url(p.get(k))
        if v and v != main and v != primary:
            out.append(v)
    return out[:10]  # GMC limit


def derive_price(p: dict) -> str:
    """RUB price WITH VAT. Format: '290.00 RUB'."""
    offers = p.get("offers") or {}
    pr = offers.get("price") or offers.get("pricePerUnit") or offers.get("pricePerBox")
    if not pr:
        return ""
    try:
        v = float(str(pr).replace(",", "."))
        return f"{v:.2f} {CURRENCY}"
    except Exception:
        return f"{pr} {CURRENCY}"


def derive_price_no_vat(p: dict) -> str:
    offers = p.get("offers") or {}
    pr = offers.get("priceExclVAT") or offers.get("pricePerBoxExclVAT")
    if not pr:
        return ""
    try:
        v = float(str(pr).replace(",", "."))
        return f"{v:.2f} {CURRENCY}"
    except Exception:
        return ""


def derive_price_usd(p: dict) -> str:
    """USD price from exportPrices (for EN feed → GMC currency match)."""
    offers = p.get("offers") or {}
    ep = offers.get("exportPrices") or {}
    usd = ep.get("USD")
    if usd is None:
        return ""
    try:
        v = float(str(usd).replace(",", "."))
        return f"{v:.2f} USD"
    except (ValueError, TypeError):
        return ""


def derive_price_usd_no_vat(p: dict) -> str:
    """Approximate USD ex-VAT (price / 1.20) from exportPrices."""
    offers = p.get("offers") or {}
    ep = offers.get("exportPrices") or {}
    usd = ep.get("USD")
    if usd is None:
        return ""
    try:
        v = float(str(usd).replace(",", "."))
        v = v / 1.20
        return f"{v:.2f} USD"
    except (ValueError, TypeError):
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
        "price": derive_price_usd(p) or derive_price(p),
        "sale_price": "",
        "brand": BRAND,
        "gtin": p.get("barcode", ""),
        "mpn": p.get("articleNumber", "") or p.get("sku", ""),
        "condition": "new",
        "identifier_exists": "yes" if p.get("barcode") else "no",
        "google_product_category": google_cat_id,
        "product_type": derive_product_type(p, tr),
        "shipping": f"{COUNTRY}:::0.00 USD",
        "shipping_weight": normalize_weight(p.get("weight", "")),
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
# OpenAI Commerce file upload (stable schema + delivery)
# https://developers.openai.com/commerce/specs/file-upload/products
# https://developers.openai.com/commerce/specs/file-upload/overview
# ----------------------------------------------------------------------
# Same relative path on every publish for SFTP overwrite (overview).
OPENAI_COMMERCE_STABLE_TSV_GZ = "openai-commerce-kazan-delicacies.tsv.gz"


def sanitize_openai_gtin(barcode) -> str:
    """OpenAI Products: GTIN 8–14 digits, no dashes or spaces."""
    if not barcode:
        return ""
    digits = re.sub(r"\D", "", str(barcode))
    if 8 <= len(digits) <= 14:
        return digits
    return ""


def clip_openai_field(s: str, max_len: int) -> str:
    if not s:
        return ""
    s = str(s).strip()
    return s[:max_len] if len(s) > max_len else s


def derive_openai_item_id(p: dict) -> str:
    """item_id: alphanumeric, max 100 (Products spec)."""
    sku = str(p.get("sku", "") or "").strip()
    sku = re.sub(r"[^\w\-]+", "", sku, flags=re.ASCII) or "sku"
    return sku[:100]


def derive_openai_availability_date(p: dict, avail: str) -> str:
    """Required when availability=pre_order (ISO 8601 date)."""
    if avail != "pre_order":
        return ""
    offers = p.get("offers") or {}
    for key in ("expectedShipDate", "availabilityDate", "preorderDate", "preOrderDate"):
        v = p.get(key) or offers.get(key)
        if v and str(v).strip():
            raw = str(v).strip()
            if len(raw) >= 10 and raw[4] == "-":
                return raw[:10]
    fut = datetime.now(timezone.utc) + timedelta(days=60)
    return fut.strftime("%Y-%m-%d")


def derive_openai_offer_id(sku: str, price_str: str) -> str:
    """Optional offer_id; unique per row within feed (SKU + normalized price)."""
    pslug = re.sub(r"[^\d.]", "", str(price_str).replace(",", "."))[:24]
    base = f"{sku}-{pslug}" if pslug else sku
    return clip_openai_field(base, 100)


def derive_openai_shipping(p: dict) -> str:
    """OpenAI shipping format: country:region:service_class:price"""
    return "RU:::0.00 RUB"


def derive_expiration_date(p: dict) -> str:
    """Derive expiration date from shelf life (for food products)."""
    shelf = p.get("shelfLife", "")
    if not shelf:
        return ""
    m = re.match(r"(\d+)\s*(суток|сутки|дней|день|месяцев|месяца|месяц)", shelf.lower())
    if not m:
        return ""
    num = int(m.group(1))
    unit = m.group(2)
    if unit in ("месяцев", "месяца", "месяц"):
        days = num * 30
    else:
        days = num
    exp = datetime.now(timezone.utc) + timedelta(days=days)
    return exp.strftime("%Y-%m-%d")


def build_openai_row(p: dict, tr: dict) -> dict:
    """Build a row matching OpenAI Commerce product schema."""
    sku_raw = str(p.get("sku", "") or "").strip()
    sku_id = derive_openai_item_id(p)
    offers = p.get("offers") or {}
    price_str = derive_price_usd(p) or derive_price(p)

    # OpenAI availability: in_stock, out_of_stock, pre_order, backorder, unknown
    avail = "in_stock"
    oa = str(offers.get("availability", "") or "")
    ol = oa.lower().replace(" ", "")
    if "outofstock" in ol or "out_of_stock" in ol:
        avail = "out_of_stock"
    elif "preorder" in ol or "pre_order" in ol:
        avail = "pre_order"
    elif "backorder" in ol:
        avail = "backorder"
    elif "unknown" in ol:
        avail = "unknown"

    addl = [normalize_image_url(p.get(k)) for k in ("imagePack", "imageSlice")]
    addl = [safe_shopping_url(u) for u in addl if u]
    main_img = (normalize_image_url(p.get("imageMain"))
                or normalize_image_url(p.get("image"))
                or OG_BY_SECTION.get(p.get("section"), "")
                or DEFAULT_IMAGE)
    main_img = safe_shopping_url(main_img) if main_img else ""

    google_cat_id, google_cat_path = derive_taxonomy(p)
    product_type = clip_openai_field(derive_product_type(p, tr), 500)
    weight_str = normalize_weight(p.get("weight", ""))
    gtin = sanitize_openai_gtin(p.get("barcode", ""))
    mpn = clip_openai_field(str(p.get("articleNumber", "") or sku_raw or sku_id), 70)
    avail_date = derive_openai_availability_date(p, avail)
    offer_id = derive_openai_offer_id(sku_id, price_str)
    mat = clip_openai_field(
        "halal meat, natural spices, no pork",
        100,
    )

    return {
        # OpenAI required
        "is_eligible_search": "true",
        "is_eligible_checkout": "false",
        "item_id": sku_id,
        "title": derive_title(p, tr),
        "description": derive_description(p, tr),
        "url": with_openai_feed_attribution(derive_link(p)),
        "brand": clip_openai_field(BRAND, 70),
        "image_url": main_img,
        "price": price_str,
        "availability": avail,
        "availability_date": avail_date,
        "seller_name": clip_openai_field(BRAND, 70),
        "seller_url": safe_shopping_url("https://kazandelikates.tatar"),
        "return_policy": safe_shopping_url("https://pepperoni.tatar/returns"),
        "target_countries": "RU,KZ,BY,UZ,KG,AZ",
        "store_country": "RU",
        # OpenAI recommended / optional
        "gtin": gtin,
        "mpn": mpn,
        "offer_id": offer_id,
        "product_category": product_type,
        "condition": "new",
        "age_group": "adult",
        "listing_has_variations": "false",
        "additional_image_urls": ",".join(addl),
        "item_weight_unit": "kg",
        "weight": weight_str,
        "expiration_date": derive_expiration_date(p),
        "seller_privacy_policy": safe_shopping_url("https://pepperoni.tatar/privacy"),
        "accepts_returns": "false",
        "shipping": derive_openai_shipping(p),
        # Compliance / context (plain text; lengths per Products spec where applicable)
        "material": mat,
        "warning": clip_openai_field(
            "Contains meat. Keep frozen -18C or refrigerated. Halal certified.",
            500,
        ),
        "age_restriction": "",
        "country_of_origin": "RU",
    }


OPENAI_FEED_FIELDNAMES = [
    "is_eligible_search", "is_eligible_checkout",
    "item_id", "title", "description", "url",
    "brand", "image_url", "price", "availability", "availability_date",
    "seller_name", "seller_url", "return_policy",
    "target_countries", "store_country",
    "gtin", "mpn", "offer_id", "product_category", "condition", "age_group",
    "listing_has_variations",
    "additional_image_urls", "item_weight_unit", "weight",
    "expiration_date", "seller_privacy_policy",
    "accepts_returns", "shipping",
    "material", "warning", "age_restriction",
    "country_of_origin",
]


def write_openai_csv(products: list, tr: dict, path: Path):
    """Generate OpenAI Commerce-compatible CSV feed."""
    rows = [build_openai_row(p, tr) for p in products]
    if not rows:
        return
    fieldnames = OPENAI_FEED_FIELDNAMES
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                           quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            r2 = {k: re.sub(r"[\r\n\t]+", " ", str(v)) for k, v in r.items()}
            w.writerow(r2)
    print(f"OK OpenAI CSV {path} — {len(rows)} rows, {path.stat().st_size//1024} KB")


def write_openai_csv_gz(products: list, tr: dict, path: Path):
    """Generate gzip-compressed OpenAI Commerce CSV for SFTP delivery."""
    rows = [build_openai_row(p, tr) for p in products]
    if not rows:
        return
    fieldnames = OPENAI_FEED_FIELDNAMES
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                           quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            r2 = {k: re.sub(r"[\r\n\t]+", " ", str(v)) for k, v in r.items()}
            w.writerow(r2)
    print(f"OK OpenAI CSV.GZ {path} — {len(rows)} rows, {path.stat().st_size//1024} KB")


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
        lines.append(f"      <g:shipping><g:country>RU</g:country><g:price>0.00 USD</g:price></g:shipping>")
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
        price_str = derive_price_usd(p) or derive_price(p)
        try:
            price_val = float(str(price_str).replace(",", ".").split()[0]) if price_str else None
        except (ValueError, IndexError):
            price_val = None
        price_excl = derive_price_usd_no_vat(p) or derive_price_no_vat(p)
        try:
            price_excl_val = float(str(price_excl).replace(",", ".").split()[0]) if price_excl else None
        except (ValueError, IndexError):
            price_excl_val = None
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
                "priceCurrency": "USD",
                "price": price_val,
                "priceExclVAT": price_excl_val,
                "availability": offer.get("availability", "https://schema.org/InStock"),
                "itemCondition": "https://schema.org/NewCondition",
                "seller": {"@type": "Organization", "name": BRAND, "url": "https://kazandelikates.tatar"},
                "exportPrices": offer.get("exportPrices"),
                "shippingDetails": {
                    "@type": "OfferShippingDetails",
                    "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "RU"},
                    "shippingRate": {"@type": "MonetaryAmount", "value": "0.00", "currency": "USD"},
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
                {"@type": "PropertyValue", "name": "weight_kg", "value": normalize_weight(p.get("weight", ""))},
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


# ----------------------------------------------------------------------
# UAE / AE feed — EN, AED prices, target country AE
# ----------------------------------------------------------------------
AED_RATE = 3.67  # 1 USD = 3.67 AED (fixed; update when rate shifts >5%)


def derive_price_aed(p: dict) -> str:
    """Convert USD exportPrice to AED."""
    ep = (p.get("offers") or {}).get("exportPrices") or {}
    usd = ep.get("USD")
    if not usd:
        return ""
    try:
        aed = float(str(usd).replace(",", ".")) * AED_RATE
        return f"{aed:.2f} AED"
    except (ValueError, TypeError):
        return ""


def build_row_ae(p: dict, tr: dict) -> dict:
    """GMC row for UAE: EN titles, AED prices, AE shipping."""
    google_cat_id, _ = derive_taxonomy(p)
    price = derive_price_aed(p) or (derive_price_usd(p) or derive_price(p))
    return {
        "id": p.get("sku", ""),
        "title": derive_title(p, tr),
        "description": derive_description(p, tr),
        "link": derive_link(p),          # /en/products/kd-NNN
        "image_link": derive_image(p),
        "additional_image_link": ",".join(derive_additional_images(p)),
        "availability": "in_stock",
        "price": price,
        "sale_price": "",
        "brand": BRAND,
        "gtin": p.get("barcode", ""),
        "mpn": p.get("articleNumber", "") or p.get("sku", ""),
        "condition": "new",
        "identifier_exists": "yes" if p.get("barcode") else "no",
        "google_product_category": google_cat_id,
        "product_type": derive_product_type(p, tr),
        # AE: no VAT on food, free shipping (EXW — buyer arranges)
        "shipping": "AE:::0.00 AED",
        "shipping_weight": normalize_weight(p.get("weight", "")),
        "tax": "AE:0:n",
        "multipack": p.get("qtyPerBox", ""),
        "is_bundle": "no",
        "age_group": "adult",
        "adult": "no",
        "country_of_origin": "RU",
        "manufacturer": BRAND,
        **derive_custom_labels(p, tr),
    }


def write_xml_ae(rows: list, path: Path) -> None:
    """RSS 2.0 / GMC XML feed for UAE (EN, AED)."""
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">',
        '  <channel>',
        '    <title>Kazan Delicacies — Halal Catalog (EN/AE)</title>',
        f'    <link>{BASE_URL}/en/</link>',
        '    <description>Halal pepperoni, sausages, kazylyk, Tatar pastries — wholesale catalog for UAE.</description>',
        '    <language>en-us</language>',
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
        lines.append(f"      <g:shipping><g:country>AE</g:country><g:price>0.00 AED</g:price></g:shipping>")
        if r["shipping_weight"]:
            lines.append(f"      <g:shipping_weight>{escape(r['shipping_weight'])}</g:shipping_weight>")
        # UAE: no VAT on basic food
        lines.append(f"      <g:tax><g:country>AE</g:country><g:rate>0</g:rate><g:tax_ship>n</g:tax_ship></g:tax>")
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
    print(f"OK XML AE {path} — {len(rows)} items, {path.stat().st_size//1024} KB")


def main():
    products, tr = load()
    rows = [build_row(p, tr) for p in products]

    write_csv(rows, PUBLIC / "products-feed.csv")
    write_xml(rows, PUBLIC / "products-feed.xml")
    write_json(rows, products, PUBLIC / "products-feed.json")

    # UAE / AE feed (EN titles, AED prices)
    rows_ae = [build_row_ae(p, tr) for p in products]
    write_xml_ae(rows_ae, PUBLIC / "products-feed-ae.xml")

    # OpenAI Commerce CSV feed (ChatGPT product discovery)
    try:
        write_openai_csv(products, tr, PUBLIC / "products-feed-openai.csv")
    except Exception as e:
        print(f"WARN OpenAI Commerce CSV generation failed: {e}")

    # OpenAI Commerce gzip-compressed CSV (SFTP delivery)
    try:
        gz_path = PUBLIC / "products-feed-openai.csv.gz"
        write_openai_csv_gz(products, tr, gz_path)
        tsv_gz = PUBLIC / "products-feed-openai.tsv.gz"
        shutil.copyfile(gz_path, tsv_gz)
        stable = PUBLIC / OPENAI_COMMERCE_STABLE_TSV_GZ
        shutil.copyfile(gz_path, stable)
        print(f"OK OpenAI TSV.GZ {tsv_gz} — {tsv_gz.stat().st_size//1024} KB (alias for OpenAI file-upload naming)")
        print(f"OK OpenAI stable snapshot {stable} — same bytes; fixed path for SFTP overwrite")
    except Exception as e:
        print(f"WARN OpenAI Commerce CSV.GZ generation failed: {e}")

    # Sanity stats
    short_titles = sum(1 for r in rows if len(r["title"]) < 30)
    short_descs = sum(1 for r in rows if len(r["description"]) < 500)
    no_image = sum(1 for r in rows if r["image_link"] in ("", DEFAULT_IMAGE, ""))
    no_gtin = sum(1 for r in rows if not r["gtin"])
    no_price = sum(1 for r in rows if not r["price"])
    print(f"\nFeed health:")
    print(f"  Short titles (<30 char): {short_titles}/{len(rows)}")
    print(f"  Short descs  (<500 char): {short_descs}/{len(rows)}")
    print(f"  Missing image  (fallback): {no_image}/{len(rows)}")
    print(f"  Missing GTIN              : {no_gtin}/{len(rows)}")
    print(f"  Missing price             : {no_price}/{len(rows)}")


if __name__ == "__main__":
    main()
