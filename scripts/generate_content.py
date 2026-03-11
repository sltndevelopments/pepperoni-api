#!/usr/bin/env python3
"""
Generate SEO content via Claude API based on opportunities from DB.
Actions:
  - new geo page         → public/geo/{slug}.html
  - blog article         → public/blog/{slug}.html
  - title/meta update    → patch existing HTML file <title> and <meta description>

Env: CLAUDE_API_KEY
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db
from claude_client import call_claude as _claude

PUBLIC_DIR   = Path(__file__).parent.parent / "public"
MAX_TOKENS   = 4096
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "3"))   # per run
MAX_TITLES   = int(os.environ.get("MAX_TITLES",   "10"))  # per run

# ---------- Claude API ----------

def call_claude(system: str, prompt: str) -> tuple[str, int]:
    """Call Claude API via proxy, return (text, tokens_used)."""
    return _claude(prompt, system=system, max_tokens=MAX_TOKENS)


# ---------- Title/Meta updater ----------

def update_title_meta(file_path: Path, new_title: str, new_desc: str) -> bool:
    """Patch <title> and <meta name="description"> in an HTML file."""
    try:
        html = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False

    html = re.sub(r"<title>[^<]*</title>", f"<title>{new_title}</title>", html, count=1)
    html = re.sub(
        r'<meta\s+name=["\']description["\']\s+content=["\'][^"\']*["\']',
        f'<meta name="description" content="{new_desc}"',
        html, count=1, flags=re.IGNORECASE,
    )
    file_path.write_text(html, encoding="utf-8")
    return True


def get_page_title(file_path: Path) -> str:
    try:
        html = file_path.read_text(encoding="utf-8")
        m = re.search(r"<title>([^<]+)</title>", html)
        return m.group(1) if m else ""
    except Exception:
        return ""


# ---------- Geo page generator ----------

GTM_SNIPPET = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-XXXXXXX');</script>
<!-- End Google Tag Manager -->"""


def generate_geo_page(query: str, slug: str, conn) -> tuple[Path, int]:
    """Ask Claude to write a full geo landing page, save it, return (path, tokens)."""

    # Extract city/region hint from slug
    city_hint = slug.replace("pepperoni-", "").replace("kotlety-dlya-burgerov-", "").replace("-", " ").strip()

    system = (
        "Ты опытный SEO-копирайтер для B2B сайта производителя халяль колбасных изделий "
        "'Казанские Деликатесы' (pepperoni.tatar). "
        "Пишешь лаконичный, убедительный текст на русском языке для оптовых покупателей. "
        "Без воды, с конкретными выгодами: халяль сертификат, HACCP, ISO, доставка по РФ и СНГ, "
        "Private Label (СТМ), пепперони из говядины/курицы/конины, разные диаметры."
    )

    prompt = f"""Напиши HTML-страницу для геозапроса «{query}» (город/регион: {city_hint}).
Верни ТОЛЬКО полный валидный HTML5, без объяснений.

Требования к HTML:
- <!DOCTYPE html> с lang="ru"
- <head>: charset, viewport, оптимизированный <title> (до 65 символов), <meta description> (до 160 символов), canonical
- Schema.org LocalBusiness + Product в JSON-LD
- Один <h1> содержащий запрос «{query}»
- Секции: краткий введение, преимущества (ul/li), ассортимент, условия поставки, CTA кнопка «Получить прайс-лист» с tel:+78005509076
- В конце breadcrumbs (microdata)
- Футер: © 2022–{datetime.now().year} Казанские Деликатесы, г. Казань, ул. Мусина 83А, +7(800)550-90-76, info@kazandelikates.ru
- Подключить Bootstrap 5 CDN для базовой стилизации
- НЕ упоминать свинину нигде (ни в тексте, ни в коде)
- Ссылка «← Все продукты» на /

Slug для canonical: /geo/{slug}
"""

    html, tokens = call_claude(system, prompt)

    # Inject GTM after <body>
    html = html.replace("<body>", f"<body>\n{GTM_SNIPPET}", 1)
    if "<body>" not in html and "<body " in html:
        html = re.sub(r"<body([^>]*)>", lambda m: f"<body{m.group(1)}>\n{GTM_SNIPPET}", html, count=1)

    out_path = PUBLIC_DIR / "geo" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- Blog article generator ----------

def generate_article(query: str, slug: str, conn) -> tuple[Path, int]:
    """Generate an informational blog article in /public/blog/."""

    system = (
        "Ты эксперт в мясной промышленности, SEO-автор для сайта pepperoni.tatar. "
        "Пишешь экспертные, полезные статьи на русском языке для профессионалов HoReCa и оптовых покупателей. "
        "Статьи без воды, с реальными фактами, халяль тематика, без упоминания свинины."
    )

    prompt = f"""Напиши информационную SEO-статью по запросу «{query}».
Верни ТОЛЬКО полный валидный HTML5, без объяснений.

Требования:
- <!DOCTYPE html> с lang="ru"
- <head>: charset, viewport, оптимизированный <title>, <meta description>, canonical /blog/{slug}
- Один <h1> с ключевым запросом
- Структура: введение (100 слов), 3-5 подзаголовков H2, практические советы, заключение с CTA
- Schema.org Article в JSON-LD (datePublished = {datetime.now().strftime("%Y-%m-%d")})
- Bootstrap 5 CDN
- Длина текста: 600-900 слов
- Ссылка на /pepperoni и /pepperoni-optom как contextual links
- Футер с контактами
"""

    html, tokens = call_claude(system, prompt)
    out_path = PUBLIC_DIR / "blog" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- Title/H1 rewriter ----------

PAGE_SLUG_MAP = {
    "https://pepperoni.tatar/":                    "index.html",
    "https://pepperoni.tatar/pepperoni":           "pepperoni.html",
    "https://pepperoni.tatar/pepperoni-optom":     "pepperoni-optom.html",
    "https://pepperoni.tatar/pepperoni-dlya-pizzerii": "pepperoni-dlya-pizzerii.html",
    "https://pepperoni.tatar/pepperoni-dlya-horeca":   "pepperoni-dlya-horeca.html",
    "https://pepperoni.tatar/pepperoni-private-label": "pepperoni-private-label.html",
    "https://pepperoni.tatar/pepperoni-v-narezke":     "pepperoni-v-narezke.html",
}

def process_low_ctr(opportunities: list, conn) -> int:
    """Rewrite titles/meta for pages with low CTR."""
    count = 0
    now = datetime.now(timezone.utc).isoformat()

    for opp in opportunities[:MAX_TITLES]:
        page_url = opp["page"] or ""
        query    = opp["query"]

        rel_path = None
        if page_url in PAGE_SLUG_MAP:
            rel_path = PUBLIC_DIR / PAGE_SLUG_MAP[page_url]
        elif "/geo/" in page_url:
            slug = page_url.split("/geo/")[-1].rstrip("/")
            rel_path = PUBLIC_DIR / "geo" / f"{slug}.html"
        elif "/blog/" in page_url:
            slug = page_url.split("/blog/")[-1].rstrip("/")
            rel_path = PUBLIC_DIR / "blog" / f"{slug}.html"

        if not rel_path or not rel_path.exists():
            continue

        current_title = get_page_title(rel_path)
        system = (
            "Ты SEO-специалист. Улучшаешь <title> и <meta description> для B2B сайта "
            "производителя халяль мясных деликатесов 'Казанские Деликатесы' (pepperoni.tatar). "
            "Цель — повысить CTR в поиске. Пиши на русском языке."
        )
        prompt = f"""Целевой запрос: «{query}»
Текущий title: «{current_title}»
CTR страницы низкий (< 3%). Позиция: {opp["position"]:.1f}.

Верни JSON в формате:
{{"title": "новый title (до 65 символов)", "description": "новый meta description (до 160 символов)"}}

Только JSON, без комментариев. Включи запрос, USP (халяль, оптом, б/с, ХАССП), CTA-слово."""

        try:
            raw, tokens = call_claude(system, prompt)
            # Extract JSON from response
            m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if not m:
                continue
            data = json.loads(m.group(0))
            new_title = data.get("title", "")
            new_desc  = data.get("description", "")
            if not new_title:
                continue

            ok = update_title_meta(rel_path, new_title, new_desc)
            if ok:
                conn.execute(
                    """INSERT INTO generated_content
                       (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (now, "title_update", "ru", query, page_url, str(rel_path),
                     new_title, "published", CLAUDE_MODEL, tokens),
                )
                conn.execute(
                    "UPDATE opportunities SET status='done', notes=? WHERE id=?",
                    (f"title→{new_title[:40]}", opp["id"]),
                )
                count += 1
                print(f"  ✏️  title updated: {rel_path.name} → {new_title[:50]}")
        except Exception as ex:
            print(f"  ⚠️  title update failed ({query}): {ex}", file=sys.stderr)

    return count


def process_new_pages(opportunities: list, conn) -> int:
    """Generate new geo pages or blog articles for high-impression queries without a page."""
    count = 0
    now = datetime.now(timezone.utc).isoformat()

    for opp in opportunities[:MAX_ARTICLES]:
        query = opp["query"]
        ql    = query.lower()

        # Decide page type
        geo_cities = [
            "москва", "спб", "санкт-петербург", "казань", "уфа", "екатеринбург",
            "сочи", "краснодар", "астрахань", "грозный", "махачкала", "дагестан",
            "ямало", "янао", "казахстан", "узбекистан", "беларусь", "армения",
            "азербайджан", "кыргызстан",
        ]
        is_geo      = any(city in ql for city in geo_cities)
        is_article  = any(kw in ql for kw in ["что такое", "как выбрать", "зачем", "почему", "виды", "состав", "калорийн"])

        # Build slug
        slug = re.sub(r"[^a-zа-яё0-9\s-]", "", ql, flags=re.IGNORECASE)
        slug = re.sub(r"\s+", "-", slug.strip())
        # Transliterate common letters
        translit = {
            "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh",
            "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
            "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts",
            "ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
        }
        slug_en = "".join(translit.get(c, c) for c in slug.lower())
        slug_en = re.sub(r"-+", "-", slug_en).strip("-")[:60]

        try:
            if is_geo:
                out_path, tokens = generate_geo_page(query, slug_en, conn)
                page_type = "geo_page"
            elif is_article:
                out_path, tokens = generate_article(query, slug_en, conn)
                page_type = "article"
            else:
                # Default: quick_growth → generate article
                out_path, tokens = generate_article(query, slug_en, conn)
                page_type = "article"

            conn.execute(
                """INSERT INTO generated_content
                   (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, page_type, "ru", query, slug_en, str(out_path),
                 query, "published", CLAUDE_MODEL, tokens),
            )
            conn.execute(
                "UPDATE opportunities SET status='done', notes=? WHERE id=?",
                (f"generated: {out_path.name}", opp["id"]),
            )
            count += 1
            print(f"  📄 Generated {page_type}: {out_path.name} ({tokens} tokens)")
        except Exception as ex:
            print(f"  ⚠️  Generation failed ({query}): {ex}", file=sys.stderr)

    return count


# ---------- Main ----------

def main():
    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    init_db()
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    # Get pending opportunities
    low_ctr_opps  = conn.execute(
        "SELECT * FROM opportunities WHERE type='low_ctr'  AND status='new' ORDER BY impressions DESC LIMIT ?",
        (MAX_TITLES,),
    ).fetchall()

    new_page_opps = conn.execute(
        "SELECT * FROM opportunities WHERE type IN ('quick_growth','new_query') AND status='new' ORDER BY impressions DESC LIMIT ?",
        (MAX_ARTICLES,),
    ).fetchall()

    print(f"🤖 Processing {len(low_ctr_opps)} low-CTR and {len(new_page_opps)} new-page opportunities …")

    titles_done = process_low_ctr(list(low_ctr_opps), conn)
    pages_done  = process_new_pages(list(new_page_opps), conn)

    conn.commit()
    conn.close()
    print(f"✅ Done — titles: {titles_done}, new pages: {pages_done}")


if __name__ == "__main__":
    main()
