#!/usr/bin/env python3
"""Generate GEO landing pages from templates — ZERO Anthropic / LLM spend.

Fills city + product facts into proven HTML shells (no page_reviewer LLM).
Structural gate only: scripts.generate_geo_bulk.is_valid_page.

Usage:
  python3 scripts/generate_geo_template.py --tasks data/geo_0.4_tasks.json
  python3 scripts/generate_geo_template.py --tasks data/geo_0.4_tasks.json --langs ru en
  python3 scripts/generate_geo_template.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS_GEO = ROOT / "data" / "products_geo.json"
sys.path.insert(0, str(ROOT / "scripts"))
from generate_geo_bulk import is_valid_page  # noqa: E402

# Display names (products_geo name_ru for v-teste is awkward)
DISPLAY_NAME = {
    "sosiski-v-teste": {
        "ru": "Сосиски в тесте",
        "en": "Halal sausages in dough",
    },
    "sosiski-hotdog": {
        "ru": "Сосиски для хот-догов",
        "en": "Halal hot-dog sausages",
    },
}

SHELLS = {
    ("sosiski-v-teste", "ru"): PUBLIC / "geo" / "sosiski-v-teste-korolev.html",
    ("sosiski-hotdog", "ru"): PUBLIC / "geo" / "sosiski-dlya-hotdog-aktobe.html",
}

INTROS_RU = [
    "{city} — точка спроса на стабильные замороженные халяль-полуфабрикаты для HoReCa и фастфуда. Ниже — параметры поставки с производства в Казани под закупщика.",
    "Для операторов общепита в городе {city} критичны подтверждённый халяль-статус, понятная фасовка и холодовая логистика. Карточка собрана под этот запрос.",
    "Закупщикам в {city} нужна предсказуемая себестоимость порции и документы по халяль/HACCP. Позиция ниже закрывает этот контур без розничной обёртки.",
    "Рынок {city} использует замороженные халяль-изделия в сетях фастфуда и кафе. Поставка — EXW Казань / через ТК с соблюдением −18°C.",
    "Ассортимент для B2B-заказа в {city}: фиксированные параметры SKU, сертификат ДУМ РТ №614A/2024, возможность СТМ. Контакты — внизу страницы.",
]

DELIVERY_RU = {
    "kz": "{city} (Казахстан): отгрузка из Казани автотранспортом с температурным режимом −18°C. Срок в пути уточняйте у менеджера.",
    "uz": "{city} (Узбекистан): экспортная отгрузка из Казани, холодовая цепь обязательна. Документы и Incoterms — по запросу.",
    "by": "{city} (Беларусь): поставка из Казани транспортными компаниями в режиме заморозки. Условия — у менеджера.",
    "az": "{city} (Азербайджан): экспорт из Казани, режим −18°C. Пакет документов — по запросу.",
    "ge": "{city} (Грузия): отгрузка из Казани, холодовой режим. Сроки и стоимость — у менеджера.",
    "ru": "{city}: доставка транспортными компаниями с соблюдением холодовой цепи (−18°C). Сроки — по запросу.",
    "default": "{city}: отгрузка с производства в Казани, температурный режим −18°C. Сроки и маршрут — у менеджера (+7 987 217-02-02).",
}


def load_products() -> dict[str, dict]:
    data = json.loads(PRODUCTS_GEO.read_text(encoding="utf-8"))
    return {p["id"]: p for p in data["products"]}


def output_path(lang: str, filename: str) -> Path:
    if lang == "ru":
        return PUBLIC / "geo" / filename
    return PUBLIC / lang / "geo" / filename


def replace_city(html: str, old_city: str, new_city: str) -> str:
    # Order: longer / specific first
    pairs = [
        (old_city, new_city),
        (old_city.replace("ё", "е"), new_city),
    ]
    # English title-case city slug leftovers e.g. Korolev / Aktobe
    # handled separately
    for a, b in pairs:
        if a and a in html:
            html = html.replace(a, b)
    return html


def extract_data_city(html: str) -> str | None:
    m = re.search(r'data-city="([^"]+)"', html)
    return m.group(1) if m else None


def render_ru(task: dict, product: dict, shell_html: str) -> str:
    city = task["city"]
    city_slug = task["city_slug"]
    country = task["country"]
    pid = product["id"]
    old_city = extract_data_city(shell_html) or "Королёв"
    html = shell_html

    html = replace_city(html, old_city, city)
    # common shell cities
    for ghost in ("Королёв", "Актобе", "Астана", "Караганда"):
        if ghost != city:
            html = html.replace(ghost, city)

    # canonical / links use slug
    html = re.sub(
        r"(sosiski-v-teste|sosiski-dlya-hotdog)-[a-z0-9-]+",
        lambda m: f"{m.group(1)}-{city_slug}",
        html,
    )

    # data attrs
    html = re.sub(r'data-city="[^"]*"', f'data-city="{city}"', html)
    html = re.sub(r'data-product="[^"]*"', f'data-product="{pid}"', html)
    html = re.sub(
        r'name="city" value="[^"]*"',
        f'name="city" value="{city}"',
        html,
    )
    html = re.sub(
        r'name="product" value="[^"]*"',
        f'name="product" value="{pid}"',
        html,
    )

    # Unique intro (avoid near-dupe gate later)
    intro = INTROS_RU[sum(map(ord, city_slug)) % len(INTROS_RU)].format(city=city)
    html = re.sub(
        r'(<!-- Вступление -->\s*<p class="lead">)(.*?)(</p>)',
        rf"\1{intro}\3",
        html,
        count=1,
        flags=re.S,
    )

    delivery = DELIVERY_RU.get(country, DELIVERY_RU["default"]).format(city=city)
    html = re.sub(
        r'(<div class="delivery-block">.*?<p class="mb-1">)(.*?)(</p>)',
        rf"\1{delivery}\3",
        html,
        count=1,
        flags=re.S,
    )

    # Related-pages label
    html = re.sub(
        r"Другие продукты для [^:<]+",
        f"Другие продукты для {city}",
        html,
    )

    # Schema areaServed city
    html = re.sub(
        r'("areaServed"\s*:\s*\{\s*"@type"\s*:\s*"City"\s*,\s*"name"\s*:\s*")[^"]+(")',
        rf"\1{city}\2",
        html,
    )

    return html


def render_en_from_ru_shell(task: dict, product: dict, shell_html: str) -> str:
    """Lightweight EN: keep structure, swap visible RU labels to EN where critical."""
    html = render_ru(task, product, shell_html)
    city = task["city"]
    name = DISPLAY_NAME[product["id"]]["en"]
    html = html.replace('lang="ru"', 'lang="en"')
    # Title/H1 soft rewrite
    html = re.sub(
        r"<title>.*?</title>",
        f"<title>{name} wholesale in {city} — Halal, HoReCa | Kazan Delicacies</title>",
        html,
        count=1,
        flags=re.S,
    )
    html = re.sub(
        r"<h1[^>]*>.*?</h1>",
        f'<h1 class="mb-0">{name} wholesale in {city} — Halal frozen for HoReCa</h1>',
        html,
        count=1,
        flags=re.S,
    )
    # Canonical under /en/geo/
    slug = f"{product.get('slug_ru')}-{task['city_slug']}"
    html = re.sub(
        r'<link rel="canonical" href="[^"]*"',
        f'<link rel="canonical" href="https://pepperoni.tatar/en/geo/{slug}/"',
        html,
        count=1,
    )
    return html


def process_task(task: dict, products: dict, dry_run: bool) -> str:
    lang = task["lang"]
    pid = task["product_id"]
    if pid not in products:
        return "skip-unknown-product"
    if lang not in ("ru", "en"):
        return "skip-lang"
    product = products[pid]
    shell_key = (pid, "ru")
    shell_path = SHELLS.get(shell_key)
    if not shell_path or not shell_path.exists():
        return "skip-no-shell"
    shell = shell_path.read_text(encoding="utf-8")
    if lang == "ru":
        html = render_ru(task, product, shell)
        out = output_path("ru", f"{product['slug_ru']}-{task['city_slug']}.html")
    else:
        html = render_en_from_ru_shell(task, product, shell)
        out = output_path("en", f"{product['slug_ru']}-{task['city_slug']}.html")

    if not is_valid_page(html):
        return "fail-invalid"
    if out.exists() and "tldr-answer" in out.read_text(encoding="utf-8", errors="ignore"):
        # already published with GEO format — leave alone
        return "skip-exists"
    if dry_run:
        return f"would-write:{out.relative_to(ROOT)}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return f"wrote:{out.relative_to(ROOT)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="data/geo_0.4_tasks.json")
    ap.add_argument("--langs", nargs="+", default=["ru", "en"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    tasks_path = ROOT / args.tasks
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks = [t for t in tasks if t.get("lang") in args.langs]
    if args.limit:
        tasks = tasks[: args.limit]
    products = load_products()

    counts: dict[str, int] = {}
    written = []
    for t in tasks:
        status = process_task(t, products, args.dry_run)
        key = status.split(":")[0]
        counts[key] = counts.get(key, 0) + 1
        if status.startswith("wrote:") or status.startswith("would-write:"):
            written.append(status)
            print(status)

    print("---")
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {k}: {v}")
    print(f"done written={len(written)} dry_run={args.dry_run} (no Anthropic calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
