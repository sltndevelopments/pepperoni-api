#!/usr/bin/env python3
"""
Bulk Geo Page Generator — Pepperoni Tatar
Generates 100–200 unique geo-targeted landing pages per run.
Products × Cities × Page-types × Languages × Templates = millions of unique combinations.
Certifications: Halal DUM RT, HACCP, ISO 22000:2018, TR CU 021/2011.
"""

from __future__ import annotations

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
from importlib import import_module as _im
try:
    _cc = _im("claude_client")
    CONTENT_MODEL = _cc.CONTENT_MODEL   # haiku by default, env-overridable
except Exception:
    CONTENT_MODEL = "claude-haiku-4-5-20251001"

# GEO_MODEL: override per-run (e.g. for A/B tests). Defaults to CONTENT_MODEL.
GEO_MODEL = os.environ.get("GEO_MODEL", "").strip() or CONTENT_MODEL
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
from claude_client import call_claude as _shared_call_claude, today_spend_usd, ANTHROPIC_API_KEY  # noqa: E402


def call_claude(prompt: str, max_tokens: int = 3000) -> tuple[str, int]:
    """Call content model via shared client. Returns (text, tokens_used)."""
    return _shared_call_claude(prompt=prompt, model=GEO_MODEL, max_tokens=max_tokens)


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

# For markets where export docs are still in process (docs_status=in_process):
# We have full Russian certs; export-market certification is being arranged.
# Pages should say we're ready to cooperate, NOT claim ready export certs.
CERT_BLOCK_RU_IN_PROCESS = (
    "**Сертификаты на производстве: Халяль (ДУМ РТ №614A/2024), HACCP, "
    "ISO 22000:2018, ТР ТС 021/2011. Продукция без нитрита натрия, без ГМО. "
    "Экспортная документация: в процессе оформления. "
    "Открыты к переговорам и пилотным поставкам.**"
)
CERT_BLOCK_EN_IN_PROCESS = (
    "**On-site certifications: Halal (DUM RT #614A/2024), HACCP, ISO 22000:2018. "
    "No sodium nitrite. Clean label — no GMO. "
    "Export documentation: being arranged for your market. "
    "Open to negotiations and pilot shipments.**"
)
CERT_BLOCK_AR_IN_PROCESS = (
    "**الشهادات في المصنع: حلال (DUM RT رقم 614A/2024)، HACCP، ISO 22000:2018. "
    "بدون نيتريت الصوديوم، بدون معدلات وراثية. "
    "وثائق التصدير: قيد الإعداد لأسواقكم. "
    "مستعدون للتفاوض وشحنات تجريبية.**"
)

# Arabic product name overrides — prevents the LLM from defaulting to لحم خنزير
# when it sees "ham" / "ветчина". Keys are matched against product slug_ru / name_ru
# (lowercase), values are the correct halal Arabic product names.
_AR_PRODUCT_NAMES: dict[str, str] = {
    "vetchina":           "جامبون بقري حلال",
    "ветчина":            "جامبون بقري حلال",
    "ham":                "جامبون بقري حلال",
    "ham-halal":          "جامبون بقري حلال",
    "djambon":            "جامبون بقري حلال",
    "бекон":              "بيكون بقري حلال",
    "bacon":              "بيكون بقري حلال",
    "halal-bacon":        "بيكون بقري حلال",
    "беконный":           "بيكون بقري حلال",
    # sujuk / hot-dog sausages — already correct name, listed for completeness
    "sujuk":              "سجق حلال",
    "sosiki":             "نقانق حلال",
    "sosiki-dlya-hotdog": "نقانق هوت دوغ حلال",
    "pepperoni":          "بيبروني حلال",
    "kazylyk":            "كازيليك (نقانق خيل حلال)",
}


def _ar_product_name(product: dict) -> str:
    """Return the safe Arabic product name, avoiding the ham→خنزير trap."""
    slug = (product.get("slug_ru") or product.get("id") or "").lower()
    name_ru = (product.get("name_ru") or "").lower()
    for key, ar_name in _AR_PRODUCT_NAMES.items():
        if key in slug or key in name_ru:
            return ar_name
    # Fallback: use existing AR name if present, else transliterated RU name
    return product.get("name_ar") or product.get("name_en") or product.get("name_ru", "")


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
        "system_note": (
            "Write in Arabic (right-to-left). Include English version at the end.\n"
            "CRITICAL: NEVER write خنزير / لحم خنزير / لحوم خنزير / لحم الخنزير "
            "as a product name, JSON-LD description, heading, or any positive context. "
            "Ham (ветчина) in Arabic = جامبون بقري حلال ONLY. "
            "Bacon (бекон) in Arabic = بيكون بقري حلال ONLY. "
            "Mentioning خنزير is allowed ONLY in explicit negation: "
            "لا خنزير / بدون خنزير / خالٍ من الخنزير."
        ),
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


def build_system_prompt(lang: str, docs_status: str = "ready") -> str:
    """Stable per-language instruction block.

    Sent as the `system` parameter so Anthropic prompt caching reuses it across
    every page of the same language in a run (cache reads cost 10% of input).
    Keep page-specific values OUT of here — they go in the user prompt.

    docs_status='in_process': markets where export certs are still being arranged.
    Cert block is honest — no overclaiming of completed export certification.
    """
    from brand_system import brand_block
    lang_cfg = LANG_PROMPTS.get(lang, LANG_PROMPTS["ru"])

    # Honest cert block: never overclaim for markets where docs are in-process
    if docs_status == "in_process":
        if lang == "ar":
            cert_block = CERT_BLOCK_AR_IN_PROCESS
        elif lang == "ru":
            cert_block = CERT_BLOCK_RU_IN_PROCESS
        else:
            cert_block = CERT_BLOCK_EN_IN_PROCESS
        cert_directive = "СЕРТИФИКАТЫ — упомяни честно (оформление ведётся для этого рынка):"
    else:
        cert_block = lang_cfg["cert_block"]
        cert_directive = "СЕРТИФИКАТЫ (упомяни ВСЕ):"

    return brand_block(lang) + f"""

{lang_cfg['system_note']}

Ты эксперт по B2B продажам халяль мясной продукции. По параметрам из сообщения пользователя пишешь уникальную SEO-оптимизированную HTML landing page для указанных страны и города.

{cert_directive}
{cert_block}

ТРЕБОВАНИЯ К HTML:
1. Верни ТОЛЬКО валидный HTML, начиная с <!DOCTYPE html>
2. Bootstrap 5 (CDN), Яндекс.Метрика и Schema.org JSON-LD
3. Структура (СТРОГО В ЭТОМ ПОРЯДКЕ):
   - <title> с городом и продуктом (60 символов)
   - <meta name="description"> (155 символов)
   - H1 с городом и продуктом
   - БЛОК ОТВЕТ-ПЕРВЫМ (ОБЯЗАТЕЛЬНЫЙ, сразу после H1, ДО вступления):
     <div class="tldr-answer"> ... </div>
     Содержание (~40–60 слов, язык закупщика): что именно поставляем,
     халяль-статус (сертификат), готовность к СТМ/OEM, минимальный объём,
     срок доставки в этот город. Прямой ответ на вопрос «кто и как поставит
     мне X» — без воды, без прилагательных превосходной степени.
     Пример структуры: «[Продукт] — [халяль-сертификат], производство Казань.
     Поставка в [Город] за [срок]. Объём от [X кг/уп.]. СТМ/OEM — да.»
   - Вступление (2-3 предложения) — уникальный контекст города
   - СЕКЦИЯ СЦЕНАРИЯ ПРИМЕНЕНИЯ (ОБЯЗАТЕЛЬНАЯ):
     <section class="use-scenario"> ... </section>
     Как продукт используется в реальном процессе клиента (пиццерия, HoReCa,
     производство, АЗС, ритейл). На основе USP/differentiator из параметров.
     Язык закупщика, не розницы: «при запекании», «в роллерном гриле»,
     «при нарезке слайсером», «в тесте выпечки», «при хранении на складе».
     2–4 конкретных тезиса — без превосходных степеней.
   - Блок преимуществ (6 карточек) — конкретные цифры и факты
   - Блок сертификатов (только те, что указаны выше — не выдумывай лишних)
   - FAQ блок (5 вопросов специфичных для этого города/региона)
   - CTA секция с формой заявки (имя, компания, телефон, email, сообщение)
   - Блок доставки в указанный город
4. Schema.org JSON-LD: LocalBusiness + Product + FAQPage + BreadcrumbList
   ЦЕНА В JSON-LD: указывай offers/price ТОЛЬКО если цена передана в параметрах
   продукта (поле price). Если цены нет — НЕ ДОБАВЛЯЙ offers/price вообще.
   НИКОГДА не выдумывай цену, availability="InStock" без реальных данных.
5. Стиль: профессиональный, B2B, акцент на надёжность и сертификаты.
   ЗАПРЕЩЕНО: «лучший в России/мире», «выбирают нас 10+ лет», «поставки в 20+
   стран», «партнёры рекомендуют», «пиццерия увеличила продажи» —
   любые непроверяемые превосходные claims → нарушение. Используй цифры
   только если они переданы в параметрах продукта.
   ЗАПРЕЩЁН заголовок-секция «Почему выбирают нас» / «Why choose us» / «Почему мы» —
   это шаблонный суперлатив-контейнер. Замени на конкретный заголовок с фактом:
   «Халяль-сертификат ДУМ РТ», «Состав без нитрита натрия», «Формат для пиццерий».
   ЗАПРЕЩЁН класс region-claim'ов: «[Город/регион] — центр/столица/лидер/признанный
   центр/крупнейший рынок/активно развивающийся хаб [отрасли]» — это
   непроверяемые оценочные суперлативы о регионе. Вместо них: нейтральный
   географический факт («г. [Город], логистика — [срок из данных]») или контекст
   спроса из переданных параметров города. Распространяется на все города и регионы.
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

    # For AR pages use the safe halal Arabic product name to prevent the
    # "ham / ветчина → لحم خنزير" semantic trap in the LLM.
    if lang == "ar":
        product_name = _ar_product_name(product)
    else:
        product_name = product.get("name_ru", product.get("name_en", ""))
    usp = product.get("usp_ru", product.get("usp_en", ""))
    keywords = " | ".join(product.get("keywords_ru", product.get("keywords_en", [])))
    differentiator = product.get("differentiator", "")

    # Verified, data-rich scenario angles — no fake reviews, no unverifiable superlatives.
    # Removed: «отзывы партнёров из этого региона» (fake reviews — invariant no-fake-reviews),
    #          «выбирают нас 10+ лет», «поставки в 20+ стран», «кейс: пиццерия увеличила продажи»
    #          (unverifiable superiority claims — brand rule «no superlatives without evidence»).
    random_angle = random.choice([
        "технология производства без нитрита натрия — состав и процесс",
        "пригодность под оборудование: роллерный гриль, слайсер, конвекционная печь",
        "процесс СТМ/OEM-разработки: от ТЗ до серийного производства под вашим брендом",
        "специфика халяль-сертификации: что проверяет ДУМ РТ на производстве",
        "логистика и хранение: температурный режим, срок годности, условия транспортировки",
        "специфика фасовки и нарезки под разные форматы HoReCa и ритейл",
        "сырьё: говядина и курица халяль — трейсабилити и документация поставщиков",
        "контроль качества на производстве: HACCP-точки, входной контроль сырья",
    ])

    price_raw = product.get("price_rub") or product.get("price") or ""
    price_line = f"ЦЕНА: {price_raw} руб./кг (EXW Казань)" if price_raw else "ЦЕНА: не передана — НЕ добавляй offers/price в JSON-LD"

    return f"""СТРАНА: {country_name}
ГОРОД: {city_name}

ПРОДУКТ: {product_name}
USP: {usp}
{f'КЛЮЧЕВОЕ ОТЛИЧИЕ: {differentiator}' if differentiator else ''}
{price_line}

КОНТЕКСТ ГОРОДА (справочно для понимания рынка — НЕ цитируй эти числа в тексте как факты, используй как смысловой фон):
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
    """Reject pages that are too broken or missing mandatory GEO-format blocks.

    A page is publishable when:
    - It has a real <head>, a heading, and a closing </html>
    - It contains the mandatory <div class="tldr-answer"> block (ANSWER-FIRST)
    - No leftover git conflict markers
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
    # Mandatory GEO-format: ANSWER-FIRST block must be present
    if 'class="tldr-answer"' not in low and "class='tldr-answer'" not in low:
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

    docs_status = task.get("docs_status", "ready")
    return {
        "status": "ready",
        "task": task,
        "page_slug": page_slug,
        "file_path": file_path,
        "system": build_system_prompt(lang, docs_status=docs_status),
        "user": build_user_prompt(product, task["city_name"], task["city_context"],
                                  lang, template_id, task["country_name"]),
    }


def finalize_page(prep: dict, html_content: str, tokens: int) -> dict:
    """Post-process generated HTML and persist the page.

    Temp-file flow: write to data/tmp/ → reviewer → on pass move to public/;
    on fail/crash delete temp so public/ is never polluted with bad content.
    """
    import shutil as _shutil
    import tempfile as _tmpmod
    task = prep["task"]
    product = task["product"]
    page_slug = prep["page_slug"]
    final_path: Path = prep["file_path"]
    try:
        html_content = clean_html(html_content)
        # Close/repair the tail BEFORE injecting links so the </body> anchor exists.
        html_content = ensure_complete_html(html_content)
        html_content = inject_internal_links(html_content, product["id"],
                                             task["city_slug"], task["lang"])

        if not is_valid_page(html_content):
            return {"status": "error", "slug": page_slug,
                    "error": "incomplete/invalid HTML — not saved"}

        # Write to data/tmp/ first — public/ only gets the file after gate passes.
        tmp_dir = DATA / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / final_path.name
        tmp_path.write_text(html_content, encoding="utf-8")

        # ── Quality gate (synchronous, before git add ever sees the file) ──
        # Fail-closed: any exception in the reviewer = hold = not published.
        try:
            import page_reviewer
            review = page_reviewer.review_page(
                tmp_path,
                meta={"slug": page_slug, "lang": task["lang"],
                      "product": product["name_ru"], "city": task["city_name"]},
            )
        except Exception as _rev_exc:
            # reviewer module itself crashed — treat as hold; delete temp
            tmp_path.unlink(missing_ok=True)
            try:
                import page_reviewer as _pr
                _pr._alert(f"🚨 Рецензент упал (import/call): {_rev_exc}\n"
                           f"Страница {page_slug} удержана.")
                _pr._log(tmp_path, "hold", [], error=str(_rev_exc))
            except Exception:
                pass
            return {"status": "held", "slug": page_slug,
                    "error": f"reviewer crashed: {_rev_exc}"}

        if review["verdict"] != "pass":
            # Temp file already handled (quarantined) by review_page(); ensure it's gone.
            tmp_path.unlink(missing_ok=True)
            return {"status": "quarantined", "slug": page_slug,
                    "reasons": review["reasons"]}

        # Gate passed — move to final public/ destination.
        final_path.parent.mkdir(parents=True, exist_ok=True)
        _shutil.move(str(tmp_path), str(final_path))

        save_page_record(page_slug, product["id"], task["city_slug"],
                         task["country_code"], task["lang"], task["template_id"],
                         str(final_path), tokens)
        return {
            "status": "generated",
            "slug": page_slug,
            "file": str(final_path),
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
        # Daily budget kill switch: stop immediately, don't burn the cap on a
        # pointless per-page sync fallback that would just re-raise.
        if exc.__class__.__name__ == "BudgetExceeded":
            print(f"🛑 {exc}", file=sys.stderr)
            raise
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


# ── Goals-driven market index ─────────────────────────────────────────────────
def _load_market_index() -> list[dict]:
    """Return target markets from goals.json sorted by market_priority (A→D).

    Each entry includes docs_status and content_langs from goals.json (single
    source of truth). Russia (market_group=RU) is excluded — it is scout-driven
    and handled via --mode=russia only.

    Also resolves the matching cities_world entry so we have actual city lists.
    """
    try:
        goals_data = json.loads((DATA / "goals.json").read_text(encoding="utf-8"))
    except Exception:
        return []

    # 2-letter ISO → country entry from cities_world
    world_by_2 = {}
    for c in COUNTRIES_WORLD:
        world_by_2[c["code"].lower()] = c

    # 3-letter ISO (goals.json) → 2-letter ISO (cities_world): heuristic match
    # by country name substring (fast, no external libs).
    def _find_world(goals_entry: dict):
        code3 = goals_entry.get("code", "").lower()
        name  = goals_entry.get("country", "").lower()
        # Direct 2-letter guesses based on known ISO-3166 pairs
        _MAP = {
            "rus": "ru", "kaz": "kz", "kgz": "kg", "uzb": "uz", "tjk": "tj",
            "geo": "ge", "aze": "az", "are": "ae", "sau": "sa", "kwt": "kw",
            "bhr": "bh", "omn": "om", "qat": "qa", "egy": "eg", "yem": "ye",
            "blr": "by", "arm": "am", "mys": "my", "idn": "id", "tur": "tr",
        }
        code2 = _MAP.get(code3)
        if code2 and code2 in world_by_2:
            return world_by_2[code2]
        # Fallback: substring match on name
        for c in COUNTRIES_WORLD:
            cname = (c.get("name_ru") or c.get("name_en") or "").lower()
            if name[:4] in cname or cname[:4] in name:
                return c
        return None

    markets = []
    for c in goals_data.get("countries", []):
        if c.get("market_group") == "RU" or c.get("market_priority") == 0:
            continue  # Russia is scout-driven, not cold-start
        mp = c.get("market_priority")
        if mp is None:
            continue  # legacy entry without priority — skip
        world_entry = _find_world(c)
        markets.append({
            "code":          c.get("code", ""),
            "name":          c.get("country", ""),
            "group":         c.get("market_group", ""),
            "market_priority": mp,
            "docs_status":   c.get("docs_status", "ready"),
            "langs":         c.get("content_langs", ["ru"]),
            "world_entry":   world_entry,  # may be None for markets not in cities_world
        })

    markets.sort(key=lambda m: m["market_priority"])
    return markets


# ── Task queue builder ────────────────────────────────────────────────────────
def build_task_queue(
    mode: str = "coverage",
    max_pages: int = 100,
    langs: list[str] | None = None,
    product_ids: list[str] | None = None,
    focus_products: list[str] | None = None,
) -> list[dict]:
    """Build a prioritized list of page generation tasks.

    mode:
      'coverage' (default) — iterate target markets from goals.json in order
                  A→D (market_priority), never Russia. Languages from goals.
                  Category order from focus_products or default cat_priority.
                  This is the autonomous, brain-directed mode.
      'russia'   — iterate Russian cities (CITIES_RU). Only for scout-driven
                  requests or manual --mode russia runs.
      'world'    — iterate cities_world (all 37 countries, unsorted). Legacy.
      'all'      — Russia + world. Legacy.
    """
    # Category priority order (commercial first) — mirrors coverage_gaps()
    _CAT_PRIORITY = [
        "private-label", "pepperoni", "kolbasnye", "sosiki-hotdog",
        "kotlety-burgery", "vetchina", "kazylyk-premium", "kopchenye",
        "farsh", "toppings-pizza", "pelmeni",
        "vypechka-tatarskaya", "vypechka-klassicheskaya", "sosiski-v-teste",
        "syroje-myaso",
    ]

    def _cat_rank(pid: str) -> int:
        try:
            return _CAT_PRIORITY.index(pid)
        except ValueError:
            return len(_CAT_PRIORITY)

    # Effective product list, optionally filtered and sorted
    products_sorted = sorted(
        [p for p in PRODUCTS if not product_ids or p["id"] in product_ids],
        key=lambda p: _cat_rank(p["id"]),
    )
    if focus_products:
        fp_rank = {pid: i for i, pid in enumerate(focus_products)}
        products_sorted.sort(key=lambda p: fp_rank.get(p["id"], _cat_rank(p["id"]) + len(fp_rank)))

    tasks: list[dict] = []

    def _add_city_tasks(city, country_entry, market_langs, country_code, country_name,
                        docs_status="ready", market_group=""):
        """Emit one task per (product, lang) for a given city."""
        city_ctx = dict(city)
        city_ctx["halal_note"] = city_ctx.get("halal_note_ru", country_entry.get("halal_note_ru", ""))
        city_ctx["delivery"]   = country_entry.get("logistics", "")
        city_ctx["muslim_pct"] = country_entry.get("halal_note_ru", "")[:50]
        city_name = city.get("name_ru", city.get("name_en", city.get("name", "")))
        city_slug_val = city.get("slug", slugify(city_name))
        for lang in market_langs:
            if langs and lang not in langs:
                continue
            lang_cfg = LANG_PROMPTS.get(lang, LANG_PROMPTS.get("ru"))
            if not lang_cfg:
                continue
            for product in products_sorted:
                tasks.append({
                    "product":      product,
                    "city_slug":    city_slug_val,
                    "city_name":    city_name,
                    "city_context": city_ctx,
                    "lang":         lang,
                    "template_id":  "A",
                    "country_code": country_code,
                    "country_name": country_name,
                    "output_dir":   lang_cfg["output_dir"],
                    "docs_status":  docs_status,
                    "market_group": market_group,
                })

    if mode == "coverage":
        # Primary mode: markets in A→D order from goals.json
        for market in _load_market_index():
            world_entry = market.get("world_entry")
            if not world_entry:
                # Market in goals.json but no cities_world entry: create a
                # single representative task using the country capital.
                # The city_context will be sparse — generator uses country name.
                synthetic_city = {
                    "name_ru": market["name"],
                    "name_en": market["name"],
                    "slug":    slugify(market["name"]),
                    "population": "", "horeca": "", "halal_note_ru": "",
                    "delivery": "", "muslim_pct": "",
                }
                synthetic_country = {"halal_note_ru": "", "logistics": ""}
                _add_city_tasks(
                    synthetic_city, synthetic_country,
                    market["langs"],
                    market["code"], market["name"],
                    docs_status=market["docs_status"],
                    market_group=market["group"],
                )
                continue
            for city in world_entry.get("cities", []):
                _add_city_tasks(
                    city, world_entry,
                    market["langs"],
                    world_entry["code"], world_entry.get("name_ru", world_entry.get("name_en", "")),
                    docs_status=market["docs_status"],
                    market_group=market["group"],
                )

    if mode in ("russia", "all"):
        for city in CITIES_RU:
            _add_city_tasks(
                city, {},
                ["ru"],
                "ru", "Россия",
                docs_status="ready",
                market_group="RU",
            )

    if mode in ("world", "all"):
        for country in COUNTRIES_WORLD:
            country_langs = country.get("langs", ["ru"])
            for city in country.get("cities", []):
                _add_city_tasks(
                    city, country,
                    country_langs,
                    country["code"], country.get("name_ru", country.get("name_en", "")),
                    docs_status="ready",
                    market_group="",
                )

    # Dedup: filter already-existing pages, cap at max_pages
    filtered: list[dict] = []
    seen_slugs: set[str] = set()
    for task in tasks:
        lang = task["lang"]
        product = task["product"]
        prod_slug = product.get(f"slug_{lang}", product.get("slug_ru", product["id"]))
        page_slug = f"{prod_slug}-{task['city_slug']}-{lang}-{task['template_id'].lower()}"
        if page_slug in seen_slugs:
            continue
        seen_slugs.add(page_slug)
        if page_exists(page_slug):
            continue
        tmpl = task["template_id"]
        fname = (f"{prod_slug}-{task['city_slug']}.html" if tmpl == "A"
                 else f"{prod_slug}-{task['city_slug']}-{tmpl.lower()}.html")
        disk_path = PUBLIC / task["output_dir"] / fname
        if disk_path.exists():
            save_page_record(page_slug, product["id"], task["city_slug"],
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
    parser.add_argument("--mode",
                        choices=["coverage", "russia", "world", "all"],
                        default="coverage",
                        help=(
                            "coverage (default): priority markets A→D from goals.json; "
                            "russia: Russian cities only (scout-driven); "
                            "world/all: legacy city-grid iteration"
                        ))
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

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    strat = {} if args.ignore_strategy else load_strategy()
    focus_products = strat.get("focus_products") or None
    # Quality mode: geo_daily_target == 0 means STOP — generate no new geo pages
    # regardless of any --max-pages passed by cron/worker.
    if not args.ignore_strategy and str(strat.get("geo_daily_target", "")).strip() == "0":
        print("🧠 Strategy: geo_daily_target=0 (quality mode) — пропускаю гео-генерацию.")
        return
    if strat.get("geo_daily_target"):
        try:
            # Strategy can only lower the cap, never raise it above the sh-level default.
            # If --max-pages was explicitly passed (≠ env default), honour it as a hard cap.
            strategy_target = int(strat["geo_daily_target"])
            if args.max_pages == MAX_PAGES_PER_RUN:
                # No explicit CLI override — let strategy steer, but cap at 20 minimum safety
                args.max_pages = min(strategy_target, MAX_PAGES_PER_RUN)
            else:
                # Explicit --max-pages was given: strategy can only reduce, not exceed
                args.max_pages = min(args.max_pages, strategy_target)
        except Exception:
            pass
    if strat.get("focus_langs") and args.langs is None:
        args.langs = list(strat["focus_langs"])
    if strat:
        print(f"🧠 Strategy applied: focus={focus_products} langs={args.langs} target={args.max_pages}")

    init_db()

    # ── Per-run bulk budget guard ──────────────────────────────────────────────
    # LLM_BULK_BUDGET_USD caps spend for a single bulk run independently of the
    # daily autonomous cap (LLM_DAILY_BUDGET_USD used by the cron agent).
    # This lets the daily autonomous cap stay tight ($10) while bulk runs can
    # spend more per invocation when explicitly launched by the owner.
    # Set LLM_BULK_BUDGET_USD=0 to disable the per-run cap.
    bulk_budget = float(os.environ.get("LLM_BULK_BUDGET_USD", "0"))
    if bulk_budget > 0:
        run_start_spend_init = today_spend_usd()
        print(f"💰 Bulk budget: ${bulk_budget:.2f} per run | spend so far today: ${run_start_spend_init:.2f}")

    print(f"🌍 Geo Bulk Generator — {TODAY}")
    print(f"   Mode: {args.mode} | Max pages: {args.max_pages} | Workers: {args.workers}")
    print("=" * 60)

    # ── Build task queue ───────────────────────────────────────────────────────
    # Pages are now gated automatically by page_reviewer (fail-closed) inside
    # finalize_page(). No human approval step — the reviewer is the barrier.
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
    quarantined = 0
    errors = 0
    total_tokens = 0
    new_urls = []
    if bulk_budget > 0:
        run_start_spend = today_spend_usd()
    else:
        run_start_spend = 0.0

    # Batch API by default (50% off + cache hits within the batch). Set
    # GEO_BATCH=0 to use the legacy threaded sync path. Tiny runs (<3 pages)
    # are not worth batch polling latency.
    use_batch = os.environ.get("GEO_BATCH", "1") != "0" and len(tasks) >= 3

    def handle(result):
        nonlocal generated, quarantined, errors, total_tokens
        status = result.get("status")
        if status == "generated":
            generated += 1
            total_tokens += result.get("tokens", 0)
            new_urls.append(f"https://pepperoni.tatar/{result.get('output_dir', 'geo')}/{result['slug']}/")
            if generated % 10 == 0 or generated <= 5:
                print(f"  ✓ [{generated}] [{result.get('lang','')}] "
                      f"{result.get('product','')} / {result.get('city','')}")
        elif status in ("quarantined", "held"):
            quarantined += 1
            print(f"  🚧 [{status}] {result.get('slug')} — "
                  f"{'; '.join(result.get('reasons', [result.get('error','?')]))[:100]}")
        elif status == "error":
            errors += 1
            print(f"  ✗ ERROR: {result.get('slug')} — {result.get('error', '')[:100]}", file=sys.stderr)
        # skipped/already_exists — silent

    if use_batch:
        print("📦 Mode: Message Batches API (−50% cost)")
        for result in generate_batch(tasks):
            handle(result)
            if bulk_budget > 0:
                run_spend = today_spend_usd() - run_start_spend
                if run_spend >= bulk_budget:
                    print(f"\n💰 Bulk budget exhausted: ${run_spend:.2f} >= ${bulk_budget:.2f} — stopping.")
                    break
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(generate_one_page, task): task for task in tasks}
            for future in as_completed(futures):
                handle(future.result())
                if bulk_budget > 0:
                    run_spend = today_spend_usd() - run_start_spend
                    if run_spend >= bulk_budget:
                        print(f"\n💰 Bulk budget exhausted: ${run_spend:.2f} >= ${bulk_budget:.2f} — stopping.")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

    # Update sitemap
    if new_urls:
        update_sitemap(new_urls)

    print(f"\n{'='*60}")
    print(f"✅ Generated: {generated} pages")
    print(f"🚧 Quarantined/held by gate: {quarantined}")
    print(f"❌ Errors: {errors}")
    print(f"🔤 Total tokens used: {total_tokens:,}")
    print(f"📍 New sitemap URLs: {len(new_urls)}")


if __name__ == "__main__":
    main()
