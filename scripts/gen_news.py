#!/usr/bin/env python3
"""
Generate news articles for /news/ section.
Static news + Claude-assisted generation for fresh content.

Schema.org NewsArticle for Google News eligibility.
Run once/week or manually.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db
from claude_client import call_claude as _claude, CLAUDE_API_KEY, DEFAULT_MODEL as CLAUDE_MODEL

PUBLIC_DIR = Path(__file__).parent.parent / "public"
NEWS_DIR   = PUBLIC_DIR / "news"
TODAY      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YEAR       = datetime.now().year

FOOTER = f"""<footer class="bg-dark text-white py-4 mt-5">
  <div class="container text-center">
    <p class="mb-1">© 2022–{YEAR} Казанские Деликатесы | Производство халяль колбасных изделий</p>
    <p class="mb-1">г. Казань, ул. Мусина 83А | <a href="tel:+78005509076" class="text-white">+7(800)550-90-76</a></p>
    <p class="mb-0"><a href="/" class="text-white me-3">Главная</a><a href="/news/" class="text-white me-3">Новости</a><a href="/pepperoni-optom" class="text-white">Оптом</a></p>
  </div>
</footer>"""

# Predefined news topics (real-looking company news)
NEWS_TOPICS = [
    {
        "slug": "novaya-lineyка-pepperoni-konina-2025",
        "title": "Казанские Деликатесы запустили новую линейку пепперони из конины",
        "desc": "Компания расширяет ассортимент: пепперони из конины теперь доступен в диаметрах 40, 50 и 60 мм для оптовых поставок.",
        "date": "2025-11-15",
        "topic": "Запуск линейки пепперони из конины: новые диаметры, упаковка, доступность для оптовых клиентов HoReCa",
    },
    {
        "slug": "eksport-kazahstan-2025",
        "title": "Начались регулярные поставки халяль продукции в Казахстан",
        "desc": "Казанские Деликатесы открыли регулярный экспортный маршрут в Казахстан: пепперони, котлеты для бургеров и сосиски.",
        "date": "2025-12-01",
        "topic": "Начало регулярных экспортных поставок халяль мясной продукции в Казахстан: условия, ассортимент, логистика",
    },
    {
        "slug": "private-label-2026",
        "title": "Казанские Деликатесы предлагают СТМ производство с новыми условиями",
        "desc": "Обновлённые условия Private Label: минимальный тираж снижен, добавлены новые форматы упаковки для ретейла.",
        "date": "2026-01-20",
        "topic": "Обновление условий производства Private Label (СТМ): снижение минимального тиража, новые форматы упаковки",
    },
    {
        "slug": "haccp-audit-2026",
        "title": "Успешно пройден ежегодный аудит HACCP и ISO 22000",
        "desc": "Производство Казанских Деликатесов подтвердило соответствие стандартам HACCP и ISO 22000 по итогам планового аудита.",
        "date": "2026-02-10",
        "topic": "Прохождение ежегодного аудита HACCP и ISO 22000: результаты, подтверждение сертификатов качества",
    },
    {
        "slug": "novyy-assortiment-kotlety-2026",
        "title": "Расширен ассортимент котлет для бургеров: три новых позиции",
        "desc": "Линейка котлет для бургеров пополнилась тремя позициями: говяжья, куриная и микс, все халяль, все под заморозку.",
        "date": "2026-03-01",
        "topic": "Расширение линейки котлет для бургеров: говяжья, куриная, микс — халяль, замороженные, для HoReCa и ретейла",
    },
]


def call_claude(system: str, prompt: str) -> tuple[str, int]:
    return _claude(prompt, system=system, max_tokens=4096)


def generate_news_article(news: dict) -> tuple[Path, int]:
    slug  = news["slug"]
    title = news["title"]
    desc  = news["desc"]
    date  = news["date"]
    topic = news["topic"]

    schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": desc,
        "datePublished": date,
        "dateModified": TODAY,
        "author": {
            "@type": "Organization",
            "name": "Казанские Деликатесы",
            "url": "https://pepperoni.tatar"
        },
        "publisher": {
            "@type": "Organization",
            "name": "Казанские Деликатесы",
            "logo": {
                "@type": "ImageObject",
                "url": "https://pepperoni.tatar/img/logo.png"
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"https://pepperoni.tatar/news/{slug}"
        }
    }, ensure_ascii=False, indent=2)

    system = (
        "Ты PR-менеджер и SEO-копирайтер компании 'Казанские Деликатесы' (pepperoni.tatar). "
        "Пишешь деловые новости о компании для раздела /news/. "
        "Тон: официальный, но живой. Халяль тематика. Без упоминания свинины."
    )
    prompt = f"""Напиши новостную статью для корпоративного сайта.
Тема: {topic}
Дата публикации: {date}

Верни ТОЛЬКО полный валидный HTML5, без объяснений.

Требования:
- <!DOCTYPE html> с lang="ru"
- <head>: charset, viewport, <title> «{title} | Казанские Деликатесы» (до 70 символов), <meta description> «{desc}» (до 160 символов), canonical /news/{slug}
- Schema.org NewsArticle в JSON-LD (вставь этот JSON-LD как есть):
<script type="application/ld+json">
{schema}
</script>
- Bootstrap 5 CDN
- <nav> breadcrumbs: Главная → Новости → {title}
- <h1>: {title}
- <p class="text-muted">Дата: {date}</p>
- 3-4 абзаца текста по теме: {topic}
- 2-3 H2 подзаголовка
- CTA блок: «Хотите стать партнёром? Звоните +7(800)550-90-76»
- Ссылка «← Все новости» на /news/
- Ссылка на /pepperoni-optom в тексте
- Футер с контактами, текст 400-600 слов"""

    html, tokens = call_claude(system, prompt)
    out_path = NEWS_DIR / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


def generate_news_index(articles: list[dict]) -> Path:
    """Generate /news/index.html listing all news articles."""
    items_html = "\n".join(
        f"""<div class="col-md-6 mb-4">
  <div class="card h-100">
    <div class="card-body">
      <p class="text-muted small mb-1">{a['date']}</p>
      <h2 class="h5 card-title"><a href="/news/{a['slug']}">{a['title']}</a></h2>
      <p class="card-text">{a['desc']}</p>
      <a href="/news/{a['slug']}" class="btn btn-outline-danger btn-sm">Читать далее</a>
    </div>
  </div>
</div>"""
        for a in sorted(articles, key=lambda x: x["date"], reverse=True)
    )

    schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Новости Казанские Деликатесы",
        "url": "https://pepperoni.tatar/news/",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "url": f"https://pepperoni.tatar/news/{a['slug']}",
                "name": a["title"]
            }
            for i, a in enumerate(articles)
        ]
    }, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Новости | Казанские Деликатесы — производитель халяль мясных изделий</title>
  <meta name="description" content="Последние новости компании Казанские Деликатесы: новый ассортимент, экспорт, сертификаты, условия поставок.">
  <link rel="canonical" href="https://pepperoni.tatar/news/">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <script type="application/ld+json">{schema}</script>
</head>
<body>
<div class="container mt-4 mb-2">
  <nav aria-label="breadcrumb">
    <ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="/">Главная</a></li>
      <li class="breadcrumb-item active">Новости</li>
    </ol>
  </nav>
  <h1 class="mb-4">Новости компании</h1>
  <div class="row">
    {items_html}
  </div>
</div>
{FOOTER}
</body>
</html>"""

    out_path = NEWS_DIR / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def add_to_sitemap(urls: list[str]):
    sitemap_path = PUBLIC_DIR / "sitemap.xml"
    if not sitemap_path.exists():
        return
    content = sitemap_path.read_text(encoding="utf-8")
    existing = set(re.findall(r"<loc>(.*?)</loc>", content))
    new_entries = []
    for url in urls:
        if url not in existing:
            new_entries.append(
                f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{TODAY}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.5</priority>\n  </url>"
            )
    if new_entries:
        content = content.replace("</urlset>", "\n".join(new_entries) + "\n</urlset>")
        sitemap_path.write_text(content, encoding="utf-8")
        print(f"  ✅ Added {len(new_entries)} news URLs to sitemap")


def main():
    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    init_db()
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()

    print(f"📰 News Generator — {TODAY}")
    count = 0
    new_urls = []

    for news in NEWS_TOPICS:
        slug = news["slug"]
        out_path = NEWS_DIR / f"{slug}.html"

        if out_path.exists():
            print(f"  ⏭️  Already exists: {slug}")
            continue

        try:
            print(f"  📰 {news['title'][:60]}")
            out_path, tokens = generate_news_article(news)
            conn.execute(
                """INSERT INTO generated_content
                   (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, "news_article", "ru", news["topic"][:100], slug,
                 str(out_path), news["title"], "published", CLAUDE_MODEL, tokens),
            )
            new_urls.append(f"https://pepperoni.tatar/news/{slug}")
            count += 1
            print(f"     ✅ {out_path.name} ({tokens} tokens)")
        except Exception as ex:
            print(f"  ⚠️  News failed ({slug}): {ex}", file=sys.stderr)

    # Always regenerate index
    print("\n  📋 Generating news index …")
    index_path = generate_news_index(NEWS_TOPICS)
    print(f"  ✅ {index_path}")
    new_urls.append("https://pepperoni.tatar/news/")

    if new_urls:
        add_to_sitemap(new_urls)

    conn.commit()
    conn.close()
    print(f"\n✅ Generated {count} news articles")


if __name__ == "__main__":
    main()
