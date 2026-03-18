#!/usr/bin/env python3
"""
Generate SEO content via Claude API.

Actions:
  1. Schedule mode: 3 RU + 3 EN blog articles/day from predefined topic list
  2. FAQ pages (RU + EN) with FAQPage Schema.org
  3. Comparison pages (beef vs chicken, etc.)
  4. Type+Geo pages (pepperoni-govyadina-moskva, etc.)
  5. Title/meta updates for low-CTR pages
  6. New geo pages from DB opportunities
  7. Product card description updates based on GSC data

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
from claude_client import call_claude as _claude, CLAUDE_API_KEY, DEFAULT_MODEL as CLAUDE_MODEL

PUBLIC_DIR   = Path(__file__).parent.parent / "public"
MAX_TOKENS   = 4096
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "3"))
MAX_TITLES   = int(os.environ.get("MAX_TITLES",   "10"))
MAX_TYPEGEO  = int(os.environ.get("MAX_TYPEGEO",  "3"))
TODAY        = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YEAR         = datetime.now().year

FOOTER_RU = f"""<footer class="bg-dark text-white py-4 mt-5">
  <div class="container text-center">
    <p class="mb-1">© 2022–{YEAR} Казанские Деликатесы | Производство халяль колбасных изделий</p>
    <p class="mb-1">г. Казань, ул. Аграрная, 2 | <a href="tel:+79872170202" class="text-white">+7 987 217-02-02</a> | <a href="mailto:info@kazandelikates.ru" class="text-white">info@kazandelikates.ru</a></p>
    <p class="mb-0"><a href="/" class="text-white me-3">Главная</a><a href="/pepperoni" class="text-white me-3">Пепперони</a><a href="/pepperoni-optom" class="text-white">Оптом</a></p>
  </div>
</footer>"""

FOOTER_EN = f"""<footer class="bg-dark text-white py-4 mt-5">
  <div class="container text-center">
    <p class="mb-1">© 2022–{YEAR} Kazan Delicacies | Halal meat products manufacturer</p>
    <p class="mb-1">Kazan, Musina St. 83A | <a href="tel:+79872170202" class="text-white">+7 987 217-02-02</a> | <a href="mailto:info@kazandelikates.ru" class="text-white">info@kazandelikates.ru</a></p>
    <p class="mb-0"><a href="/en/" class="text-white me-3">Home</a><a href="/en/pepperoni" class="text-white me-3">Pepperoni</a><a href="/pepperoni-optom" class="text-white">Wholesale</a></p>
  </div>
</footer>"""

GTM_SNIPPET = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-XXXXXXX');</script>
<!-- End Google Tag Manager -->"""

# ---------- Schedule topics ----------

BLOG_TOPICS_RU = [
    ("Что такое халяль пепперони: состав, производство, отличия", "chto-takoe-halyal-pepperoni"),
    ("Пепперони из говядины: преимущества для пиццерий и HoReCa", "pepperoni-iz-govyadiny"),
    ("Как выбрать пепперони для пиццерии: руководство для закупщика", "kak-vybrat-pepperoni-dlya-pizzerii"),
    ("Пепперони куриный: характеристики, диаметры, применение", "pepperoni-kuriniy"),
    ("Private Label колбасных изделий: как работает СТМ производство", "private-label-kolbasnyh-izdeliy"),
    ("Пепперони оптом: как найти надёжного поставщика", "pepperoni-optom-postavshchik"),
    ("HACCP и ISO на производстве мясных деликатесов: что это значит", "haccp-iso-myasnoe-proizvodstvo"),
    ("Пепперони из конины: особенности и рынок сбыта", "pepperoni-iz-koniny"),
    ("Экспорт халяль продукции в страны СНГ: Казахстан, Беларусь, Узбекистан", "eksport-halyal-snг"),
    ("Хот-дог сосиски оптом: ассортимент и условия поставки", "sosiki-dlya-hotdog-optom"),
    ("Котлеты для бургеров оптом: как выбрать производителя", "kotlety-dlya-burgerov-optom"),
    ("Халяль сертификация мясной продукции в России", "halyal-sertifikaciya-myasa"),
    ("Как хранить пепперони: температурный режим и сроки", "kak-hranit-pepperoni"),
    ("Замороженные мясные полуфабрикаты для HoReCa: что важно знать", "zamorozhennye-polufarikaty-horeca"),
    ("Пепперони для суши: особенности нарезки и применения", "pepperoni-dlya-sushi"),
    ("Мясные деликатесы из Казани: история и традиции производства", "myasnye-delikatesy-kazan"),
    ("Пепперони миксовый (говядина+курица): состав и применение", "pepperoni-miksoviy"),
    ("Поставки мясных изделий в рестораны: логистика и условия", "postavki-myasnye-restorany"),
    ("Как отличить настоящий халяль продукт от подделки", "kak-otlichit-halyal"),
    ("B2B продажи мясной продукции: как работает оптовый рынок", "b2b-myasnaya-produkciya"),
]

BLOG_TOPICS_EN = [
    ("Halal Pepperoni: Ingredients, Production, and B2B Sourcing Guide", "halal-pepperoni-guide"),
    ("Beef Pepperoni vs Chicken Pepperoni: Key Differences for Buyers", "beef-vs-chicken-pepperoni"),
    ("How to Source Halal Pepperoni for Pizzerias: A Complete Guide", "source-halal-pepperoni-pizzeria"),
    ("Private Label Meat Products: How Contract Manufacturing Works", "private-label-meat-products"),
    ("Halal Certification for Meat Products in Russia: What You Need to Know", "halal-certification-russia"),
    ("Wholesale Pepperoni Supplier from Russia: Export Capabilities", "wholesale-pepperoni-russia-export"),
    ("Hot Dog Sausages Wholesale: Choosing the Right Supplier", "hot-dog-sausages-wholesale"),
    ("Burger Patties Wholesale: Halal Options for HoReCa", "burger-patties-wholesale-halal"),
    ("HACCP and ISO in Meat Production: Quality Assurance Explained", "haccp-iso-meat-production"),
    ("Halal Meat Export to CIS Countries: Kazakhstan, Uzbekistan, Belarus", "halal-meat-export-cis"),
    ("Frozen Meat Semi-Products for HoReCa: Bulk Ordering Guide", "frozen-meat-products-horeca"),
    ("Kazan Delicacies: Halal Meat Producer in Russia Since 2022", "kazan-delicacies-halal-producer"),
    ("Pepperoni for Sushi Rolls: Specifications and Applications", "pepperoni-for-sushi"),
    ("Mixed Pepperoni (Beef+Chicken): Composition and Use Cases", "mixed-pepperoni-beef-chicken"),
    ("Horse Meat Pepperoni: Market, Properties, and Halal Status", "horse-meat-pepperoni"),
    ("B2B Meat Products Supply Chain: How Wholesale Works", "b2b-meat-products-supply"),
    ("How to Store Pepperoni: Temperature, Shelf Life, and Tips", "how-to-store-pepperoni"),
    ("Halal Food Market in Russia: Trends and Opportunities 2025", "halal-food-market-russia"),
    ("Pepperoni Slicing Specifications: Thickness, Diameter Guide", "pepperoni-slicing-specs"),
    ("Meat Products Quality Control: What Buyers Should Check", "meat-products-quality-control"),
]

# ---------- Type+Geo combinations ----------

PRODUCT_TYPES = [
    ("pepperoni-govyadina", "пепперони из говядины", "beef pepperoni"),
    ("pepperoni-kurica",    "пепперони куриный",    "chicken pepperoni"),
    ("pepperoni-konina",    "пепперони из конины",  "horse meat pepperoni"),
    ("pepperoni-miks",      "пепперони микс",       "mixed pepperoni"),
]

GEO_CITIES = [
    ("moskva",       "Москва",       "Moscow"),
    ("spb",          "Санкт-Петербург", "Saint Petersburg"),
    ("kazan",        "Казань",       "Kazan"),
    ("ufa",          "Уфа",          "Ufa"),
    ("ekaterinburg", "Екатеринбург", "Yekaterinburg"),
    ("krasnodar",    "Краснодар",    "Krasnodar"),
    ("sochi",        "Сочи",         "Sochi"),
    ("astrahan",     "Астрахань",    "Astrakhan"),
    ("grozny",       "Грозный",      "Grozny"),
    ("mahachkala",   "Махачкала",    "Makhachkala"),
    ("kazakhstan",   "Казахстан",    "Kazakhstan"),
    ("uzbekistan",   "Узбекистан",   "Uzbekistan"),
    ("belarus",      "Беларусь",     "Belarus"),
]

# ---------- FAQ topics ----------

FAQ_TOPICS = [
    {
        "slug": "faq-pepperoni-halyal",
        "title": "FAQ: Халяль пепперони — частые вопросы покупателей",
        "desc": "Ответы на частые вопросы о халяль пепперони: состав, сертификация, поставки оптом, Private Label.",
        "lang": "ru",
        "questions": [
            ("Из чего делают халяль пепперони?", "Халяль пепперони производится из говядины, курицы или конины без добавления свинины и её производных. Мы используем только сертифицированное халяль сырьё с подтверждёнными документами."),
            ("Есть ли халяль сертификат на продукцию?", "Да, вся продукция Казанских Деликатесов имеет халяль сертификат от аккредитованного органа. Копии сертификатов предоставляются по запросу."),
            ("Какой минимальный заказ при оптовой покупке?", "Минимальный заказ на оптовую поставку — от 100 кг. Для крупных сетей и HoReCa предусмотрены специальные условия."),
            ("Возможно ли производство под СТМ (Private Label)?", "Да, мы выпускаем продукцию под брендом заказчика. Разрабатываем рецептуру, упаковку и маркировку в соответствии с вашими требованиями."),
            ("В каких диаметрах доступен пепперони?", "Доступны диаметры: 40 мм, 50 мм, 60 мм и 75 мм. Нарезка — слайсером или целыми батонами."),
            ("Осуществляете ли вы доставку в регионы и СНГ?", "Да, поставки осуществляются по всей России, а также в Казахстан, Узбекистан, Беларусь, Армению, Азербайджан и Кыргызстан."),
            ("Какие сертификаты качества есть на производстве?", "Производство сертифицировано по стандартам HACCP и ISO 22000. Предоставляем все необходимые ветеринарные документы и декларации соответствия."),
        ]
    },
    {
        "slug": "faq-pepperoni-en",
        "title": "FAQ: Halal Pepperoni — Frequently Asked Questions",
        "desc": "Answers to common questions about halal pepperoni: ingredients, certification, wholesale orders, Private Label.",
        "lang": "en",
        "questions": [
            ("What is halal pepperoni made of?", "Halal pepperoni is made from beef, chicken, or horse meat without any pork or pork derivatives. We use only certified halal raw materials with full documentation."),
            ("Do you have halal certification?", "Yes, all Kazan Delicacies products hold halal certification from an accredited body. Copies of certificates are available upon request."),
            ("What is the minimum order quantity for wholesale?", "Minimum wholesale order is 100 kg. Special terms are available for retail chains and HoReCa businesses."),
            ("Do you offer Private Label production?", "Yes, we manufacture products under your brand. We develop recipes, packaging, and labeling according to your requirements."),
            ("What diameters is pepperoni available in?", "Available diameters: 40mm, 50mm, 60mm, and 75mm. We offer sliced or whole stick formats."),
            ("Do you deliver to CIS countries?", "Yes, we ship across Russia and to Kazakhstan, Uzbekistan, Belarus, Armenia, Azerbaijan, and Kyrgyzstan."),
            ("What quality certifications do you have?", "Our production is certified to HACCP and ISO 22000 standards. We provide all required veterinary documents and conformity declarations."),
        ]
    },
]

# ---------- Comparison topics ----------

COMPARISON_TOPICS = [
    {
        "slug": "pepperoni-govyadina-vs-kurica",
        "title": "Пепперони говяжий vs куриный: в чём разница?",
        "desc": "Сравнение пепперони из говядины и курицы: вкус, состав, цена, применение в пиццерии. Что выбрать для бизнеса?",
        "lang": "ru",
        "h1": "Пепперони говяжий vs куриный: полное сравнение для бизнеса",
        "aspect_a": ("пепперони из говядины", "beef pepperoni"),
        "aspect_b": ("пепперони куриный", "chicken pepperoni"),
    },
    {
        "slug": "halal-pepperoni-comparison",
        "title": "Halal Pepperoni: Beef vs Chicken vs Horse — Full Comparison",
        "desc": "Compare halal pepperoni types: beef, chicken, and horse meat. Taste, price, shelf life, and best use cases for pizzerias and HoReCa.",
        "lang": "en",
        "h1": "Halal Pepperoni Types: Beef vs Chicken vs Horse Meat",
        "aspect_a": ("beef pepperoni", "говяжий пепперони"),
        "aspect_b": ("chicken pepperoni", "куриный пепперони"),
    },
]

# ---------- Sitemap updater ----------

def update_sitemap_lastmod():
    """Update <lastmod> in sitemap.xml based on file modification dates."""
    sitemap_path = PUBLIC_DIR / "sitemap.xml"
    if not sitemap_path.exists():
        return

    content = sitemap_path.read_text(encoding="utf-8")

    def replace_loc_with_lastmod(match):
        url = match.group(1)
        # Map URL to file path
        rel = url.replace("https://pepperoni.tatar", "")
        if not rel or rel == "/":
            rel = "/index.html"
        elif not rel.endswith(".html"):
            rel = rel.rstrip("/") + ".html"

        file_path = PUBLIC_DIR / rel.lstrip("/")
        if file_path.exists():
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            lastmod = mtime.strftime("%Y-%m-%d")
        else:
            lastmod = TODAY

        block = match.group(0)
        if "<lastmod>" in block:
            block = re.sub(r"<lastmod>[^<]+</lastmod>", f"<lastmod>{lastmod}</lastmod>", block)
        else:
            block = block.replace(f"<loc>{url}</loc>", f"<loc>{url}</loc>\n    <lastmod>{lastmod}</lastmod>")
        return block

    new_content = re.sub(
        r"<url>\s*<loc>([^<]+)</loc>.*?</url>",
        replace_loc_with_lastmod,
        content,
        flags=re.DOTALL,
    )

    sitemap_path.write_text(new_content, encoding="utf-8")
    print("✅ sitemap.xml updated with <lastmod> dates")


def add_to_sitemap(urls: list[str]):
    """Append new URLs to sitemap.xml."""
    sitemap_path = PUBLIC_DIR / "sitemap.xml"
    if not sitemap_path.exists():
        return

    content = sitemap_path.read_text(encoding="utf-8")
    existing = set(re.findall(r"<loc>(.*?)</loc>", content))

    new_entries = []
    for url in urls:
        if url not in existing:
            new_entries.append(
                f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{TODAY}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.6</priority>\n  </url>"
            )

    if new_entries:
        content = content.replace("</urlset>", "\n".join(new_entries) + "\n</urlset>")
        sitemap_path.write_text(new_content := content, encoding="utf-8")
        print(f"  ✅ Added {len(new_entries)} URLs to sitemap")


# ---------- Claude caller ----------

def call_claude(system: str, prompt: str) -> tuple[str, int]:
    return _claude(prompt, system=system, max_tokens=MAX_TOKENS)


# ---------- Internal linking helper ----------

def get_related_geo_links(current_slug: str, product_prefix: str, count: int = 4) -> str:
    """Build HTML links to related geo pages."""
    geo_dir = PUBLIC_DIR / "geo"
    links = []
    for f in sorted(geo_dir.glob(f"{product_prefix}*.html")):
        slug = f.stem
        if slug == current_slug:
            continue
        city = slug.replace(product_prefix + "-", "").replace("-", " ").title()
        links.append(f'<a href="/geo/{slug}" class="badge bg-secondary text-decoration-none me-1 mb-1">{city}</a>')
        if len(links) >= count:
            break
    return "\n".join(links)


def inject_internal_links(html: str, current_slug: str) -> str:
    """Inject internal links section before </body>."""
    prefix = re.sub(r"-[^-]+$", "", current_slug)
    links = get_related_geo_links(current_slug, prefix, count=6)
    if not links:
        return html

    section = f"""
<section class="container my-4">
  <h3 class="h6 text-muted">Похожие страницы</h3>
  <div>{links}</div>
</section>"""
    return html.replace("</body>", section + "\n</body>", 1)


# ---------- HTML shell ----------

def html_shell(lang: str, title: str, desc: str, canonical: str, body: str, schema: str = "") -> str:
    footer = FOOTER_RU if lang == "ru" else FOOTER_EN
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="https://pepperoni.tatar{canonical}">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  {schema}
</head>
<body>
{GTM_SNIPPET}
<div class="container mt-4">
  <a href="/" class="text-muted small">← Главная</a>
</div>
{body}
{footer}
</body>
</html>"""


# ---------- Blog article generator (RU) ----------

ARTICLE_CSS = """
:root{--green:#1b7a3d;--green-dark:#145c2e;--green-light:#e8f5e9;--text:#1a1a1a;--muted:#666;--border:#e5e5e5;--radius:10px;--shadow:0 2px 12px rgba(0,0,0,.08)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:var(--text);line-height:1.7;font-size:16px}
a{color:var(--green);text-decoration:none}
a:hover{text-decoration:underline}
.nav{background:#fff;border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100}
.nav__inner{max-width:800px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.nav__logo{font-weight:700;font-size:1.05rem;color:var(--green)}
.nav__links{display:flex;gap:16px;flex-wrap:wrap;font-size:.88rem;color:var(--muted)}
.nav__links a{color:var(--muted)}
.nav__links a:hover{color:var(--green);text-decoration:none}
.article-wrap{max-width:800px;margin:0 auto;padding:40px 20px 60px}
.breadcrumb{font-size:.82rem;color:var(--muted);margin-bottom:24px}
.breadcrumb a{color:var(--muted)}
.breadcrumb span{color:var(--green)}
h1{font-size:clamp(1.5rem,3vw,2rem);font-weight:800;line-height:1.25;margin-bottom:20px;color:var(--text)}
h2{font-size:1.25rem;font-weight:700;margin:36px 0 12px;color:var(--text);border-left:3px solid var(--green);padding-left:12px}
h3{font-size:1.05rem;font-weight:700;margin:24px 0 8px;color:var(--text)}
p{margin-bottom:16px;color:#333}
ul,ol{margin:0 0 16px 24px}
li{margin-bottom:6px;color:#333}
.lead{font-size:1.05rem;color:#444;line-height:1.75;margin-bottom:24px;padding:16px 20px;background:#fff;border-radius:var(--radius);border-left:4px solid var(--green)}
.cta-block{background:var(--green);color:#fff;border-radius:var(--radius);padding:28px 32px;margin:40px 0;text-align:center}
.cta-block h2{color:#fff;border:none;padding:0;margin:0 0 10px;font-size:1.3rem}
.cta-block p{color:rgba(255,255,255,.9);margin-bottom:18px}
.btn-cta{display:inline-block;background:#fff;color:var(--green);font-weight:700;padding:12px 28px;border-radius:8px;font-size:.95rem;transition:all .2s}
.btn-cta:hover{background:var(--green-light);text-decoration:none;transform:translateY(-1px)}
.info-box{background:var(--green-light);border:1px solid #c8e6c9;border-radius:var(--radius);padding:16px 20px;margin:24px 0}
.info-box p{margin:0;color:var(--green-dark);font-size:.92rem}
footer{background:#1a1a1a;color:#aaa;text-align:center;font-size:.82rem;padding:24px 20px;margin-top:48px}
footer a{color:#aaa}
footer a:hover{color:#fff;text-decoration:none}
@media(max-width:600px){.article-wrap{padding:24px 16px 40px}.cta-block{padding:20px 18px}}
"""

def generate_article_ru(topic: str, slug: str, conn) -> tuple[Path, int]:
    system = (
        "Ты эксперт в мясной промышленности, SEO-автор для сайта pepperoni.tatar. "
        "Пишешь экспертные, полезные статьи на русском языке для профессионалов HoReCa и оптовых покупателей. "
        "Статьи без воды, с реальными фактами. Халяль тематика, без упоминания свинины."
    )
    prompt = f"""Напиши информационную SEO-статью по теме: «{topic}».
Верни ТОЛЬКО полный валидный HTML5, без объяснений, без markdown-блоков.

Требования:
- <!DOCTYPE html> с lang="ru"
- <head>: charset, viewport, theme-color="#1b7a3d", оптимизированный <title> (до 65 символов), <meta description> (до 160 символов), canonical https://pepperoni.tatar/blog/{slug}
- Schema.org Article в JSON-LD (datePublished={TODAY}, author="Казанские Деликатесы", publisher org, url=https://pepperoni.tatar/blog/{slug})
- Schema.org BreadcrumbList в JSON-LD
- Google Tag Manager сниппет: (function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f)}})(window,document,'script','dataLayer','GTM-W2Q5S8HF'); и noscript версия
- CSS встроен в <style> тегом — используй ТОЧНО этот CSS без изменений:
{ARTICLE_CSS}
- Структура body:
  <nav class="nav"><div class="nav__inner"><a href="/" class="nav__logo">Казанские Деликатесы</a><div class="nav__links"><a href="/">Каталог</a><a href="/pepperoni">Пепперони</a><a href="/blog">Блог</a><a href="/faq">FAQ</a><a href="/delivery">Доставка</a></div></div></nav>
  <main class="article-wrap">
    breadcrumb: Главная → Блог → [название статьи]
    <h1> с ключевым запросом
    <div class="lead"> — вводный абзац 60-80 слов
    4 секции H2 с содержательным текстом
    <div class="info-box"> — полезный факт или совет
    <div class="cta-block"> — призыв к действию, кнопка <a href="tel:+79872170202" class="btn-cta">+7 987 217-02-02</a>
  </main>
  <footer> © 2022–{YEAR} Казанские Деликатесы · г. Казань, ул. Аграрная, 2 · <a href="tel:+79872170202">+7 987 217-02-02</a> · <a href="/">pepperoni.tatar</a> </footer>
- Текст 700-900 слов
- Контекстные ссылки в тексте: /pepperoni, /pepperoni-optom, /pepperoni-dlya-pizzerii
- НЕ использовать Bootstrap
- НЕ упоминать свинину"""

    html, tokens = call_claude(system, prompt)
    out_path = PUBLIC_DIR / "blog" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- Blog article generator (EN) ----------

def generate_article_en(topic: str, slug: str, conn) -> tuple[Path, int]:
    system = (
        "You are an expert in meat industry and SEO copywriting for pepperoni.tatar — "
        "a B2B halal meat products manufacturer from Russia. "
        "Write expert, informative articles in English for HoReCa and wholesale buyers. "
        "No fluff, real facts. Halal theme, no mention of pork."
    )
    prompt = f"""Write an informational SEO article on the topic: «{topic}».
Return ONLY full valid HTML5, no explanations, no markdown blocks.

Requirements:
- <!DOCTYPE html> with lang="en"
- <head>: charset, viewport, theme-color="#1b7a3d", optimized <title> (max 65 chars), <meta description> (max 160 chars), canonical https://pepperoni.tatar/en/blog/{slug}
- Schema.org Article in JSON-LD (datePublished={TODAY}, author="Kazan Delicacies", publisher org, url=https://pepperoni.tatar/en/blog/{slug})
- Schema.org BreadcrumbList in JSON-LD
- Google Tag Manager snippet: (function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f)}})(window,document,'script','dataLayer','GTM-W2Q5S8HF'); and noscript version
- CSS embedded in <style> — use EXACTLY this CSS without changes:
{ARTICLE_CSS}
- Body structure:
  <nav class="nav"><div class="nav__inner"><a href="/en/" class="nav__logo">Kazan Delicacies</a><div class="nav__links"><a href="/en/">Catalog</a><a href="/en/pepperoni">Pepperoni</a><a href="/blog">Blog</a><a href="/faq">FAQ</a></div></div></nav>
  <main class="article-wrap">
    breadcrumb: Home → Blog → [article title]
    <h1> with main keyword
    <div class="lead"> — intro paragraph 60-80 words
    4 sections with H2 headings and content
    <div class="info-box"> — useful fact or tip
    <div class="cta-block"> — call to action, button <a href="tel:+79872170202" class="btn-cta">+7 987 217-02-02</a>
  </main>
  <footer> © 2022–{YEAR} Kazan Delicacies · Kazan, Agrarnaya St. 2 · <a href="tel:+79872170202">+7 987 217-02-02</a> · <a href="/en/">pepperoni.tatar</a> </footer>
- Text 700-900 words
- Contextual links: /en/, /pepperoni-optom, /en/pepperoni
- Do NOT use Bootstrap
- Do NOT mention pork"""

    html, tokens = call_claude(system, prompt)
    out_path = PUBLIC_DIR / "en" / "blog" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- FAQ page generator ----------

def generate_faq_page(faq: dict) -> tuple[Path, int]:
    slug = faq["slug"]
    lang = faq["lang"]
    title = faq["title"]
    desc = faq["desc"]
    questions = faq["questions"]

    qa_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a}
            }
            for q, a in questions
        ]
    }, ensure_ascii=False, indent=2)

    qa_html = "\n".join(
        f"""<div class="accordion-item">
  <h3 class="accordion-header">
    <button class="accordion-button {'collapsed' if i > 0 else ''}" type="button" data-bs-toggle="collapse" data-bs-target="#faq{i}">
      {q}
    </button>
  </h3>
  <div id="faq{i}" class="accordion-collapse collapse {'show' if i == 0 else ''}">
    <div class="accordion-body">{a}</div>
  </div>
</div>"""
        for i, (q, a) in enumerate(questions)
    )

    canonical = f"/faq/{slug}" if lang == "ru" else f"/en/faq/{slug}"
    back_link = "/" if lang == "ru" else "/en/"
    back_text = "← Главная" if lang == "ru" else "← Home"

    schema_tag = f'<script type="application/ld+json">{qa_schema}</script>'
    body = f"""
<div class="container my-5">
  <a href="{back_link}" class="text-muted small">{back_text}</a>
  <h1 class="mt-3 mb-4">{title}</h1>
  <div class="accordion" id="faqAccordion">
    {qa_html}
  </div>
  <div class="mt-5 p-4 bg-light rounded">
    <h2 class="h4">{'Нужна консультация?' if lang == 'ru' else 'Need a consultation?'}</h2>
    <p>{'Свяжитесь с нами для получения прайс-листа и образцов продукции.' if lang == 'ru' else 'Contact us for a price list and product samples.'}</p>
    <a href="tel:+79872170202" class="btn btn-danger">+7 987 217-02-02</a>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>"""

    html = html_shell(lang, title, desc, canonical, body, schema_tag)

    if lang == "ru":
        out_path = PUBLIC_DIR / "faq" / f"{slug}.html"
    else:
        out_path = PUBLIC_DIR / "en" / "faq" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, 0


# ---------- Comparison page generator ----------

def generate_comparison_page(comp: dict) -> tuple[Path, int]:
    lang = comp["lang"]
    slug = comp["slug"]
    a_ru, a_en = comp["aspect_a"]
    b_ru, b_en = comp["aspect_b"]

    if lang == "ru":
        system = (
            "Ты эксперт в мясной промышленности, SEO-копирайтер для pepperoni.tatar. "
            "Пишешь сравнительные статьи на русском языке для оптовых покупателей."
        )
        prompt = f"""Напиши SEO-страницу сравнения: «{a_ru}» vs «{b_ru}» для оптовых покупателей.
Верни ТОЛЬКО полный валидный HTML5, без объяснений.

Требования:
- <!DOCTYPE html> с lang="ru"
- <title>: {comp['title']}
- <meta description>: {comp['desc']}
- <link canonical href="https://pepperoni.tatar/blog/{slug}">
- Schema.org Article + BreadcrumbList
- Bootstrap 5 CDN
- <h1>: {comp['h1']}
- Таблица сравнения (состав, вкус, цена, применение, срок хранения)
- 4 H2 секции с подробным сравнением
- CTA с ссылкой на /pepperoni-optom
- Текст 600-800 слов, без упоминания свинины
- Футер с контактами"""
    else:
        system = (
            "You are a meat industry expert and SEO copywriter for pepperoni.tatar. "
            "Write comparison articles in English for wholesale buyers and HoReCa."
        )
        prompt = f"""Write an SEO comparison page: «{a_en}» vs «{b_en}» for wholesale buyers.
Return ONLY full valid HTML5, no explanations.

Requirements:
- <!DOCTYPE html> with lang="en"
- <title>: {comp['title']}
- <meta description>: {comp['desc']}
- <link canonical href="https://pepperoni.tatar/en/blog/{slug}">
- Schema.org Article + BreadcrumbList
- Bootstrap 5 CDN
- <h1>: {comp['h1']}
- Comparison table (ingredients, taste, price, use cases, shelf life)
- 4 H2 sections with detailed comparison
- CTA linking to /pepperoni-optom
- Text 600-800 words, no mention of pork
- Footer with contacts"""

    html, tokens = call_claude(system, prompt)

    if lang == "ru":
        out_path = PUBLIC_DIR / "blog" / f"{slug}.html"
    else:
        out_path = PUBLIC_DIR / "en" / "blog" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- Type+Geo page generator ----------

def generate_type_geo_page(type_slug: str, type_ru: str, type_en: str,
                            city_slug: str, city_ru: str, city_en: str) -> tuple[Path, int]:
    slug = f"{type_slug}-{city_slug}"
    query_ru = f"{type_ru} {city_ru} оптом"

    system = (
        "Ты SEO-копирайтер для B2B сайта производителя халяль мясных изделий pepperoni.tatar. "
        "Пишешь лаконичные посадочные страницы для оптовых покупателей на русском языке."
    )
    prompt = f"""Напиши посадочную страницу для запроса «{query_ru}».
Верни ТОЛЬКО полный валидный HTML5, без объяснений.

Требования:
- <!DOCTYPE html> с lang="ru"
- <title>: {type_ru} {city_ru} — купить оптом | Казанские Деликатесы (до 65 символов)
- <meta description>: до 160 символов, включи запрос и USP (халяль, HACCP, доставка)
- canonical: /geo/{slug}
- Schema.org LocalBusiness + Product JSON-LD
- Bootstrap 5 CDN
- <h1>: {type_ru} в {city_ru} — оптовые поставки
- Секции: о продукте (3 абзаца), преимущества (ul 5 пунктов), условия поставки, CTA
- Кнопка «Получить прайс» → tel:+79872170202
- Контекстные ссылки: /pepperoni, /pepperoni-optom
- Футер с контактами
- НЕ упоминать свинину, текст 400-500 слов"""

    html, tokens = call_claude(system, prompt)
    html = inject_internal_links(html, slug)

    out_path = PUBLIC_DIR / "geo" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- Title/Meta updater ----------

def update_title_meta(file_path: Path, new_title: str, new_desc: str) -> bool:
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


# ---------- Geo page generator (from DB opportunities) ----------

def generate_geo_page(query: str, slug: str, conn) -> tuple[Path, int]:
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

Требования:
- <!DOCTYPE html> с lang="ru"
- <head>: charset, viewport, <title> (до 65 символов), <meta description> (до 160 символов), canonical /geo/{slug}
- Schema.org LocalBusiness + Product JSON-LD
- Bootstrap 5 CDN
- <h1> с запросом «{query}»
- Секции: краткое введение, преимущества (ul/li), ассортимент, условия поставки, CTA → tel:+79872170202
- BreadcrumbList microdata
- Футер: © 2022–{YEAR} Казанские Деликатесы, г. Казань, ул. Аграрная, 2, +7 987 217-02-02
- НЕ упоминать свинину
- Ссылка «← Все продукты» на /"""

    html, tokens = call_claude(system, prompt)
    html = html.replace("<body>", f"<body>\n{GTM_SNIPPET}", 1)
    html = inject_internal_links(html, slug)

    out_path = PUBLIC_DIR / "geo" / f"{slug}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path, tokens


# ---------- Blog index auto-updater ----------

def update_blog_index() -> None:
    """Rebuild public/blog.html from all existing RU blog article files."""
    blog_dir = PUBLIC_DIR / "blog"
    index_path = PUBLIC_DIR / "blog.html"
    if not index_path.exists() or not blog_dir.exists():
        return

    content = index_path.read_text(encoding="utf-8")
    start_marker = "<!-- BLOG_ARTICLES_START -->"
    end_marker = "<!-- BLOG_ARTICLES_END -->"
    if start_marker not in content or end_marker not in content:
        return

    # Collect all RU blog articles with metadata
    articles = []
    skip_slugs = {"api", "bakery", "export", "halal-production", "kazylyk", "pepperoni-pizzeria", "production"}
    all_slugs = set()

    for html_file in sorted(blog_dir.glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True):
        slug = html_file.stem
        all_slugs.add(slug)
        file_content = html_file.read_text(encoding="utf-8")

        # Extract title
        import re as _re
        og_title = _re.search(r'<meta property="og:title" content="([^"]+)"', file_content)
        title_tag = _re.search(r'<title>([^<]+)</title>', file_content)
        title = (og_title.group(1) if og_title else (title_tag.group(1) if title_tag else slug))
        title = _re.sub(r'\s*[|–—]\s*(Казанские Деликатесы|pepperoni\.tatar).*$', '', title).strip()

        # Extract description
        desc_match = _re.search(r'<meta name="description" content="([^"]+)"', file_content)
        desc = desc_match.group(1)[:200] if desc_match else ""

        # Extract date
        date_match = _re.search(r'<time[^>]*datetime="([^"]+)"', file_content)
        date_str = date_match.group(1)[:10] if date_match else ""
        if date_str:
            try:
                from datetime import datetime as _dt
                d = _dt.strptime(date_str, "%Y-%m-%d")
                months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
                date_display = f"{d.day} {months[d.month-1]} {d.year}"
            except Exception:
                date_display = date_str
        else:
            date_display = "2026"

        articles.append((slug, title, desc, date_display))

    if not articles:
        return

    # Build HTML blocks
    blocks = []
    for slug, title, desc, date_display in articles:
        blocks.append(f"""    <div class="article">
      <h2><a href="/blog/{slug}" style="color:#1b7a3d;text-decoration:none">{title}</a></h2>
      <div class="date">{date_display}</div>
      <p>{desc}</p>
      <a href="/blog/{slug}" style="color:#0066cc;font-size:.9rem">Читать полностью →</a>
    </div>""")

    new_section = f"{start_marker}\n" + "\n\n".join(blocks) + f"\n    {end_marker}"
    new_content = _re.sub(
        rf"{_re.escape(start_marker)}.*?{_re.escape(end_marker)}",
        new_section,
        content,
        flags=_re.DOTALL,
    )
    index_path.write_text(new_content, encoding="utf-8")
    print(f"✅ blog.html updated — {len(articles)} articles")


# ---------- Blog article (legacy, from DB) ----------

def generate_article(query: str, slug: str, conn) -> tuple[Path, int]:
    return generate_article_ru(query, slug, conn)


# ---------- Schedule: daily articles ----------

def run_scheduled_articles(conn) -> int:
    """Generate 3 RU + 3 EN blog articles per day from predefined topic list."""
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    new_urls = []

    # Find already-generated slugs
    done_slugs = set()
    for f in (PUBLIC_DIR / "blog").glob("*.html"):
        done_slugs.add(f.stem)
    for f in (PUBLIC_DIR / "en" / "blog").glob("*.html") if (PUBLIC_DIR / "en" / "blog").exists() else []:
        done_slugs.add(f.stem)

    # RU articles
    ru_pending = [(t, s) for t, s in BLOG_TOPICS_RU if s not in done_slugs]
    for topic, slug in ru_pending[:MAX_ARTICLES]:
        try:
            print(f"  📝 [RU] {topic[:60]}")
            out_path, tokens = generate_article_ru(topic, slug, conn)
            conn.execute(
                """INSERT INTO generated_content
                   (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, "article", "ru", topic, slug, str(out_path), topic, "published", CLAUDE_MODEL, tokens),
            )
            new_urls.append(f"https://pepperoni.tatar/blog/{slug}")
            count += 1
            print(f"     ✅ {out_path.name} ({tokens} tokens)")
        except Exception as ex:
            print(f"  ⚠️  RU article failed ({slug}): {ex}", file=sys.stderr)

    # EN articles
    en_pending = [(t, s) for t, s in BLOG_TOPICS_EN if s not in done_slugs]
    for topic, slug in en_pending[:MAX_ARTICLES]:
        try:
            print(f"  📝 [EN] {topic[:60]}")
            out_path, tokens = generate_article_en(topic, slug, conn)
            conn.execute(
                """INSERT INTO generated_content
                   (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, "article", "en", topic, slug, str(out_path), topic, "published", CLAUDE_MODEL, tokens),
            )
            new_urls.append(f"https://pepperoni.tatar/en/blog/{slug}")
            count += 1
            print(f"     ✅ {out_path.name} ({tokens} tokens)")
        except Exception as ex:
            print(f"  ⚠️  EN article failed ({slug}): {ex}", file=sys.stderr)

    if new_urls:
        add_to_sitemap(new_urls)

    return count


# ---------- Schedule: FAQ pages ----------

def run_faq_pages(conn) -> int:
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    new_urls = []

    for faq in FAQ_TOPICS:
        slug = faq["slug"]
        lang = faq["lang"]

        if lang == "ru":
            out_path = PUBLIC_DIR / "faq" / f"{slug}.html"
            url = f"https://pepperoni.tatar/faq/{slug}"
        else:
            out_path = PUBLIC_DIR / "en" / "faq" / f"{slug}.html"
            url = f"https://pepperoni.tatar/en/faq/{slug}"

        if out_path.exists():
            continue

        try:
            print(f"  ❓ [FAQ/{lang}] {faq['title'][:60]}")
            out_path, tokens = generate_faq_page(faq)
            conn.execute(
                """INSERT INTO generated_content
                   (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, "faq_page", lang, faq["title"], slug, str(out_path),
                 faq["title"], "published", CLAUDE_MODEL, tokens),
            )
            new_urls.append(url)
            count += 1
            print(f"     ✅ {out_path.name}")
        except Exception as ex:
            print(f"  ⚠️  FAQ failed ({slug}): {ex}", file=sys.stderr)

    if new_urls:
        add_to_sitemap(new_urls)

    return count


# ---------- Schedule: comparison pages ----------

def run_comparison_pages(conn) -> int:
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    new_urls = []

    for comp in COMPARISON_TOPICS:
        slug = comp["slug"]
        lang = comp["lang"]

        if lang == "ru":
            out_path = PUBLIC_DIR / "blog" / f"{slug}.html"
            url = f"https://pepperoni.tatar/blog/{slug}"
        else:
            out_path = PUBLIC_DIR / "en" / "blog" / f"{slug}.html"
            url = f"https://pepperoni.tatar/en/blog/{slug}"

        if out_path.exists():
            continue

        try:
            print(f"  ⚖️  [Comparison/{lang}] {comp['title'][:60]}")
            out_path, tokens = generate_comparison_page(comp)
            conn.execute(
                """INSERT INTO generated_content
                   (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, "comparison", lang, comp["title"], slug, str(out_path),
                 comp["title"], "published", CLAUDE_MODEL, tokens),
            )
            new_urls.append(url)
            count += 1
            print(f"     ✅ {out_path.name} ({tokens} tokens)")
        except Exception as ex:
            print(f"  ⚠️  Comparison failed ({slug}): {ex}", file=sys.stderr)

    if new_urls:
        add_to_sitemap(new_urls)

    return count


# ---------- Schedule: type+geo pages ----------

def run_type_geo_pages(conn) -> int:
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    new_urls = []

    for type_slug, type_ru, type_en in PRODUCT_TYPES:
        for city_slug, city_ru, city_en in GEO_CITIES:
            if count >= MAX_TYPEGEO:
                break

            slug = f"{type_slug}-{city_slug}"
            out_path = PUBLIC_DIR / "geo" / f"{slug}.html"
            if out_path.exists():
                continue

            try:
                print(f"  🌍 [type+geo] {type_ru} × {city_ru}")
                out_path, tokens = generate_type_geo_page(
                    type_slug, type_ru, type_en,
                    city_slug, city_ru, city_en,
                )
                conn.execute(
                    """INSERT INTO generated_content
                       (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (now, "geo_page", "ru", f"{type_ru} {city_ru} оптом", slug,
                     str(out_path), f"{type_ru} {city_ru}", "published", CLAUDE_MODEL, tokens),
                )
                new_urls.append(f"https://pepperoni.tatar/geo/{slug}")
                count += 1
                print(f"     ✅ {out_path.name} ({tokens} tokens)")
            except Exception as ex:
                print(f"  ⚠️  type+geo failed ({slug}): {ex}", file=sys.stderr)

    if new_urls:
        add_to_sitemap(new_urls)

    return count


# ---------- Title/meta low-CTR processor ----------

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
        elif "/faq/" in page_url:
            slug = page_url.split("/faq/")[-1].rstrip("/")
            rel_path = PUBLIC_DIR / "faq" / f"{slug}.html"

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

Верни JSON:
{{"title": "новый title (до 65 символов)", "description": "новый meta description (до 160 символов)"}}

Только JSON, без комментариев. Включи запрос, USP (халяль, оптом, ХАССП), CTA-слово."""

        try:
            raw, tokens = call_claude(system, prompt)
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


# ---------- New pages from DB opportunities ----------

def process_new_pages(opportunities: list, conn) -> int:
    count = 0
    now = datetime.now(timezone.utc).isoformat()

    for opp in opportunities[:MAX_ARTICLES]:
        query = opp["query"]
        ql    = query.lower()

        geo_cities_kw = [
            "москва", "спб", "санкт-петербург", "казань", "уфа", "екатеринбург",
            "сочи", "краснодар", "астрахань", "грозный", "махачкала", "дагестан",
            "ямало", "янао", "казахстан", "узбекистан", "беларусь", "армения",
            "азербайджан", "кыргызстан",
        ]
        is_geo     = any(city in ql for city in geo_cities_kw)
        is_article = any(kw in ql for kw in ["что такое", "как выбрать", "зачем", "почему", "виды", "состав", "калорийн"])

        slug = re.sub(r"[^a-zа-яё0-9\s-]", "", ql, flags=re.IGNORECASE)
        slug = re.sub(r"\s+", "-", slug.strip())
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
            else:
                out_path, tokens = generate_article_ru(query, slug_en, conn)
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

    print(f"🚀 SEO Content Generator — {TODAY}")
    print("=" * 50)

    # 1. Update sitemap lastmod (no Claude needed)
    print("\n[1/7] Updating sitemap.xml lastmod …")
    update_sitemap_lastmod()

    # 2. FAQ pages (static, no Claude if already built)
    print("\n[2/7] Generating FAQ pages …")
    faq_done = run_faq_pages(conn)
    print(f"  → {faq_done} FAQ pages generated")

    # 3. Comparison pages
    print("\n[3/7] Generating comparison pages …")
    cmp_done = run_comparison_pages(conn)
    print(f"  → {cmp_done} comparison pages generated")

    # 4. Scheduled blog articles (3 RU + 3 EN)
    print("\n[4/7] Generating scheduled blog articles …")
    art_done = run_scheduled_articles(conn)
    print(f"  → {art_done} articles generated")
    update_blog_index()

    # 5. Type+Geo pages
    print("\n[5/7] Generating type+geo pages …")
    tg_done = run_type_geo_pages(conn)
    print(f"  → {tg_done} type+geo pages generated")

    # 6. Low-CTR title updates (from DB)
    low_ctr_opps = conn.execute(
        "SELECT * FROM opportunities WHERE type='low_ctr' AND status='new' ORDER BY impressions DESC LIMIT ?",
        (MAX_TITLES,),
    ).fetchall()
    print(f"\n[6/7] Updating {len(low_ctr_opps)} low-CTR titles …")
    titles_done = process_low_ctr(list(low_ctr_opps), conn)
    print(f"  → {titles_done} titles updated")

    # 7. New pages from DB opportunities
    new_page_opps = conn.execute(
        "SELECT * FROM opportunities WHERE type IN ('quick_growth','new_query','commercial_gap') AND status='new' ORDER BY impressions DESC LIMIT ?",
        (MAX_ARTICLES,),
    ).fetchall()
    print(f"\n[7/7] Generating {len(new_page_opps)} pages from DB opportunities …")
    pages_done = process_new_pages(list(new_page_opps), conn)
    print(f"  → {pages_done} pages generated")

    conn.commit()
    conn.close()

    total = faq_done + cmp_done + art_done + tg_done + titles_done + pages_done
    print(f"\n✅ Total: {total} items generated/updated")


if __name__ == "__main__":
    main()
