#!/usr/bin/env python3
"""Content-plan 2026-10-16 items 2–4, 8–9 and 13.

Catalog-backed pages. Facts come from products.json, site_facts.json and
evidence_registry.json. No invented oven tests, transit days, diameters,
clients, capacities, UZS offer prices or shipment promises. KD-012 stays out.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from landing_chrome import stylesheet_link, topbar_html  # noqa: E402
from metrika_snippet import ensure_metrika_html  # noqa: E402
from organization_ld import ORGANIZATION, SCRIPT  # noqa: E402
from site_facts import (  # noqa: E402
    FACTS,
    bakery_halal_line,
    cert_line_en,
    cert_line_ru,
    plural_ru,
    sku_count,
    sku_matrix,
    term,
)

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
_TRANSLATIONS = json.loads((Path(__file__).resolve().parent / "translations.json").read_text(encoding="utf-8"))
PHONE = FACTS["company"]["phone"]
EMAIL = FACTS["company"]["email"]
ADDR_RU = FACTS["company"]["address_ru"]
BASE = "https://pepperoni.tatar"

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
.container{max-width:860px;margin:0 auto;padding:40px 24px}
nav{font-size:.85rem;color:#888;margin-bottom:32px}nav a{color:#0066cc;text-decoration:none}
h1{font-size:2rem;font-weight:700;margin-bottom:8px}
h2{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}
h3{font-size:1.05rem;font-weight:600;margin:20px 0 8px}
p{margin-bottom:14px}
.badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0}
.badge-outline{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}
.lead{background:#f0f9f3;border-left:4px solid #1b7a3d;padding:14px 18px;border-radius:4px;margin-bottom:20px}
.card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:20px;margin:16px 0}
.products-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin:20px 0}
.product-card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:20px}
.product-card .sku{font-size:.75rem;color:#aaa}
.product-card .name{font-weight:600;font-size:.95rem;margin:4px 0 8px}
.product-card .meta{font-size:.8rem;color:#888}
.product-card a{display:inline-block;margin-top:12px;color:#1b7a3d;text-decoration:none;font-weight:600;font-size:.85rem}
table{width:100%;border-collapse:collapse;margin:12px 0}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}
th{background:#f5f5f5;font-weight:600}
ul{margin:8px 0 14px 24px}li{margin-bottom:6px}
.cta{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0}
.cta-outline{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}
.faq-section details{background:#fff;border:1px solid #e5e5e5;border-radius:8px;margin:8px 0;padding:4px 0}
.faq-section summary{padding:12px 16px;cursor:pointer;font-weight:600}
.faq-section .ans{padding:4px 16px 14px;color:#555;font-size:.92rem}
footer{margin-top:60px;padding-top:20px;border-top:1px solid #eee;font-size:.8rem;color:#888;text-align:center}
footer a{color:#0066cc;text-decoration:none}
figure img{max-width:100%;height:auto;border-radius:8px}
.note{font-size:.9rem;color:#555;background:#fff8e8;border-left:4px solid #c9a227;padding:12px 16px;border-radius:4px;margin:16px 0}
"""


def catalog() -> dict:
    return json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))


def by_sku(data: dict, *skus: str) -> list[dict]:
    want = {s.upper() for s in skus}
    found = [p for p in data["products"] if p["sku"].upper() in want]
    order = {s.upper(): i for i, s in enumerate(skus)}
    found.sort(key=lambda p: order.get(p["sku"].upper(), 99))
    missing = want - {p["sku"].upper() for p in found}
    if missing:
        raise SystemExit(f"content_plan_pages: SKUs missing from catalog: {sorted(missing)}")
    return found


def price_label(p: dict, lang: str) -> str:
    offers = p.get("offers") or {}
    price = offers.get("price")
    ppu = offers.get("pricePerUnit")
    ppb = offers.get("pricePerBox")
    if ppu not in (None, ""):
        return f"{ppu} ₽/шт" if lang == "ru" else f"{ppu} RUB/pc"
    if price not in (None, ""):
        return f"{price} ₽/упак." if lang == "ru" else f"{price} RUB/pack"
    if ppb not in (None, ""):
        return f"{ppb} ₽/кор." if lang == "ru" else f"{ppb} RUB/box"
    return "—" if lang == "ru" else "on request"


def weight_label(p: dict, lang: str = "ru") -> str:
    w = (p.get("weight") or "").strip()
    if not w:
        return "—"
    if not any(u in w.lower() for u in ("кг", "г", "kg", "g")):
        w = f"{w} кг"
    return catalog_units(w, lang)


def product_name(p: dict, lang: str) -> str:
    if lang != "en":
        return p["name"]
    return _TRANSLATIONS.get("products", {}).get(p["name"].strip().lower()) or p["name"]


def catalog_units(text: str | None, lang: str) -> str:
    """Mechanical RU→EN units from the Sheet cell. No invented numbers."""
    if not text:
        return "—"
    if lang != "en":
        return text
    out = text.replace("суток", "days").replace("сут.", "days")
    out = re.sub(r"\bсут\b", "days", out)
    out = out.replace(" кг", " kg").replace("кг", "kg")
    out = out.replace(" г", " g")
    out = re.sub(r"\bдо\s+", "up to ", out)
    out = out.replace("влажность", "humidity")
    return out


def prefix(lang: str) -> str:
    return "/en" if lang == "en" else ""


def product_url(sku: str, lang: str) -> str:
    return f"{prefix(lang)}/products/{sku.lower()}"


def faq_ld(pairs: list[tuple[str, str]]) -> str:
    entities = [
        {"@type": "Question", "name": q,
         "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in pairs
    ]
    return json.dumps(entities, ensure_ascii=False)


def faq_html(pairs: list[tuple[str, str]]) -> str:
    blocks = []
    for q, a in pairs:
        blocks.append(
            f'<details><summary>{q}</summary><div class="ans">{a}</div></details>'
        )
    return "\n".join(blocks)


def org_script() -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(ORGANIZATION, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def shell(lang: str, slug: str, title: str, desc: str, h1: str, body: str,
          faq: list[tuple[str, str]], extra_ld: list | None = None,
          robots: str = "index, follow") -> str:
    url = f"{BASE}{prefix(lang)}/{slug}"
    alt_lang = "en" if lang == "ru" else "ru"
    alt_url = f"{BASE}{prefix(alt_lang)}/{slug}"
    home = f"{BASE}/" if lang == "ru" else f"{BASE}/en/"
    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": 1,
              "name": "Главная" if lang == "ru" else "Home", "item": home},
             {"@type": "ListItem", "position": 2, "name": h1, "item": url},
         ]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity":
         json.loads(faq_ld(faq))},
    ]
    if extra_ld:
        ld.extend(extra_ld)
    nav = (
        f'<nav><a href="{prefix(lang) or "/"}">'
        f'{"Каталог" if lang == "ru" else "Catalog"}</a> → {h1}'
        f' · <a href="{prefix(alt_lang)}/{slug}">'
        f'{"EN" if lang == "ru" else "RU"}</a></nav>'
    )
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="alternate" hreflang="ru" href="{BASE}/{slug}">
<link rel="alternate" hreflang="en" href="{BASE}/en/{slug}">
<link rel="alternate" hreflang="x-default" href="{BASE}/{slug}">
{org_script()}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>
{stylesheet_link()}
<style>{CSS}</style>
</head>
<body class="kd-landing">
{topbar_html(lang, slug)}
<div class="container">
{nav}
<h1>{h1}</h1>
{body}
<section class="faq-section">
<h2>{"Частые вопросы" if lang == "ru" else "FAQ"}</h2>
{faq_html(faq)}
</section>
<p><a class="cta" href="tel:+79872170202">{PHONE}</a>
<a class="cta cta-outline" href="https://wa.me/79872170202">WhatsApp</a>
<a class="cta cta-outline" href="mailto:{EMAIL}">{EMAIL}</a></p>
<footer><p>ООО «Казанские Деликатесы» · <a href="{prefix(lang) or "/"}">pepperoni.tatar</a> · {ADDR_RU} · {PHONE}</p></footer>
</div>
</body>
</html>"""


def _row_price_kind(p: dict) -> str:
    offers = p.get("offers") or {}
    if offers.get("pricePerUnit") not in (None, ""):
        return "piece"
    if offers.get("price") not in (None, ""):
        return "pack"
    if offers.get("pricePerBox") not in (None, ""):
        return "box"
    return "unknown"


def sku_table_note(products: list[dict], lang: str) -> str:
    """Price footnote matches the units actually shown in the table."""
    kinds = {_row_price_kind(p) for p in products}
    if lang == "ru":
        if kinds == {"piece"}:
            unit = "Для выпечки в каталоге указана цена за штуку. "
        elif kinds == {"pack"}:
            unit = "Цена указана за упаковку. "
        elif "pack" in kinds and "piece" in kinds:
            unit = "Мясные позиции — цена за упаковку; для выпечки в каталоге указана цена за штуку. "
        else:
            unit = ""
        return (
            "Цена — из products.json, EXW Казань, с НДС. "
            + unit
            + "Пустая ячейка значит, что сумму подтверждает отдел продаж."
        )
    if kinds == {"piece"}:
        unit = "Bakery rows use per-piece price. "
    elif kinds == {"pack"}:
        unit = "Rows use per-pack price. "
    elif "pack" in kinds and "piece" in kinds:
        unit = "Pack rows use per-pack price; bakery rows use per-piece price. "
    else:
        unit = ""
    return (
        "Price is from products.json, EXW Kazan, VAT included. "
        + unit
        + "A blank cell means sales confirms the amount."
    )


def sku_table(products: list[dict], lang: str) -> str:
    head = ("SKU", "Название", "Масса", "Хранение", "Срок", "Цена EXW") if lang == "ru" else (
        "SKU", "Name", "Weight", "Storage", "Shelf life", "EXW price")
    rows = []
    for p in products:
        rows.append(
            "<tr>"
            f'<td><a href="{product_url(p["sku"], lang)}">{p["sku"]}</a></td>'
            f"<td>{product_name(p, lang)}</td><td>{weight_label(p, lang)}</td>"
            f"<td>{catalog_units(p.get('storage'), lang)}</td>"
            f"<td>{catalog_units(p.get('shelfLife'), lang)}</td>"
            f"<td>{price_label(p, lang)}</td></tr>"
        )
    note = sku_table_note(products, lang)
    return (
        "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head)
        + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table><p>" + note + "</p>"
    )


def cards(products: list[dict], lang: str) -> str:
    bits = []
    more = "Подробнее →" if lang == "ru" else "Details →"
    for p in products:
        bits.append(
            f'<div class="product-card"><div class="sku">{p["sku"]}</div>'
          f'<div class="name">{product_name(p, lang)}</div>'
          f'<div class="meta">{weight_label(p, lang)} · {catalog_units(p.get("shelfLife"), lang)} · {catalog_units(p.get("storage"), lang)}</div>'
            f'<a href="{product_url(p["sku"], lang)}">{more}</a></div>'
        )
    return '<div class="products-grid">' + "".join(bits) + "</div>"


def photos(products: list[dict], lang: str) -> str:
    figures = []
    caps = {"imageMain": ("продукт", "product"), "imageSlice": ("срез", "slice"),
            "imagePack": ("упаковка", "pack")}
    for p in products:
        for key, (ru, en) in caps.items():
            src = p.get(key)
            if not src:
                continue
            cap = ru if lang == "ru" else en
            figures.append(
                f'<figure class="product-card"><img src="{src}" alt="{product_name(p, lang)}, {cap}" '
                f'loading="lazy" width="240" height="180">'
                f'<figcaption>{p["sku"]} · {cap}</figcaption></figure>'
            )
    if not figures:
        return ("<p>Фото этой позиции в каталоге нет.</p>" if lang == "ru"
                else "<p>No catalog photo for this SKU yet.</p>")
    return '<div class="products-grid">' + "".join(figures) + "</div>"


def offer_amount(p: dict) -> str | None:
    offers = p.get("offers") or {}
    price = offers.get("price")
    if price not in (None, ""):
        return str(price)
    ppu = offers.get("pricePerUnit")
    if ppu not in (None, ""):
        return str(ppu)
    return None


def catalog_shelf_life(p: dict, lang: str) -> str:
    """Structured shelfLife from products.json — not the Sheet SEO cell."""
    return catalog_units(p.get("shelfLife"), lang)


def product_description(p: dict, lang: str) -> str:
    """Catalog fields only. Drops SEO-cell copy (60 days, охлаждённый/chilled)."""
    name = product_name(p, lang)
    weight = weight_label(p, lang)
    life = catalog_shelf_life(p, lang)
    store = catalog_units(p.get("storage"), lang)
    if lang == "ru":
        text = (
            f"{name}, {weight}. Срок хранения {life} (поле shelfLife каталога). "
            f"Хранение: {store}."
        )
    else:
        text = (
            f"{name}, {weight}. Shelf life {life} (catalog shelfLife field). "
            f"Storage: {store}."
        )
    return re.sub(r"(?i)\s*(охлаждённ\w*|охлажденн\w*|chilled)\s*", " ", text).strip()


def unique_images(p: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for key in ("imageMain", "imagePack", "imageSlice", "image"):
        src = p.get(key)
        if src and src not in seen:
            seen.add(src)
            out.append(src)
    return out


def product_offer_ld(p: dict, lang: str, offer_url: str) -> dict:
    offers = p.get("offers") or {}
    price = offer_amount(p)
    node: dict = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product_name(p, lang),
        "sku": p["sku"],
        "url": f"{BASE}{product_url(p['sku'], lang)}",
        "description": product_description(p, lang)[:400],
        "brand": {"@type": "Brand",
                  "name": "Казанские Деликатесы" if lang == "ru" else "Kazan Delicacies"},
        "manufacturer": {"@id": f"{BASE}/#organization"},
    }
    images = unique_images(p)
    if images:
        node["image"] = images
    barcode = str(p.get("barcode") or "").strip()
    try:
        from index_policy_check import valid_gtin  # noqa: WPS433
        if valid_gtin(barcode, 13):
            node["gtin13"] = barcode
    except Exception:
        pass
    if price is not None:
        offer = {
            "@type": "Offer",
            "url": offer_url,
            "priceCurrency": offers.get("priceCurrency") or "RUB",
            "price": price,
        }
        # Availability only from products.json — never invent InStock.
        avail = str(offers.get("availability") or "").strip()
        if avail:
            offer["availability"] = avail
        node["offers"] = offer
    return node


def sku_list(products: list[dict], lang: str) -> str:
    """Compact inventory — not a clone of sku_table(), for similarity audit."""
    items = []
    for p in products:
        items.append(
            f'<li><a href="{product_url(p["sku"], lang)}">{p["sku"]}</a> — '
            f"{product_name(p, lang)}, {weight_label(p, lang)}, "
            f"{catalog_units(p.get('storage'), lang)}, "
            f"{catalog_units(p.get('shelfLife'), lang)}</li>"
        )
    return "<ul>" + "".join(items) + "</ul>"


def frozen_bakery_skus(data: dict) -> list[dict]:
    found = []
    for product in data["products"]:
        if product.get("section") != "Выпечка":
            continue
        storage = product.get("storage") or ""
        if any(token in storage for token in ("-18", "–18", "−18")):
            found.append(product)
    return found


def write_html(lang: str, slug: str, html: str) -> None:
    dest = PUBLIC / "en" / f"{slug}.html" if lang == "en" else PUBLIC / f"{slug}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")


# ── item 3: /sosiska-v-teste ──────────────────────────────────────────────

def write_sosiska() -> None:
    data = catalog()
    p018, p061 = by_sku(data, "KD-018", "KD-061")
    p017 = next((p for p in data["products"] if p["sku"] == "KD-017"), None)
    for lang in ("ru", "en"):
        if lang == "ru":
            title = "Сосиска в тесте оптом для пекарен — KD-018 и KD-061 | Казанские Деликатесы"
            desc = (
                "Для пекарен: сосиска без оболочки KD-018 (45 г — вес сосиски, упаковка 2 кг) "
                "под своё тесто и готовая сосиска в тесте KD-061 (120 г, −18 °C, 360 суток). "
                f"{cert_line_ru()}."
            )
            h1 = "Сосиска в тесте оптом — для пекарен"
            intro = (
                f"<p class=\"lead\">Две позиции из актуального каталога ({sku_count()} SKU всего): "
                "сосиска без оболочки под тесто пекарни и готовая замороженная сосиска в тесте. "
                "Цифры — из products.json, не из рекламного текста.</p>"
            )
            who = (
                "<h2>Для пекарен</h2><ul>"
                "<li><strong>KD-018</strong> — сосиски «К завтраку» без оболочки для «сосиски в тесте»; "
                f"в названии каталога указан вес сосиски 45 г, масса упаковки {weight_label(p018)}, "
                f"хранение {p018.get('storage')}, срок {p018.get('shelfLife')}. "
                "Пекарня использует свою тестовую заготовку.</li>"
                "<li><strong>KD-061</strong> — готовая «Сосиска в тесте», "
                f"масса {weight_label(p061)}, хранение {p061.get('storage')}, срок {p061.get('shelfLife')}. "
                "Раздел каталога — классическая выпечка.</li></ul>"
            )
            link017 = (
                f'<p>Рядом в категории сосисок — <a href="{product_url("KD-017", "ru")}">KD-017 «К завтраку»</a> '
                f"({weight_label(p017)}, {p017.get('shelfLife')}) — с оболочкой, не для выпечки в тесте. "
                "На этой странице она дана ссылкой, не как замена KD-018.</p>"
                if p017 else ""
            )
            test = (
                "<h2>Срез после выпечки</h2>"
                "<p class=\"note\">Фото реального теста в печи на этой странице нет. "
                "Публикуем только снимок фактического выпекания; пока его нет — не ставим "
                "температуру, время или «не лопается». Образец для вашей печи согласует отдел продаж.</p>"
            )
            docs = (
                "<h2>Документы</h2><ul>"
                f"<li>KD-018 (охлаждённая мясная позиция): Халяль ДУМ РТ №0008 и №614A/2024.</li>"
                f"<li>KD-061 (выпечка): Халяль ДУМ РТ №884A/2025.</li>"
                "<li>ISO 22000:2018 (FSMS-2351/А) — контур безопасности, это не халяль-сертификат.</li>"
                "<li>MOQ — одна паллета, сборная возможна. EXW Казань.</li></ul>"
            )
            faq = [
                ("Какие SKU на этой странице?",
                 "Только KD-018 (сосиска без оболочки под тесто) и KD-061 (готовая сосиска в тесте). "
                 "KD-017 — ссылкой, это сосиска «К завтраку» с оболочкой."),
                ("Есть ли фото среза после выпечки?",
                 "Нет. Когда появится снимок реального теста, он будет на этой странице. "
                 "Срок, масса и цена — в карточках SKU."),
                ("Как подтверждается халяль?",
                 f"{cert_line_ru()}. Для выпечки действует №884A/2025, для мясной сосиски — №0008 и №614A/2024."),
                ("Как заказать?",
                 f"Укажите SKU и объём. {PHONE}, {EMAIL}. Минимальный заказ — одна паллета, сборная возможна."),
            ]
        else:
            title = "Sausage in dough wholesale for bakeries — KD-018 and KD-061"
            desc = (
                "For bakeries: casing-free breakfast sausage KD-018 (45 g sausage weight, 2 kg pack) "
                "for your own dough, and ready frozen sausage-in-dough KD-061 (120 g, −18 °C, 360 days). "
                f"{cert_line_en()}."
            )
            h1 = "Sausage in dough wholesale — for bakeries"
            intro = (
                f"<p class=\"lead\">Two SKUs from the live catalog ({sku_count()} SKUs total): "
                "a casing-free sausage for the bakery's own dough, and a ready frozen sausage roll. "
                "Figures are from products.json.</p>"
            )
            who = (
                "<h2>For bakeries</h2><ul>"
                "<li><strong>KD-018</strong> — casing-free breakfast sausages for sausage-in-dough; "
                f"the catalog name states 45 g sausage weight, pack {weight_label(p018, lang)}, "
                f"storage {catalog_units(p018.get('storage'), lang)}, shelf life {catalog_units(p018.get('shelfLife'), lang)}.</li>"
                "<li><strong>KD-061</strong> — ready «Sausage in dough», "
                f"{weight_label(p061, lang)}, {catalog_units(p061.get('storage'), lang)}, {catalog_units(p061.get('shelfLife'), lang)}. "
                "Catalog section: classic bakery.</li></ul>"
            )
            link017 = (
                f'<p>Related: <a href="{product_url("KD-017", "en")}">KD-017 breakfast sausages</a> '
                f"({weight_label(p017, lang)}, {catalog_units(p017.get('shelfLife'), lang)}) — with casing, not a dough filling. "
                "Linked here, not substituted for KD-018.</p>"
                if p017 else ""
            )
            test = (
                "<h2>Bake-test slice</h2>"
                "<p class=\"note\">This page has no photo of a real oven test. "
                "We publish only an actual bake shot; until it exists we do not state "
                "temperature, time or 'does not burst'. Sales can agree a sample for your oven.</p>"
            )
            docs = (
                "<h2>Documents</h2><ul>"
                "<li>KD-018 (chilled meat): Halal DUM RT No. 0008 and No. 614A/2024.</li>"
                "<li>KD-061 (bakery): Halal DUM RT No. 884A/2025.</li>"
                "<li>ISO 22000:2018 (FSMS-2351/A) is food-safety, not a halal certificate.</li>"
                "<li>MOQ — one pallet, mixed pallet possible. EXW Kazan.</li></ul>"
            )
            faq = [
                ("Which SKUs are on this page?",
                 "Only KD-018 (casing-free sausage for dough) and KD-061 (ready sausage in dough). "
                 "KD-017 is a link — breakfast sausage with casing."),
                ("Is there a post-bake slice photo?",
                 "No. When a real oven-test photo exists it will appear here. "
                 "Weight, shelf life and price are on the SKU cards."),
                ("How is halal confirmed?",
                 f"{cert_line_en()}. Bakery SKU uses No. 884A/2025; the meat sausage uses No. 0008 and No. 614A/2024."),
                ("How to order?",
                 f"Name the SKU and volume. {PHONE}, {EMAIL}. Minimum order is one pallet; mixed pallets are possible."),
            ]
        extra = [{
            "@context": "https://schema.org", "@type": "ItemList",
            "name": h1, "numberOfItems": 2,
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "url": f"{BASE}{product_url('KD-018', lang)}", "name": p018["name"]},
                {"@type": "ListItem", "position": 2,
                 "url": f"{BASE}{product_url('KD-061', lang)}", "name": p061["name"]},
            ],
        }]
        body = (
            intro + who + link017
            + f"<h2>{'Ассортимент' if lang == 'ru' else 'Assortment'}</h2>"
            + sku_table([p018, p061], lang) + cards([p018, p061], lang)
            + f"<h2>{'Фото из каталога' if lang == 'ru' else 'Catalog photos'}</h2>"
            + photos([p018, p061], lang) + test + docs
            + f'<p>{"Смотрите также" if lang == "ru" else "See also"}: '
            f'<a href="{prefix(lang)}/vyipechka-halyal">'
            f'{"Выпечка халяль" if lang == "ru" else "Halal bakery"}</a> · '
            f'<a href="{prefix(lang)}/halyal-vypechka-optom-dlya-pekaren">'
            f'{"Выпечка для пекарен и кофеен" if lang == "ru" else "Bakery for bakeries and coffee shops"}</a> · '
            f'<a href="{prefix(lang)}/dlya-pekaren">'
            f'{"Для пекарен" if lang == "ru" else "For bakeries"}</a> · '
            f'<a href="{prefix(lang)}/zamorozhennaya-vypechka-dlya-kofeen">'
            f'{"Выпечка для кофеен" if lang == "ru" else "Bakery for coffee shops"}</a></p>'
        )
        html = ensure_metrika_html(shell(lang, "sosiska-v-teste", title, desc, h1, body, faq, extra))
        dest = PUBLIC / ("en" if lang == "en" else ".")
        if lang == "en":
            (PUBLIC / "en" / "sosiska-v-teste.html").write_text(html, encoding="utf-8")
        else:
            (PUBLIC / "sosiska-v-teste.html").write_text(html, encoding="utf-8")
        print(f"  sosiska-v-teste [{lang}]")


# ── item 4: /vyipechka-halyal ─────────────────────────────────────────────

TATAR_SKUS = ["KD-046", "KD-047", "KD-048", "KD-049", "KD-050", "KD-051",
              "KD-052", "KD-065", "KD-066"]


def write_bakery() -> None:
    data = catalog()
    tatar = by_sku(data, *TATAR_SKUS)
    all_bakery = [p for p in data["products"] if p.get("section") == "Выпечка"]
    chak = [p for p in all_bakery if p["sku"] in {"KD-053", "KD-054"}]
    classic = [p for p in all_bakery if p.get("category") == "Классическая выпечка"]
    n_bakery = len(all_bakery)
    for lang in ("ru", "en"):
        if lang == "ru":
            title = "Татарская выпечка оптом — халяль эчпочмак, губадия, самса | Казанские Деликатесы"
            desc = (
                f"Хаб татарской выпечки: {len(tatar)} SKU из прайса (губадия, чебурек, перемяч, "
                f"самса, эчпочмак, элеш, беккен, вак балиш). Всего в разделе «Выпечка» {n_bakery} SKU. "
                "Халяль ДУМ РТ №884A/2025."
            )
            h1 = "Выпечка халяль — татарская выпечка оптом"
            intro = (
                f"<p class=\"lead\">Продуктовый хаб выпечки. Ядро страницы — национальная татарская "
                f"линейка ({len(tatar)} SKU из Google Sheets). Классическая выпечка — в таблице ниже. "
                "Чак-чак вынесен на <a href=\"/chak-chak-optom\">/chak-chak-optom</a>. "
                "Заказ для пекарен и кофеен — "
                "<a href=\"/halyal-vypechka-optom-dlya-pekaren\">/halyal-vypechka-optom-dlya-pekaren</a>.</p>"
            )
            who = (
                "<h2>Для кого</h2><ul>"
                "<li><a href=\"/dlya-pekaren\">Пекарни</a> и заморозка для выкладки</li>"
                "<li><a href=\"/dlya-horeca\">HoReCa</a> и <a href=\"/dlya-setey\">сети</a></li>"
                "<li><a href=\"/sosiska-v-teste\">Сосиска в тесте</a> — отдельный интент для пекарен</li></ul>"
            )
            line = (
                "<h2>Фото линии</h2>"
                "<p class=\"note\">Отдельного фото хлебопечного цеха в каталоге нет. "
                "Не подставляем кадр мясного производства. Фото изделий — из карточек SKU.</p>"
            )
            docs = (
                "<h2>Документы</h2><ul>"
                f"<li>{bakery_halal_line('ru')} Проверка — <a href=\"/halal\">/halal</a>.</li>"
                "<li>ISO 22000:2018 — контур безопасности, не халяль.</li>"
                "<li>MOQ — одна паллета, сборная возможна. EXW Казань.</li></ul>"
            )
            faq = [
                ("Сколько SKU в хабе?",
                 f"В ядре татарской выпечки {len(tatar)} позиций (KD-046–052, 065, 066). "
                 f"Весь раздел «Выпечка» в каталоге — {n_bakery} SKU, включая классику и чак-чак."),
                ("Чак-чак — отдельная страница?",
                 "Да. KD-053 и KD-054 — на /chak-chak-optom. Здесь остаётся краткая таблица из каталога."),
                ("Кто автор рецептур?",
                 "Имя технолога на сайте не публикуем: в реестре доказательств нет согласованной персоны. "
                 "Состав и срок — в карточке SKU."),
                ("Как заказать?",
                 f"{PHONE}, {EMAIL}. Минимальный заказ — одна паллета."),
            ]
        else:
            title = "Tatar halal bakery wholesale — echpochmak, gubadiya, samsa"
            desc = (
                f"Tatar bakery hub: {len(tatar)} SKUs from the price list (gubadiya, cheburek, peremyach, "
                f"samsa, echpochmak, elesh, bekken, vak balish). Bakery section total {n_bakery} SKUs. "
                "Halal DUM RT No. 884A/2025."
            )
            h1 = "Halal bakery — Tatar pastry wholesale"
            intro = (
                f"<p class=\"lead\">Bakery product hub. The core is the Tatar national line "
                f"({len(tatar)} SKUs from Google Sheets). Classic pastry is in the table below. "
                "Chak-chak has its own page: <a href=\"/en/chak-chak-optom\">/en/chak-chak-optom</a>. "
                "Bakery and coffee-shop ordering: "
                "<a href=\"/en/halyal-vypechka-optom-dlya-pekaren\">/en/halyal-vypechka-optom-dlya-pekaren</a>.</p>"
            )
            who = (
                "<h2>Who it is for</h2><ul>"
                "<li><a href=\"/en/dlya-pekaren\">Bakeries</a></li>"
                "<li><a href=\"/en/dlya-horeca\">HoReCa</a> and <a href=\"/en/dlya-setey\">retail chains</a></li>"
                "<li><a href=\"/en/sosiska-v-teste\">Sausage in dough</a> — bakery-specific intent</li></ul>"
            )
            line = (
                "<h2>Line photo</h2>"
                "<p class=\"note\">There is no bakery-line photo in the catalog. "
                "We do not reuse a meat-plant still. Product photos come from SKU cards.</p>"
            )
            docs = (
                "<h2>Documents</h2><ul>"
                f"<li>{bakery_halal_line('en')} Verify on <a href=\"/en/halal\">/en/halal</a>.</li>"
                "<li>ISO 22000:2018 is food-safety, not halal.</li>"
                "<li>MOQ — one pallet, mixed pallet possible. EXW Kazan.</li></ul>"
            )
            faq = [
                ("How many SKUs?",
                 f"Tatar core: {len(tatar)} SKUs (KD-046–052, 065, 066). "
                 f"Whole bakery section: {n_bakery} SKUs including classic pastry and chak-chak."),
                ("Is chak-chak a separate page?",
                 "Yes. KD-053 and KD-054 live on /en/chak-chak-optom. This hub keeps a short catalog table."),
                ("Who is the technologist author?",
                 "No person is named: the evidence registry has no consented Person. "
                 "Composition and shelf life are on the SKU card."),
                ("How to order?",
                 f"{PHONE}, {EMAIL}. Minimum order is one pallet."),
            ]
        extra = [{
            "@context": "https://schema.org", "@type": "ItemList",
            "name": h1, "numberOfItems": len(tatar),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "url": f"{BASE}{product_url(p['sku'], lang)}", "name": p["name"]}
                for i, p in enumerate(tatar)
            ],
        }]
        h_core = "Татарская линейка" if lang == "ru" else "Tatar line"
        h_classic = "Классическая выпечка" if lang == "ru" else "Classic pastry"
        h_chak = (
            'Чак-чак — <a href="/chak-chak-optom">отдельная страница</a>'
            if lang == "ru" else
            'Chak-chak — <a href="/en/chak-chak-optom">separate page</a>'
        )
        body = (
            intro + who
            + f"<h2>{h_core} ({len(tatar)} SKU)</h2>"
            + sku_table(tatar, lang) + cards(tatar, lang) + photos(tatar[:4], lang)
            + line
            + f"<h2>{h_chak}</h2>" + sku_table(chak, lang)
            + f"<h2>{h_classic}</h2>" + sku_table(classic, lang)
            + docs
        )
        html = ensure_metrika_html(shell(lang, "vyipechka-halyal", title, desc, h1, body, faq, extra))
        path = PUBLIC / "en" / "vyipechka-halyal.html" if lang == "en" else PUBLIC / "vyipechka-halyal.html"
        path.write_text(html, encoding="utf-8")
        print(f"  vyipechka-halyal [{lang}] {n_bakery} bakery SKU, core {len(tatar)}")


# ── item 9: /pepperoni-dlya-pizzerii ──────────────────────────────────────

def write_pizzeria() -> None:
    data = catalog()
    items = by_sku(data, "KD-013", "KD-014")
    assert not any(p["sku"] == "KD-012" for p in data["products"])
    for lang in ("ru", "en"):
        if lang == "ru":
            title = "Пепперони для пиццерии — куриный KD-013 / KD-014 | Казанские Деликатесы"
            desc = (
                "Где купить пепперони для пиццерии: куриный варёно-копчёный "
                "KD-013 нарезка 0,5 кг и KD-014 целый батон 0,8 кг. Халяль ДУМ РТ №0008 / №614A/2024. "
                "Форматы и оптовый каталог — на /pepperoni."
            )
            h1 = "Пепперони для пиццерии"
            intro = (
                "<p class=\"lead\">Эта страница — про применение на кухне пиццерии. "
                "Продукт и форматы — на <a href=\"/pepperoni\">/pepperoni</a>. "
                "В каталоге две позиции: нарезка KD-013 (0,5 кг) и батон KD-014 (0,8 кг), "
                "оба варёно-копчёные куриные, 360 суток при −18 °C.</p>"
            )
            oven = (
                "<h2>Тест в печи</h2>"
                "<p class=\"note\">Публичного фото теста в пицца-печи с условиями (температура, "
                "время, диаметр слайса) нет. Не указываем «не скручивается» и диаметр в миллиметрах, "
                "пока нет спецификации партии или снимка реального теста. "
                "Отдел продаж согласует образец для вашей печи.</p>"
            )
            use = (
                "<h2>Как берут на кухне</h2><ul>"
                "<li>KD-013 — готовая нарезка, 0,5 кг, без слайсера на смене.</li>"
                "<li>KD-014 — целый батон 0,8 кг, нарезка толщины — на вашем слайсере.</li>"
                "<li>Состав, цена EXW и наличие — в карточках SKU, не в рекламном тексте.</li></ul>"
            )
            faq = [
                ("Из какого мяса пепперони?",
                 "В текущем каталоге — курица: KD-013 нарезка 0,5 кг и KD-014 батон 0,8 кг. "
                 "Пепперони из конины в текущем каталоге нет."),
                ("Какой диаметр слайса?",
                 "Диаметр на этой странице не публикуем: в products.json поля диаметра нет. "
                 "Значение — в спецификации партии по запросу."),
                ("Есть ли тест в печи?",
                 "Снимка реального теста с условиями нет. Образец для вашей печи — через отдел продаж."),
                ("Где продукт и форматы?",
                 "На /pepperoni. Здесь — сценарий пиццерии."),
            ]
        else:
            title = "Pepperoni for pizzerias — chicken KD-013 / KD-014 | Kazan Delicacies"
            desc = (
                "Where to buy pepperoni for a pizzeria: cooked-smoked chicken "
                "KD-013 sliced 0.5 kg and KD-014 whole stick 0.8 kg. Halal DUM RT No. 0008 / "
                "No. 614A/2024. Formats and wholesale catalog live on /en/pepperoni."
            )
            h1 = "Pepperoni for pizzerias"
            intro = (
                "<p class=\"lead\">This page is the pizzeria application. "
                "Product and formats live on <a href=\"/en/pepperoni\">/en/pepperoni</a>. "
                "Catalog: KD-013 sliced 0.5 kg and KD-014 whole stick 0.8 kg, both chicken "
                "cooked-smoked, 360 days at −18 °C.</p>"
            )
            oven = (
                "<h2>Oven test</h2>"
                "<p class=\"note\">There is no published pizza-oven test photo with conditions "
                "(temperature, time, slice diameter). We do not claim 'does not cup' or a millimetre "
                "diameter until a batch spec or a real test shot exists. Sales can agree a sample.</p>"
            )
            use = (
                "<h2>Kitchen formats</h2><ul>"
                "<li>KD-013 — factory sliced, 0.5 kg, no slicer on the shift.</li>"
                "<li>KD-014 — whole 0.8 kg stick, slice thickness on your slicer.</li>"
                "<li>Composition, EXW price and stock are on the SKU cards.</li></ul>"
            )
            faq = [
                ("What meat is the pepperoni?",
                 "Current catalog is chicken: KD-013 sliced 0.5 kg and KD-014 stick 0.8 kg. "
                 "Horse-meat pepperoni is not in the current catalog."),
                ("What slice diameter?",
                 "Not published here: products.json has no diameter field. "
                 "The batch specification is sent on request."),
                ("Is there an oven test?",
                 "No published test photo with conditions. A sample for your oven is via sales."),
                ("Where are product and formats?",
                 "On /en/pepperoni. This URL is the pizzeria scenario."),
            ]
        extra = [{
            "@context": "https://schema.org", "@type": "ItemList",
            "name": h1, "numberOfItems": 2,
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "url": f"{BASE}{product_url(p['sku'], lang)}", "name": p["name"]}
                for i, p in enumerate(items)
            ],
        }]
        body = (
            intro + use
            + sku_table(items, lang) + cards(items, lang) + photos(items, lang)
            + oven
            + f'<p><a href="{prefix(lang)}/pepperoni">'
            f'{"Продукт и форматы →" if lang == "ru" else "Product and formats →"}</a></p>'
        )
        html = ensure_metrika_html(
            shell(lang, "pepperoni-dlya-pizzerii", title, desc, h1, body, faq, extra)
        )
        path = (PUBLIC / "en" / "pepperoni-dlya-pizzerii.html" if lang == "en"
                else PUBLIC / "pepperoni-dlya-pizzerii.html")
        path.write_text(html, encoding="utf-8")
        print(f"  pepperoni-dlya-pizzerii [{lang}]")


# ── item 8: /export/kazakhstan ────────────────────────────────────────────

def write_kazakhstan() -> None:
    n = sku_count()
    current_ru = ", ".join(FACTS["export"]["current_ru"])
    current_en = ", ".join(FACTS["export"]["current_en"])
    data = catalog()
    pepp = by_sku(data, "KD-013", "KD-014")
    kazy = [p for p in data["products"] if p.get("category") == "Премиум Казылык"]
    for lang, slug_dir in (("ru", PUBLIC / "export"), ("en", PUBLIC / "en" / "export")):
        slug_dir.mkdir(parents=True, exist_ok=True)
        if lang == "ru":
            title = "Экспорт халяль колбасы в Казахстан — Цербер, EXW Казань"
            desc = (
                f"Экспорт халяль колбасы в Казахстан из текущего экспорта ({current_ru}). "
                f"Каталог {n} SKU, площадка в реестре «Цербер» RU-016/SB88273. "
                "Срок доставки на странице не фиксируем. EXW Казань."
            )
            h1 = "Экспорт халяль колбасы в Казахстан"
            tag = "Текущие поставки · ЕАЭС · EXW Казань"
            intro = (
                f"<p class=\"lead\">Казахстан входит в текущие экспортные направления "
                f"({current_ru}). Предприятие № RU-016/SB88273 внесено в "
                "реестр «Цербер» Россельхознадзора и аттестовано для экспорта в Казахстан. "
                "Аттестация площадки — не обещание конкретной партии.</p>"
            )
            cert = (
                f"<h2>Сертификация и допуск</h2><div class=\"card\">"
                f"<p>{cert_line_ru()}</p>"
                "<p>Признание сертификата в Казахстане подтверждаем по конкретной поставке "
                "с импортёром. На странице нет заявления о взаимном признании органа страны назначения.</p>"
                "<p>Площадка в реестре «Цербер» (№ RU-016/SB88273), аттестована для экспорта в Казахстан.</p>"
                "<p>Казахстан — член ЕАЭС: таможенное оформление в контуре союза, детали — по партии.</p></div>"
            )
            how = (
                "<h2>Как организована поставка</h2>"
                "<p>Базис по умолчанию — EXW Казань (Incoterms 2020). Перевозку организует покупатель "
                "или согласовываем отдельно. Срок в днях на этой странице не публикуем: "
                "в реестре доказательств нет подтверждённого транзитного времени.</p>"
                "<p>Цены в тенге на странице нет. Базовая цена — рубли EXW; валюта расчёта — по договору, "
                "это не оферта в KZT.</p>"
            )
            facts = (
                f"<div class=\"card\"><ul>\n"
                f"<li>Ассортимент: {n} наименований халяль — пепперони, сосиски, котлеты, "
                "копчёные колбасы, казылык, татарская выпечка.</li>"
                "<li>Для запроса чаще берут KD-013/014 (куриный пепперони), сосиски и казылык — "
                "состав и цена только из карточек SKU.</li>"
                "<li>Документы к отгрузке: халяль, декларация, ВСД («Меркурий»), «Честный знак», ЭТрН.</li>"
                "<li>MOQ — одна паллета, сборная возможна.</li></ul></div>"
            )
            faq = [
                ("Вы уже поставляете в Казахстан?",
                 f"Казахстан указан среди текущих направлений ({current_ru}). "
                 "Конкретный объём, город и график — по договору, без публикации клиентов."),
                ("Сколько дней занимает доставка в Алматы?",
                 "На странице нет числа дней. Срок подтверждаем по маршруту и партии."),
                ("Какая цена в тенге?",
                 "Оферты в KZT нет. База — рубли EXW Казань; валюту счёта согласуем."),
                ("Признаёт ли Казахстан сертификат ДУМ РТ?",
                 "Признание подтверждаем по поставке. Публичного документа о безусловном признании "
                 "в реестре доказательств нет."),
            ]
        else:
            title = "Halal sausage export to Kazakhstan — Cerberus, EXW Kazan"
            desc = (
                f"Kazakhstan is a current shipment destination ({current_en}). "
                f"{n} SKU catalog, Cerberus facility RU-016/SB88273. "
                "No invented transit days. EXW Kazan."
            )
            h1 = "Halal sausage export to Kazakhstan"
            tag = "Current shipments · EAEU · EXW Kazan"
            intro = (
                f"<p class=\"lead\">Kazakhstan is listed among current export destinations "
                f"({current_en}). Facility No. RU-016/SB88273 is in the "
                "Rosselkhoznadzor Cerberus registry and attested for export to Kazakhstan. "
                "Facility attestation is not a promise of a specific shipment.</p>"
            )
            cert = (
                f"<h2>Certification and market access</h2><div class=\"card\">"
                f"<p>{cert_line_en()}</p>"
                "<p>Certificate recognition in Kazakhstan is confirmed per shipment with the importer. "
                "This page does not claim destination-authority approval.</p>"
                "<p>The facility is in the Cerberus registry (No. RU-016/SB88273) and attested for export to Kazakhstan.</p>"
                "<p>Kazakhstan is an EAEU member; customs details are confirmed per consignment.</p></div>"
            )
            how = (
                "<h2>How supply works</h2>"
                "<p>Default basis is EXW Kazan (Incoterms 2020). The buyer arranges freight, or we agree otherwise. "
                "We do not publish a day-count: the evidence registry has no confirmed transit time.</p>"
                "<p>No tenge offer price on this page. Base price is RUB EXW; invoice currency is by contract.</p>"
            )
            facts = (
                f"<div class=\"card\"><ul>\n"
                f"<li>Range: {n} halal SKUs — pepperoni, sausages, burger patties, smoked sausages, "
                "kazylyk, Tatar pastry.</li>"
                "<li>Typical enquiry mix: KD-013/014 chicken pepperoni, sausages and kazylyk — "
                "composition and price only from SKU cards.</li>"
                "<li>Shipping documents: halal, declaration, Mercury VSD, Chestny Znak, e-waybill.</li>"
                "<li>MOQ — one pallet, mixed pallet possible.</li></ul></div>"
            )
            faq = [
                ("Do you already ship to Kazakhstan?",
                 f"Kazakhstan is a current destination ({current_en}). "
                 "Volume, city and schedule are per contract; we do not publish clients."),
                ("How many days to Almaty?",
                 "No day-count on this page. Transit is confirmed per route and consignment."),
                ("What is the price in KZT?",
                 "There is no KZT offer. Base is RUB EXW Kazan; invoice currency is agreed."),
                ("Does Kazakhstan recognise the DUM RT certificate?",
                 "Recognition is confirmed per shipment. The evidence registry has no public "
                 "unconditional recognition document."),
            ]
        extra = [{
            "@context": "https://schema.org", "@type": "Service",
            "name": h1, "serviceType": "Wholesale halal meat export",
            "areaServed": {"@type": "Country", "name": "Kazakhstan"},
            "provider": {"@id": "https://pepperoni.tatar/#organization"},
        }]
        pepp_h = "Пепперони из каталога" if lang == "ru" else "Pepperoni from the catalog"
        body = (
            f"<p>{tag}</p>" + intro + cert + how + facts
            + f"<h2>{pepp_h}</h2>" + sku_table(pepp + kazy, lang)
            + '<p><a class="cta" href="tel:+79872170202">' + PHONE + "</a></p>"
        )
        # Kazakhstan uses export/ in the path — custom shell
        url = f"{BASE}{prefix(lang)}/export/kazakhstan"
        alt = f"{BASE}{'/en' if lang == 'ru' else ''}/export/kazakhstan"
        home = f"{BASE}/" if lang == "ru" else f"{BASE}/en/"
        ld = [
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Главная" if lang == "ru" else "Home", "item": home},
                {"@type": "ListItem", "position": 2,
                 "name": "Экспорт" if lang == "ru" else "Export",
                 "item": f"{BASE}{prefix(lang)}/export"},
                {"@type": "ListItem", "position": 3, "name": "Kazakhstan" if lang == "en" else "Казахстан",
                 "item": url},
            ]},
            {"@context": "https://schema.org", "@type": "FAQPage",
             "mainEntity": json.loads(faq_ld(faq))},
            extra[0],
        ]
        html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="alternate" hreflang="ru" href="{BASE}/export/kazakhstan">
<link rel="alternate" hreflang="en" href="{BASE}/en/export/kazakhstan">
<link rel="alternate" hreflang="ru-KZ" href="{BASE}/export/kazakhstan">
<link rel="alternate" hreflang="en-KZ" href="{BASE}/en/export/kazakhstan">
<link rel="alternate" hreflang="x-default" href="{BASE}/en/export/kazakhstan">
{org_script()}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<nav><a href="{prefix(lang) or '/'}">{"Главная" if lang == "ru" else "Home"}</a> →
<a href="{prefix(lang)}/export">{"Экспорт" if lang == "ru" else "Export"}</a> →
{"Казахстан" if lang == "ru" else "Kazakhstan"}
· <a href="{"/en" if lang == "ru" else ""}/export/kazakhstan">{"EN" if lang == "ru" else "RU"}</a></nav>
<h1>🇰🇿 {h1}</h1>
{body}
<section class="faq-section"><h2>{"Частые вопросы" if lang == "ru" else "FAQ"}</h2>
{faq_html(faq)}</section>
<footer><p><a href="{prefix(lang) or '/'}">pepperoni.tatar</a></p></footer>
</div>
</body>
</html>"""
        path = slug_dir / "kazakhstan.html"
        path.write_text(ensure_metrika_html(html), encoding="utf-8")
        print(f"  export/kazakhstan [{lang}] sku={n}")


# ── item 13: /export/uzbekistan (readiness only) ───────────────────────────

def write_uzbekistan() -> None:
    """Cerberus-attested readiness. Not current shipments, not EAEU, no UZS offer."""
    n = sku_count()
    current_ru = ", ".join(FACTS["export"]["current_ru"])
    current_en = ", ".join(FACTS["export"]["current_en"])
    data = catalog()
    pepp = by_sku(data, "KD-013", "KD-014")
    kazy = [p for p in data["products"] if p.get("category") == "Премиум Казылык"]
    for lang, slug_dir in (("ru", PUBLIC / "export"), ("en", PUBLIC / "en" / "export")):
        slug_dir.mkdir(parents=True, exist_ok=True)
        if lang == "ru":
            title = "Халяль мясная продукция из России в Узбекистан | Казанские Деликатесы"
            desc = (
                "Халяль мясная продукция из России в Узбекистан: площадка RU-016/SB88273 "
                f"в реестре «Цербер» среди аттестованных направлений. Текущие отгрузки — "
                f"{current_ru}; аттестация не равна поставке. Оферты в UZS нет. EXW Казань."
            )
            h1 = "Халяль мясная продукция из России в Узбекистан"
            tag = "Готовность площадки · Цербер · не текущая отгрузка"
            intro = (
                "<p class=\"lead\">Узбекистан указан среди стран, на которые площадка "
                "№ RU-016/SB88273 аттестована в реестре «Цербер» Россельхознадзора. "
                "Это аттестация предприятия, не обещание конкретной партии "
                f"и не текущая отгрузка. Текущие поставки — {current_ru}.</p>"
            )
            cert = (
                f"<h2>Сертификация и допуск</h2><div class=\"card\">"
                f"<p>{cert_line_ru()}</p>"
                "<p>Признание сертификата в Узбекистане подтверждаем по конкретной поставке "
                "с импортёром. На странице нет заявления о взаимном признании органа страны назначения.</p>"
                "<p>Площадка в реестре «Цербер» (№ RU-016/SB88273), аттестована для экспорта в Узбекистан. "
                "Аттестация площадки — не график отгрузки.</p>"
                "<p>Узбекистан не входит в ЕАЭС: таможенное оформление — вне контура союза, "
                "детали подтверждаем по партии. Сроки в днях на странице не публикуем.</p></div>"
            )
            how = (
                "<h2>Как устроена логистика (факты, которые есть)</h2>"
                "<p>Базис по умолчанию — EXW Казань (Incoterms 2020). Перевозку организует покупатель "
                "или согласовываем отдельно. Срок в днях и «регулярные поставки в Ташкент» "
                "на этой странице не публикуем: в реестре доказательств нет подтверждённого "
                "транзитного времени и нет обещания объёма.</p>"
                "<p>Цены в сумах (UZS) на странице нет. Базовая цена — рубли EXW; валюта расчёта — "
                "по договору. Справочные валюты каталога не являются офертой в UZS.</p>"
            )
            facts = (
                f"<div class=\"card\"><ul>\n"
                f"<li>Ассортимент: {n} наименований халяль в каталоге — пепперони, сосиски, "
                "котлеты, копчёные колбасы, казылык, татарская выпечка.</li>"
                "<li>Для запроса чаще берут KD-013/014 (куриный пепперони) и сосиски — "
                "состав и цена только из карточек SKU, в рублях EXW.</li>"
                "<li>Документы к отгрузке: халяль, декларация, ВСД («Меркурий»), «Честный знак», ЭТрН.</li>"
                "<li>MOQ — одна паллета, сборная возможна.</li>"
                "<li>Образцы — индивидуально, см. <a href=\"/kak-zakazat#samples\">как заказать</a>.</li></ul></div>"
            )
            faq = [
                ("Вы уже поставляете в Узбекистан?",
                 f"Среди текущих отгрузок указаны {current_ru}. Узбекистан — в списке "
                 "аттестации «Цербер», не в списке текущих поставок. Конкретную партию "
                 "не обещаем на странице."),
                ("Сколько дней занимает доставка в Ташкент?",
                 "На странице нет числа дней. Срок подтверждаем по маршруту и партии."),
                ("Какая цена в сумах?",
                 "Оферты в UZS нет. База — рубли EXW Казань; валюту счёта согласуем."),
                ("Узбекистан в ЕАЭС?",
                 "Нет. Таможня и ветеринарные документы — по конкретной поставке, не по правилам союза."),
            ]
        else:
            title = "Halal meat from Russia to Uzbekistan | Kazan Delicacies"
            desc = (
                "Halal meat from Russia to Uzbekistan: facility RU-016/SB88273 is Cerberus-attested "
                f"for this destination. Current shipments are {current_en}; attestation is not a "
                "shipment. No UZS offer. EXW Kazan."
            )
            h1 = "Halal meat from Russia to Uzbekistan"
            tag = "Facility readiness · Cerberus · not a current shipment"
            intro = (
                "<p class=\"lead\">Uzbekistan is listed among destinations for which facility "
                "No. RU-016/SB88273 is attested in the Rosselkhoznadzor Cerberus registry. "
                "That is a facility attestation, not a promise of a consignment "
                f"and not a current shipment. Current shipments are {current_en}.</p>"
            )
            cert = (
                f"<h2>Certification and market access</h2><div class=\"card\">"
                f"<p>{cert_line_en()}</p>"
                "<p>Certificate recognition in Uzbekistan is confirmed per shipment with the importer. "
                "This page does not claim destination-authority approval.</p>"
                "<p>The facility is in the Cerberus registry (No. RU-016/SB88273) and attested for export to Uzbekistan. "
                "Attestation is not a shipping timetable.</p>"
                "<p>Uzbekistan is not an EAEU member; customs are outside the union and confirmed per consignment. "
                "No day-count is published here.</p></div>"
            )
            how = (
                "<h2>Logistics facts we can state</h2>"
                "<p>Default basis is EXW Kazan (Incoterms 2020). The buyer arranges freight, or we agree otherwise. "
                "We do not publish transit days or a regular Tashkent schedule: the evidence registry has "
                "no confirmed transit time and no volume promise.</p>"
                "<p>No som (UZS) offer on this page. Base price is RUB EXW; invoice currency is by contract. "
                "Catalog reference currencies are not a UZS offer.</p>"
            )
            facts = (
                f"<div class=\"card\"><ul>\n"
                f"<li>Range: {n} halal SKUs — pepperoni, sausages, burger patties, smoked sausages, "
                "kazylyk, Tatar pastry.</li>"
                "<li>Typical enquiry mix: KD-013/014 chicken pepperoni and sausages — "
                "composition and price only from SKU cards, RUB EXW.</li>"
                "<li>Shipping documents: halal, declaration, Mercury VSD, Chestny Znak, e-waybill.</li>"
                "<li>MOQ — one pallet, mixed pallet possible.</li>"
                "<li>Samples individually — <a href=\"/en/kak-zakazat#samples\">how to order</a>.</li></ul></div>"
            )
            faq = [
                ("Do you already ship to Uzbekistan?",
                 f"Current shipments are {current_en}. Uzbekistan is on the Cerberus attestation list, "
                 "not the current-shipment list. This page does not promise a consignment."),
                ("How many days to Tashkent?",
                 "No day-count on this page. Transit is confirmed per route and consignment."),
                ("What is the price in UZS?",
                 "There is no UZS offer. Base is RUB EXW Kazan; invoice currency is agreed."),
                ("Is Uzbekistan in the EAEU?",
                 "No. Customs and veterinary documents are confirmed per consignment, not under union rules."),
            ]
        extra = [{
            "@context": "https://schema.org", "@type": "Service",
            "name": h1, "serviceType": "Halal meat export readiness",
            "areaServed": {"@type": "Country", "name": "Uzbekistan"},
            "provider": {"@id": "https://pepperoni.tatar/#organization"},
        }]
        pepp_h = "Пепперони и казылык из каталога" if lang == "ru" else "Pepperoni and kazylyk from the catalog"
        body = (
            f"<p>{tag}</p>" + intro + cert + how + facts
            + f"<h2>{pepp_h}</h2>" + sku_table(pepp + kazy, lang)
            + '<p><a class="cta" href="tel:+79872170202">' + PHONE + "</a></p>"
        )
        url = f"{BASE}{prefix(lang)}/export/uzbekistan"
        home = f"{BASE}/" if lang == "ru" else f"{BASE}/en/"
        ld = [
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Главная" if lang == "ru" else "Home", "item": home},
                {"@type": "ListItem", "position": 2,
                 "name": "Экспорт" if lang == "ru" else "Export",
                 "item": f"{BASE}{prefix(lang)}/export"},
                {"@type": "ListItem", "position": 3, "name": "Uzbekistan" if lang == "en" else "Узбекистан",
                 "item": url},
            ]},
            {"@context": "https://schema.org", "@type": "FAQPage",
             "mainEntity": json.loads(faq_ld(faq))},
            extra[0],
        ]
        html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="alternate" hreflang="ru" href="{BASE}/export/uzbekistan">
<link rel="alternate" hreflang="en" href="{BASE}/en/export/uzbekistan">
<link rel="alternate" hreflang="ru-UZ" href="{BASE}/export/uzbekistan">
<link rel="alternate" hreflang="en-UZ" href="{BASE}/en/export/uzbekistan">
<link rel="alternate" hreflang="x-default" href="{BASE}/en/export/uzbekistan">
{org_script()}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>
{stylesheet_link()}
<style>{CSS}</style>
</head>
<body class="kd-landing">
{topbar_html(lang, "export/uzbekistan")}
<div class="container">
<nav><a href="{prefix(lang) or '/'}">{"Главная" if lang == "ru" else "Home"}</a> →
<a href="{prefix(lang)}/export">{"Экспорт" if lang == "ru" else "Export"}</a> →
{"Узбекистан" if lang == "ru" else "Uzbekistan"}
· <a href="{"/en" if lang == "ru" else ""}/export/uzbekistan">{"EN" if lang == "ru" else "RU"}</a></nav>
<h1>🇺🇿 {h1}</h1>
{body}
<section class="faq-section"><h2>{"Частые вопросы" if lang == "ru" else "FAQ"}</h2>
{faq_html(faq)}</section>
<footer><p><a href="{prefix(lang) or '/'}">pepperoni.tatar</a></p></footer>
</div>
</body>
</html>"""
        path = slug_dir / "uzbekistan.html"
        path.write_text(ensure_metrika_html(html), encoding="utf-8")
        print(f"  export/uzbekistan [{lang}] sku={n}")


# ── item 2: /halal verify block ───────────────────────────────────────────

MATRIX_START, MATRIX_END = "<!-- cert-matrix:start -->", "<!-- cert-matrix:end -->"
MATRIX_RX = re.compile(re.escape(MATRIX_START) + r".*?" + re.escape(MATRIX_END), re.S)


def matrix_html(lang: str) -> str:
    rows = sku_matrix()
    meat = next(r for r in rows if r["key"] == "halal_0008")
    meat_b = next(r for r in rows if r["key"] == "halal_614a")
    bak = next(r for r in rows if r["key"] == "halal_bakery")
    iso = next(r for r in rows if r["key"] == "iso_22000")
    mir = next(r for r in rows if r["key"] == "made_in_russia")
    n = sku_count()
    if lang == "ru":
        h = "Проверить наш халяль"
        lead = (
            f"Матрица «сертификат → раздел каталога → срок». Живой каталог — {n} SKU. "
            "ISO 22000 — контур безопасности пищевой продукции, это не халяль-сертификат."
        )
        th = ("Сертификат", "К чему относится", "SKU в каталоге", "Срок", "Проверка")
        iso_note = "не халяль"
    else:
        h = "Verify our halal"
        lead = (
            f"Certificate → catalog section → validity. Live catalog — {n} SKUs. "
            "ISO 22000 is food-safety, not a halal certificate."
        )
        th = ("Certificate", "Scope", "SKUs in catalog", "Validity", "Check")
        iso_note = "not halal"

    def row(item, scope, extra=""):
        until = item.get("valid_until") or "—"
        url = item.get("verify_url") or "/halal"
        n_sku = item.get("sku_count") or 0
        label = "проверить" if lang == "ru" else "verify"
        return (
            f"<tr><td>{item['number']}{extra}</td><td>{scope}</td>"
            f"<td>{n_sku}</td><td>{until}</td>"
            f'<td><a href="{url}" rel="noopener">{label}</a></td></tr>'
        )

    meat_scope = "Заморозка + охлаждёнка" if lang == "ru" else "Frozen + chilled"
    bak_scope = "Выпечка" if lang == "ru" else "Bakery"
    fac = "площадка (все разделы)" if lang == "ru" else "facility (all sections)"
    table = (
        "<table class=\"data-table\"><thead><tr>"
        + "".join(f"<th>{x}</th>" for x in th)
        + "</tr></thead><tbody>"
        + row(meat, meat_scope)
        + row(meat_b, meat_scope)
        + row(bak, bak_scope)
        + row(iso, fac, f" · {iso_note}")
        + row(mir, fac)
        + "</tbody></table>"
    )
    return (
        f"{MATRIX_START}\n<section id=\"proverit\" class=\"card\" style=\"margin:24px 0\">"
        f"<h2>{h}</h2><p>{lead}</p>{table}</section>\n{MATRIX_END}"
    )


def inject_halal() -> None:
    for lang, rel in (("ru", "halal.html"), ("en", "en/halal.html")):
        path = PUBLIC / rel
        html = path.read_text(encoding="utf-8")
        block = matrix_html(lang)
        if MATRIX_RX.search(html):
            html = MATRIX_RX.sub(block, html)
        else:
            html = html.replace("<h1>", block + "\n    <h1>", 1)
        path.write_text(html, encoding="utf-8")
        print(f"  halal matrix [{lang}]")


HUB_RECOG_RU = re.compile(
    r"<p class=\"lead\">.*?<h2>2\.\s*Ветеринарная аккредитация",
    re.S,
)
HUB_RECOG_EN = re.compile(
    r"<p class=\"lead\">.*?<h2>2\.\s*Veterinary accreditation",
    re.S,
)
HUB_SKU_RU = re.compile(
    r"(<strong>Продукция:</strong> )\d+( наименований халяль)"
)
HUB_SKU_EN = re.compile(
    r"(<strong>Products:</strong> )\d+( halal SKUs)"
)
HUB_CURRENT_RU = re.compile(
    r"Текущие экспортные направления — [^.<]+"
)
HUB_CURRENT_EN = re.compile(
    r"Current export directions — [^.<]+"
)


def write_export_hub() -> None:
    """Honest /export hubs: live SKU count, current shipments, no JAKIM/GSO map."""
    n = sku_count()
    current_ru = ", ".join(FACTS["export"]["current_ru"])
    current_en = ", ".join(FACTS["export"]["current_en"])
    ru_block = f"""<p class="lead">
<strong>Текущие поставки — {current_ru}.</strong>
Базис EXW Казань, минимальный заказ — одна паллета. Страны Персидского залива — на стадии подготовки: халяль-контур документов готов, разрешение Россельхознадзора на экспорт оформляется. Аттестация площадки в «Цербере» и наличие сертификата ДУМ РТ не равны отгрузке в конкретную страну.
</p>

<h2>1. Халяль-сертификат</h2>
<p>{cert_line_ru()} Проверка документов — на <a href="/halal">/halal</a>. ISO 22000 — контур безопасности пищевой продукции, это не халяль. Признание сертификата в стране назначения подтверждаем по конкретной поставке с импортёром.</p>
<h3>Текущие поставки</h3>
<div class="countries">
<span>🇰🇿 Казахстан</span>
<span>🇧🇾 Беларусь</span>
<span>🇰🇬 Кыргызстан</span>
</div>
<h3>Страны Персидского залива — подготовка</h3>
<p class="section-sub" style="margin:4px 0 10px;font-size:.92rem;color:#555">Халяль-контур документов готов, разрешение Россельхознадзора оформляется; принимаем предварительные запросы. Это не текущая отгрузка.</p>
<div class="countries">
<span>🇸🇦 Саудовская Аравия</span>
<span>🇦🇪 ОАЭ</span>
<span>🇶🇦 Катар</span>
<span>🇴🇲 Оман</span>
<span>🇰🇼 Кувейт</span>
<span>🇧🇭 Бахрейн</span>
</div>
<p class="note">Карточка компании в реестре ДУМ РТ: <a href="https://halalrt.ru/certificates/company/119/kazanskiye-delikatesy/" target="_blank" rel="noopener noreferrer" style="color:#0066cc">halalrt.ru</a>. Список стран признания органа на этой странице не публикуем.</p>

<h2>2. Ветеринарная аккредитация"""
    en_block = f"""<p class="lead">
<strong>Today we ship to {current_en}.</strong>
Prices are EXW Kazan; the minimum order is one pallet. Gulf states are at the preparation stage: the halal document pack is ready and the Rosselkhoznadzor export permit is being obtained. Cerberus facility attestation and a DUM RT certificate are not the same as a completed shipment.
</p>

<h2>1. Halal certificate</h2>
<p>{cert_line_en()} Check documents on <a href="/en/halal">/en/halal</a>. ISO 22000 is food-safety, not a halal certificate. Certificate recognition in a destination market is confirmed per shipment with the importer.</p>
<h3>Current shipments</h3>
<div class="countries">
<span>🇰🇿 Kazakhstan</span>
<span>🇧🇾 Belarus</span>
<span>🇰🇬 Kyrgyzstan</span>
</div>
<h3>Gulf states — preparation</h3>
<p class="section-sub" style="margin:4px 0 10px;font-size:.92rem;color:#555">The halal document package is ready and the Rosselkhoznadzor export permit is being obtained; preliminary enquiries are welcome. This is not a current shipment.</p>
<div class="countries">
<span>🇸🇦 Saudi Arabia</span>
<span>🇦🇪 UAE</span>
<span>🇶🇦 Qatar</span>
<span>🇴🇲 Oman</span>
<span>🇰🇼 Kuwait</span>
<span>🇧🇭 Bahrain</span>
</div>
<p class="note">Company record in the DUM RT registry: <a href="https://halalrt.ru/certificates/company/119/kazanskiye-delikatesy/" target="_blank" rel="noopener noreferrer" style="color:#0066cc">halalrt.ru</a>. This page does not publish a destination-authority recognition list.</p>

<h2>2. Veterinary accreditation"""

    ru_title = "Экспорт халяль мясной продукции из России | Казанские Деликатесы"
    ru_desc = (
        f"Экспорт халяль мясной продукции из России. Текущие поставки — {current_ru}. "
        "Площадка RU-016/SB88273 в «Цербере», в том числе аттестация на Узбекистан. "
        "EXW Казань. Признание сертификата — по поставке, не список стран органа."
    )
    en_title = "Halal meat export from Russia | Kazan Delicacies"
    en_desc = (
        f"Halal meat export from Russia. Current shipments: {current_en}. "
        "Cerberus facility RU-016/SB88273, including Uzbekistan attestation. "
        "EXW Kazan. Certificate recognition is confirmed per shipment."
    )

    ru_path = PUBLIC / "export.html"
    ru = ru_path.read_text(encoding="utf-8")
    ru2, n_ru = HUB_RECOG_RU.subn(ru_block, ru, count=1)
    ru2 = HUB_SKU_RU.sub(rf"\g<1>{n}\2", ru2)
    ru2 = HUB_CURRENT_RU.sub(f"Текущие экспортные направления — {current_ru}", ru2)
    ru2 = re.sub(r"<title>[^<]*</title>", f"<title>{ru_title}</title>", ru2, count=1)
    ru2 = re.sub(
        r'(<meta name="description" content=")[^"]*(")',
        rf"\1{ru_desc}\2", ru2, count=1)
    ru2 = re.sub(r"<h1>[^<]*</h1>", "<h1>Экспорт халяль мясной продукции из России</h1>", ru2, count=1)
    ru2 = ru2.replace('href="/export/yemen"', 'href="/export/uzbekistan"')
    ru2 = ru2.replace(">🇾🇪 Йемен</a>", ">🇺🇿 Узбекистан</a>")
    ru2 = ru2.replace("<span>🇺🇿 Узбекистан</span>",
                      '<span><a href="/export/uzbekistan" style="text-decoration:none;color:inherit">🇺🇿 Узбекистан</a></span>')
    if ru2 != ru:
        ru_path.write_text(ru2, encoding="utf-8")
    print(f"  export hub [ru] sku={n} recog={n_ru}")

    en_path = PUBLIC / "en" / "export.html"
    en = en_path.read_text(encoding="utf-8")
    en2, n_en = HUB_RECOG_EN.subn(en_block, en, count=1)
    en2 = HUB_SKU_EN.sub(rf"\g<1>{n}\2", en2)
    en2 = HUB_CURRENT_EN.sub(f"Current export directions — {current_en}", en2)
    en2 = re.sub(r"<title>[^<]*</title>", f"<title>{en_title}</title>", en2, count=1)
    en2 = re.sub(
        r'(<meta name="description" content=")[^"]*(")',
        rf"\1{en_desc}\2", en2, count=1)
    en2 = re.sub(r"<h1>[^<]*</h1>", "<h1>Halal meat export from Russia</h1>", en2, count=1)
    en2 = en2.replace('href="/en/export/yemen"', 'href="/en/export/uzbekistan"')
    en2 = en2.replace(">🇾🇪 Yemen</a>", ">🇺🇿 Uzbekistan</a>")
    en2 = en2.replace("<span>🇺🇿 Uzbekistan</span>",
                      '<span><a href="/en/export/uzbekistan" style="text-decoration:none;color:inherit">🇺🇿 Uzbekistan</a></span>')
    if en2 != en:
        en_path.write_text(en2, encoding="utf-8")
    print(f"  export hub [en] sku={n} recog={n_en}")


# ── /chak-chak-optom ──────────────────────────────────────────────────────

def write_chakchak() -> None:
    data = catalog()
    items = by_sku(data, "KD-053", "KD-054")
    p053, p054 = items
    cert = bakery_halal_line("ru")
    cert_en = bakery_halal_line("en")
    for lang in ("ru", "en"):
        life053 = catalog_shelf_life(p053, lang)
        life054 = catalog_shelf_life(p054, lang)
        store053 = catalog_units(p053.get("storage"), lang)
        store054 = catalog_units(p054.get("storage"), lang)
        moq = term("moq", lang)
        basis = term("basis", lang)
        box053 = p053.get("qtyPerBox") or "—"
        box054 = p054.get("qtyPerBox") or "—"
        landing = f"{BASE}{prefix(lang)}/chak-chak-optom"
        extra = [
            product_offer_ld(p053, lang, landing),
            product_offer_ld(p054, lang, landing),
        ]
        if lang == "ru":
            title = "Чак-чак оптом — KD-053 пластик и KD-054 крафт 300 г | Казанские Деликатесы"
            desc = (
                f"Чак-чак оптом: {p053['name']} и {p054['name']}, масса 300 г. "
                f"Цена EXW из каталога, срок {life053}, хранение {store053}. {cert}"
            )
            h1 = "Чак-чак оптом — две упаковки из каталога"
            intro = (
                "<p class=\"lead\">Две позиции из Google Sheets, не из рекламного текста: "
                f"<strong>{p053['sku']}</strong> «{p053['name']}» и "
                f"<strong>{p054['sku']}</strong> «{p054['name']}». "
                "Обе в разделе «Выпечка», категория «Национальная татарская выпечка». "
                "Это готовая сладость комнатного хранения, не замороженный пирог.</p>"
            )
            packs = (
                "<h2>Чем упаковки отличаются</h2>"
                "<p>В названии каталога зафиксированы только форматы: пластиковая упаковка "
                "и крафтовая подарочная. Масса обеих строк — 300 г. "
                f"В коробе {box053} шт (KD-053) и {box054} шт (KD-054). "
                "Состава и пищевой ценности в таблице нет — на странице их нет.</p>"
                f"<p>Срок годности из поля shelfLife каталога: {life053} (KD-053) и "
                f"{life054} (KD-054). Хранение: {store053}. "
                "Это не −18 °C и не 360 суток, как у замороженной выпечки.</p>"
            )
            docs = (
                "<h2>Халяль</h2>"
                f"<p>{cert} Проверка документов — <a href=\"/halal\">/halal</a>. "
                "ISO 22000:2018 — контур безопасности пищевой продукции, это не халяль-сертификат.</p>"
            )
            order = (
                "<h2>Как заказать</h2>"
                f"<p>Базис {basis}, минимум {moq}. "
                "Прайс и заявка: <a href=\"/kak-zakazat\">/kak-zakazat</a> и "
                "<a href=\"/price\">/price</a>. "
                "Срок перевозки в днях не публикуем.</p>"
            )
            related = (
                "<p>Смежные страницы: "
                "<a href=\"/vyipechka-halyal\">выпечка халяль</a> · "
                "<a href=\"/halyal-vypechka-optom-dlya-pekaren\">выпечка для пекарен и кофеен</a> · "
                "<a href=\"/zamorozhennaya-vypechka-dlya-kofeen\">заморозка для кофеен</a>.</p>"
            )
            faq = [
                ("Какие SKU на этой странице?",
                 f"Только {p053['sku']} ({p053['name']}) и {p054['sku']} ({p054['name']}). "
                 "Обе по 300 г. Других фасовок чак-чака в текущем каталоге нет."),
                ("Какой срок и температура?",
                 f"{life053}, хранение {store053}. Цифры из products.json "
                 "(поле shelfLife и поле storage), не из рекламного текста."),
                ("Какой сертификат халяль?",
                 f"{cert} Страница проверки — /halal."),
                ("Как заказать оптом?",
                 f"Укажите SKU и объём. {PHONE}, {EMAIL}. Минимум {moq}, базис {basis}. "
                 "Форма и шаги — /kak-zakazat, прайс — /price."),
            ]
        else:
            title = "Chak-chak wholesale — KD-053 plastic and KD-054 kraft 300 g"
            desc = (
                f"Chak-chak wholesale: {product_name(p053, 'en')} and {product_name(p054, 'en')}, "
                f"300 g. EXW price from the catalog, shelf life {life053}, storage {store053}. {cert_en}"
            )
            h1 = "Chak-chak wholesale — two catalog packs"
            intro = (
                "<p class=\"lead\">Two rows from Google Sheets, not from ad copy: "
                f"<strong>{p053['sku']}</strong> «{product_name(p053, 'en')}» and "
                f"<strong>{p054['sku']}</strong> «{product_name(p054, 'en')}». "
                "Both sit in the Bakery section, Tatar national pastry category. "
                "This is a ready sweet stored at ambient temperature, not a frozen pie.</p>"
            )
            packs = (
                "<h2>What differs between the packs</h2>"
                "<p>The catalog names record only the formats: plastic pack and kraft gift box. "
                "Both rows weigh 300 g. "
                f"Box count: {box053} pcs (KD-053) and {box054} pcs (KD-054). "
                "Composition and nutrition cells are empty — this page does not invent them.</p>"
                f"<p>Shelf life from the catalog shelfLife field: {life053} (KD-053) and "
                f"{life054} (KD-054). Storage: {store053}. "
                "That is not −18 °C and not 360 days, unlike frozen pastry.</p>"
            )
            docs = (
                "<h2>Halal</h2>"
                f"<p>{cert_en} Check documents on <a href=\"/en/halal\">/en/halal</a>. "
                "ISO 22000:2018 is food-safety, not a halal certificate.</p>"
            )
            order = (
                "<h2>How to order</h2>"
                f"<p>Basis {basis}, minimum {moq}. "
                "Price list and enquiry: <a href=\"/en/kak-zakazat\">/en/kak-zakazat</a> and "
                "<a href=\"/en/price\">/en/price</a>. "
                "We do not publish transit days.</p>"
            )
            related = (
                "<p>Related: "
                "<a href=\"/en/vyipechka-halyal\">halal bakery</a> · "
                "<a href=\"/en/halyal-vypechka-optom-dlya-pekaren\">bakery for bakeries and coffee shops</a> · "
                "<a href=\"/en/zamorozhennaya-vypechka-dlya-kofeen\">frozen bakery for coffee shops</a>.</p>"
            )
            faq = [
                ("Which SKUs are on this page?",
                 f"Only {p053['sku']} ({product_name(p053, 'en')}) and "
                 f"{p054['sku']} ({product_name(p054, 'en')}). Both 300 g. "
                 "The live catalog has no other chak-chak pack sizes."),
                ("What shelf life and storage?",
                 f"{life053}, storage {store053}. Figures come from products.json "
                 "(shelfLife and storage fields)."),
                ("Which halal certificate?",
                 f"{cert_en} Verification page: /en/halal."),
                ("How to order wholesale?",
                 f"Name the SKU and volume. {PHONE}, {EMAIL}. Minimum {moq}, {basis}. "
                 "Steps: /en/kak-zakazat, price list: /en/price."),
            ]
        body = (
            intro + packs
            + f"<h2>{'Ассортимент' if lang == 'ru' else 'Assortment'}</h2>"
            + sku_table(items, lang) + cards(items, lang)
            + f"<h2>{'Фото из каталога' if lang == 'ru' else 'Catalog photos'}</h2>"
            + photos(items, lang) + docs + order + related
        )
        html = ensure_metrika_html(
            shell(lang, "chak-chak-optom", title, desc, h1, body, faq, extra)
        )
        write_html(lang, "chak-chak-optom", html)
        print(f"  chak-chak-optom [{lang}] {p053['sku']}/{p054['sku']}")


# ── /halyal-vypechka-optom-dlya-pekaren ───────────────────────────────────

def write_bakery_for_bakeries() -> None:
    data = catalog()
    frozen = frozen_bakery_skus(data)
    sausage = by_sku(data, "KD-018", "KD-061")
    p018, p061 = sausage
    meat_cert_ru = (
        "Халяль ДУМ РТ №"
        f"{FACTS['certificates']['halal_0008']['number']} и №"
        f"{FACTS['certificates']['halal_614a']['number']}"
    )
    meat_cert_en = (
        "Halal DUM RT No. "
        f"{FACTS['certificates']['halal_0008']['number']} and No. "
        f"{FACTS['certificates']['halal_614a']['number']}"
    )
    cert_ru = bakery_halal_line("ru")
    cert_en = bakery_halal_line("en")
    frozen_without_061 = [p for p in frozen if p["sku"] != "KD-061"]
    listed = sausage + frozen_without_061
    n_frozen = len(frozen)
    n_distinct = len(listed)
    for lang in ("ru", "en"):
        moq = term("moq", lang)
        basis = term("basis", lang)
        if lang == "ru":
            title = "Халяль выпечка оптом для пекарен и кофеен | Казанские Деликатесы"
            desc = (
                f"{n_distinct} {plural_ru(n_distinct, 'позиция', 'позиции', 'позиций')} без повторов: "
                f"замороженная выпечка ({n_frozen} SKU, включая KD-061) и охлаждённая сосиска KD-018. "
                f"Заказ — /kak-zakazat и /price. {cert_ru}"
            )
            h1 = "Халяль-выпечка оптом для пекарен и кофеен"
            intro = (
                "<p class=\"lead\">Статья для закупщика пекарни или кофейни: какие строки "
                "заморозки и сосиски в тесте есть в текущем каталоге, какой сертификат "
                "закрывает выпечку, и куда отправлять заявку. "
                "Температуру и минуты печи не публикуем — в реестре доказательств нет "
                "воспроизводимого теста.</p>"
            )
            who = (
                "<h2>Для кого эта страница</h2><ul>"
                "<li>Пекарня, которой нужна заморозка на выкладку и сосиска под своё тесто "
                "или готовая сосиска в тесте — детали KD-018/KD-061 на "
                "<a href=\"/sosiska-v-teste\">/sosiska-v-teste</a>.</li>"
                "<li>Кофейня или точка с печью: сценарий «из морозилки на витрину» остаётся на "
                "<a href=\"/zamorozhennaya-vypechka-dlya-kofeen\">/zamorozhennaya-vypechka-dlya-kofeen</a>.</li>"
                "<li>Татарская линейка целиком — хаб "
                "<a href=\"/vyipechka-halyal\">/vyipechka-halyal</a>. "
                "Чак-чак (не заморозка) — <a href=\"/chak-chak-optom\">/chak-chak-optom</a>.</li></ul>"
            )
            sausage_block = (
                "<h2>Сосиска в тесте</h2>"
                f"<p><strong>KD-018</strong> — {p018['name']}: масса упаковки "
                f"{weight_label(p018)}, хранение {p018.get('storage')}, срок "
                f"{p018.get('shelfLife')}. Это охлаждённая мясная позиция под тесто пекарни, "
                f"не выпечка. Халяль мяса: {meat_cert_ru}.</p>"
                f"<p><strong>KD-061</strong> — {p061['name']}: масса {weight_label(p061)}, "
                f"короб {p061.get('qtyPerBox') or '—'} шт, хранение {p061.get('storage')}, "
                f"срок {p061.get('shelfLife')}. Раздел каталога — классическая выпечка. "
                f"{cert_ru}</p>"
            )
            docs = (
                "<h2>Сертификат на выпечку</h2>"
                f"<p>{cert_ru} Проверка — <a href=\"/halal\">/halal</a>. "
                f"Для KD-018 действует мясной контур ({meat_cert_ru}), не сертификат выпечки.</p>"
            )
            order = (
                "<h2>Как заказать</h2>"
                f"<p>Шаги заявки — <a href=\"/kak-zakazat\">/kak-zakazat</a>. "
                f"Прайс из того же каталога — <a href=\"/price\">/price</a>. "
                f"Базис {basis}, минимум {moq}. "
                "Образцы и пробная паллета — "
                "<a href=\"/kak-zakazat#samples\">/kak-zakazat#samples</a>. "
                "Срок доставки в днях и режим вашей печи на странице не фиксируем.</p>"
            )
            related = (
                "<p>Каналы: <a href=\"/dlya-pekaren\">/dlya-pekaren</a> · "
                "<a href=\"/dlya-horeca\">/dlya-horeca</a> · "
                "<a href=\"/dlya-azs\">/dlya-azs</a>.</p>"
            )
            faq = [
                ("Какие SKU входят в статью?",
                 f"{n_distinct} {plural_ru(n_distinct, 'позиция', 'позиции', 'позиций')} без повторов: "
                 f"охлаждённая KD-018 и {n_frozen} строк "
                 "замороженной выпечки (KD-061 входит в заморозку, не считается дважды). "
                 "Чак-чак KD-053/054 — на /chak-chak-optom, это не заморозка."),
                ("Какой сертификат на выпечку?",
                 f"{cert_ru} Проверка — /halal. KD-018 закрывается мясными свидетельствами."),
                ("Где сосиска в тесте отдельно?",
                 "На /sosiska-v-teste: только KD-018 и KD-061, без выдуманного теста в печи."),
                ("Как оформить заказ?",
                 f"/kak-zakazat и /price. Минимум {moq}, базис {basis}. {PHONE}, {EMAIL}."),
            ]
        else:
            title = "Halal bakery wholesale for bakeries and coffee shops | Kazan Delicacies"
            desc = (
                f"{n_distinct} distinct SKUs: frozen bakery ({n_frozen} rows, including KD-061) "
                f"and chilled sausage KD-018. Order via /en/kak-zakazat and /en/price. {cert_en}"
            )
            h1 = "Halal bakery wholesale for bakeries and coffee shops"
            intro = (
                "<p class=\"lead\">A buyer article for a bakery or coffee shop: which frozen "
                "rows and sausage-in-dough SKUs are in the live catalog, which certificate "
                "covers bakery, and where to send the enquiry. "
                "Oven temperature and minutes are not published — the evidence registry has "
                "no reproducible bake test.</p>"
            )
            who = (
                "<h2>Who this page is for</h2><ul>"
                "<li>A bakery that needs freezer stock and either a casing-free sausage for "
                "its own dough or a ready sausage roll — KD-018/KD-061 details on "
                "<a href=\"/en/sosiska-v-teste\">/en/sosiska-v-teste</a>.</li>"
                "<li>A coffee shop with an oven: the freezer-to-counter scenario stays on "
                "<a href=\"/en/zamorozhennaya-vypechka-dlya-kofeen\">/en/zamorozhennaya-vypechka-dlya-kofeen</a>.</li>"
                "<li>The full Tatar line is the hub "
                "<a href=\"/en/vyipechka-halyal\">/en/vyipechka-halyal</a>. "
                "Chak-chak (not frozen) is "
                "<a href=\"/en/chak-chak-optom\">/en/chak-chak-optom</a>.</li></ul>"
            )
            sausage_block = (
                "<h2>Sausage in dough</h2>"
                f"<p><strong>KD-018</strong> — {product_name(p018, 'en')}: pack "
                f"{weight_label(p018, lang)}, storage {catalog_units(p018.get('storage'), lang)}, "
                f"shelf life {catalog_units(p018.get('shelfLife'), lang)}. "
                f"This is a chilled meat SKU for the bakery's dough, not pastry. "
                f"Meat halal: {meat_cert_en}.</p>"
                f"<p><strong>KD-061</strong> — {product_name(p061, 'en')}: "
                f"{weight_label(p061, lang)}, {p061.get('qtyPerBox') or '—'} pcs/box, "
                f"{catalog_units(p061.get('storage'), lang)}, "
                f"{catalog_units(p061.get('shelfLife'), lang)}. "
                f"Catalog section: classic bakery. {cert_en}</p>"
            )
            docs = (
                "<h2>Bakery certificate</h2>"
                f"<p>{cert_en} Verify on <a href=\"/en/halal\">/en/halal</a>. "
                f"KD-018 uses the meat certificates ({meat_cert_en}), not the bakery certificate.</p>"
            )
            order = (
                "<h2>How to order</h2>"
                f"<p>Enquiry steps: <a href=\"/en/kak-zakazat\">/en/kak-zakazat</a>. "
                f"Price list from the same catalog: <a href=\"/en/price\">/en/price</a>. "
                f"Basis {basis}, minimum {moq}. "
                "Samples and a pilot pallet: "
                "<a href=\"/en/kak-zakazat#samples\">/en/kak-zakazat#samples</a>. "
                "This page does not publish transit days or your oven programme.</p>"
            )
            related = (
                "<p>Channels: <a href=\"/en/dlya-pekaren\">/en/dlya-pekaren</a> · "
                "<a href=\"/en/dlya-horeca\">/en/dlya-horeca</a> · "
                "<a href=\"/en/dlya-azs\">/en/dlya-azs</a>.</p>"
            )
            faq = [
                ("Which SKUs are in this article?",
                 f"{n_distinct} distinct SKUs: chilled KD-018 and {n_frozen} frozen bakery "
                 "rows (KD-061 is in the frozen list, not counted twice). "
                 "Chak-chak KD-053/054 is on /en/chak-chak-optom — it is not frozen."),
                ("Which certificate covers bakery?",
                 f"{cert_en} Verify on /en/halal. KD-018 is covered by the meat certificates."),
                ("Where is sausage in dough on its own?",
                 "On /en/sosiska-v-teste: only KD-018 and KD-061, with no invented oven test."),
                ("How do we order?",
                 f"/en/kak-zakazat and /en/price. Minimum {moq}, {basis}. {PHONE}, {EMAIL}."),
            ]
        extra = [
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": h1,
                "description": desc,
                "mainEntityOfPage": f"{BASE}{prefix(lang)}/halyal-vypechka-optom-dlya-pekaren",
                "author": {"@id": f"{BASE}/#organization"},
                "publisher": {"@id": f"{BASE}/#organization"},
            },
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": h1,
                "numberOfItems": n_distinct,
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1,
                     "url": f"{BASE}{product_url(p['sku'], lang)}",
                     "name": product_name(p, lang)}
                    for i, p in enumerate(listed)
                ],
            },
        ]
        if lang == "ru":
            h_frozen = (
                f"Замороженная выпечка из каталога ({n_frozen} SKU; "
                "KD-061 разобрана в блоке «Сосиска в тесте»)"
            )
        else:
            h_frozen = (
                f"Frozen bakery from the catalog ({n_frozen} SKUs; "
                "KD-061 is covered in the sausage-in-dough block)"
            )
        body = (
            intro + who + sausage_block
            + sku_table(sausage, lang)
            + f"<h2>{h_frozen}</h2>"
            + sku_list(frozen_without_061, lang)
            + docs + order + related
        )
        html = ensure_metrika_html(
            shell(lang, "halyal-vypechka-optom-dlya-pekaren", title, desc, h1, body, faq, extra)
        )
        write_html(lang, "halyal-vypechka-optom-dlya-pekaren", html)
        print(f"  bakery-for-bakeries [{lang}] frozen={n_frozen} distinct={n_distinct}")


def write_chakchak_blogs() -> None:
    """Noindex notes that exist so the old URLs can link to the landing."""
    data = catalog()
    items = by_sku(data, "KD-053", "KD-054")
    p053, p054 = items
    for lang, slug, kind in (
        ("ru", "blog/chakchak-optom", "optom"),
        ("ru", "blog/chakchak-wholesale-gifts", "gifts"),
        ("en", "en/blog/chakchak-optom", "optom"),
        ("en", "en/blog/chakchak-wholesale-gifts", "gifts"),
    ):
        landing = "/chak-chak-optom" if lang == "ru" else "/en/chak-chak-optom"
        if lang == "ru" and kind == "optom":
            title = "Чак-чак оптом — две SKU из каталога | Казанские Деликатесы"
            desc = (
                f"Краткая заметка: {p053['name']} и {p054['name']}. "
                f"Цены и срок — на {landing}."
            )
            h1 = "Чак-чак оптом: пластик и крафт"
            body = (
                f"<p class=\"lead\">Отдельная оптовая страница — "
                f"<a href=\"{landing}\">{landing}</a>. "
                "Здесь только указатель, чтобы старый адрес не оставлял закупщика без ссылки.</p>"
                f"<p>В каталоге две строки: <a href=\"/products/kd-053\">{p053['sku']}</a> "
                f"«{p053['name']}» ({price_label(p053, 'ru')}, {catalog_shelf_life(p053, 'ru')}, "
                f"{p053.get('storage')}) и <a href=\"/products/kd-054\">{p054['sku']}</a> "
                f"«{p054['name']}» ({price_label(p054, 'ru')}, {catalog_shelf_life(p054, 'ru')}, "
                f"{p054.get('storage')}). Масса обеих — 300 г.</p>"
                f"<p>{bakery_halal_line('ru')} Проверка — <a href=\"/halal\">/halal</a>.</p>"
                f"<p><a class=\"cta\" href=\"{landing}\">Открыть /chak-chak-optom</a></p>"
            )
            faq = [
                ("Где полный разбор?",
                 f"На {landing}: таблица, фото, Product/Offer и заявка."),
                ("Это та же страница, что /blog/chak-chak?",
                 "Нет. /blog/chak-chak — черновая заметка. Канон закупки — /chak-chak-optom."),
            ]
        elif lang == "ru":
            title = "Чак-чак в подарочной упаковке оптом | Казанские Деликатесы"
            desc = (
                f"Подарочный чак-чак {p054['name']} и пластик {p053['name']}. "
                f"Опт и цены — {landing}."
            )
            h1 = "Чак-чак в подарочной упаковке"
            body = (
                f"<p class=\"lead\">Крафтовая подарочная упаковка — {p054['sku']}. "
                f"Полный опт обеих фасовок — <a href=\"{landing}\">{landing}</a>.</p>"
                f"<p>{p054['name']}: {weight_label(p054)}, {price_label(p054, 'ru')}, "
                f"{catalog_shelf_life(p054, 'ru')}, {p054.get('storage')}. "
                f"Рядом в каталоге пластик {p053['sku']} за {price_label(p053, 'ru')}.</p>"
                f"<p>{bakery_halal_line('ru')} Проверка — <a href=\"/halal\">/halal</a>.</p>"
                f"<p><a class=\"cta\" href=\"{landing}\">К оптовой странице чак-чака</a></p>"
            )
            faq = [
                ("Какой SKU подарочный?",
                 f"{p054['sku']} — крафтовая подарочная упаковка 300 г. Пластик — {p053['sku']}."),
                ("Где заказать оптом?",
                 f"{landing}, /kak-zakazat и /price."),
            ]
        elif kind == "optom":
            title = "Chak-chak wholesale — two catalog SKUs | Kazan Delicacies"
            desc = (
                f"Short note: {product_name(p053, 'en')} and {product_name(p054, 'en')}. "
                f"Prices and shelf life live on {landing}."
            )
            h1 = "Chak-chak wholesale: plastic and kraft"
            body = (
                f"<p class=\"lead\">The wholesale page is "
                f"<a href=\"{landing}\">{landing}</a>. "
                "This note exists so the old URL still points to the live assortment.</p>"
                f"<p>Catalog rows: <a href=\"/en/products/kd-053\">{p053['sku']}</a> "
                f"«{product_name(p053, 'en')}» ({price_label(p053, 'en')}, "
                f"{catalog_shelf_life(p053, 'en')}, {catalog_units(p053.get('storage'), 'en')}) and "
                f"<a href=\"/en/products/kd-054\">{p054['sku']}</a> "
                f"«{product_name(p054, 'en')}» ({price_label(p054, 'en')}, "
                f"{catalog_shelf_life(p054, 'en')}, {catalog_units(p054.get('storage'), 'en')}). "
                "Both weigh 300 g.</p>"
                f"<p>{bakery_halal_line('en')} Verify on <a href=\"/en/halal\">/en/halal</a>.</p>"
                f"<p><a class=\"cta\" href=\"{landing}\">Open /en/chak-chak-optom</a></p>"
            )
            faq = [
                ("Where is the full page?",
                 f"On {landing}: table, photos, Product/Offer and the enquiry path."),
                ("Is this the same as /en/blog/chakchak-wholesale-gifts?",
                 "That note highlights the kraft gift pack. The buying URL is /en/chak-chak-optom."),
            ]
        else:
            title = "Chak-chak in a gift box, wholesale | Kazan Delicacies"
            desc = (
                f"Gift-pack chak-chak {product_name(p054, 'en')} and plastic "
                f"{product_name(p053, 'en')}. Wholesale lives on {landing}."
            )
            h1 = "Chak-chak in a gift box"
            body = (
                f"<p class=\"lead\">The kraft gift pack is {p054['sku']}. "
                f"Both pack formats: <a href=\"{landing}\">{landing}</a>.</p>"
                f"<p>{product_name(p054, 'en')}: {weight_label(p054, 'en')}, "
                f"{price_label(p054, 'en')}, {catalog_shelf_life(p054, 'en')}, "
                f"{catalog_units(p054.get('storage'), 'en')}. "
                f"Plastic {p053['sku']} is {price_label(p053, 'en')}.</p>"
                f"<p>{bakery_halal_line('en')} Verify on <a href=\"/en/halal\">/en/halal</a>.</p>"
                f"<p><a class=\"cta\" href=\"{landing}\">Go to the chak-chak wholesale page</a></p>"
            )
            faq = [
                ("Which SKU is the gift pack?",
                 f"{p054['sku']} — kraft gift box, 300 g. Plastic is {p053['sku']}."),
                ("How to order wholesale?",
                 f"{landing}, /en/kak-zakazat and /en/price."),
            ]
        # shell() prefixes /en for lang=en; blog lives at /blog/... or /en/blog/...
        if lang == "en":
            html = ensure_metrika_html(shell(
                lang, f"blog/{slug.split('/')[-1]}", title, desc, h1, body, faq,
                robots="noindex, follow",
            ))
            dest = PUBLIC / "en" / "blog" / f"{slug.split('/')[-1]}.html"
        else:
            html = ensure_metrika_html(shell(
                lang, slug, title, desc, h1, body, faq,
                robots="noindex, follow",
            ))
            dest = PUBLIC / f"{slug}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        print(f"  chakchak-blog [{slug}]")


PEKAREN_MARK = "<!-- content-plan-pekaren:start -->"
PEKAREN_MARK_END = "<!-- content-plan-pekaren:end -->"
CHAK_BLOG_MARK = "<!-- content-plan-chakchak-cta:start -->"
CHAK_BLOG_MARK_END = "<!-- content-plan-chakchak-cta:end -->"


def patch_pekaren_and_chak_blog() -> None:
    for lang, rel in (("ru", "dlya-pekaren.html"), ("en", "en/dlya-pekaren.html")):
        path = PUBLIC / rel
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        if lang == "ru":
            block = (
                f"{PEKAREN_MARK}<p>Замороженная выпечка и сосиска в тесте для пекарен и кофеен — "
                "<a href=\"/halyal-vypechka-optom-dlya-pekaren\">/halyal-vypechka-optom-dlya-pekaren</a>. "
                "Чак-чак оптом — <a href=\"/chak-chak-optom\">/chak-chak-optom</a>. "
                "Халяль выпечки — <a href=\"/halal\">/halal</a>.</p>"
                f"{PEKAREN_MARK_END}"
            )
            needle = '<h2>Какие позиции берут пекарни</h2>'
        else:
            block = (
                f"{PEKAREN_MARK}<p>Frozen bakery and sausage in dough for bakeries and coffee shops — "
                "<a href=\"/en/halyal-vypechka-optom-dlya-pekaren\">/en/halyal-vypechka-optom-dlya-pekaren</a>. "
                "Chak-chak wholesale — <a href=\"/en/chak-chak-optom\">/en/chak-chak-optom</a>. "
                "Bakery halal — <a href=\"/en/halal\">/en/halal</a>.</p>"
                f"{PEKAREN_MARK_END}"
            )
            needle = "<h2>SKUs that work for bakery chains</h2>"
        html = re.sub(
            re.escape(PEKAREN_MARK) + r".*?" + re.escape(PEKAREN_MARK_END),
            block, html, count=1, flags=re.S,
        )
        if PEKAREN_MARK not in html:
            html = html.replace(needle, block + "\n    " + needle, 1)
        path.write_text(html, encoding="utf-8")
        print(f"  dlya-pekaren link [{lang}]")

    blog = PUBLIC / "blog" / "chak-chak.html"
    if blog.exists():
        html = blog.read_text(encoding="utf-8")
        block = (
            f"{CHAK_BLOG_MARK}<p class=\"lead\">Оптовая страница с актуальными ценами из каталога — "
            "<a href=\"/chak-chak-optom\">/chak-chak-optom</a>. "
            "Эта заметка остаётся черновиком вне индекса.</p>"
            f"{CHAK_BLOG_MARK_END}"
        )
        html = re.sub(
            re.escape(CHAK_BLOG_MARK) + r".*?" + re.escape(CHAK_BLOG_MARK_END),
            block, html, count=1, flags=re.S,
        )
        if CHAK_BLOG_MARK not in html:
            html = html.replace("<h1>", block + "\n<h1>", 1)
        blog.write_text(html, encoding="utf-8")
        print("  blog/chak-chak CTA")


def main() -> int:
    write_sosiska()
    write_bakery()
    write_pizzeria()
    write_kazakhstan()
    write_uzbekistan()
    write_export_hub()
    inject_halal()
    write_chakchak()
    write_bakery_for_bakeries()
    write_chakchak_blogs()
    patch_pekaren_and_chak_blog()
    from content_plan_audience import write_batch4
    write_batch4()
    print("content_plan_pages: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
