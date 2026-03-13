#!/usr/bin/env python3
"""
Bulk Geo Page Generator — Pepperoni Tatar
Generates 100–200 unique geo-targeted landing pages per run.
Products × Cities × Page-types × Languages × Templates = millions of unique combinations.
Certifications: Halal DUM RT, HACCP, FSSC 22000, ISO 22000, TR CU 021/2011.
"""

import json
import os
import re
import sys
import time
import random
import hashlib
import sqlite3
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
DB_PATH = DATA / "seo_data.db"

# ── API ───────────────────────────────────────────────────────────────────────
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL = "claude-3-5-haiku-20241022"  # fast + cheap for bulk
CLAUDE_ENDPOINT = "https://api.anthropic.com/v1/messages"
SOCKS_PROXY = os.environ.get("SOCKS_PROXY", "")

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_PAGES_PER_RUN = int(os.environ.get("MAX_GEO_PAGES", "100"))
MAX_WORKERS = int(os.environ.get("GEO_WORKERS", "5"))
SLEEP_BETWEEN_CALLS = float(os.environ.get("GEO_SLEEP", "0.5"))
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ── Load data ─────────────────────────────────────────────────────────────────
with open(DATA / "cities_russia.json", encoding="utf-8") as f:
    RU_DATA = json.load(f)
    CITIES_RU = RU_DATA["cities"]

with open(DATA / "cities_world.json", encoding="utf-8") as f:
    WORLD_DATA = json.load(f)
    COUNTRIES_WORLD = WORLD_DATA["countries"]

with open(DATA / "products_geo.json", encoding="utf-8") as f:
    PRODUCTS_DATA = json.load(f)
    PRODUCTS = PRODUCTS_DATA["products"]
    CERTS = PRODUCTS_DATA["certs_block"]
    TEMPLATES = PRODUCTS_DATA["templates"]

# ── DB ────────────────────────────────────────────────────────────────────────
def get_conn():
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS geo_pages (
            slug TEXT PRIMARY KEY,
            product_id TEXT,
            city_slug TEXT,
            country_code TEXT,
            lang TEXT,
            template_id TEXT,
            file_path TEXT,
            created_at TEXT,
            tokens_used INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def page_exists(slug: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM geo_pages WHERE slug=?", (slug,)).fetchone()
    conn.close()
    return row is not None


def save_page_record(slug, product_id, city_slug, country_code, lang, template_id, file_path, tokens):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO geo_pages
           (slug, product_id, city_slug, country_code, lang, template_id, file_path, created_at, tokens_used)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (slug, product_id, city_slug, country_code, lang, template_id, file_path, TODAY, tokens),
    )
    conn.commit()
    conn.close()


# ── HTTP helper ───────────────────────────────────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 3000) -> tuple[str, int]:
    """Call Claude API. Returns (text, tokens_used)."""
    import urllib.request
    import urllib.error

    if not CLAUDE_API_KEY:
        raise RuntimeError("CLAUDE_API_KEY not set")

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    proxies = {}
    if SOCKS_PROXY:
        try:
            import socks
            import socket
            proxy_host, proxy_port = SOCKS_PROXY.replace("socks5://", "").split(":")
            socks.set_default_proxy(socks.SOCKS5, proxy_host, int(proxy_port))
            socket.socket = socks.socksocket
        except Exception:
            pass

    req = urllib.request.Request(CLAUDE_ENDPOINT, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            text = data["content"][0]["text"]
            tokens = data.get("usage", {}).get("output_tokens", 0)
            return text, tokens
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Claude API error {e.code}: {e.read().decode()}")


# ── Slug helpers ──────────────────────────────────────────────────────────────
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

def slugify(text: str) -> str:
    text = text.lower()
    result = ""
    for ch in text:
        result += _TRANSLIT.get(ch, ch)
    result = re.sub(r"[^a-z0-9]+", "-", result)
    return result.strip("-")


def make_slug(product_slug: str, city_slug: str, lang: str, template_id: str) -> str:
    return f"{product_slug}-{city_slug}-{lang}-{template_id}".lower()


# ── Prompt builders ───────────────────────────────────────────────────────────
CERT_BLOCK_RU = (
    "**Сертификаты: Халяль (ДУМ РТ №614A/2024), HACCP, FSSC 22000, ISO 22000, "
    "ТР ТС 021/2011. Ветеринарные свидетельства РФ. Продукция без нитрита натрия. "
    "Чистый состав без ГМО и красителей. Private Label / СТМ.**"
)
CERT_BLOCK_EN = (
    "**Certifications: Halal (DUM RT #614A/2024), HACCP, FSSC 22000, ISO 22000, "
    "TR CU 021/2011. Russian veterinary certificates. No sodium nitrite. "
    "Clean label — no GMO, no artificial colors. Private Label available.**"
)
CERT_BLOCK_AR = (
    "**شهادات: حلال (DUM RT رقم 614A/2024)، HACCP، FSSC 22000، ISO 22000. "
    "بدون نيتريت الصوديوم. تسمية نظيفة. الإنتاج بالعلامة التجارية الخاصة.**"
)

LANG_PROMPTS = {
    "ru": {
        "system_note": "Пиши только на русском языке.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "geo",
        "lang_label": "RU",
    },
    "en": {
        "system_note": "Write in English only.",
        "cert_block": CERT_BLOCK_EN,
        "output_dir": "en/geo",
        "lang_label": "EN",
    },
    "kk": {
        "system_note": "Пиши на казахском языке (кириллица). Добавь версию на русском в конце страницы.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "kk/geo",
        "lang_label": "KK",
    },
    "uz": {
        "system_note": "Напиши на узбекском языке (латиница). Добавь версию на русском в конце.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "uz/geo",
        "lang_label": "UZ",
    },
    "ky": {
        "system_note": "Напиши на кыргызском языке. Добавь версию на русском в конце.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "ky/geo",
        "lang_label": "KY",
    },
    "tg": {
        "system_note": "Напиши на таджикском языке. Добавь версию на русском в конце.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "tg/geo",
        "lang_label": "TG",
    },
    "az": {
        "system_note": "Напиши на азербайджанском языке. Добавь версию на русском в конце.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "az/geo",
        "lang_label": "AZ",
    },
    "ar": {
        "system_note": "Write in Arabic (right-to-left). Include English version at the end.",
        "cert_block": CERT_BLOCK_AR,
        "output_dir": "ar/geo",
        "lang_label": "AR",
    },
    "ka": {
        "system_note": "Write in Georgian language. Add Russian version at the end.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "ka/geo",
        "lang_label": "KA",
    },
    "mn": {
        "system_note": "Write in Mongolian (Cyrillic). Add Russian version at the end.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "mn/geo",
        "lang_label": "MN",
    },
    "ro": {
        "system_note": "Write in Romanian language. Add Russian version at the end.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "ro/geo",
        "lang_label": "RO",
    },
    "hy": {
        "system_note": "Write in Armenian language. Add Russian version at the end.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "hy/geo",
        "lang_label": "HY",
    },
    "be": {
        "system_note": "Пиши на белорусском языке. Добавь версию на русском в конце.",
        "cert_block": CERT_BLOCK_RU,
        "output_dir": "be/geo",
        "lang_label": "BE",
    },
}

TEMPLATE_PROMPTS = {
    "A": "Акцент на профессиональный HoReCa сегмент: рестораны, кафе, фастфуд. Упомяни профессиональную упаковку, условия хранения, работу с шефами.",
    "B": "Акцент на ретейл: розничные магазины, сети супермаркетов, упаковка для конечного потребителя, срок годности, визуальный мерчандайзинг.",
    "C": "Акцент на оптовые поставки: минимальная партия, условия доставки, отсрочка платежа, логистика, дистрибьюторские условия.",
    "D": "Акцент на халяль рынок: детальный разбор сертификатов, религиозные требования, контроль производства, доверие мусульманских потребителей.",
    "E": "Акцент на Private Label / СТМ: производство под брендом клиента, разработка рецептуры, дизайн упаковки, минимальный тираж.",
    "F": "Акцент на чистый состав: без нитрита натрия, без ГМО, без красителей, натуральные ингредиенты, здоровое питание.",
}


def build_prompt(product: dict, city_name: str, city_context: dict,
                 lang: str, template_id: str, country_name: str) -> str:
    """Build a unique, high-quality Claude prompt for one page."""

    lang_cfg = LANG_PROMPTS.get(lang, LANG_PROMPTS["ru"])
    template_note = TEMPLATE_PROMPTS.get(template_id, TEMPLATE_PROMPTS["A"])
    cert_block = lang_cfg["cert_block"]

    # City-specific context
    population = city_context.get("population", "")
    horeca = city_context.get("horeca", "")
    halal_note = city_context.get("halal_note_ru", city_context.get("halal_note", ""))
    delivery = city_context.get("delivery", "")
    muslim_pct = city_context.get("muslim_pct", "")

    # Product-specific
    product_name = product.get("name_ru", product.get("name_en", ""))
    usp = product.get("usp_ru", product.get("usp_en", ""))
    keywords = " | ".join(product.get("keywords_ru", product.get("keywords_en", [])))
    differentiator = product.get("differentiator", "")

    # Random variation for uniqueness
    random_angle = random.choice([
        "история бренда Pepperoni Tatar из Казани",
        "контроль качества на производстве",
        "почему клиенты выбирают нас уже 10+ лет",
        "сравнение с конкурентами — в чём наше преимущество",
        "кейс: как пиццерия увеличила продажи с нашим пепперони",
        "технология производства без нитрита натрия",
        "экспортный опыт: поставки в 20+ стран",
        "отзывы партнёров из этого региона",
    ])

    prompt = f"""
{lang_cfg['system_note']}

Ты эксперт по B2B продажам халяль мясной продукции. Напиши уникальную SEO-оптимизированную HTML landing page для {country_name}, город {city_name}.

ПРОДУКТ: {product_name}
USP: {usp}
{f'КЛЮЧЕВОЕ ОТЛИЧИЕ: {differentiator}' if differentiator else ''}

КОНТЕКСТ ГОРОДА:
- Население: {population}
- HoReCa: {horeca}
- Халяль спрос: {halal_note}
- Мусульмане: {muslim_pct}
- Доставка: {delivery}

ШАБЛОН (тема страницы): {template_note}

ДОПОЛНИТЕЛЬНЫЙ УГОЛ: {random_angle}

СЕРТИФИКАТЫ (упомяни ВСЕ):
{cert_block}

КЛЮЧЕВЫЕ СЛОВА (вплети органично): {keywords}

ТРЕБОВАНИЯ К HTML:
1. Верни ТОЛЬКО валидный HTML, начиная с <!DOCTYPE html>
2. Bootstrap 5 (CDN), Яндекс.Метрика и Schema.org JSON-LD
3. Структура:
   - <title> с городом и продуктом (60 символов)
   - <meta name="description"> (155 символов)
   - H1 с городом и продуктом
   - Вступление (2-3 предложения) — уникальный контекст города
   - Блок преимуществ (6 карточек) — конкретные цифры и факты
   - Таблица сертификатов (Халяль ДУМ РТ, HACCP, FSSC 22000, ISO 22000, ТР ТС 021/2011, Ветеринарные свидетельства)
   - FAQ блок (5 вопросов специфичных для этого города/региона)
   - CTA секция с формой заявки (имя, компания, телефон, email, сообщение)
   - Блок доставки в {city_name}
4. Schema.org JSON-LD: LocalBusiness + Product + FAQPage + BreadcrumbList
5. Стиль: профессиональный, B2B, акцент на надёжность и сертификаты
6. Добавь в <head>: <link rel="canonical" href="https://pepperoni.tatar/geo/{product['slug_ru']}-{slugify(city_name)}/">
7. НЕ добавляй navigation header и footer — страница встраивается в существующий сайт
8. Добавь data-city="{city_name}" и data-product="{product['id']}" к <body>

ВАЖНО: Страница должна быть на {100}% уникальной. Упомяни конкретный контекст {city_name}. 
Избегай шаблонных фраз. Пиши как живой эксперт по мясному рынку {country_name}.
""".strip()

    return prompt


# ── HTML post-processing ──────────────────────────────────────────────────────
def clean_html(html: str) -> str:
    """Strip markdown fences if Claude returns them."""
    html = re.sub(r"^```html?\s*\n?", "", html.strip(), flags=re.IGNORECASE)
    html = re.sub(r"\n?```\s*$", "", html.strip())
    return html.strip()


def inject_internal_links(html: str, product_id: str, city_slug: str, lang: str) -> str:
    """Append related pages section before </body>."""
    related = []
    for prod in PRODUCTS[:4]:
        if prod["id"] != product_id:
            slug = prod.get(f"slug_{lang}", prod.get("slug_ru", ""))
            name = prod.get(f"name_{lang}", prod.get("name_ru", ""))
            related.append(f'<a href="/geo/{slug}-{city_slug}/" class="btn btn-outline-secondary btn-sm m-1">{name}</a>')

    block = f"""
<section class="related-pages py-4 bg-light mt-5">
  <div class="container">
    <h6 class="text-muted mb-3">Другие продукты для {city_slug.replace("-", " ").title()}:</h6>
    <div>{''.join(related)}</div>
  </div>
</section>
"""
    return html.replace("</body>", block + "\n</body>")


def update_sitemap(new_urls: list[str]):
    """Add new URLs to sitemap.xml."""
    sitemap_path = PUBLIC / "sitemap.xml"
    if not sitemap_path.exists():
        return

    content = sitemap_path.read_text(encoding="utf-8")
    entries = []
    for url in new_urls:
        if url not in content:
            entries.append(
                f"  <url>\n    <loc>{url}</loc>\n"
                f"    <lastmod>{TODAY}</lastmod>\n"
                f"    <changefreq>monthly</changefreq>\n"
                f"    <priority>0.6</priority>\n  </url>"
            )
    if entries:
        content = content.replace("</urlset>", "\n".join(entries) + "\n</urlset>")
        sitemap_path.write_text(content, encoding="utf-8")
        print(f"  → Sitemap: added {len(entries)} URLs")


# ── Page generation ───────────────────────────────────────────────────────────
def generate_one_page(task: dict) -> dict:
    """Generate a single geo page. Returns result dict."""
    product = task["product"]
    city_slug = task["city_slug"]
    city_name = task["city_name"]
    city_context = task["city_context"]
    lang = task["lang"]
    template_id = task["template_id"]
    country_code = task["country_code"]
    country_name = task["country_name"]
    output_dir = task["output_dir"]

    prod_slug = product.get(f"slug_{lang}", product.get("slug_ru", product["id"]))
    page_slug = f"{prod_slug}-{city_slug}-{lang}-{template_id.lower()}"

    # Check if already generated
    if page_exists(page_slug):
        return {"status": "skipped", "slug": page_slug}

    # Check if file exists
    out_dir = PUBLIC / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prod_slug}-{city_slug}.html"
    # For multiple templates, distinguish by template ID
    if template_id != "A":
        filename = f"{prod_slug}-{city_slug}-{template_id.lower()}.html"
    file_path = out_dir / filename

    if file_path.exists():
        save_page_record(page_slug, product["id"], city_slug, country_code,
                         lang, template_id, str(file_path), 0)
        return {"status": "already_exists", "slug": page_slug}

    try:
        time.sleep(SLEEP_BETWEEN_CALLS + random.uniform(0, 0.5))
        prompt = build_prompt(product, city_name, city_context, lang, template_id, country_name)
        html_content, tokens = call_claude(prompt, max_tokens=4000)
        html_content = clean_html(html_content)
        html_content = inject_internal_links(html_content, product["id"], city_slug, lang)

        file_path.write_text(html_content, encoding="utf-8")
        save_page_record(page_slug, product["id"], city_slug, country_code,
                         lang, template_id, str(file_path), tokens)

        return {
            "status": "generated",
            "slug": page_slug,
            "file": str(file_path),
            "tokens": tokens,
            "city": city_name,
            "product": product["name_ru"],
            "lang": lang,
        }

    except Exception as exc:
        return {"status": "error", "slug": page_slug, "error": str(exc)}


# ── Task queue builder ────────────────────────────────────────────────────────
def build_task_queue(
    mode: str = "russia",
    max_pages: int = 100,
    langs: list[str] | None = None,
    product_ids: list[str] | None = None,
) -> list[dict]:
    """
    Build a prioritized list of page generation tasks.
    mode: 'russia' | 'world' | 'all'
    """
    tasks = []

    def add_tasks_for_city(city_slug, city_name, city_context, country_code, country_name, country_langs):
        for product in PRODUCTS:
            if product_ids and product["id"] not in product_ids:
                continue
            for lang in country_langs:
                if langs and lang not in langs:
                    continue
                # Rotate templates — each combo gets a unique template
                template_id = random.choice(["A", "B", "C", "D", "F"])
                lang_cfg = LANG_PROMPTS.get(lang, LANG_PROMPTS["ru"])
                tasks.append({
                    "product": product,
                    "city_slug": city_slug,
                    "city_name": city_name,
                    "city_context": city_context,
                    "lang": lang,
                    "template_id": template_id,
                    "country_code": country_code,
                    "country_name": country_name,
                    "output_dir": lang_cfg["output_dir"],
                })

    if mode in ("russia", "all"):
        for city in CITIES_RU:
            add_tasks_for_city(
                city["slug"], city["name"], city,
                "ru", "Россия", ["ru"]
            )

    if mode in ("world", "all"):
        for country in COUNTRIES_WORLD:
            for city in country["cities"]:
                city_ctx = dict(city)
                city_ctx["halal_note"] = city_ctx.get("halal_note_ru", country.get("halal_note_ru", ""))
                city_ctx["delivery"] = country.get("logistics", "")
                city_ctx["muslim_pct"] = country.get("halal_note_ru", "")[:50]
                city_name = city.get("name_ru", city.get("name_en", ""))
                for lang in country["langs"]:
                    if langs and lang not in langs:
                        continue
                    lang_cfg = LANG_PROMPTS.get(lang, LANG_PROMPTS.get("en", LANG_PROMPTS["ru"]))
                    for product in PRODUCTS:
                        if product_ids and product["id"] not in product_ids:
                            continue
                        template_id = random.choice(["A", "C", "D"])
                        tasks.append({
                            "product": product,
                            "city_slug": city["slug"],
                            "city_name": city_name,
                            "city_context": city_ctx,
                            "lang": lang,
                            "template_id": template_id,
                            "country_code": country["code"],
                            "country_name": country.get("name_ru", country.get("name_en", "")),
                            "output_dir": lang_cfg["output_dir"],
                        })

    # Shuffle to avoid patterns, filter already done, limit
    random.shuffle(tasks)

    filtered = []
    for task in tasks:
        prod_slug = task["product"].get(f"slug_{task['lang']}", task["product"].get("slug_ru", task["product"]["id"]))
        page_slug = f"{prod_slug}-{task['city_slug']}-{task['lang']}-{task['template_id'].lower()}"
        if not page_exists(page_slug):
            filtered.append(task)
        if len(filtered) >= max_pages:
            break

    return filtered


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Bulk geo page generator")
    parser.add_argument("--mode", choices=["russia", "world", "all"], default="all",
                        help="Which cities to process")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_RUN,
                        help="Max pages to generate this run")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS,
                        help="Parallel workers")
    parser.add_argument("--langs", nargs="+", default=None,
                        help="Restrict to specific languages: ru en ar kk uz ...")
    parser.add_argument("--products", nargs="+", default=None,
                        help="Restrict to specific product IDs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Just print task list, don't generate")
    args = parser.parse_args()

    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    init_db()

    print(f"🌍 Geo Bulk Generator — {TODAY}")
    print(f"   Mode: {args.mode} | Max pages: {args.max_pages} | Workers: {args.workers}")
    print("=" * 60)

    tasks = build_task_queue(
        mode=args.mode,
        max_pages=args.max_pages,
        langs=args.langs,
        product_ids=args.products,
    )

    print(f"📋 Tasks in queue: {len(tasks)}")

    if args.dry_run:
        for t in tasks[:20]:
            print(f"  → [{t['lang']}|{t['template_id']}] {t['product']['name_ru']} / {t['city_name']} ({t['country_code']})")
        return

    if not tasks:
        print("✅ All requested pages already exist. Nothing to generate.")
        return

    generated = 0
    errors = 0
    total_tokens = 0
    new_urls = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(generate_one_page, task): task for task in tasks}
        for future in as_completed(futures):
            result = future.result()
            status = result.get("status")
            if status == "generated":
                generated += 1
                total_tokens += result.get("tokens", 0)
                city = result.get("city", "")
                product = result.get("product", "")
                lang = result.get("lang", "")
                new_urls.append(f"https://pepperoni.tatar/{result.get('output_dir', 'geo')}/{result['slug']}/")
                if generated % 10 == 0 or generated <= 5:
                    print(f"  ✓ [{generated}] [{lang}] {product} / {city}")
            elif status == "error":
                errors += 1
                print(f"  ✗ ERROR: {result.get('slug')} — {result.get('error', '')[:100]}", file=sys.stderr)
            # skipped/already_exists — silent

    # Update sitemap
    if new_urls:
        update_sitemap(new_urls)

    print(f"\n{'='*60}")
    print(f"✅ Generated: {generated} pages")
    print(f"❌ Errors: {errors}")
    print(f"🔤 Total tokens used: {total_tokens:,}")
    print(f"📍 New sitemap URLs: {len(new_urls)}")


if __name__ == "__main__":
    main()
