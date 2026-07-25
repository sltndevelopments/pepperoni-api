#!/usr/bin/env python3
"""Remove invented pepperoni SKUs that are not in Google Sheets / products.json.

Catalog truth (as of 2026-07): only cooked-smoked pepperoni exists:
  KD-012 Пепперони варено-копченый из конины (0,5 кг)
  KD-013 Пепперони варено-копченый куриный (0,5 кг)
  KD-014 Пепперони варено-копченый куриный целый батон (1 кг)

There is NO dry-cured («сырокопчёный») pepperoni and NO «классика говядина+курица»
pepperoni SKU. Those claims were hardcoded in commercial generators, FAQ, OEM,
wholesale snapshots and stale product overrides.

This script:
  1) Regenerates wholesale-price-list*.{txt,md} from products.json
  2) Patches commercial / FAQ / OEM / pizzeria HTML claims
  3) Replaces product-card boilerplate «сырокопчёная/варёно-копчёная» → варёно-копчёная
  4) Quarantines toxic overrides bound to wrong SKUs (kd-017*)

Run after editing generators; then: python3 scripts/gen-llms-full.py
"""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS = PUBLIC / "products.json"

TRUE_FAQ_RU = (
    "Халяль пепперони от «Казанских Деликатесов» — варёно-копчёный: "
    "куриный (KD-013 нарезка 0,5 кг, KD-014 целый батон 1 кг) и из конины "
    "(KD-012 нарезка 0,5 кг). Свинины нет. Сертификат Halal № 614A/2024 (ДУМ РТ). "
    "Актуальные цены и SKU — в каталоге https://pepperoni.tatar/pepperoni "
    "и в API https://api.pepperoni.tatar/api/products."
)
TRUE_FAQ_RU_SHORT = (
    "Варёно-копчёный куриный (KD-013 нарезка, KD-014 батон) и из конины (KD-012). "
    "Свинины нет. Halal № 614A/2024. Актуальный ассортимент — в каталоге и API."
)
TRUE_FAQ_EN = (
    "Halal pepperoni from Kazan Delicacies is cooked-smoked only: chicken "
    "(KD-013 sliced 0.5 kg, KD-014 whole stick 1 kg) and horse meat "
    "(KD-012 sliced 0.5 kg). No pork. Halal certificate #614A/2024 (DUM RT). "
    "Live SKUs and prices: https://pepperoni.tatar/en/pepperoni and "
    "https://api.pepperoni.tatar/api/products."
)
TRUE_FAQ_EN_SHORT = (
    "Cooked-smoked chicken (KD-013 sliced, KD-014 stick) and horse meat (KD-012). "
    "No pork. Halal #614A/2024. Live catalog via /en/pepperoni and the products API."
)

OEM_FAQ_RU = (
    "Классическое пепперони из свинины халяльным не является. Пепперони "
    "«Казанских Деликатесов» — 100% халяль: варёно-копчёный куриный "
    "(KD-013/KD-014) и из конины (KD-012) по стандарту «Халяль» ДУМ РТ "
    "(№ 614A/2024). Нарезка и целый батон. Актуальный ассортимент — в каталоге."
)
OEM_FAQ_EN = (
    "Classic pork pepperoni is not halal. Kazan Delicacies pepperoni is 100% "
    "halal cooked-smoked chicken (KD-013/KD-014) and horse meat (KD-012) under "
    "DUM RT Halal #614A/2024. Sliced or whole stick. Live catalog only."
)

# Price-grid HTML used on commercial pages (RUB from live catalog).
LIVE_ASSORTMENT_RU = """    <div class="prices-grid">
      <div class="price-card"><div class="name">Вар-коп куриный KD-013</div><div class="weight">Нарезка 0,5 кг</div><div class="price">274 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп куриный KD-014</div><div class="weight">Батон 1 кг</div><div class="price">457 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп из конины KD-012</div><div class="weight">Нарезка 0,5 кг</div><div class="price">315 ₽</div></div>
    </div>"""

PIZZERIA_ASSORTMENT = """    <div class="prices-grid">
      <div class="price-card">
        <div class="name">Вар-коп куриный KD-013</div>
        <div class="weight">0.5 кг, нарезка</div>
        <div class="price">274 ₽</div>
      </div>
      <div class="price-card">
        <div class="name">Вар-коп куриный KD-014</div>
        <div class="weight">1 кг, целый батон</div>
        <div class="price">457 ₽</div>
      </div>
      <div class="price-card">
        <div class="name">Вар-коп из конины KD-012</div>
        <div class="weight">0.5 кг, нарезка</div>
        <div class="price">315 ₽</div>
      </div>
    </div>"""


def load_products() -> list[dict]:
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    return data.get("products") or []


def regenerate_wholesale(products: list[dict]) -> None:
    """Rewrite wholesale snapshots from live products.json (class fix)."""
    today = date.today().strftime("%d.%m.%Y")
    by_section: dict[str, list] = defaultdict(list)
    for p in products:
        by_section[p.get("section") or "Прочее"].append(p)

    def usd(p):
        ep = (p.get("offers") or {}).get("exportPrices") or {}
        v = ep.get("USD")
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def table_ru(items):
        lines = [
            "| SKU | Наименование | Вес | Мин. заказ | Цена (USD) | Срок годности | Хранение |",
            "|-----|-------------|------|------------|------------|---------------|----------|",
        ]
        for p in sorted(items, key=lambda x: x.get("sku") or ""):
            u = usd(p)
            price = f"${u:g}" if u is not None else "—"
            lines.append(
                f"| {p.get('sku','')} | {p.get('name','')} | {p.get('weight') or '—'} | "
                f"— | {price} | {p.get('shelfLife') or '—'} | {p.get('storage') or '—'} |"
            )
        return "\n".join(lines)

    def table_en(items):
        lines = [
            "| SKU | Name | Weight | MOQ | Price (USD) | Shelf life | Storage |",
            "|-----|------|--------|-----|-------------|------------|---------|",
        ]
        for p in sorted(items, key=lambda x: x.get("sku") or ""):
            u = usd(p)
            price = f"${u:g}" if u is not None else "—"
            name = p.get("nameEn") or p.get("name") or ""
            lines.append(
                f"| {p.get('sku','')} | {name} | {p.get('weight') or '—'} | "
                f"— | {price} | {p.get('shelfLife') or '—'} | {p.get('storage') or '—'} |"
            )
        return "\n".join(lines)

    n = len(products)
    sections = list(by_section.keys())

    ru_parts = [
        "# Казанские Деликатесы — Оптовый каталог халяль продукции",
        "",
        f"> **{n} халяль-сертифицированных SKU** | Производитель, Казань, Татарстан, Россия",
        "> Инкотермс: **EXW Казань** | Халяль №614A/2024 (ДУМ РТ) | ХАССП | ISO 22000:2018",
        f"> Цены в **USD** (из exportPrices.products.json) | Обновлено: {today}",
        "> Контакт: info@kazandelikates.tatar | +7 987 217-02-02",
        "> Источник правды: Google Sheets → https://api.pepperoni.tatar/api/products",
        "",
        "---",
        "",
        "## Содержание",
    ]
    for sec in sections:
        ru_parts.append(f"- [{sec}](#{sec.lower().replace(' ', '-')}) — {len(by_section[sec])} SKU")
    ru_parts.append("")
    for sec in sections:
        ru_parts += ["---", "", f"## {sec}", "", table_ru(by_section[sec]), ""]

    en_parts = [
        "# Kazan Delicacies — Wholesale Halal Catalog",
        "",
        f"> **{n} Halal-certified SKUs** | Manufacturer, Kazan, Tatarstan, Russia",
        "> Incoterms: **EXW Kazan** | Halal #614A/2024 (DUM RT) | HACCP | ISO 22000:2018",
        f"> Prices in **USD** (from exportPrices) | Updated: {today}",
        "> Contact: info@kazandelikates.tatar | +7 987 217-02-02",
        "> Source of truth: Google Sheets → https://api.pepperoni.tatar/api/products",
        "",
        "---",
        "",
    ]
    for sec in sections:
        en_parts += ["", f"## {sec}", "", table_en(by_section[sec]), ""]

    for path, body in (
        (PUBLIC / "wholesale-price-list-ru.txt", "\n".join(ru_parts) + "\n"),
        (PUBLIC / "wholesale-price-list-ru.md", "\n".join(ru_parts) + "\n"),
        (PUBLIC / "wholesale-price-list.txt", "\n".join(en_parts) + "\n"),
        (PUBLIC / "wholesale-price-list.md", "\n".join(en_parts) + "\n"),
    ):
        path.write_text(body, encoding="utf-8")
        print(f"✅ wholesale regenerated: {path.name}")


def replace_price_grids(html: str) -> str:
    """Replace any prices-grid that still lists Сырокопчёный / Вар-коп классика."""
    if "Сырокопчёный" not in html and "Вар-коп классика" not in html and "Dry-Cured" not in html:
        return html

    # RU multi-line pizzeria-style cards
    html = re.sub(
        r'<div class="prices-grid">\s*'
        r'(?:<div class="price-card">[\s\S]*?</div>\s*){2,8}'
        r'</div>',
        lambda m: PIZZERIA_ASSORTMENT
        if "Сырокопчёный" in m.group(0) or "Вар-коп классика" in m.group(0)
        else m.group(0),
        html,
        count=8,
    )
    # Compact one-line cards (commercial generator style)
    html = re.sub(
        r'<div class="prices-grid">\s*'
        r'(?:<div class="price-card"><div class="name">[^<]+</div><div class="weight">[^<]*</div><div class="price">[^<]*</div></div>\s*){2,8}'
        r'</div>',
        lambda m: LIVE_ASSORTMENT_RU
        if any(x in m.group(0) for x in ("Сырокопчёный", "Вар-коп классика", "Dry-Cured"))
        else m.group(0),
        html,
        count=8,
    )
    return html


def strip_syrokopch_offers_jsonld(html: str) -> str:
    """Remove Offer objects whose name mentions сырокопч / Dry-Cured / классика говядина."""
    def scrub_offers(m: re.Match) -> str:
        block = m.group(0)
        # Drop offer objects with invented names
        block = re.sub(
            r',\s*\{"@type":"Offer","name":"[^"]*(?:сырокопч|Dry-Cured|вар-коп классика|классика \(говядина)[^"]*"[^\}]*'
            r'(?:\{[^{}]*\}[^\}]*)*\}',
            "",
            block,
            flags=re.I,
        )
        block = re.sub(
            r'\{"@type":"Offer","name":"[^"]*(?:сырокопч|Dry-Cured|вар-коп классика)[^"]*"[^\}]*'
            r'(?:\{[^{}]*\}[^\}]*)*\}\s*,?',
            "",
            block,
            flags=re.I,
        )
        # Rename remaining «классика» offers to chicken SKU labels when prices match
        block = block.replace(
            "Пепперони вар-коп классика (0.5 кг)",
            "Пепперони варёно-копчёный куриный KD-013 (0.5 кг)",
        )
        block = block.replace(
            "Пепперони вар-коп классика целый батон (1 кг)",
            "Пепперони варёно-копчёный куриный KD-014 (1 кг)",
        )
        return block

    return re.sub(
        r'<script type="application/ld\+json">\{"@context":"https://schema\.org","@type":"Product"[^<]+</script>',
        scrub_offers,
        html,
    )


def patch_faq_html(path: Path, lang: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    old = text
    if lang == "ru":
        text = re.sub(
            r'(Из чего делается халяль пепперони\?</div><div class="faq-a">)(.*?)(</div>)',
            r"\1" + TRUE_FAQ_RU_SHORT + r"\3",
            text,
            count=1,
            flags=re.S,
        )
        text = re.sub(
            r'("name":\s*"Из чего делается халяль пепперони\?",\s*"acceptedAnswer":\s*\{\s*"@type":\s*"Answer",\s*"text":\s*")([^"]+)(")',
            r"\1" + TRUE_FAQ_RU.replace('"', '\\"') + r"\3",
            text,
            count=1,
        )
        # JSON-LD often uses escaped quotes differently — also plain long answer
        text = text.replace(
            "Халяль пепперони от Казанских Деликатесов производится из говядины и курицы (классика) или из конины. В отличие от традиционного пепперони, который делается из свинины, наш продукт полностью соответствует стандартам Halal. Доступен в варёно-копчёном и сырокопчёном вариантах, в нарезке и целым батоном.",
            TRUE_FAQ_RU,
        )
        text = text.replace(
            "Из говядины и курицы (классика) или из конины. В отличие от традиционного пепперони из свинины, наш продукт полностью Halal. Доступен в варёно-копчёном и сырокопчёном вариантах, в нарезке и целым батоном.",
            TRUE_FAQ_RU_SHORT,
        )
    else:
        text = text.replace(
            "Halal Pepperoni by Kazan Delicacies is made from beef and chicken (classic) or from horse meat. Unlike traditional pepperoni made from pork, our product is fully Halal-compliant. Available in cooked-smoked and dry-cured varieties, sliced or as a whole stick.",
            TRUE_FAQ_EN,
        )
        text = re.sub(
            r'(What is halal pepperoni made from\?</div><div class="faq-a">)(.*?)(</div>)',
            r"\1" + TRUE_FAQ_EN_SHORT + r"\3",
            text,
            count=1,
            flags=re.S | re.I,
        )
    if text != old:
        path.write_text(text, encoding="utf-8")
        print(f"✅ FAQ patched: {path.relative_to(ROOT)}")
    else:
        print(f"· FAQ unchanged: {path.relative_to(ROOT)}")


def patch_file(path: Path, replacers: list[tuple[str, str]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    old = text
    for a, b in replacers:
        text = text.replace(a, b)
    text = replace_price_grids(text)
    text = strip_syrokopch_offers_jsonld(text)
    # Table rows inventing dry-cured as a sold type
    text = re.sub(
        r'\s*<tr><td>Сырокопчёный</td><td>Говядина \+ курица</td><td>[^<]*</td></tr>\n?',
        "\n",
        text,
    )
    text = re.sub(
        r'\s*<tr><td>Варёно-копчёный классика</td><td>Говядина \+ курица</td><td>[^<]*</td></tr>\n?',
        '\n          <tr><td>Варёно-копчёный куриный</td><td>Курица (KD-013 / KD-014)</td><td>Термостабильный топпинг для пиццы</td></tr>\n',
        text,
        count=1,
    )
    text = re.sub(
        r'\s*<tr><td>Сырокопчёный</td><td>Говядина \+ курица</td><td>Нарезка 0,5 кг / батон 1 кг</td></tr>\n?',
        "\n",
        text,
    )
    # EN dry-cured price / by-request rows
    text = re.sub(
        r'\s*<tr[^>]*>\s*<td[^>]*>Dry-Cured Pepperoni[^<]*</td>[\s\S]*?</tr>\n?',
        "\n",
        text,
        flags=re.I,
    )
    if text != old:
        path.write_text(text, encoding="utf-8")
        print(f"✅ {path.relative_to(ROOT)}")
        return True
    return False


def patch_product_boilerplate() -> int:
    n = 0
    old = "сырокопчёная/варёно-копчёная продукция"
    new = "варёно-копчёная / копчёная продукция"
    for folder in (PUBLIC / "products", PUBLIC / "en" / "products"):
        if not folder.exists():
            continue
        for p in folder.glob("kd-*.html"):
            t = p.read_text(encoding="utf-8")
            if old in t:
                p.write_text(t.replace(old, new), encoding="utf-8")
                n += 1
    print(f"✅ product boilerplate fixed on {n} pages")
    return n


def quarantine_overrides() -> None:
    src_dir = ROOT / "data" / "product_overrides"
    qdir = src_dir / "_quarantine_stale_syrokopch"
    qdir.mkdir(parents=True, exist_ok=True)
    for name in ("kd-017.html", "kd-017.en.html"):
        src = src_dir / name
        if src.exists():
            dest = qdir / name
            shutil.move(str(src), str(dest))
            print(f"✅ quarantined override {name} → {dest.relative_to(ROOT)}")


def main() -> None:
    products = load_products()
    pepperoni = [p for p in products if "пепперон" in (p.get("name") or "").lower()]
    print("Live pepperoni SKUs:")
    for p in pepperoni:
        print(f"  {p['sku']}: {p['name']}")
    if not pepperoni:
        raise SystemExit("No pepperoni in products.json — abort")

    regenerate_wholesale(products)

    patch_faq_html(PUBLIC / "faq.html", "ru")
    patch_faq_html(PUBLIC / "en" / "faq.html", "en")

    commercial = [
        PUBLIC / "pepperoni-optom.html",
        PUBLIC / "pepperoni-dlya-pizzerii.html",
        PUBLIC / "pepperoni-dlya-horeca.html",
        PUBLIC / "pepperoni-v-narezke.html",
        PUBLIC / "pepperoni-private-label.html",
        PUBLIC / "pizzeria.html",
        PUBLIC / "dlya-horeca.html",
        PUBLIC / "dlya-setey.html",
        PUBLIC / "oem" / "toppings.html",
        PUBLIC / "oem" / "meat.html",
        PUBLIC / "private-label.html",
        PUBLIC / "kontraktnoe-proizvodstvo.html",
        PUBLIC / "faq-ai.txt",
        PUBLIC / "en" / "pepperoni-optom.html",
        PUBLIC / "en" / "pepperoni-v-narezke.html",
        PUBLIC / "en" / "dlya-pizzerii.html",
        PUBLIC / "en" / "dlya-distributorov.html",
        PUBLIC / "en" / "oem" / "toppings.html",
        PUBLIC / "en" / "oem" / "meat.html",
        PUBLIC / "en" / "halal-pepperoni-for-pizzerias.html",
        PUBLIC / "en" / "wholesale-halal-pepperoni-supplier.html",
        PUBLIC / "en" / "beef-halal-pepperoni.html",
        PUBLIC / "en" / "halal-sliced-pepperoni-for-pizza.html",
        PUBLIC / "en" / "private-label.html",
        PUBLIC / "en" / "kontraktnoe-proizvodstvo.html",
        PUBLIC / "blog" / "pepperoni-pizzeria.html",
        PUBLIC / "en" / "blog" / "pepperoni-for-pizzeria-horeca.html",
    ]

    common_repl = [
        (
            "Доступен в варёно-копчёном и сырокопчёном вариантах, в нарезке и целым батоном.",
            "В каталоге — варёно-копчёный куриный (KD-013/KD-014) и из конины (KD-012), нарезка и батон.",
        ),
        (
            "Available in cooked-smoked and dry-cured varieties, sliced or as a whole stick.",
            "Catalog: cooked-smoked chicken (KD-013/KD-014) and horse meat (KD-012), sliced or whole stick.",
        ),
        (
            "производится из говядины и курицы (классика) или из конины",
            "производится из курицы (KD-013/KD-014) или из конины (KD-012)",
        ),
        (
            "made from beef and chicken (classic) or from horse meat",
            "made from chicken (KD-013/KD-014) or horse meat (KD-012)",
        ),
        (
            "из говядины и курицы (классика) или из конины",
            "из курицы (KD-013/KD-014) или из конины (KD-012)",
        ),
        (
            "from beef and chicken (classic) or from horse meat",
            "from chicken (KD-013/KD-014) or horse meat (KD-012)",
        ),
        (
            "Варёно-копчёный и сырокопчёный. Термостабилен",
            "Варёно-копчёный куриный и из конины. Термостабилен",
        ),
        (
            "pepperoni (boiled-smoked, dry-cured)",
            "pepperoni (cooked-smoked: chicken KD-013/014, horse KD-012)",
        ),
        (
            "Доступно в варёно-копчёном и сырокопчёном вариантах, в нарезке и батоном.",
            "Варёно-копчёный куриный (KD-013/KD-014) и из конины (KD-012), нарезка и батон.",
        ),
        (
            "Available cooked-smoked and dry-cured, sliced or whole.",
            "Cooked-smoked chicken (KD-013/014) and horse meat (KD-012), sliced or whole stick.",
        ),
        (OEM_FAQ_RU[:40], OEM_FAQ_RU[:40]),  # noop placeholder kept for structure
    ]

    # OEM FAQ full replace
    oem_ru = PUBLIC / "oem" / "toppings.html"
    if oem_ru.exists():
        t = oem_ru.read_text(encoding="utf-8")
        t2 = re.sub(
            r'("name":"Пепперони — это халяль\?","acceptedAnswer":\{"@type":"Answer","text":")([^"]+)(")',
            r"\1" + OEM_FAQ_RU.replace('"', '\\"') + r"\3",
            t,
            count=1,
        )
        if t2 != t:
            oem_ru.write_text(t2, encoding="utf-8")
            print(f"✅ OEM FAQ RU: {oem_ru.relative_to(ROOT)}")
    oem_en = PUBLIC / "en" / "oem" / "toppings.html"
    if oem_en.exists():
        t = oem_en.read_text(encoding="utf-8")
        t2 = re.sub(
            r'("name":"Is pepperoni halal\?","acceptedAnswer":\{"@type":"Answer","text":")([^"]+)(")',
            r"\1" + OEM_FAQ_EN.replace('"', '\\"') + r"\3",
            t,
            count=1,
        )
        if t2 != t:
            oem_en.write_text(t2, encoding="utf-8")
            print(f"✅ OEM FAQ EN: {oem_en.relative_to(ROOT)}")

    changed = 0
    for path in commercial:
        if patch_file(path, common_repl):
            changed += 1
    print(f"Commercial/segment files touched: {changed}")

    # Blog commercial claim: pepperoni-pizzeria lists dry-cured as assortment
    blog = PUBLIC / "blog" / "pepperoni-pizzeria.html"
    if blog.exists():
        t = blog.read_text(encoding="utf-8")
        t2 = t.replace(
            "варёно-копчёный классика — 0,5 кг в нарезке или 1 кг целый батон, варёно-копчёный из конины — 0,5 кг в нарезке, сырокопчёный — 0,5 кг в нарезке или 1 кг целый батон",
            "варёно-копчёный куриный — 0,5 кг в нарезке (KD-013) или 1 кг целый батон (KD-014), варёно-копчёный из конины — 0,5 кг в нарезке (KD-012)",
        )
        t2 = t2.replace(
            "Продукция доступна <strong>в батонах и в нарезке</strong> — варёно-копчёный и сырокопчёный варианты.",
            "Продукция доступна <strong>в батонах и в нарезке</strong> — варёно-копчёный куриный и из конины (актуальные SKU в каталоге).",
        )
        t2 = re.sub(
            r"\s*<li>Сырокопчёный — 0,5 кг в нарезке, 1 кг целый батон</li>\n?",
            "\n",
            t2,
        )
        if t2 != t:
            blog.write_text(t2, encoding="utf-8")
            print(f"✅ {blog.relative_to(ROOT)}")

    patch_product_boilerplate()
    quarantine_overrides()

    # Sanity: commercial pages must not sell dry-cured pepperoni
    bad = []
    scan_roots = [
        PUBLIC / "pepperoni-optom.html",
        PUBLIC / "pepperoni-v-narezke.html",
        PUBLIC / "pepperoni-dlya-pizzerii.html",
        PUBLIC / "pepperoni-dlya-horeca.html",
        PUBLIC / "pizzeria.html",
        PUBLIC / "faq.html",
        PUBLIC / "en" / "faq.html",
        PUBLIC / "wholesale-price-list-ru.txt",
        PUBLIC / "wholesale-price-list.txt",
        PUBLIC / "oem" / "toppings.html",
    ]
    for path in scan_roots:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"Сырокопч|Dry-Cured Pepperoni|сырокопчёном вариант", text, re.I):
            # allow educational words only if not price-card context — still fail commercial
            bad.append(str(path.relative_to(ROOT)))
    if bad:
        print("⚠️  still mentions dry-cured on commercial surfaces:")
        for b in bad:
            print(f"   - {b}")
    else:
        print("✅ commercial surfaces clean of dry-cured pepperoni claims")


if __name__ == "__main__":
    main()
