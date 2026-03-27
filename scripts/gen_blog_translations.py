#!/usr/bin/env python3
"""
Generate missing blog article translations (RU→EN and EN→RU).
Usage: CLAUDE_API_KEY=sk-ant-... python3 scripts/gen_blog_translations.py
"""

import os, sys, re, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from claude_client import call_claude

ROOT   = Path(__file__).parent.parent
RU_DIR = ROOT / "public" / "blog"
EN_DIR = ROOT / "public" / "en" / "blog"

GTM = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->"""

GTM_NS = """<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>"""

CSS = """<style>
:root{--green:#1b7a3d;--green-dark:#145c2e;--green-light:#e8f5e9;--text:#1a1a1a;--muted:#666;--border:#e5e5e5;--radius:10px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:var(--text);line-height:1.7;font-size:16px}
a{color:var(--green);text-decoration:none}a:hover{text-decoration:underline}
.nav{background:#fff;border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100}
.nav__inner{max-width:800px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.nav__logo{font-weight:700;font-size:1.05rem;color:var(--green)}
.nav__links{display:flex;gap:16px;flex-wrap:wrap;font-size:.88rem}
.nav__links a{color:var(--muted)}.nav__links a:hover{color:var(--green);text-decoration:none}
.nav__lang{margin-left:auto;font-size:.85rem}
.article-wrap{max-width:740px;margin:0 auto;padding:40px 32px 60px}
.breadcrumb{font-size:.82rem;color:var(--muted);margin-bottom:24px}
.breadcrumb a{color:var(--muted)}.breadcrumb span{color:var(--green)}
.meta{font-size:.82rem;color:var(--muted);margin-bottom:24px}
h1{font-size:clamp(1.5rem,3vw,2rem);font-weight:800;line-height:1.25;margin-bottom:12px}
h2{font-size:1.25rem;font-weight:700;margin:36px 0 12px;border-left:3px solid var(--green);padding-left:12px}
h3{font-size:1.05rem;font-weight:700;margin:24px 0 8px}
p{margin-bottom:16px;color:#333}
ul,ol{margin:0 0 16px 24px}li{margin-bottom:6px;color:#333}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:.9rem}
th{background:var(--green);color:#fff;padding:10px 12px;text-align:left}
td{padding:9px 12px;border-bottom:1px solid var(--border)}
tr:nth-child(even) td{background:#f5f5f5}
.lead{font-size:1.05rem;color:#444;padding:16px 20px;background:#fff;border-radius:var(--radius);border-left:4px solid var(--green);margin-bottom:28px}
.info-box{background:var(--green-light);border:1px solid #c8e6c9;border-radius:var(--radius);padding:16px 20px;margin:24px 0}
.info-box p{margin:0;color:var(--green-dark);font-size:.92rem}
.cta-block{background:var(--green);color:#fff;border-radius:var(--radius);padding:28px 32px;margin:40px 0;text-align:center}
.cta-block h2{color:#fff;border:none;padding:0;margin:0 0 10px;font-size:1.3rem}
.cta-block p{color:rgba(255,255,255,.9);margin-bottom:18px}
.btn-cta{display:inline-block;background:#fff;color:var(--green);font-weight:700;padding:12px 28px;border-radius:8px;font-size:.95rem}
.btn-cta:hover{background:var(--green-light);text-decoration:none}
footer{background:#1a1a1a;color:#aaa;text-align:center;font-size:.82rem;padding:24px 20px;margin-top:48px}
footer a{color:#aaa}footer a:hover{color:#fff;text-decoration:none}
@media(max-width:600px){.article-wrap{padding:24px 20px 40px}.cta-block{padding:20px 18px}}
</style>"""

def nav_en(slug):
    return f"""<nav class="nav">
  <div class="nav__inner">
    <a href="/en/" class="nav__logo">🥩 Kazan Delicacies</a>
    <div class="nav__links">
      <a href="/en/">Catalog</a>
      <a href="/en/pepperoni.html">Pepperoni</a>
      <a href="/en/blog">Blog</a>
      <a href="/en/faq.html">FAQ</a>
      <a href="/en/delivery.html">Delivery</a>
    </div>
    <div class="nav__lang"><a href="/">🇷🇺 Русский</a></div>
  </div>
</nav>"""

def nav_ru(slug):
    return f"""<nav class="nav">
  <div class="nav__inner">
    <a href="/" class="nav__logo">🥩 Казанские Деликатесы</a>
    <div class="nav__links">
      <a href="/">Каталог</a>
      <a href="/pepperoni">Пепперони</a>
      <a href="/blog">Блог</a>
      <a href="/faq">FAQ</a>
      <a href="/delivery">Доставка</a>
    </div>
    <div class="nav__lang"><a href="/en/">🇬🇧 English</a></div>
  </div>
</nav>"""

def footer_en():
    return """<footer>
  © 2022–2026 <a href="/en/">Kazan Delicacies</a> · Kazan, ul. Agrarnaya, 2 · <a href="tel:+79872170202">+7 987 217-02-02</a>
</footer>"""

def footer_ru():
    return """<footer>
  © 2022–2026 <a href="/">Казанские Деликатесы</a> · г. Казань, ул. Аграрная, 2 · <a href="tel:+79872170202">+7 987 217-02-02</a>
</footer>"""

def extract_text(html):
    """Extract readable text from HTML for use as translation source."""
    # Remove scripts, styles, nav, footer
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL)
    # Keep meaningful tags
    html = re.sub(r'<(h[1-6])[^>]*>', r'<\1>', html)
    html = re.sub(r'</(h[1-6])>', r'</\1>', html)
    html = re.sub(r'<(p|li|td|th)[^>]*>', r'<\1>', html)
    # Strip remaining tags
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:4000]

def generate_en_article(ru_slug, ru_html, en_slug, date):
    """Generate EN article from RU source."""
    source_text = extract_text(ru_html)

    prompt = f"""You are writing an English blog article for Kazan Delicacies — a halal meat manufacturer in Kazan, Tatarstan, Russia.

Source article (Russian, for reference only — adapt the topic and content for English B2B audience):
---
{source_text}
---

Write a complete HTML article in English. Requirements:
- URL slug: /en/blog/{en_slug}
- Date: {date}
- Target audience: B2B buyers, HoReCa operators, wholesale distributors
- Language: professional English
- Length: 600-900 words of body text
- Include: h1, 3-5 h2 sections, lead paragraph, info-box, CTA block
- Company details: Kazan Delicacies, Kazan Russia, phone +7 987 217-02-02, email info@kazandelikates.tatar, halal cert #614A/2024 MSB Tatarstan

Output ONLY the <main class="article-wrap">...</main> block and the <title>, <meta name="description">, and JSON-LD schema (Article type). No other HTML wrapper needed."""

    text, _ = call_claude(
        system="You are an expert B2B content writer for food industry. Write in clean, professional English.",
        prompt=prompt,
        max_tokens=3000
    )
    return text

def generate_ru_article(en_slug, en_html, ru_slug, date):
    """Generate RU article from EN source."""
    source_text = extract_text(en_html)

    prompt = f"""Ты пишешь статью для блога «Казанские Деликатесы» — производителя халяль мясных изделий в Казани, Татарстан.

Исходная статья (английская, для справки — адаптируй тему и содержание для русскоязычной B2B аудитории):
---
{source_text}
---

Напиши полноценную HTML-статью на русском языке. Требования:
- URL slug: /blog/{ru_slug}
- Дата: {date}
- Целевая аудитория: B2B покупатели, HoReCa операторы, оптовые дистрибьюторы
- Язык: профессиональный русский
- Объём: 600-900 слов основного текста
- Включи: h1, 3-5 секций h2, lead-абзац, info-box, CTA блок
- Реквизиты: Казанские Деликатесы, г. Казань, тел. +7 987 217-02-02, info@kazandelikates.tatar, халяль сертификат №614A/2024 ДУМ РТ

Выдай ТОЛЬКО блок <main class="article-wrap">...</main> и теги <title>, <meta name="description">, JSON-LD схему (тип Article). Никакой другой HTML обёртки не нужно."""

    text, _ = call_claude(
        system="Ты эксперт по B2B контенту для пищевой промышленности. Пиши на чистом профессиональном русском языке.",
        prompt=prompt,
        max_tokens=3000
    )
    return text

def wrap_en(slug, date, generated):
    """Wrap generated content into full EN HTML page."""
    # Extract parts
    title_m = re.search(r'<title>([^<]+)</title>', generated)
    desc_m  = re.search(r'<meta name="description" content="([^"]+)"', generated)
    schema_m = re.search(r'<script type="application/ld\+json">(.*?)</script>', generated, re.DOTALL)
    main_m  = re.search(r'<main[^>]*>(.*?)</main>', generated, re.DOTALL)

    title = title_m.group(1) if title_m else f"Kazan Delicacies — {slug.replace('-',' ').title()}"
    desc  = desc_m.group(1)  if desc_m  else "Halal meat products wholesale from Kazan Delicacies."
    schema = f'<script type="application/ld+json">{schema_m.group(1)}</script>' if schema_m else ""
    main_content = main_m.group(0) if main_m else f"<main class=\"article-wrap\">{generated}</main>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#1b7a3d">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/en/blog/{slug}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://pepperoni.tatar/en/blog/{slug}">
{schema}
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
  {{"@type":"ListItem","position":1,"name":"Home","item":"https://pepperoni.tatar/en/"}},
  {{"@type":"ListItem","position":2,"name":"Blog","item":"https://pepperoni.tatar/en/blog"}},
  {{"@type":"ListItem","position":3,"name":"{title.split('|')[0].strip()}","item":"https://pepperoni.tatar/en/blog/{slug}"}}
]}}
</script>
{CSS}
</head>
<body>
{GTM_NS}
{nav_en(slug)}
{main_content}
{footer_en()}
</body>
</html>"""

def wrap_ru(slug, date, generated):
    """Wrap generated content into full RU HTML page."""
    title_m = re.search(r'<title>([^<]+)</title>', generated)
    desc_m  = re.search(r'<meta name="description" content="([^"]+)"', generated)
    schema_m = re.search(r'<script type="application/ld\+json">(.*?)</script>', generated, re.DOTALL)
    main_m  = re.search(r'<main[^>]*>(.*?)</main>', generated, re.DOTALL)

    title = title_m.group(1) if title_m else f"Казанские Деликатесы — {slug.replace('-',' ').title()}"
    desc  = desc_m.group(1)  if desc_m  else "Халяль мясные изделия оптом от Казанских Деликатесов."
    schema = f'<script type="application/ld+json">{schema_m.group(1)}</script>' if schema_m else ""
    main_content = main_m.group(0) if main_m else f"<main class=\"article-wrap\">{generated}</main>"

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#1b7a3d">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/blog/{slug}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://pepperoni.tatar/blog/{slug}">
{schema}
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
  {{"@type":"ListItem","position":1,"name":"Главная","item":"https://pepperoni.tatar/"}},
  {{"@type":"ListItem","position":2,"name":"Блог","item":"https://pepperoni.tatar/blog"}},
  {{"@type":"ListItem","position":3,"name":"{title.split('|')[0].strip()}","item":"https://pepperoni.tatar/blog/{slug}"}}
]}}
</script>
{CSS}
</head>
<body>
{GTM_NS}
{nav_ru(slug)}
{main_content}
{footer_ru()}
</body>
</html>"""

# ── Mapping: RU slug → EN slug ────────────────────────────────
RU_TO_EN = {
    "api":                        "api-catalog-for-developers",
    "b2b-myasnaya-produkciya":    "b2b-meat-products-supply",       # already exists EN
    "bakery":                     "tatar-bakery-wholesale",
    "chto-takoe-halyal-pepperoni":"what-is-halal-pepperoni",
    "eksport-halyal-snг":         "halal-meat-export-cis",          # already exists EN
    "export":                     "halal-meat-export-russia",
    "haccp-iso-myasnoe-proizvodstvo": "haccp-iso-meat-production",  # already exists EN
    "halal-production":           "halal-meat-production-standards",
    "halyal-sertifikaciya-myasa": "halal-certification-russia",     # already exists EN
    "iso-22000-sertifikaciya":    "iso-22000-certification",        # already exists EN
    "kak-hranit-pepperoni":       "how-to-store-pepperoni",         # already exists EN
    "kak-otlichit-halyal":        "how-to-identify-halal-meat",
    "kak-vybrat-pepperoni-dlya-pizzerii": "source-halal-pepperoni-pizzeria", # already exists EN
    "kazylyk":                    "kazylyk-horse-meat-sausage",
    "kotlety-dlya-burgerov-optom":"burger-patties-wholesale-halal", # already exists EN
    "myasnye-delikatesy-kazan":   "kazan-delicacies-halal-producer",# already exists EN
    "pepperoni-dlya-sushi":       "pepperoni-for-sushi",            # already exists EN
    "pepperoni-govyadina-vs-kurica": "beef-vs-chicken-pepperoni",   # already exists EN
    "pepperoni-halyal":           "halal-pepperoni-guide",          # already exists EN
    "pepperoni-iz-govyadiny":     "beef-pepperoni-wholesale",
    "pepperoni-iz-koniny":        "horse-meat-pepperoni",           # already exists EN
    "pepperoni-kuriniy":          "chicken-pepperoni-wholesale",
    "pepperoni-miksoviy":         "mixed-pepperoni-beef-chicken",   # already exists EN
    "pepperoni-optom-postavshchik":"wholesale-pepperoni-russia-export", # already exists EN
    "pepperoni-pizzeria":         "pepperoni-for-pizzeria-horeca",
    "postavki-myasnye-restorany": "meat-supply-restaurants-horeca",
    "private-label-kolbasnyh-izdeliy": "private-label-meat-products", # already exists EN
    "production":                 "halal-meat-production-kazan",
    "sosiki-dlya-hotdog-optom":   "hot-dog-sausages-wholesale",     # already exists EN
    "zamorozhennye-polufarikaty-horeca": "frozen-meat-products-horeca", # already exists EN
}

EN_TO_RU = {
    "b2b-meat-products-supply":         "b2b-myasnye-postavki",
    "beef-vs-chicken-pepperoni":        "pepperoni-govyadina-vs-kurica",  # already exists RU
    "burger-patties-wholesale-halal":   "kotlety-dlya-burgerov-optom",    # already exists RU
    "frozen-meat-products-horeca":      "zamorozhennye-polufarikaty-horeca", # already exists RU
    "haccp-iso-meat-production":        "haccp-iso-myasnoe-proizvodstvo", # already exists RU
    "halal-certification-russia":       "halyal-sertifikaciya-myasa",     # already exists RU
    "halal-food-market-russia":         "rynok-halyal-rossiya",
    "halal-meat-export-cis":            "eksport-halyal-snг",             # already exists RU
    "halal-pepperoni-comparison":       "sravnenie-halyal-pepperoni",
    "halal-pepperoni-guide":            "pepperoni-halyal",               # already exists RU
    "horse-meat-pepperoni":             "pepperoni-iz-koniny",            # already exists RU
    "hot-dog-sausages-wholesale":       "sosiki-dlya-hotdog-optom",       # already exists RU
    "how-to-store-pepperoni":           "kak-hranit-pepperoni",           # already exists RU
    "iso-22000-certification":          "iso-22000-sertifikaciya",        # already exists RU
    "kazan-delicacies-halal-producer":  "myasnye-delikatesy-kazan",       # already exists RU
    "meat-products-quality-control":    "kontrol-kachestva-myasnye-izdeliya",
    "mixed-pepperoni-beef-chicken":     "pepperoni-miksoviy",             # already exists RU
    "pepperoni-for-sushi":              "pepperoni-dlya-sushi",           # already exists RU
    "pepperoni-slicing-specs":          "narezka-pepperoni-parametry",
    "private-label-meat-products":      "private-label-kolbasnyh-izdeliy",# already exists RU
    "source-halal-pepperoni-pizzeria":  "kak-vybrat-pepperoni-dlya-pizzerii", # already exists RU
    "wholesale-pepperoni-russia-export":"pepperoni-optom-postavshchik",   # already exists RU
}

def main():
    date = "2026-03-27"

    # --- EN articles needed from RU sources ---
    ru_files = {f.stem: f for f in RU_DIR.glob("*.html")}
    en_files = {f.stem: f for f in EN_DIR.glob("*.html")}

    en_needed = []
    for ru_slug, en_slug in RU_TO_EN.items():
        if en_slug not in en_files and ru_slug in ru_files:
            en_needed.append((ru_slug, en_slug))

    ru_needed = []
    for en_slug, ru_slug in EN_TO_RU.items():
        if ru_slug not in ru_files and en_slug in en_files:
            ru_needed.append((en_slug, ru_slug))

    print(f"Need to generate: {len(en_needed)} EN articles, {len(ru_needed)} RU articles")

    # Generate EN articles
    for i, (ru_slug, en_slug) in enumerate(en_needed):
        print(f"\n[{i+1}/{len(en_needed)}] EN: {ru_slug} → {en_slug}")
        ru_html = ru_files[ru_slug].read_text(encoding="utf-8")
        try:
            generated = generate_en_article(ru_slug, ru_html, en_slug, date)
            full_html = wrap_en(en_slug, date, generated)
            out = EN_DIR / f"{en_slug}.html"
            out.write_text(full_html, encoding="utf-8")
            print(f"  ✅ Written {out}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        time.sleep(2)

    # Generate RU articles
    for i, (en_slug, ru_slug) in enumerate(ru_needed):
        print(f"\n[{i+1}/{len(ru_needed)}] RU: {en_slug} → {ru_slug}")
        en_html = en_files[en_slug].read_text(encoding="utf-8")
        try:
            generated = generate_ru_article(en_slug, en_html, ru_slug, date)
            full_html = wrap_ru(ru_slug, date, generated)
            out = RU_DIR / f"{ru_slug}.html"
            out.write_text(full_html, encoding="utf-8")
            print(f"  ✅ Written {out}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        time.sleep(2)

    print("\n✅ Done!")

if __name__ == "__main__":
    main()
