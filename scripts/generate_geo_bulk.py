#!/usr/bin/env python3
"""
Bulk Geo Page Generator — Pepperoni Tatar
Generates 100–200 unique geo-targeted landing pages per run.
Products × Cities × Page-types × Languages × Templates = millions of unique combinations.
Certifications: Halal DUM RT, HACCP, ISO 22000:2018, TR CU 021/2011.
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
DEEPSEEK_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
from importlib import import_module as _im
try:
    DEEPSEEK_MODEL = _im("claude_client").DEFAULT_MODEL  # claude-sonnet-4-6
except Exception:
    DEEPSEEK_MODEL = "claude-sonnet-4-6"

# GEO_MODEL: override the generation model (e.g. Haiku pilot at 1/3 the price).
GEO_MODEL = os.environ.get("GEO_MODEL", "").strip() or DEEPSEEK_MODEL
# GEO_EFFORT: output-token spend control; templated pages don't need "high".
GEO_EFFORT = os.environ.get("GEO_EFFORT", "medium")

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

# ── Brain strategy (optional) ──────────────────────────────────────────────────
STRATEGY_FILE = DATA / "strategy.json"

def load_strategy() -> dict:
    try:
        return json.loads(STRATEGY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

# ── DB ────────────────────────────────────────────────────────────────────────
def get_conn():
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Best-effort: create stats table. Dedup does NOT depend on it."""
    try:
        conn = get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS geo_pages (
                slug TEXT PRIMARY KEY, product_id TEXT, city_slug TEXT,
                country_code TEXT, lang TEXT, template_id TEXT,
                file_path TEXT, created_at TEXT, tokens_used INTEGER DEFAULT 0
            )
        """)
        conn.commit(); conn.close()
    except Exception:
        pass


def _slug_to_paths(slug: str) -> list:
    """page_slug = '{prodslug}-{cityslug}-{lang}-{tmpl}'. Map to on-disk html."""
    parts = slug.rsplit("-", 2)  # [.., lang, tmpl]
    if len(parts) < 3:
        return []
    base, lang, tmpl = parts[0], parts[1], parts[2]
    out_dir = "en/geo" if lang == "en" else "geo"
    fnames = [f"{base}.html"] if tmpl == "a" else [f"{base}-{tmpl}.html"]
    return [PUBLIC / out_dir / fn for fn in fnames]


def page_exists(slug: str) -> bool:
    # File-based dedup: robust against DB resets by cron/sync.
    for p in _slug_to_paths(slug):
        if p.exists():
            return True
    # Fallback to DB if available (non-fatal).
    try:
        conn = get_conn()
        row = conn.execute("SELECT 1 FROM geo_pages WHERE slug=?", (slug,)).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def save_page_record(slug, product_id, city_slug, country_code, lang, template_id, file_path, tokens):
    try:
        init_db()
        conn = get_conn()
        conn.execute(
        """INSERT OR REPLACE INTO geo_pages
           (slug, product_id, city_slug, country_code, lang, template_id, file_path, created_at, tokens_used)
           VALUES (?,?,?,?,?,?,?,?,?)""",
            (slug, product_id, city_slug, country_code, lang, template_id, file_path, TODAY, tokens),
        )
        conn.commit(); conn.close()
    except Exception:
        pass


# ── HTTP helper ───────────────────────────────────────────────────────────────
# Delegates to the shared DeepSeek client.
sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude as _shared_call_claude  # noqa: E402


def call_claude(prompt: str, max_tokens: int = 3000) -> tuple[str, int]:
    """Call DeepSeek API via shared client. Returns (text, tokens_used)."""
    return _shared_call_claude(prompt=prompt, model=DEEPSEEK_MODEL, max_tokens=max_tokens)


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
    "**Сертификаты: Халяль (ДУМ РТ №614A/2024), HACCP, ISO 22000:2018, "
    "ТР ТС 021/2011. Ветеринарные свидетельства РФ. Продукция без нитрита натрия. "
    "Чистый состав без ГМО и красителей. Private Label / СТМ.**"
)
CERT_BLOCK_EN = (
    "**Certifications: Halal (DUM RT #614A/2024), HACCP, ISO 22000:2018, "
    "TR CU 021/2011. Russian veterinary certificates. No sodium nitrite. "
    "Clean label — no GMO, no artificial colors. Private Label available.**"
)
CERT_BLOCK_AR = (
    "**شهادات: حلال (DUM RT رقم 614A/2024)، HACCP، ISO 22000:2018. "
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
    "ms": {
        "system_note": "Write in Malay (Bahasa Melayu). Add English version at the end.",
        "cert_block": CERT_BLOCK_EN,
        "output_dir": "ms/geo",
        "lang_label": "MS",
    },
    "id": {
        "system_note": "Write in Indonesian (Bahasa Indonesia). Add English version at the end.",
        "cert_block": CERT_BLOCK_EN,
        "output_dir": "id/geo",
        "lang_label": "ID",
    },
    "tr": {
        "system_note": "Write in Turkish language. Add English version at the end.",
        "cert_block": CERT_BLOCK_EN,
        "output_dir": "tr/geo",
        "lang_label": "TR",
    },
    "fr": {
        "system_note": "Write in French language. Add English version at the end.",
        "cert_block": CERT_BLOCK_EN,
        "output_dir": "fr/geo",
        "lang_label": "FR",
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


def build_system_prompt(lang: str) -> str:
    """Stable per-language instruction block.

    Sent as the `system` parameter so Anthropic prompt caching reuses it across
    every page of the same language in a run (cache reads cost 10% of input).
    Keep page-specific values OUT of here — they go in the user prompt."""
    lang_cfg = LANG_PROMPTS.get(lang, LANG_PROMPTS["ru"])
    return f"""{lang_cfg['system_note']}

Ты эксперт по B2B продажам халяль мясной продукции. По параметрам из сообщения пользователя пишешь уникальную SEO-оптимизированную HTML landing page для указанных страны и города.

СЕРТИФИКАТЫ (упомяни ВСЕ):
{lang_cfg['cert_block']}

ТРЕБОВАНИЯ К HTML:
1. Верни ТОЛЬКО валидный HTML, начиная с <!DOCTYPE html>
2. Bootstrap 5 (CDN), Яндекс.Метрика и Schema.org JSON-LD
3. Структура:
   - <title> с городом и продуктом (60 символов)
   - <meta name="description"> (155 символов)
   - H1 с городом и продуктом
   - Вступление (2-3 предложения) — уникальный контекст города
   - Блок преимуществ (6 карточек) — конкретные цифры и факты
   - Таблица сертификатов (Халяль ДУМ РТ, HACCP, ISO 22000:2018, ТР ТС 021/2011, Ветеринарные свидетельства)
   - FAQ блок (5 вопросов специфичных для этого города/региона)
   - CTA секция с формой заявки (имя, компания, телефон, email, сообщение)
   - Блок доставки в указанный город
4. Schema.org JSON-LD: LocalBusiness + Product + FAQPage + BreadcrumbList
5. Стиль: профессиональный, B2B, акцент на надёжность и сертификаты
6. Добавь в <head> канонический тег: <link rel="canonical" href="CANONICAL из параметров">
7. НЕ добавляй navigation header и footer — страница встраивается в существующий сайт
8. Добавь к <body> атрибуты data-city и data-product (значения — из параметров)
9. КОНТАКТЫ — используй СТРОГО эти и никакие другие: телефон +7 987 217-02-02 (tel:+79872170202), email info@kazandelikates.tatar, адрес: г. Казань, ул. Аграрная, 2, оф. 7. НИКОГДА не выдумывай номера 8-800, другие адреса/email.

ОБЪЁМ: 600–800 слов видимого текста. НЕ раздувай страницу — лаконичные карточки и
FAQ-ответы по 2-3 предложения. ОБЯЗАТЕЛЬНО заверши документ закрывающими
</body></html> — незакрытая страница будет отброшена.

ВАЖНО: Страница должна быть на 100% уникальной. Упомяни конкретный контекст города.
Избегай шаблонных фраз. Пиши как живой эксперт по мясному рынку указанной страны."""


def build_user_prompt(product: dict, city_name: str, city_context: dict,
                      lang: str, template_id: str, country_name: str) -> str:
    """Per-page variable parameters (the cheap, uncached part of the prompt)."""
    template_note = TEMPLATE_PROMPTS.get(template_id, TEMPLATE_PROMPTS["A"])

    population = city_context.get("population", "")
    horeca = city_context.get("horeca", "")
    halal_note = city_context.get("halal_note_ru", city_context.get("halal_note", ""))
    delivery = city_context.get("delivery", "")
    muslim_pct = city_context.get("muslim_pct", "")

    product_name = product.get("name_ru", product.get("name_en", ""))
    usp = product.get("usp_ru", product.get("usp_en", ""))
    keywords = " | ".join(product.get("keywords_ru", product.get("keywords_en", [])))
    differentiator = product.get("differentiator", "")

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

    return f"""СТРАНА: {country_name}
ГОРОД: {city_name}

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
КЛЮЧЕВЫЕ СЛОВА (вплети органично): {keywords}

CANONICAL: https://pepperoni.tatar/geo/{product['slug_ru']}-{slugify(city_name)}/
data-city="{city_name}" data-product="{product['id']}"
""".strip()


def build_prompt(product: dict, city_name: str, city_context: dict,
                 lang: str, template_id: str, country_name: str) -> str:
    """Back-compat: combined single prompt (system + user)."""
    return (build_system_prompt(lang) + "\n\n"
            + build_user_prompt(product, city_name, city_context, lang,
                                template_id, country_name))


# ── HTML post-processing ──────────────────────────────────────────────────────
def clean_html(html: str) -> str:
    """Strip markdown fences if the model returns them."""
    html = re.sub(r"^```html?\s*\n?", "", html.strip(), flags=re.IGNORECASE)
    html = re.sub(r"\n?```\s*$", "", html.strip())
    return html.strip()


# Footer appended when the model omitted/truncated the page tail. Keeps every
# page self-contained and valid even if generation ran into the token limit.
_FALLBACK_FOOTER = (
    '\n<footer class="py-4 mt-5" style="background:#1f3b2c;color:#fff">'
    '<div class="container">'
    '<p class="mb-1">Казанские деликатесы (Pepperoni Tatar) — производство халяльной '
    'мясной продукции и татарской выпечки в Казани.</p>'
    '<p class="small mb-0">'
    '<a href="https://pepperoni.tatar/" style="color:#fff">pepperoni.tatar</a> · '
    'info@kazandelikates.tatar · +7 987 217-02-02</p>'
    '</div></footer>\n'
)


def ensure_complete_html(html: str) -> str:
    """Guarantee the page is structurally closed.

    The model occasionally hits the token limit and returns HTML truncated
    mid-tag (no </body></html>, sometimes mid-element). We trim any dangling
    final line and append the closing tags so the page is always valid.
    """
    html = html.rstrip()

    has_body_open = "<body" in html.lower()
    has_body_close = "</body>" in html.lower()
    has_html_close = "</html>" in html.lower()

    if has_body_close and has_html_close:
        return html  # already complete

    # If truncated, the last line is likely a half-written tag/sentence.
    # Drop it only when it looks unterminated (open '<' without matching '>').
    lines = html.split("\n")
    if lines:
        last = lines[-1]
        opens = last.count("<")
        closes = last.count(">")
        if opens > closes:
            lines = lines[:-1]
            html = "\n".join(lines).rstrip()

    if has_body_open and not has_body_close:
        # Close an opened (but unclosed) <main> if present.
        if "<main" in html.lower() and "</main>" not in html.lower():
            html += "\n</main>"
        if "</footer>" not in html.lower():
            html += _FALLBACK_FOOTER
        html += "\n</body>"

    if not has_html_close:
        html += "\n</html>"

    return html + "\n"


def is_valid_page(html: str) -> bool:
    """Reject pages that are too broken to publish.

    A page is publishable when it has a real <head>, a heading, and (after
    ensure_complete_html) a closing </html>. Also reject leftover conflict
    markers as a last line of defense.
    """
    low = html.lower()
    if any(m in html for m in ("<<<<<<<", "=======\n", ">>>>>>>")):
        return False
    if "</head>" not in low:
        return False
    if "<h1" not in low:
        return False
    if "</html>" not in low:
        return False
    return True


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
def prepare_task(task: dict) -> dict:
    """Pre-flight checks + prompt building. Returns {"status": ...} when the
    page should be skipped, else {"status": "ready", ...prepared fields}."""
    product = task["product"]
    city_slug = task["city_slug"]
    lang = task["lang"]
    template_id = task["template_id"]
    output_dir = task["output_dir"]

    prod_slug = product.get(f"slug_{lang}", product.get("slug_ru", product["id"]))
    page_slug = f"{prod_slug}-{city_slug}-{lang}-{template_id.lower()}"

    if page_exists(page_slug):
        return {"status": "skipped", "slug": page_slug}

    out_dir = PUBLIC / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prod_slug}-{city_slug}.html"
    if template_id != "A":
        filename = f"{prod_slug}-{city_slug}-{template_id.lower()}.html"
    file_path = out_dir / filename

    if file_path.exists():
        save_page_record(page_slug, product["id"], city_slug, task["country_code"],
                         lang, template_id, str(file_path), 0)
        return {"status": "already_exists", "slug": page_slug}

    return {
        "status": "ready",
        "task": task,
        "page_slug": page_slug,
        "file_path": file_path,
        "system": build_system_prompt(lang),
        "user": build_user_prompt(product, task["city_name"], task["city_context"],
                                  lang, template_id, task["country_name"]),
    }


def finalize_page(prep: dict, html_content: str, tokens: int) -> dict:
    """Post-process generated HTML and persist the page."""
    task = prep["task"]
    product = task["product"]
    page_slug = prep["page_slug"]
    try:
        html_content = clean_html(html_content)
        # Close/repair the tail BEFORE injecting links so the </body> anchor exists.
        html_content = ensure_complete_html(html_content)
        html_content = inject_internal_links(html_content, product["id"],
                                             task["city_slug"], task["lang"])

        if not is_valid_page(html_content):
            return {"status": "error", "slug": page_slug,
                    "error": "incomplete/invalid HTML — not saved"}

        prep["file_path"].write_text(html_content, encoding="utf-8")
        save_page_record(page_slug, product["id"], task["city_slug"],
                         task["country_code"], task["lang"], task["template_id"],
                         str(prep["file_path"]), tokens)
        return {
            "status": "generated",
            "slug": page_slug,
            "file": str(prep["file_path"]),
            "tokens": tokens,
            "city": task["city_name"],
            "product": product["name_ru"],
            "lang": task["lang"],
        }
    except Exception as exc:
        return {"status": "error", "slug": page_slug, "error": str(exc)}


def generate_one_page(task: dict) -> dict:
    """Synchronous path: prepare → call → finalize. Used when batch is off."""
    prep = prepare_task(task)
    if prep["status"] != "ready":
        return prep
    try:
        time.sleep(SLEEP_BETWEEN_CALLS + random.uniform(0, 0.5))
        # 9000 tokens: a full geo page (head + 6 cards + cert table + FAQ + CTA
        # + schema) runs ~5–7k tokens; lower caps truncated long pages mid-tag.
        html_content, tokens = _shared_call_claude(
            prompt=prep["user"], system=prep["system"],
            model=GEO_MODEL, max_tokens=9000, effort=GEO_EFFORT)
        return finalize_page(prep, html_content, tokens)
    except Exception as exc:
        return {"status": "error", "slug": prep["page_slug"], "error": str(exc)}


def generate_batch(tasks: list) -> list:
    """Batch path: all pages in one Message Batch (50% off, cache-friendly)."""
    from claude_client import call_claude_batch

    preps, results = {}, []
    items = []
    for task in tasks:
        prep = prepare_task(task)
        if prep["status"] != "ready":
            results.append(prep)
            continue
        cid = prep["page_slug"][:64]  # custom_id is capped at 64 chars
        preps[cid] = prep
        items.append({
            "custom_id": cid,
            "prompt": prep["user"],
            "system": prep["system"],
            "model": GEO_MODEL,
            # 9000: headroom above the instructed 600-800 words so the model
            # closes </html> instead of truncating mid-tag at the cap.
            "max_tokens": 9000,
            # Templated city landings don't need deep reasoning — medium cuts
            # output-token spend ($15/MTok) without touching the page spec.
            "effort": GEO_EFFORT,
        })

    if not items:
        return results

    try:
        batch_out = call_claude_batch(items)
    except Exception as exc:
        print(f"⚠️  batch failed ({exc}) — falling back to sync generation",
              file=sys.stderr)
        return results + [generate_one_page(p["task"]) for p in preps.values()]

    for cid, prep in preps.items():
        res = batch_out.get(cid)
        if res is None:
            results.append({"status": "error", "slug": prep["page_slug"],
                            "error": "missing from batch results"})
        elif res.get("ok"):
            results.append(finalize_page(prep, res["text"], res.get("tokens", 0)))
        else:
            results.append({"status": "error", "slug": prep["page_slug"],
                            "error": res.get("error", "batch item failed")})
    return results


# ── Task queue builder ────────────────────────────────────────────────────────
def build_task_queue(
    mode: str = "russia",
    max_pages: int = 100,
    langs: list[str] | None = None,
    product_ids: list[str] | None = None,
    focus_products: list[str] | None = None,
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
                # One canonical page per product×city. Template variants
                # (-b/-c/-d/-f) were self-canonicalizing duplicates with 0 clicks
                # in GSC, so we only ever emit the base template "A".
                template_id = "A"
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
                        template_id = "A"  # base only — no duplicate variants
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

    if focus_products:
        rank = {pid: i for i, pid in enumerate(focus_products)}
        tasks.sort(key=lambda t: rank.get(t["product"]["id"], len(rank) + 1))

    filtered = []
    for task in tasks:
        prod_slug = task["product"].get(f"slug_{task['lang']}", task["product"].get("slug_ru", task["product"]["id"]))
        page_slug = f"{prod_slug}-{task['city_slug']}-{task['lang']}-{task['template_id'].lower()}"
        if page_exists(page_slug):
            continue
        # Also skip if the HTML file already exists on disk (legacy pages
        # generated before geo_pages DB existed) — backfill the DB record
        # so we never regenerate or waste a daily slot on them.
        tmpl = task["template_id"]
        fname = f"{prod_slug}-{task['city_slug']}.html" if tmpl == "A" \
            else f"{prod_slug}-{task['city_slug']}-{tmpl.lower()}.html"
        disk_path = PUBLIC / task["output_dir"] / fname
        if disk_path.exists():
            save_page_record(page_slug, task["product"]["id"], task["city_slug"],
                             task["country_code"], task["lang"], tmpl,
                             str(disk_path), 0)
            continue
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
    parser.add_argument("--ignore-strategy", action="store_true",
                        help="Ignore data/strategy.json brain directives")
    args = parser.parse_args()

    if not DEEPSEEK_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    strat = {} if args.ignore_strategy else load_strategy()
    focus_products = strat.get("focus_products") or None
    if strat.get("geo_daily_target") and args.max_pages == MAX_PAGES_PER_RUN:
        try:
            args.max_pages = int(strat["geo_daily_target"])
        except Exception:
            pass
    if strat.get("focus_langs") and args.langs is None:
        args.langs = list(strat["focus_langs"])
    if strat:
        print(f"🧠 Strategy applied: focus={focus_products} langs={args.langs} target={args.max_pages}")

    init_db()

    print(f"🌍 Geo Bulk Generator — {TODAY}")
    print(f"   Mode: {args.mode} | Max pages: {args.max_pages} | Workers: {args.workers}")
    print("=" * 60)

    tasks = build_task_queue(
        mode=args.mode,
        max_pages=args.max_pages,
        langs=args.langs,
        product_ids=args.products,
        focus_products=focus_products,
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

    # Batch API by default (50% off + cache hits within the batch). Set
    # GEO_BATCH=0 to use the legacy threaded sync path. Tiny runs (<3 pages)
    # are not worth batch polling latency.
    use_batch = os.environ.get("GEO_BATCH", "1") != "0" and len(tasks) >= 3

    def handle(result):
        nonlocal generated, errors, total_tokens
        status = result.get("status")
        if status == "generated":
            generated += 1
            total_tokens += result.get("tokens", 0)
            new_urls.append(f"https://pepperoni.tatar/{result.get('output_dir', 'geo')}/{result['slug']}/")
            if generated % 10 == 0 or generated <= 5:
                print(f"  ✓ [{generated}] [{result.get('lang','')}] "
                      f"{result.get('product','')} / {result.get('city','')}")
        elif status == "error":
            errors += 1
            print(f"  ✗ ERROR: {result.get('slug')} — {result.get('error', '')[:100]}", file=sys.stderr)
        # skipped/already_exists — silent

    if use_batch:
        print("📦 Mode: Message Batches API (−50% cost)")
        for result in generate_batch(tasks):
            handle(result)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(generate_one_page, task): task for task in tasks}
            for future in as_completed(futures):
                handle(future.result())

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
