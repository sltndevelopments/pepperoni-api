"""Shared HTML shell for pepperoni.tatar blog articles (RU + EN)."""
from __future__ import annotations

import json
import re
from datetime import datetime

SITE = "https://pepperoni.tatar"
YEAR = datetime.now().year
PHONE_DISPLAY = "+7 987 217-02-02"
PHONE_TEL = "+79872170202"
EMAIL = "info@kazandelikates.tatar"

GTM = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->"""

GTM_NS = """<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>"""

BLOG_CSS = """<style>
:root{--green:#1b7a3d;--green-dark:#145c2e;--green-light:#e8f5e9;--text:#1a1a1a;--muted:#666;--border:#e5e5e5;--radius:10px;--shadow:0 2px 12px rgba(0,0,0,.08)}
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
h1{font-size:clamp(1.5rem,3vw,2rem);font-weight:800;line-height:1.25;margin-bottom:12px;color:var(--text)}
h2{font-size:1.25rem;font-weight:700;margin:36px 0 12px;color:var(--text);border-left:3px solid var(--green);padding-left:12px}
h3{font-size:1.05rem;font-weight:700;margin:24px 0 8px;color:var(--text)}
p{margin-bottom:16px;color:#333}
ul,ol{margin:0 0 16px 24px}li{margin-bottom:6px;color:#333}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:.9rem}
th{background:var(--green);color:#fff;padding:10px 12px;text-align:left}
td{padding:9px 12px;border-bottom:1px solid var(--border)}
tr:nth-child(even) td{background:#f5f5f5}
.lead{font-size:1.05rem;color:#444;line-height:1.75;margin-bottom:24px;padding:16px 20px;background:#fff;border-radius:var(--radius);border-left:4px solid var(--green)}
.info-box{background:var(--green-light);border:1px solid #c8e6c9;border-radius:var(--radius);padding:16px 20px;margin:24px 0}
.info-box p{margin:0;color:var(--green-dark);font-size:.92rem}
.cta-block{background:var(--green);color:#fff;border-radius:var(--radius);padding:28px 32px;margin:40px 0;text-align:center}
.cta-block h2,.cta-block h3{color:#fff;border:none;padding:0;margin:0 0 10px;font-size:1.3rem}
.cta-block p{color:rgba(255,255,255,.9);margin-bottom:18px}
.btn-cta{display:inline-block;background:#fff;color:var(--green);font-weight:700;padding:12px 28px;border-radius:8px;font-size:.95rem;margin:4px 6px}
.btn-cta:hover{background:var(--green-light);text-decoration:none;transform:translateY(-1px)}
.cta-block a:not(.btn-cta){color:#fff;text-decoration:underline}
.card{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin:20px 0}
.card p:last-child{margin-bottom:0}
.tag{display:inline-block;background:var(--green-light);color:var(--green-dark);font-size:.78rem;padding:3px 10px;border-radius:20px;margin:2px 4px 2px 0}
footer{background:#1a1a1a;color:#aaa;text-align:center;font-size:.82rem;padding:24px 20px;margin-top:48px}
footer a{color:#aaa}footer a:hover{color:#fff;text-decoration:none}
.faq-section{max-width:740px;margin:0 auto 40px;padding:0 32px}
.faq-section h2{font-size:1.4rem;color:var(--green);margin-bottom:1rem;border:none;padding:0}
.faq-section details{border:1px solid var(--border);border-radius:8px;margin-bottom:.6rem;padding:.8rem 1rem}
.faq-section details[open]{border-color:var(--green)}
.faq-section summary{font-weight:600;cursor:pointer;list-style:none;color:var(--text)}
.faq-section summary::after{content:' +';color:var(--green);float:right}
.faq-section details[open] summary::after{content:' −'}
.faq-section p{margin-top:.6rem;color:var(--muted);line-height:1.6}
@media(max-width:600px){.article-wrap{padding:24px 20px 40px}.cta-block{padding:20px 18px}.faq-section{padding:0 20px}}
</style>"""

RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def nav_ru() -> str:
    return """<nav class="nav">
  <div class="nav__inner">
    <a href="/" class="nav__logo">🥩 Казанские Деликатесы</a>
    <div class="nav__links">
      <a href="/">Каталог</a>
      <a href="/pepperoni">Пепперони</a>
      <a href="/blog">Блог</a>
      <a href="/faq">FAQ</a>
      <a href="/delivery">Доставка</a>
    </div>
    <div class="nav__lang"><a href="/en/blog">🇬🇧 English</a></div>
  </div>
</nav>"""


def nav_en() -> str:
    return """<nav class="nav">
  <div class="nav__inner">
    <a href="/en/" class="nav__logo">🥩 Kazan Delicacies</a>
    <div class="nav__links">
      <a href="/en/">Catalog</a>
      <a href="/en/pepperoni.html">Pepperoni</a>
      <a href="/en/blog">Blog</a>
      <a href="/en/faq.html">FAQ</a>
      <a href="/en/delivery.html">Delivery</a>
    </div>
    <div class="nav__lang"><a href="/blog">🇷🇺 Русский</a></div>
  </div>
</nav>"""


def footer_ru() -> str:
    return f"""<footer>
  <p><a href="/">Каталог</a> · <a href="/pepperoni">Пепперони</a> · <a href="/about">О компании</a> · <a href="/faq">FAQ</a> · <a href="/delivery">Доставка</a> · <a href="/en/blog">English</a></p>
  <p>&copy; 2022–{YEAR} <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> · г. Казань, ул. Аграрная, 2 · <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a></p>
</footer>"""


def footer_en() -> str:
    return f"""<footer>
  <p><a href="/en/">Catalog</a> · <a href="/en/pepperoni.html">Pepperoni</a> · <a href="/en/about.html">About</a> · <a href="/en/faq.html">FAQ</a> · <a href="/en/delivery.html">Delivery</a> · <a href="/blog">Русский</a></p>
  <p>&copy; 2022–{YEAR} <a href="https://kazandelikates.tatar">Kazan Delicacies</a> · Kazan, ul. Agrarnaya, 2 · <a href="tel:{PHONE_TEL}">{PHONE_DISPLAY}</a></p>
</footer>"""


def format_date_display(iso_date: str | None, lang: str) -> str:
    if not iso_date:
        return "2026"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00")[:10])
    except ValueError:
        return iso_date[:10]
    if lang == "ru":
        return f"{dt.day} {RU_MONTHS.get(dt.month, '')} {dt.year}"
    return dt.strftime("%b %d, %Y")


def short_title(title: str) -> str:
    t = re.split(r"\s*[|—–]\s*(Казанские Деликатесы|Kazan Delicacies|pepperoni\.tatar)\s*$", title)[0]
    return t.strip()[:80]


def breadcrumb_ru(title: str) -> str:
    return f'<div class="breadcrumb"><a href="/">Главная</a> → <a href="/blog">Блог</a> → <span>{short_title(title)}</span></div>'


def breadcrumb_en(title: str) -> str:
    return f'<div class="breadcrumb"><a href="/en/">Home</a> → <a href="/en/blog">Blog</a> → <span>{short_title(title)}</span></div>'


def breadcrumb_schema(lang: str, title: str, slug: str) -> str:
    if lang == "en":
        items = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/en/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{SITE}/en/blog"},
            {"@type": "ListItem", "position": 3, "name": short_title(title), "item": f"{SITE}/en/blog/{slug}"},
        ]
    else:
        items = [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Блог", "item": f"{SITE}/blog"},
            {"@type": "ListItem", "position": 3, "name": short_title(title), "item": f"{SITE}/blog/{slug}"},
        ]
    return f'<script type="application/ld+json">\n{json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}, ensure_ascii=False, indent=2)}\n</script>'


def wrap_blog_page(
    *,
    lang: str,
    slug: str,
    title: str,
    description: str,
    body_main: str,
    article_schema: str = "",
    extra_head: str = "",
    tail_sections: str = "",
    date_iso: str | None = None,
) -> str:
    if lang == "en":
        canonical = f"{SITE}/en/blog/{slug}"
        hreflang_ru = f"{SITE}/blog/{slug}" if slug else None
        content_lang = "en"
        meta_line = f"{format_date_display(date_iso, 'en')} · Kazan Delicacies"
        nav = nav_en()
        footer = footer_en()
        breadcrumb = breadcrumb_en(title)
        publisher = "Kazan Delicacies"
    else:
        canonical = f"{SITE}/blog/{slug}"
        hreflang_ru = None
        content_lang = "ru"
        meta_line = f"{format_date_display(date_iso, 'ru')} · Казанские Деликатесы"
        nav = nav_ru()
        footer = footer_ru()
        breadcrumb = breadcrumb_ru(title)
        publisher = "Казанские Деликатесы"

    hreflang = ""
    if lang == "ru":
        hreflang = f"""<link rel="alternate" hreflang="ru" href="{canonical}">
<link rel="alternate" hreflang="en" href="{SITE}/en/blog/{slug}">
<link rel="alternate" hreflang="x-default" href="{canonical}">"""
    elif lang == "en":
        hreflang = f"""<link rel="alternate" hreflang="en" href="{canonical}">
<link rel="alternate" hreflang="ru" href="{SITE}/blog/{slug}">
<link rel="alternate" hreflang="x-default" href="{SITE}/blog/{slug}">"""

    llms = '/llms.txt' if lang == 'ru' else '/en/llms.txt'

    return f"""<!DOCTYPE html>
<html lang="{content_lang}">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="content-language" content="{content_lang}">
<meta name="theme-color" content="#1b7a3d">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">
{hreflang}
<link rel="llms" href="{llms}" type="text/plain" title="LLM instructions">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{publisher}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="{'ru_RU' if lang == 'ru' else 'en_US'}">
{article_schema}
{breadcrumb_schema(lang, title, slug)}
{extra_head}
{BLOG_CSS}
</head>
<body>
{GTM_NS}
{nav}
<main class="article-wrap">
{breadcrumb}
{body_main}
</main>
{tail_sections}
{footer}
</body>
</html>"""


TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
DESC_RE = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', re.I | re.S)
JSONLD_RE = re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)


def _strip_tags(html: str) -> str:
    from html import unescape

    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_generated_blog_parts(generated: str) -> dict:
    """Extract title/meta/schema/body from LLM blog output."""
    title_m = TITLE_RE.search(generated)
    desc_m = DESC_RE.search(generated)
    title = _strip_tags(title_m.group(1)) if title_m else "Казанские Деликатесы"
    desc = desc_m.group(1).strip() if desc_m else title[:160]

    article_schema = ""
    extra_head = ""
    for block in JSONLD_RE.findall(generated):
        block = block.strip()
        tag = f'<script type="application/ld+json">\n{block}\n</script>'
        if '"FAQPage"' in block:
            extra_head += tag + "\n"
        elif '"BreadcrumbList"' in block:
            continue
        elif '"Article"' in block or '"BlogPosting"' in block:
            article_schema = tag

    main_m = re.search(r"<main[^>]*class=[\"']article-wrap[\"'][^>]*>(.*?)</main>", generated, re.I | re.S)
    if main_m:
        body_main = main_m.group(1).strip()
    else:
        body = generated
        body = re.sub(r"<!DOCTYPE[^>]*>", "", body, flags=re.I)
        body = re.sub(r"<html[^>]*>", "", body, flags=re.I)
        body = re.sub(r"</html>", "", body, flags=re.I)
        body = re.sub(r"<head[^>]*>.*?</head>", "", body, flags=re.I | re.S)
        body = re.sub(r"<body[^>]*>", "", body, flags=re.I)
        body = re.sub(r"</body>", "", body, flags=re.I)
        body = re.sub(r"<nav[^>]*>.*?</nav>", "", body, flags=re.I | re.S)
        body = re.sub(r"<footer[^>]*>.*?</footer>", "", body, flags=re.I | re.S)
        body_main = body.strip()

    if "<h1" not in body_main.lower():
        h1_m = H1_RE.search(generated)
        if h1_m:
            body_main = f"<h1>{h1_m.group(1).strip()}</h1>\n{body_main}"

    return {
        "title": title,
        "description": desc,
        "article_schema": article_schema,
        "extra_head": extra_head.strip(),
        "body_main": body_main,
    }


def wrap_generated_blog(lang: str, slug: str, generated: str, date_iso: str | None = None) -> str:
    parts = parse_generated_blog_parts(generated)
    if "<div class=\"meta\"" not in parts["body_main"] and "<div class='meta'" not in parts["body_main"]:
        meta = (
            f"{format_date_display(date_iso or datetime.now().strftime('%Y-%m-%d'), lang)} · "
            + ("Казанские Деликатесы" if lang == "ru" else "Kazan Delicacies")
        )
        if re.search(r"<h1[^>]*>", parts["body_main"], re.I):
            parts["body_main"] = re.sub(
                r"(<h1[^>]*>.*?</h1>)",
                rf"\1\n<div class=\"meta\">{meta}</div>",
                parts["body_main"],
                count=1,
                flags=re.I | re.S,
            )
    return wrap_blog_page(
        lang=lang,
        slug=slug,
        title=parts["title"],
        description=parts["description"],
        body_main=parts["body_main"],
        article_schema=parts["article_schema"],
        extra_head=parts["extra_head"],
        date_iso=date_iso,
    )


BLOG_ARTICLE_OUTPUT_RULES_RU = """
Верни ТОЛЬКО фрагмент HTML (без <!DOCTYPE>, без <html>, без nav/footer):
- <title>…</title>
- <meta name="description" content="…">
- <script type="application/ld+json"> Article + datePublished={date} </script>
- <main class="article-wrap"> с h1, lead-абзацем, 4× h2, списками/таблицей, 1–2 info-box, cta-block
Стилизация: классы article-wrap, lead, info-box, cta-block, btn-cta. БЕЗ Bootstrap, БЕЗ hero-section, БЕЗ красной темы.
"""

BLOG_ARTICLE_OUTPUT_RULES_EN = """
Return ONLY an HTML fragment (no <!DOCTYPE>, no <html>, no nav/footer):
- <title>…</title>
- <meta name="description" content="…">
- <script type="application/ld+json"> Article + datePublished={date} </script>
- <main class="article-wrap"> with h1, lead paragraph, 4× h2, lists/table, 1–2 info-box, cta-block
Use classes article-wrap, lead, info-box, cta-block, btn-cta. NO Bootstrap, NO hero-section, NO red theme.
"""
