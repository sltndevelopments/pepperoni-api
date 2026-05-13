#!/usr/bin/env python3
"""Generate EN geo pages for all Russian regional geo pages (94 pages).
Maps RU product × meat × city combos to EN equivalents with translated content.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
RU_GEO = PUBLIC / "geo"
EN_GEO = PUBLIC / "en" / "geo"
EN_GEO.mkdir(parents=True, exist_ok=True)

# --- Translation maps ---
CITY_EN = {
    "moskva": "Moscow", "spb": "St. Petersburg", "kazan": "Kazan",
    "ufa": "Ufa", "ekaterinburg": "Yekaterinburg", "sochi": "Sochi",
    "krasnodar": "Krasnodar", "astrahan": "Astrakhan", "dagestan": "Dagestan",
    "grozny": "Grozny", "mahachkala": "Makhachkala", "yanao": "Yamalo-Nenets",
    "kazakhstan": "Kazakhstan", "uzbekistan": "Uzbekistan", "belarus": "Belarus",
    "armenia": "Armenia", "azerbaijan": "Azerbaijan", "kyrgyzstan": "Kyrgyzstan",
}

MEAT_EN = {
    "govyadina": "Beef", "kurica": "Chicken", "konina": "Horse Meat",
    "miks": "Mixed Meat",
}

PRODUCT_LABEL_EN = {
    "pepperoni": "Halal Pepperoni",
    "kotlety-dlya-burgerov": "Halal Burger Patties",
    "sosiki-dlya-hotdog": "Halal Hot Dog Sausages",
}

PRODUCT_DESC_EN = {
    "pepperoni": "halal pepperoni for pizzerias and food service",
    "kotlety-dlya-burgerov": "halal burger patties for restaurants and fast food",
    "sosiki-dlya-hotdog": "halal hot dog sausages for C-stores and street food",
}

MEAT_DESC_EN = {
    "govyadina": "beef",
    "kurica": "chicken",
    "konina": "horse meat",
    "miks": "beef and chicken blend",
}

# --- Template ---
TPL = """<!DOCTYPE html>
<html lang="en">
<head>
<!-- perf-hints: preconnect -->
<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
<link rel="dns-prefetch" href="https://www.googletagmanager.com">
<link rel="preconnect" href="https://mc.yandex.ru" crossorigin>
<link rel="dns-prefetch" href="https://mc.yandex.ru">

<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="content-language" content="en">
<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/images/icon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/images/icon-180.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="manifest" href="/manifest.json">
<link rel="llms" href="/en/llms.txt" type="text/plain" title="LLM instructions (English)">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="{keywords}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/en/geo/{slug}">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/geo/{slug}">
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/geo/{ru_slug}">

<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="https://pepperoni.tatar/en/geo/{slug}">
<meta property="og:image" content="https://pepperoni.tatar/og-default-en.png">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="https://pepperoni.tatar/og-default-en.png">

<script type="application/ld+json">{product_jsonld}</script>
<script type="application/ld+json">{breadcrumb_jsonld}</script>

<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}}
.container{{max-width:800px;margin:0 auto;padding:40px 24px}}
nav.bc{{font-size:.85rem;color:#888;margin-bottom:32px}}
nav.bc a{{color:#0066cc;text-decoration:none}}
h1{{font-size:2rem;font-weight:700;margin-bottom:8px}}
h2{{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}}
p{{margin-bottom:14px}}
.hero-subtitle{{color:#666;font-size:1.05rem;margin-bottom:4px}}
.badge{{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0}}
.badge-outline{{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}}
.card{{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}}
.spec-table{{width:100%;border-collapse:collapse;margin:12px 0}}
.spec-table td{{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}}
.spec-table td:first-child{{color:#666;width:35%}}
.spec-value{{font-weight:600;color:#1b7a3d}}
ul{{margin:8px 0 14px 24px}}
li{{margin-bottom:4px}}
.geo-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin:16px 0}}
.geo-card{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;text-decoration:none;color:#1a1a1a;font-size:.88rem}}
.geo-card strong{{display:block;margin-bottom:3px}}
.cta{{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0;font-size:.95rem}}
.cta-outline{{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}}
footer{{text-align:center;color:#aaa;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}}
footer a{{color:#888;text-decoration:none}}
@media(max-width:600px){{.geo-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
<div class="container">
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
    <a href="/en/" style="color:#0066cc;text-decoration:none;font-weight:600">Catalog</a>
    <a href="/en/pepperoni" style="color:#0066cc;text-decoration:none">Pepperoni</a>
    <a href="/en/about" style="color:#0066cc;text-decoration:none">About</a>
    <a href="/en/delivery" style="color:#0066cc;text-decoration:none">Delivery</a>
    <a href="/en/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
    <a href="/{ru_slug_rel}" style="color:#888;text-decoration:none;margin-left:auto">🇷🇺 Русский</a>
  </div>
  <nav class="bc" aria-label="Breadcrumb">
    <a href="/en/">Catalog</a> &rsaquo; <a href="/en/{parent_page}">{parent_label}</a> &rsaquo; <span>{city_en}</span>
  </nav>

  <h1>{h1}</h1>
  <p class="hero-subtitle">{subtitle}</p>
  <span class="badge">HALAL #614A/2024</span>
  <span class="badge badge-outline">HACCP + ISO 22000:2018</span>
  <span class="badge badge-outline">EXW Kazan</span>
  <span class="badge badge-outline">Made in Tatarstan</span>

  <p>{intro_text}</p>

  <h2>Why Choose Our {product_label} for {city_en}</h2>
  <div class="card">
    <ul style="margin-left:0;list-style:none">
      <li>✅ <strong>100% Halal</strong> — certified by Muslim Spiritual Board of Tatarstan (#614A/2024)</li>
      <li>✅ <strong>Direct from manufacturer</strong> — no middlemen, factory pricing EXW Kazan</li>
      <li>✅ <strong>HACCP + ISO 22000:2018</strong> — full quality control at every production stage</li>
      <li>✅ <strong>No pork, no GMO, no meat glue</strong> — strictly halal ingredients only</li>
      <li>✅ <strong>Private Label available</strong> — production under your brand from 500 kg/month</li>
      <li>✅ <strong>Flexible logistics</strong> — refrigerated truck delivery, veterinary certificates included</li>
      <li>✅ <strong>7 currencies</strong> — invoicing in RUB, USD, KZT, UZS, KGS, BYN, AZN</li>
    </ul>
  </div>

  <h2>Delivery to {city_en}</h2>
  <div class="card">
    <p>{delivery_text}</p>
    <table class="spec-table">
      <tbody>
        <tr><td>Origin</td><td class="spec-value">Kazan, Tatarstan, Russia</td></tr>
        <tr><td>Shipping terms</td><td class="spec-value">EXW Kazan (Incoterms 2020)</td></tr>
        <tr><td>Transport</td><td class="spec-value">Refrigerated truck (0…+6°C)</td></tr>
        <tr><td>Documents</td><td class="spec-value">Veterinary certificate, Halal cert #614A/2024, EAEU declaration</td></tr>
        <tr><td>Payment</td><td class="spec-value">RUB, USD + 5 CIS currencies — live prices via API</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Available Products for {city_en}</h2>
  <p>{available_text}</p>
  <div class="geo-grid">
    {related_links}
  </div>

  <h2>Order for {city_en}</h2>
  <p>Contact us for a personalized quote with delivery to {city_en}. We'll send a price list within one working day.</p>
  <a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
  <a href="mailto:info@kazandelikates.tatar?subject={email_subject}" class="cta cta-outline">📧 info@kazandelikates.tatar</a>
  <a href="https://wa.me/79872170202?text={whatsapp_text}" class="cta cta-outline">💬 WhatsApp</a>

  <footer>
    <p><a href="/en/">← Catalog</a> &middot; <a href="/en/pepperoni">Pepperoni</a> &middot; <a href="/en/about">About</a> &middot; <a href="/en/faq">FAQ</a> &middot; <a href="/en/delivery">Delivery</a></p>
    <p>&copy; <a href="https://kazandelikates.tatar">Kazan Delicacies</a> &middot; <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
  </footer>
</div>
</body>
</html>
"""

# --- Parsing ---
def parse_slug(slug: str) -> dict:
    """Parse RU geo slug into components.
    Patterns:
      pepperoni-{city}
      pepperoni-{meat}-{city}
      kotlety-dlya-burgerov-{city}
      sosiki-dlya-hotdog-{city}
    """
    parts = slug.split("-")
    info = {"slug": slug, "product": "", "meat": None, "city_raw": ""}

    # Check product type
    if slug.startswith("kotlety-dlya-burgerov"):
        info["product"] = "kotlety-dlya-burgerov"
        info["city_raw"] = slug[len("kotlety-dlya-burgerov-"):]
    elif slug.startswith("sosiki-dlya-hotdog"):
        info["product"] = "sosiki-dlya-hotdog"
        info["city_raw"] = slug[len("sosiki-dlya-hotdog-"):]
    elif slug.startswith("pepperoni-"):
        rest = slug[len("pepperoni-"):]
        # Check if next token is a meat type
        for meat in ["govyadina", "kurica", "konina", "miks"]:
            if rest.startswith(meat + "-"):
                info["product"] = "pepperoni"
                info["meat"] = meat
                info["city_raw"] = rest[len(meat + "-"):]
                break
        else:
            info["product"] = "pepperoni"
            info["city_raw"] = rest

    return info


def build_page(info: dict) -> str:
    product = info["product"]
    meat = info.get("meat")
    city_raw = info["city_raw"]
    city_en = CITY_EN.get(city_raw, city_raw.replace("-", " ").title())
    ru_slug = info["slug"]

    product_label = PRODUCT_LABEL_EN.get(product, "Halal Products")
    product_desc = PRODUCT_DESC_EN.get(product, "halal meat products")
    meat_label = MEAT_EN.get(meat, "")
    meat_desc = MEAT_DESC_EN.get(meat, "")

    # Build title and descriptions
    if meat:
        h1 = f"{meat_label} Pepperoni Wholesale to {city_en} — Direct from Manufacturer"
        subtitle = f"Halal {meat_desc.lower()} pepperoni for pizzerias and HoReCa in {city_en}. Certified, HACCP, EXW Kazan."
        intro = f"Kazan Delicacies supplies <strong>halal {meat_desc.lower()} pepperoni</strong> wholesale to {city_en} and surrounding areas. Our {meat_desc.lower()} pepperoni is made from premium halal-certified meat, naturally smoked, and delivered in refrigerated trucks with full veterinary documentation."
        available = f"Explore our full range of halal pepperoni available for wholesale delivery to {city_en}:"
    else:
        h1 = f"{product_label} Wholesale to {city_en} — Direct from Manufacturer"
        subtitle = f"{product_label} for {product_desc} in {city_en}. Certified Halal, HACCP, EXW Kazan."
        intro = f"Kazan Delicacies supplies <strong>{product_label.lower()}</strong> wholesale to {city_en} and surrounding areas. Our products are made from premium halal-certified meats — beef, chicken, horse meat, turkey — with no pork, no GMO, and no meat glue."
        available = f"Explore our full range of {product_label.lower()} available for wholesale delivery to {city_en}:"

    # Delivery text
    if city_raw in ["kazakhstan", "uzbekistan", "belarus", "armenia", "azerbaijan", "kyrgyzstan"]:
        delivery_text = f"We deliver to {city_en} by refrigerated truck on EXW Kazan terms. As an EAEU/CIS member, customs clearance is simplified with Mercury FGIS veterinary certificates. Typical transit time is 5–10 days depending on distance. Multi-currency invoicing available."
    else:
        delivery_text = f"We deliver to {city_en} and the surrounding region by refrigerated truck (0…+6°C) on EXW Kazan terms. Regular shipments with full veterinary documentation. Contact us for delivery schedule and pricing in your preferred currency."

    # Parent page
    parent_page = "pepperoni"
    parent_label = "Pepperoni"
    if product == "kotlety-dlya-burgerov":
        parent_page = "en/for-horeca"
        parent_label = "HoReCa"
    elif product == "sosiki-dlya-hotdog":
        parent_page = "en/for-gas-stations"
        parent_label = "Gas Stations"

    # Related links
    related = []
    all_cities = ["moskva", "spb", "kazan", "ufa", "ekaterinburg", "sochi",
                  "krasnodar", "astrahan", "dagestan", "grozny", "mahachkala",
                  "yanao", "kazakhstan", "uzbekistan", "belarus", "armenia",
                  "azerbaijan", "kyrgyzstan"]
    for c in all_cities[:8]:  # show up to 8 related
        if c != city_raw:
            cn = CITY_EN.get(c, c.title())
            if meat:
                rslug = f"pepperoni-{meat}-{c}"
            else:
                rslug = f"{product}-{c}"
            related.append(f'<a href="/en/geo/{rslug}" class="geo-card"><strong>{cn}</strong>{product_label}</a>')

    # JSON-LD
    product_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": h1,
        "description": subtitle,
        "brand": {"@type": "Brand", "name": "Kazan Delicacies"},
        "manufacturer": {
            "@type": "Organization",
            "name": "Kazan Delicacies (ООО «Казанские Деликатесы»)",
            "url": "https://kazandelikates.tatar",
            "address": {"@type": "PostalAddress", "addressLocality": "Kazan", "addressRegion": "Tatarstan", "addressCountry": "RU"}
        },
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "Certification", "value": "Halal #614A/2024 (DUM RT)"},
            {"@type": "PropertyValue", "name": "Quality Control", "value": "HACCP + ISO 22000:2018"},
            {"@type": "PropertyValue", "name": "Market", "value": city_en}
        ],
        "offers": {"@type": "Offer", "priceCurrency": "RUB", "availability": "https://schema.org/InStock"}
    }, ensure_ascii=False)

    breadcrumb_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Catalog", "item": "https://pepperoni.tatar/en/"},
            {"@type": "ListItem", "position": 2, "name": parent_label, "item": f"https://pepperoni.tatar/{parent_page}"},
            {"@type": "ListItem", "position": 3, "name": city_en, "item": f"https://pepperoni.tatar/en/geo/{ru_slug}"}
        ]
    }, ensure_ascii=False)

    # SEO metadata
    if meat:
        title = f"{meat_label} Pepperoni {city_en} — Wholesale Halal Supplier | Kazan Delicacies"
        keywords = f"halal {meat_desc.lower()} pepperoni {city_en.lower()}, {meat_desc.lower()} pepperoni wholesale {city_en.lower()}, halal pepperoni supplier {city_en.lower()}, kazan delicacies {city_en.lower()}"
    else:
        title = f"{product_label} {city_en} — Wholesale Halal Supplier | Kazan Delicacies"
        keywords = f"halal {product_label.lower()} {city_en.lower()}, {product_label.lower()} wholesale {city_en.lower()}, halal supplier {city_en.lower()}, kazan delicacies {city_en.lower()}"

    description = subtitle + f" Halal Certificate #614A/2024 (DUM RT). HACCP + ISO 22000:2018. Direct factory pricing, EXW Kazan."

    return TPL.format(
        slug=ru_slug,
        ru_slug=ru_slug,
        ru_slug_rel=f"geo/{ru_slug}",
        title=title,
        description=description,
        keywords=keywords,
        h1=h1,
        subtitle=subtitle,
        intro_text=intro,
        city_en=city_en,
        product_label=product_label,
        available_text=available,
        delivery_text=delivery_text,
        parent_page=parent_page,
        parent_label=parent_label,
        related_links="\n    ".join(related),
        product_jsonld=product_jsonld,
        breadcrumb_jsonld=breadcrumb_jsonld,
        email_subject=quote(f"Halal {product_label} inquiry — {city_en}"),
        whatsapp_text=quote(f"Hi! I'm interested in halal {product_label.lower()} with delivery to {city_en}. Please send a quote."),
    )


def main():
    ru_slugs = sorted([f.stem for f in RU_GEO.glob("*.html")])
    # Filter out non-matching files (keep only our patterns)
    valid_slugs = []
    for s in ru_slugs:
        if s.startswith("pepperoni-") or s.startswith("kotlety-dlya-burgerov-") or s.startswith("sosiki-dlya-hotdog-"):
            valid_slugs.append(s)

    print(f"Found {len(valid_slugs)} RU geo pages to generate EN versions for")

    count = 0
    for slug in valid_slugs:
        info = parse_slug(slug)
        html = build_page(info)
        out = EN_GEO / f"{slug}.html"
        out.write_text(html, encoding="utf-8")
        count += 1

    print(f"✅ Generated {count} EN geo pages → {EN_GEO}")


if __name__ == "__main__":
    main()
