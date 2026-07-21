#!/usr/bin/env python3
"""Generate a Google Merchant Center / OpenAI Commerce-compatible product feed.

Outputs:
  public/products-feed.csv   — GMC CSV (tab-separated, GMC standard)
  public/products-feed.xml   — RSS 2.0 / Google Merchant XML feed (RU / RUB)
  public/products-feed.json  — Schema.org ItemList for AI crawlers (Bing, Perplexity, ChatGPT)
  public/products-feed-ae.xml — UAE single-country GMC feed (AED)
  public/products-feed-{cc}.xml — per-country GMC feeds (SA/KW/…, BY/KZ/…); PRIMARY for GMC
  public/products-feed-arab.xml / products-feed-cis.xml — multi-country aggregates (NOT for
    single-country GMC datafeeds; importing them into one country causes invalid_currency)
  public/products-feed-openai.csv / .csv.gz / .tsv.gz — OpenAI Commerce (tab-separated UTF-8; .tsv.gz per file-upload overview)
  public/openai-commerce-kazan-delicacies.tsv.gz — stable snapshot path (same bytes; SFTP overwrite per overview)

Sources:
  public/products.json        — live catalog (SKU count from Sheets)
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

# NOTE: Do NOT pad offers with shared section/category photo pools.
# GMC "click potential" and image diagnostics punish reused/broken
# additional_image_link (404s + same sausage shot on unrelated SKUs).
# Only the product's own Sheets photos go into the feed; empty → OG hero.


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


def format_weight_en(weight: str) -> str:
    """Human weight for EN titles/descriptions. Never emit '100 г kg'."""
    if not weight:
        return ""
    w = str(weight).strip()
    w = re.sub(r"\s+", " ", w)
    # Already has a unit (RU or EN)
    if re.search(r"(?i)\b(kg|g|кг|г)\b", w):
        w = re.sub(r"(?i)\bкг\b", "kg", w)
        w = re.sub(r"(?i)\bг\b", "g", w)
        return w
    # Bare number: Sheets frozen/cooled use kg (0,48); bakery uses grams as "100 г"
    try:
        val = float(w.replace(",", "."))
    except ValueError:
        return w
    if val >= 10:  # e.g. 80 without unit → grams pack size
        return f"{int(val) if val == int(val) else val} g"
    # 0.48 / 1.2 → kilograms
    s = f"{val:.3f}".rstrip("0").rstrip(".")
    return f"{s} kg"


def title_already_has_weight(title: str) -> bool:
    return bool(
        re.search(
            r"(?i)\d+([.,]\d+)?\s*(g|kg|г|кг)\b|\d+\s*[×x]\s*\d+|\b\d+\s*(pcs|pieces|шт)\b",
            title or "",
        )
    )


def derive_title(p: dict, tr: dict) -> str:
    """Build a GMC-compliant title (≤150 chars, EN).

    GMC ranks titles with brand + key attribute + product highly. We aim for
    ~50-130 chars: "Halal {NAME} ({WEIGHT}) — Kazan Delicacies".
    """
    seo_title, _, _, _ = parse_seo(p.get("seoDescriptionEN", ""))
    name_en = seo_title or t_product(p.get("name", ""), tr)
    name_en = re.sub(r"\s+", " ", name_en).strip()
    # Scrub legacy bad suffix if SEO/title ever contained it
    name_en = re.sub(r"\s*\(\s*[\d.,]+\s*г\s*kg\s*\)", "", name_en, flags=re.I)
    name_en = re.sub(r"\s+г\s*kg\b", " g", name_en, flags=re.I)

    # Halal prefix (skip if already present)
    halal_prefix = "" if re.search(r"\bhalal\b", name_en, re.I) else "Halal "
    title = f"{halal_prefix}{name_en}"

    weight_fmt = format_weight_en(p.get("weight", ""))
    if weight_fmt and not title_already_has_weight(title) and len(title) < 70:
        title = f"{title} ({weight_fmt})"

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
            w_fmt = format_weight_en(weight)
            chunks.append(f"Net weight: {w_fmt}." if w_fmt else f"Net weight: {weight}.")
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
        "Shipment options: EXW Kazan warehouse."
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
    u = str(url).strip()
    if u.startswith("v") and "/" in u and not u.startswith("http"):
        u = f"https://res.cloudinary.com/duygfl3vz/image/upload/{u}"
    if not (u.startswith("http://") or u.startswith("https://")):
        return None
    # Prefer canonical Cloudinary delivery without w_800 — truncated
    # public_ids under /upload/w_800/v…/… often 404 in GMC diagnostics.
    if "res.cloudinary.com" in u and "/upload/w_800/" in u:
        u = u.replace("/upload/w_800/", "/upload/")
    return u


def get_product_images(p: dict, target: int = 7, *, allow_og_fallback: bool = True) -> list[str]:
    """Own product photos only (imageMain/image/imagePack/imageSlice).

    Do not pad with unrelated category shots — that tanks GMC click potential
    and triggers image_link_broken on broken pool URLs. If the SKU has no
    photos, optionally fall back to a single section OG for image_link only.

    If Sheets put another SKU's `products/kd-XXX.jpg` into imageMain, prefer
    pack/slice URLs that don't embed a foreign KD number.
    """
    sku = (p.get("sku") or "").upper()
    sku_num = sku.replace("KD-", "").lstrip("0") or "0"

    def foreign_sku_penalty(url: str) -> int:
        m = re.search(r"(?i)(?:^|/)kd-0*(\d{1,3})(?:\D|$)", url)
        if not m:
            return 0
        other = m.group(1).lstrip("0") or "0"
        return 1 if other != sku_num else 0

    keyed: list[tuple[int, str]] = []  # (field_order, url)
    for idx, key in enumerate(("imageMain", "image", "imagePack", "imageSlice")):
        u = normalize_image_url(p.get(key))
        if not u:
            continue
        # Drop Sheets mistakes: another SKU's kd-XXX file on this row
        if foreign_sku_penalty(u):
            continue
        keyed.append((idx, u))
    # Prefer pack/slice when main was dropped as foreign: re-order by idx still ok
    imgs: list[str] = []
    for _, u in keyed:
        if u not in imgs:
            imgs.append(u)
        if len(imgs) >= target:
            break
    # If everything was foreign/empty, retry without the foreign filter (last resort)
    if not imgs:
        for key in ("imageMain", "image", "imagePack", "imageSlice"):
            u = normalize_image_url(p.get(key))
            if u and u not in imgs:
                imgs.append(u)
            if len(imgs) >= target:
                break

    if not imgs and allow_og_fallback:
        fallback = OG_BY_SECTION.get(p.get("section", "")) or DEFAULT_IMAGE
        imgs = [fallback]

    return imgs[:target]


def derive_image(p: dict) -> str:
    imgs = get_product_images(p, target=1, allow_og_fallback=True)
    return imgs[0] if imgs else (OG_BY_SECTION.get(p.get("section"), "") or DEFAULT_IMAGE)


def derive_additional_images(p: dict) -> list:
    # Only extras from the same SKU — never OG/section fillers as "additional".
    imgs = get_product_images(p, target=7, allow_og_fallback=False)
    return imgs[1:] if len(imgs) > 1 else []


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
    # Primary GMC feed targets RU — currency MUST be RUB (Google Merchant
    # answer/160637). USD+RU was the root cause of ~1.1k "invalid currency"
    # disapprovals in account 513449343.
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
        "shipping_weight": normalize_weight(p.get("weight", "")),
        "tax": f"{COUNTRY}:20:y",
        # Food products: returns only for defective goods (RU law art.25 ZOZPP)
        "return_policy_label": "no-returns-food",
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


def derive_openai_shipping(p: dict, country: str = "RU") -> str:
    """OpenAI shipping format: country:region:service_class:price"""
    if country == "AE":
        return "AE:::0.00 AED"
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
    # OpenAI RU/CIS feed: store_country=RU → RUB (matches shipping currency).
    price_str = derive_price(p)

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

    all_imgs = [safe_shopping_url(u) for u in get_product_images(p, target=7) if u]
    main_img = all_imgs[0] if all_imgs else safe_shopping_url(DEFAULT_IMAGE)
    addl = all_imgs[1:] if len(all_imgs) > 1 else []

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
        "shipping": derive_openai_shipping(p, "RU"),
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


def build_openai_row_ae(p: dict, tr: dict) -> dict:
    """OpenAI Commerce row for UAE: AED prices, AE target, EN content."""
    row = build_openai_row(p, tr)
    price_aed = derive_price_aed(p)
    if price_aed:
        row["price"] = price_aed
    row["target_countries"] = "AE"
    row["store_country"] = "RU"
    row["shipping"] = derive_openai_shipping(p, "AE")
    return row


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
        # Match the primary RU GMC feed: RUB prices for RU destination.
        price_str = derive_price(p)
        try:
            price_val = float(str(price_str).replace(",", ".").split()[0]) if price_str else None
        except (ValueError, IndexError):
            price_val = None
        price_excl = derive_price_no_vat(p)
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
                "priceCurrency": CURRENCY,
                "price": price_val,
                "priceExclVAT": price_excl_val,
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
                {"@type": "PropertyValue", "name": "weight_kg", "value": normalize_weight(p.get("weight", ""))},
                {"@type": "PropertyValue", "name": "minOrder_boxes", "value": p.get("minOrder", "")},
                {"@type": "PropertyValue", "name": "diameter_mm", "value": p.get("diameter", "")},
                {"@type": "PropertyValue", "name": "casing", "value": p.get("casing", "")},
                {"@type": "PropertyValue", "name": "packageType", "value": p.get("packageType", "")},
            ],
        })

    n = len(item_list)
    out = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "@id": f"{BASE_URL}/products-feed.json",
        "name": "Kazan Delicacies — Halal Product Catalog Feed",
        "description": (
            f"Machine-readable feed of {n} halal SKUs (sausages, pepperoni, kazylyk, ham, "
            "Tatar pastries) from Kazan Delicacies LLC. Compatible with Google Merchant Center, "
            "OpenAI Commerce, Bing Shopping, Perplexity Shopping."
        ),
        "url": f"{BASE_URL}/products-feed.json",
        "inLanguage": "en",
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "publisher": {
            "@type": "Organization",
            "name": BRAND,
            "url": "https://kazandelikates.tatar",
            "logo": "https://pepperoni.tatar/images/logo.png",
        },
        "numberOfItems": n,
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": p} for i, p in enumerate(item_list)
        ],
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK JSON  {path} — {n} products, {path.stat().st_size//1024} KB")


def write_json_ru(products: list, path: Path):
    """RU Schema.org ItemList — always rebuilt from live products.json (no stale SKUs)."""
    item_list = []
    for p in products:
        sku = p.get("sku") or ""
        offer = p.get("offers") or {}
        price = offer.get("price")
        price_excl = offer.get("priceExclVAT")
        images = []
        for key in ("imageMain", "imagePack", "imageSlice", "image"):
            u = p.get(key)
            if u and u not in images:
                images.append(u)
        for u in p.get("images") or []:
            if u and u not in images:
                images.append(u)
        url = f"{BASE_URL}/products/{sku.lower()}"
        item_list.append({
            "@type": "Product",
            "@id": f"{url}#product",
            "sku": sku,
            "mpn": p.get("articleNumber") or sku,
            "gtin13": p.get("barcode") or None,
            "name": p.get("name") or sku,
            "description": (p.get("description") or p.get("name") or "")[:5000],
            "image": images or [DEFAULT_IMAGE],
            "url": url,
            "brand": {"@type": "Brand", "name": "Казанские Деликатесы"},
            "manufacturer": {
                "@type": "Organization",
                "name": "Казанские Деликатесы",
                "url": "https://kazandelikates.tatar",
            },
            "countryOfOrigin": "RU",
            "category": f"{p.get('section', '')} > {p.get('category', '')}".strip(" >"),
            "offers": {
                "@type": "Offer",
                "url": url,
                "priceCurrency": CURRENCY,
                "price": price,
                "priceExclVAT": price_excl,
                "availability": offer.get("availability", "https://schema.org/InStock"),
                "itemCondition": "https://schema.org/NewCondition",
                "exportPrices": offer.get("exportPrices"),
            },
        })
    n = len(item_list)
    out = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "@id": f"{BASE_URL}/ru/products-feed.json",
        "name": "Казанские Деликатесы — Каталог халяль продукции",
        "description": (
            f"Машиночитаемый каталог {n} халяль SKU (пепперони, сосиски, казылык, ветчина, "
            "татарская выпечка) от ООО «Казанские Деликатесы». Совместим с Google Merchant Center, "
            "OpenAI Commerce, Bing Shopping, Perplexity Shopping."
        ),
        "url": f"{BASE_URL}/ru/products-feed.json",
        "inLanguage": "ru",
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "publisher": {
            "@type": "Organization",
            "name": "Казанские Деликатесы",
            "url": "https://kazandelikates.tatar",
            "logo": "https://pepperoni.tatar/images/logo.png",
        },
        "numberOfItems": n,
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": item}
            for i, item in enumerate(item_list)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK JSON RU {path} — {n} products, {path.stat().st_size//1024} KB")


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


# ----------------------------------------------------------------------
# CIS feed — RU language, native currencies where available
# Countries: BY KZ UZ TJ KG AM GE AZ
# ----------------------------------------------------------------------
# Approximate USD rates for countries without native currency in Sheets
# (TJS, AMD, GEL) — update quarterly when drift > 5%
CIS_FX = {
    "TJS": 10.93,   # Tajikistani somoni
    "AMD": 390.0,   # Armenian dram
    "GEL": 2.74,    # Georgian lari
}

# Countries that already have native prices in exportPrices
CIS_NATIVE: dict[str, str] = {
    "BY": "BYN",
    "KZ": "KZT",
    "UZ": "UZS",
    "KG": "KGS",
    "AZ": "AZN",
}

# Countries needing FX conversion from USD
CIS_FX_COUNTRIES: dict[str, str] = {
    "TJ": "TJS",
    "AM": "AMD",
    "GE": "GEL",
}

CIS_COUNTRIES = list(CIS_NATIVE.keys()) + list(CIS_FX_COUNTRIES.keys())


def derive_price_cis(p: dict, country: str) -> str:
    """Return price string in native CIS currency."""
    ep = (p.get("offers") or {}).get("exportPrices") or {}
    if country in CIS_NATIVE:
        cur = CIS_NATIVE[country]
        v = ep.get(cur)
        if v:
            return f"{float(v):.2f} {cur}"
    if country in CIS_FX_COUNTRIES:
        cur = CIS_FX_COUNTRIES[country]
        usd = ep.get("USD")
        if usd:
            try:
                val = float(str(usd).replace(",", ".")) * CIS_FX[cur]
                return f"{val:.2f} {cur}"
            except (ValueError, TypeError):
                pass
    # Fallback to USD
    usd = ep.get("USD")
    if usd:
        return f"{float(usd):.2f} USD"
    return ""


def build_row_cis(p: dict, tr: dict, country: str) -> dict:
    """GMC row for a CIS country: RU lang, native currency, RU product links."""
    google_cat_id, _ = derive_taxonomy(p)
    price = derive_price_cis(p, country)
    cur = CIS_NATIVE.get(country) or CIS_FX_COUNTRIES.get(country, "USD")
    return {
        "id": p.get("sku", ""),
        # Use RU name (not translated) — CIS audience reads Russian
        "title": p.get("name", derive_title(p, tr)),
        "description": derive_description(p, tr),
        "link": f"{BASE_URL}/products/{p.get('sku', '').lower()}",
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
        "shipping": f"{country}:::0.00 {cur}",
        "shipping_weight": normalize_weight(p.get("weight", "")),
        "tax": f"{country}:0:n",
        "multipack": p.get("qtyPerBox", ""),
        "is_bundle": "no",
        "age_group": "adult",
        "adult": "no",
        "country_of_origin": "RU",
        "manufacturer": BRAND,
        **derive_custom_labels(p, tr),
    }


def write_xml_single_country(
    rows: list,
    path: Path,
    *,
    country: str,
    currency: str,
    title: str,
    description: str,
    language: str,
    channel_link: str,
    id_suffix: bool = True,
) -> None:
    """RSS 2.0 / GMC XML with ONLY one country's items (matching currency).

    Primary path for GMC single-country datafeeds. Multi-country aggregates
    (arab/cis) must NOT be registered as a single-country feed — Google imports
    every row into that country and rejects foreign currencies
    (invalid_currency_for_country).
    """
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">',
        '  <channel>',
        f'    <title>{escape(title)}</title>',
        f'    <link>{escape(channel_link)}</link>',
        f'    <description>{escape(description)}</description>',
        f'    <language>{language}</language>',
        f'    <pubDate>{now}</pubDate>',
    ]
    for r in rows:
        addl = [x.strip() for x in r["additional_image_link"].split(",") if x.strip()]
        item_id = f"{r['id']}-{country}" if id_suffix else r["id"]
        sh_parts = r["shipping"].split(":::")
        sh_country, sh_price = (
            (sh_parts[0], sh_parts[1]) if len(sh_parts) == 2 else (country, f"0.00 {currency}")
        )
        lines.append("    <item>")
        lines.append(f"      <g:id>{escape(item_id)}</g:id>")
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
        lines.append(
            f"      <g:shipping><g:country>{escape(sh_country)}</g:country>"
            f"<g:price>{escape(sh_price)}</g:price></g:shipping>"
        )
        if r["shipping_weight"]:
            lines.append(f"      <g:shipping_weight>{escape(r['shipping_weight'])}</g:shipping_weight>")
        lines.append(
            f"      <g:tax><g:country>{escape(sh_country)}</g:country>"
            f"<g:rate>0</g:rate><g:tax_ship>n</g:tax_ship></g:tax>"
        )
        if r["multipack"]:
            lines.append(f"      <g:multipack>{escape(str(r['multipack']))}</g:multipack>")
        lines.append(f"      <g:age_group>{r['age_group']}</g:age_group>")
        lines.append(f"      <g:adult>{r['adult']}</g:adult>")
        for i, key in enumerate(
            ("custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4")
        ):
            v = r.get(key, "")
            if v:
                lines.append(f"      <g:custom_label_{i}>{escape(str(v))}</g:custom_label_{i}>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK XML {country} {path} — {len(rows)} items ({currency}), {path.stat().st_size//1024} KB")


def write_xml_cis(rows_by_country: dict[str, list], path: Path) -> None:
    """Multi-country CIS aggregate (NOT for single-country GMC datafeeds)."""
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    country_list = ",".join(sorted(rows_by_country.keys()))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">',
        '  <channel>',
        '    <title>Казанские Деликатесы — Халяль Каталог (CIS)</title>',
        f'    <link>{BASE_URL}/</link>',
        '    <description>Халяль пепперони, колбасы, казылык, татарская выпечка — оптовый каталог для СНГ. Multi-country aggregate — use products-feed-{cc}.xml for GMC.</description>',
        '    <language>ru</language>',
        f'    <pubDate>{now}</pubDate>',
    ]
    # Emit each product once per country with country-specific price/shipping
    for country, rows in sorted(rows_by_country.items()):
        for r in rows:
            addl = [x.strip() for x in r["additional_image_link"].split(",") if x.strip()]
            item_id = f"{r['id']}-{country}"
            lines.append("    <item>")
            lines.append(f"      <g:id>{escape(item_id)}</g:id>")
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
            # Parse shipping field "CC:::0.00 CUR"
            sh_parts = r["shipping"].split(":::")
            sh_country, sh_price = (sh_parts[0], sh_parts[1]) if len(sh_parts) == 2 else (country, "0.00 USD")
            lines.append(f"      <g:shipping><g:country>{sh_country}</g:country><g:price>{sh_price}</g:price></g:shipping>")
            if r["shipping_weight"]:
                lines.append(f"      <g:shipping_weight>{escape(r['shipping_weight'])}</g:shipping_weight>")
            lines.append(f"      <g:tax><g:country>{sh_country}</g:country><g:rate>0</g:rate><g:tax_ship>n</g:tax_ship></g:tax>")
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
    total = sum(len(v) for v in rows_by_country.values())
    print(f"OK XML CIS {path} — {total} items ({country_list}), {path.stat().st_size//1024} KB")


# ----------------------------------------------------------------------
# Arab feed — EN language, LOCAL currencies (Google Merchant answer/160637)
# Countries: AE SA QA KW BH OM YE EG
# USD was rejected as "invalid currency" for these targets; convert from
# exportPrices.USD via fixed rates (same pattern as CIS_FX). Update when
# peg/float drifts >5%. AE also has a dedicated products-feed-ae.xml.
# ----------------------------------------------------------------------
ARAB_COUNTRIES = ["AE", "SA", "QA", "KW", "BH", "OM", "YE", "EG"]

# Units of local currency per 1 USD
ARAB_FX: dict[str, tuple[str, float]] = {
    "AE": ("AED", AED_RATE),   # pegged
    "SA": ("SAR", 3.75),       # pegged
    "QA": ("QAR", 3.64),       # pegged
    "KW": ("KWD", 0.307),      # pegged-band
    "BH": ("BHD", 0.376),      # pegged
    "OM": ("OMR", 0.385),      # pegged
    "EG": ("EGP", 48.50),      # float — update quarterly
    "YE": ("YER", 250.0),      # float — update quarterly
}


def derive_price_arab(p: dict, country: str) -> str:
    """Return price string in the local currency for an Arab/GCC country."""
    cur, rate = ARAB_FX.get(country, ("USD", 1.0))
    if country == "AE":
        # Prefer the shared AED helper (same rate) for consistency with AE feed
        aed = derive_price_aed(p)
        if aed:
            return aed
    ep = (p.get("offers") or {}).get("exportPrices") or {}
    usd = ep.get("USD")
    if usd is None:
        return ""
    try:
        val = float(str(usd).replace(",", ".")) * rate
        # KWD/BHD/OMR are high-value: keep 3 decimals; others 2
        if cur in ("KWD", "BHD", "OMR"):
            return f"{val:.3f} {cur}"
        return f"{val:.2f} {cur}"
    except (ValueError, TypeError):
        return ""


def build_row_arab(p: dict, tr: dict, country: str) -> dict:
    """GMC row for Arab country: EN titles, local currency, country shipping."""
    google_cat_id, _ = derive_taxonomy(p)
    price = derive_price_arab(p, country)
    cur = ARAB_FX.get(country, ("USD", 1.0))[0]
    return {
        "id": p.get("sku", ""),
        "title": derive_title(p, tr),
        "description": derive_description(p, tr),
        "link": derive_link(p),
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
        "shipping": f"{country}:::0.00 {cur}",
        "shipping_weight": normalize_weight(p.get("weight", "")),
        "tax": f"{country}:0:n",
        "multipack": p.get("qtyPerBox", ""),
        "is_bundle": "no",
        "age_group": "adult",
        "adult": "no",
        "country_of_origin": "RU",
        "manufacturer": BRAND,
        **derive_custom_labels(p, tr),
    }


def write_xml_arab(rows_by_country: dict[str, list], path: Path) -> None:
    """Multi-country Arab/GCC aggregate (NOT for single-country GMC datafeeds)."""
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    country_list = ",".join(sorted(rows_by_country.keys()))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">',
        '  <channel>',
        '    <title>Kazan Delicacies — Halal Catalog (Arab/GCC)</title>',
        f'    <link>{BASE_URL}/en/</link>',
        '    <description>Halal pepperoni, sausages, kazylyk, Tatar pastries — wholesale catalog for Arab/GCC markets. Multi-country aggregate — use products-feed-{cc}.xml for GMC.</description>',
        '    <language>en-us</language>',
        f'    <pubDate>{now}</pubDate>',
    ]
    for country, rows in sorted(rows_by_country.items()):
        cur = ARAB_FX.get(country, ("USD", 1.0))[0]
        for r in rows:
            addl = [x.strip() for x in r["additional_image_link"].split(",") if x.strip()]
            item_id = f"{r['id']}-{country}"
            lines.append("    <item>")
            lines.append(f"      <g:id>{escape(item_id)}</g:id>")
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
            lines.append(f"      <g:shipping><g:country>{country}</g:country><g:price>0.00 {cur}</g:price></g:shipping>")
            if r["shipping_weight"]:
                lines.append(f"      <g:shipping_weight>{escape(r['shipping_weight'])}</g:shipping_weight>")
            lines.append(f"      <g:tax><g:country>{country}</g:country><g:rate>0</g:rate><g:tax_ship>n</g:tax_ship></g:tax>")
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
    total = sum(len(v) for v in rows_by_country.values())
    print(f"OK XML Arab {path} — {total} items ({country_list}), {path.stat().st_size//1024} KB")


def main():
    products, tr = load()
    rows = [build_row(p, tr) for p in products]

    write_csv(rows, PUBLIC / "products-feed.csv")
    write_xml(rows, PUBLIC / "products-feed.xml")
    write_json(rows, products, PUBLIC / "products-feed.json")
    write_json_ru(products, PUBLIC / "ru" / "products-feed.json")

    # UAE / AE feed (EN titles, AED prices) — kept for backward compat
    rows_ae = [build_row_ae(p, tr) for p in products]
    write_xml_ae(rows_ae, PUBLIC / "products-feed-ae.xml")

    # CIS: multi-country aggregate (non-GMC) + per-country GMC feeds
    cis_rows_by_country = {c: [build_row_cis(p, tr, c) for p in products] for c in CIS_COUNTRIES}
    write_xml_cis(cis_rows_by_country, PUBLIC / "products-feed-cis.xml")
    for country, crows in cis_rows_by_country.items():
        cur = CIS_NATIVE.get(country) or CIS_FX_COUNTRIES.get(country, "USD")
        write_xml_single_country(
            crows,
            PUBLIC / f"products-feed-{country.lower()}.xml",
            country=country,
            currency=cur,
            title=f"Казанские Деликатесы — Халяль Каталог ({country})",
            description=(
                f"Халяль пепперони, колбасы, казылык, татарская выпечка — "
                f"оптовый каталог для {country} ({cur})."
            ),
            language="ru",
            channel_link=f"{BASE_URL}/",
        )

    # Arab/GCC: multi-country aggregate (non-GMC) + per-country GMC feeds.
    # AE keeps dedicated products-feed-ae.xml (no -AE id suffix) — skip overwrite.
    arab_rows_by_country = {c: [build_row_arab(p, tr, c) for p in products] for c in ARAB_COUNTRIES}
    write_xml_arab(arab_rows_by_country, PUBLIC / "products-feed-arab.xml")
    for country, arows in arab_rows_by_country.items():
        if country == "AE":
            continue  # products-feed-ae.xml already written above
        cur = ARAB_FX[country][0]
        write_xml_single_country(
            arows,
            PUBLIC / f"products-feed-{country.lower()}.xml",
            country=country,
            currency=cur,
            title=f"Kazan Delicacies — Halal Catalog ({country})",
            description=(
                f"Halal pepperoni, sausages, kazylyk, Tatar pastries — "
                f"wholesale catalog for {country} ({cur})."
            ),
            language="en-us",
            channel_link=f"{BASE_URL}/en/",
        )

    # OpenAI Commerce CSV feed (ChatGPT product discovery — RU/CIS)
    try:
        write_openai_csv(products, tr, PUBLIC / "products-feed-openai.csv")
    except Exception as e:
        print(f"WARN OpenAI Commerce CSV generation failed: {e}")

    # OpenAI Commerce CSV feed — UAE/AE (EN titles, AED prices)
    try:
        rows_openai_ae = [build_openai_row_ae(p, tr) for p in products]
        ae_openai_path = PUBLIC / "products-feed-openai-ae.csv"
        with ae_openai_path.open("w", encoding="utf-8", newline="") as f:
            import csv as _csv
            w = _csv.DictWriter(f, fieldnames=OPENAI_FEED_FIELDNAMES, delimiter="\t", extrasaction="ignore")
            w.writeheader()
            w.writerows(rows_openai_ae)
        print(f"OK OpenAI CSV AE {ae_openai_path} — {len(rows_openai_ae)} rows, {ae_openai_path.stat().st_size//1024} KB")
    except Exception as e:
        print(f"WARN OpenAI Commerce AE CSV generation failed: {e}")

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
    bad_weight_title = sum(1 for r in rows if re.search(r"(?i)г\s*kg", r["title"]))
    no_image = sum(
        1
        for r in rows
        if r["image_link"] in ("", DEFAULT_IMAGE) or r["image_link"] in OG_BY_SECTION.values()
    )
    addl_counts = [
        len([x for x in (r.get("additional_image_link") or "").split(",") if x.strip()])
        for r in rows
    ]
    no_gtin = sum(1 for r in rows if not r["gtin"])
    no_price = sum(1 for r in rows if not r["price"])
    print(f"\nFeed health:")
    print(f"  Short titles (<30 char): {short_titles}/{len(rows)}")
    print(f"  Bad 'г kg' titles         : {bad_weight_title}/{len(rows)}")
    print(f"  Short descs  (<500 char): {short_descs}/{len(rows)}")
    print(f"  Missing own image (OG)  : {no_image}/{len(rows)}")
    print(f"  Additional images/offer : min={min(addl_counts)} med={sorted(addl_counts)[len(addl_counts)//2]} max={max(addl_counts)}")
    print(f"  Missing GTIN              : {no_gtin}/{len(rows)}")
    print(f"  Missing price             : {no_price}/{len(rows)}")


if __name__ == "__main__":
    main()
