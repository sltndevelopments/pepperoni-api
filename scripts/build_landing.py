#!/usr/bin/env python3
"""
LANDING-BUILDER — closes the Scout → human-approval → page loop.

Scout queues "create_landing" approvals when it finds real demand that only the
homepage ranks for. Once you approve in Telegram, this agent builds a high-quality
landing page for that query and registers it in the experiments ledger so the
optimizer/measure loop tracks whether it actually wins traffic.

Flow per approved request:
  approvals.take_approved("create_landing")
    → generate HTML (LLM, strict template: schema.org Service + FAQ + Breadcrumb)
    → validate, write to public/landing/<slug>.html
    → add to sitemap.xml
    → record an experiment {change_type: "new_landing", before_pos = current
      homepage position for the query} so we can measure lift later
    → Telegram confirmation

Env: DEEPSEEK_API_KEY (required), TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (optional).

Usage:
  python3 scripts/build_landing.py                 # process all approved requests
  python3 scripts/build_landing.py --query "..."   # build one ad-hoc (no approval)
  python3 scripts/build_landing.py --max 3
"""

from __future__ import annotations

import argparse
import json
import os
import time
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude, DEEPSEEK_API_KEY, DEFAULT_MODEL, CONTENT_MODEL
from seo_db import get_conn, init_db

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
LANDING_DIR = PUBLIC / "landing"
SITEMAP = PUBLIC / "sitemap.xml"
LEDGER_PATH = ROOT / "data" / "experiments.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YEAR = datetime.now().year
MAX_TOKENS = 8000

PHONE_DISPLAY = "+7 987 217-02-02"
PHONE_TEL = "+79872170202"
EMAIL = "info@kazandelikates.tatar"
ADDR_RU = "г. Казань, ул. Аграрная, 2, оф. 7"

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(query: str) -> str:
    s = re.sub(r"[^a-zа-яё0-9\s-]", "", query.lower(), flags=re.IGNORECASE)
    s = re.sub(r"\s+", "-", s.strip())
    s = "".join(TRANSLIT.get(c, c) for c in s)
    return re.sub(r"-+", "-", s).strip("-")[:60]


# ---------------------------------------------------------------- HTML helpers

_FALLBACK_FOOTER = (
    f'\n<footer class="py-4 mt-5" style="background:#1f3b2c;color:#fff">'
    f'<div class="container">'
    f'<p class="mb-1">Казанские Деликатесы (Pepperoni Tatar) — производство халяльной '
    f'мясной продукции и татарской выпечки в Казани.</p>'
    f'<p class="small mb-0">'
    f'<a href="https://pepperoni.tatar/" style="color:#fff">pepperoni.tatar</a> · '
    f'{EMAIL} · {PHONE_DISPLAY}</p>'
    f'</div></footer>\n'
)


def ensure_complete_html(html: str) -> str:
    html = (html or "").rstrip()
    low = html.lower()
    if "</body>" in low and "</html>" in low:
        return html
    lines = html.split("\n")
    if lines and lines[-1].count("<") > lines[-1].count(">"):
        html = "\n".join(lines[:-1]).rstrip()
        low = html.lower()
    if "<body" in low and "</body>" not in low:
        if "<main" in low and "</main>" not in low:
            html += "\n</main>"
        if "</footer>" not in low:
            html += _FALLBACK_FOOTER
        html += "\n</body>"
    if "</html>" not in html.lower():
        html += "\n</html>"
    return html + "\n"


def is_valid_page(html: str) -> bool:
    if any(m in html for m in ("<<<<<<<", "=======\n", ">>>>>>>")):
        return False
    low = html.lower()
    return ("</head>" in low) and ("<h1" in low) and ("</html>" in low) \
        and ("application/ld+json" in low)


GTM = ("<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),"
       "event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),"
       "dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='"
       "+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>")

# Exact site stylesheet (mirrors public/oem/*.html) — keeps every landing on-brand.
SITE_CSS = """  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
    .container{max-width:820px;margin:0 auto;padding:40px 24px}
    nav{font-size:.85rem;color:#888;margin-bottom:32px}nav a{color:#0066cc;text-decoration:none}
    h1{font-size:2rem;font-weight:700;margin-bottom:8px;line-height:1.25}
    h2{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}
    h3{font-size:1.05rem;font-weight:600;margin:20px 0 8px}
    p{margin-bottom:14px}
    .segment-chip{display:inline-block;background:#fef3c7;color:#92400e;padding:4px 10px;border-radius:4px;font-size:.75rem;font-weight:700;margin-bottom:10px;letter-spacing:.5px;text-transform:uppercase}
    .badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0;letter-spacing:.5px}
    .badge-outline{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}
    .hero-subtitle{color:#666;font-size:1.05rem;margin-bottom:4px}
    .card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}
    .grid-2{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:16px 0}
    .feat-card{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px}
    .feat-card .icon{font-size:1.6rem;margin-bottom:6px}.feat-card .title{font-weight:600;font-size:.9rem}.feat-card .desc{font-size:.82rem;color:#666;margin-top:4px}
    table{width:100%;border-collapse:collapse;margin:12px 0}
    th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}th{background:#f5f5f5;font-weight:600}
    ul{margin:8px 0 14px 24px}li{margin-bottom:4px}
    .spec-value{font-weight:600;color:#1b7a3d}
    .faq dt{font-weight:600;margin:14px 0 4px}.faq dd{margin:0 0 10px;color:#555;font-size:.92rem}
    .cta{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0;font-size:.95rem}.cta:hover{background:#15652f}
    .cta-outline{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}
    footer{text-align:center;color:#aaa;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}footer a{color:#888;text-decoration:none}
    @media(max-width:600px){.grid-2{grid-template-columns:1fr}}
  </style>"""

SITE_NAV = """  <div class="container">
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
      <a href="/" style="color:#0066cc;text-decoration:none;font-weight:600">Каталог</a>
      <a href="/oem" style="color:#0066cc;text-decoration:none">OEM</a>
      <a href="/private-label" style="color:#0066cc;text-decoration:none">Private Label</a>
      <a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
      <a href="/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
    </div>"""

SITE_FOOTER = """    <footer>
      <p><a href="/oem">← OEM</a> &middot; <a href="/private-label">Private Label</a> &middot; <a href="/about">О компании</a> &middot; <a href="/faq">FAQ</a></p>
      <p>&copy; <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> &middot; <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
    </footer>
  </div>"""


def build_schema(query: str, canonical: str, faq_pairs: list) -> str:
    """Service + BreadcrumbList + FAQPage JSON-LD (FAQ filled from generated Q/A)."""
    import json as _json
    url = f"https://pepperoni.tatar{canonical}"
    service = {
        "@context": "https://schema.org", "@type": "Service",
        "name": f"Контрактное производство: {query}",
        "serviceType": "Private Label / OEM",
        "areaServed": ["RU", "KZ", "AE", "UZ", "AZ"],
        "provider": {
            "@type": "Organization", "name": "Казанские Деликатесы",
            "url": "https://pepperoni.tatar", "telephone": PHONE_DISPLAY, "email": EMAIL,
            "address": {"@type": "PostalAddress", "addressLocality": "Казань",
                        "addressRegion": "Республика Татарстан", "addressCountry": "RU"}},
    }
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList",
              "itemListElement": [
                  {"@type": "ListItem", "position": 1, "name": "Каталог", "item": "https://pepperoni.tatar/"},
                  {"@type": "ListItem", "position": 2, "name": "OEM", "item": "https://pepperoni.tatar/oem"},
                  {"@type": "ListItem", "position": 3, "name": query, "item": url}]}
    faq = {"@context": "https://schema.org", "@type": "FAQPage",
           "mainEntity": [{"@type": "Question", "name": q,
                           "acceptedAnswer": {"@type": "Answer", "text": a}}
                          for q, a in faq_pairs]}
    blocks = [service, crumbs] + ([faq] if faq_pairs else [])
    return "\n".join(
        f'  <script type="application/ld+json">\n  {_json.dumps(b, ensure_ascii=False)}\n  </script>'
        for b in blocks)


def related_links_block(current_slug: str) -> str:
    """Link the new landing to a few existing OEM pages (cheap SEO lift)."""
    cards = []
    oem_dir = PUBLIC / "oem"
    if oem_dir.exists():
        for f in sorted(oem_dir.glob("*.html")):
            if f.stem == current_slug:
                continue
            name = f.stem.replace("-", " ").title()
            cards.append(
                f'<a href="/oem/{f.stem}" style="display:block;background:#fff;'
                f'border:1px solid #e5e5e5;border-radius:8px;padding:14px;'
                f'text-decoration:none;color:#1a1a1a;font-size:.9rem">'
                f'<strong>{name}</strong><br>'
                f'<span style="color:#666;font-size:.82rem">Контрактное производство под СТМ</span></a>')
            if len(cards) >= 3:
                break
    if not cards:
        return ""
    return ('\n    <h2>Смотрите также</h2>\n    <div class="grid-2">\n      '
            + "\n      ".join(cards) + "\n    </div>")


# ---------------------------------------------------------------- generation

_PORK_PATTERNS = [
    # "...халяль. В составе нет свинины, используются..." → "...халяль. В составе используются..."
    (re.compile(r"\s*В составе нет свинины,?\s*", re.I), " В составе "),
    (re.compile(r",?\s*без свинины", re.I), ""),
    (re.compile(r",?\s*не содержит свинин\w*", re.I), ""),
    (re.compile(r",?\s*нет свинины", re.I), ""),
    (re.compile(r",?\s*no pork", re.I), ""),
]


def _scrub_redundant_pork(html: str) -> str:
    """Halal already implies no pork — strip redundant 'no pork' phrasing."""
    for pat, repl in _PORK_PATTERNS:
        html = pat.sub(repl, html)
    # tidy any double spaces / spaces before punctuation we may have introduced
    html = re.sub(r"  +", " ", html)
    html = re.sub(r"\s+([.,;])", r"\1", html)
    return html


def build_prompt(query: str) -> tuple[str, str]:
    system = (
        "Ты SEO-копирайтер B2B-производителя ХАЛЯЛЬ мясных деликатесов «Казанские "
        "Деликатесы» (pepperoni.tatar) из Казани. Пишешь убедительный, фактический "
        "контент для оптовых/HoReCa покупателей. Без воды и кликбейта. "
        "Отвечаешь СТРОГО валидным JSON без markdown."
    )
    prompt = f"""Сгенерируй контент посадочной страницы под поисковый запрос «{query}».
Верни ТОЛЬКО JSON-объект (без ```), строго по схеме:

{{
  "title": "до 65 символов, запрос «{query}» в начале, в конце ' | Pepperoni.tatar'",
  "description": "до 160 символов, с запросом и УТП (опт, халяль, СТМ)",
  "chip": "короткая надпись-плашка, напр. 'Опт · Контрактное производство'",
  "h1": "H1 с запросом «{query}»",
  "subtitle": "1 предложение-подзаголовок",
  "intro": "вводный абзац (2-3 предложения, <strong> для ключевых фраз) — обычный текст с HTML-тегами внутри",
  "sections": [
    {{"h2": "Заголовок секции", "html": "HTML-контент секии: <p>, <ul><li>, либо <table>. Используй классы card/grid-2/feat-card/spec-value где уместно."}}
  ],
  "faq": [{{"q": "вопрос под запрос", "a": "фактический ответ"}}]
}}

ТРЕБОВАНИЯ К КОНТЕНТУ:
- 4-6 секций: преимущества, ассортимент/спецификации, условия поставки (MOQ от 500 кг/мес),
  сертификаты (Халяль ДУМ РТ № 614A/2024 и № 884А/2025, ХАССП, ISO 22000:2018), кому подходит.
- 4-5 пунктов FAQ под запрос «{query}».
- Контакты НЕ вставляй в секции (их добавит шаблон). Не выдумывай 8-800.
- ХАЛЯЛЬ уже подразумевает отсутствие свинины — НЕ пиши «без свинины», «нет свинины»,
  «no pork». Состав описывай позитивно: «только говядина и/или курица (конина)».
- Только факты о производителе из Казани, опт по РФ и экспорт в СНГ/ОАЭ.
- HTML внутри полей — только инлайн-разметка (p, ul, li, table, strong, div.card и т.п.),
  без <html>, <head>, <script>, <style>."""
    return system, prompt


def _parse_content(raw: str) -> dict | None:
    import json as _json
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw).rstrip("`").rstrip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return _json.loads(m.group(0))
    except Exception:
        return None


def _assemble(query: str, slug: str, data: dict) -> str:
    canonical = f"/landing/{slug}"
    title = (data.get("title") or f"{query} оптом | Pepperoni.tatar").strip()
    desc = (data.get("description") or "").strip()
    chip = escape_attr(data.get("chip") or "Опт · Контрактное производство")
    h1 = data.get("h1") or query.capitalize()
    subtitle = data.get("subtitle") or ""
    intro = data.get("intro") or ""
    faq_pairs = [(f.get("q", "").strip(), f.get("a", "").strip())
                 for f in (data.get("faq") or []) if f.get("q") and f.get("a")]

    sections_html = []
    for s in (data.get("sections") or []):
        h2 = (s.get("h2") or "").strip()
        body = (s.get("html") or "").strip()
        if h2 or body:
            sections_html.append(f"    <h2>{h2}</h2>\n    {body}")
    sections_block = "\n\n".join(sections_html)

    faq_block = ""
    if faq_pairs:
        items = "\n".join(f"      <dt>{q}</dt>\n      <dd>{a}</dd>" for q, a in faq_pairs)
        faq_block = f'\n    <h2>Частые вопросы</h2>\n    <dl class="faq">\n{items}\n    </dl>'

    cta = (
        '\n    <h2>Обсудить производство под ваш бренд</h2>\n'
        '    <p>Напишите нам — подберём рецептуру, формат и упаковку, сделаем образец.</p>\n'
        f'    <a href="tel:{PHONE_TEL}" class="cta">📞 {PHONE_DISPLAY}</a>\n'
        f'    <a href="mailto:{EMAIL}?subject={query}" class="cta cta-outline">📧 {EMAIL}</a>\n'
        f'    <a href="https://wa.me/{PHONE_TEL.lstrip("+")}" class="cta cta-outline">💬 WhatsApp</a>')

    related = related_links_block(slug)
    schema = build_schema(query, canonical, faq_pairs)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
<link rel="preconnect" href="https://mc.yandex.ru" crossorigin>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="content-language" content="ru">
  <meta name="theme-color" content="#1b7a3d">
  <title>{title}</title>
  <meta name="description" content="{escape_attr(desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://pepperoni.tatar{canonical}">
  <link rel="alternate" hreflang="ru" href="https://pepperoni.tatar{canonical}">
  <link rel="alternate" hreflang="x-default" href="https://pepperoni.tatar{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escape_attr(title)}">
  <meta property="og:description" content="{escape_attr(desc)}">
  <meta property="og:url" content="https://pepperoni.tatar{canonical}">
  <link rel="icon" href="/favicon.ico" sizes="any">
{schema}
{SITE_CSS}
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
{SITE_NAV}
    <nav aria-label="Breadcrumb"><a href="/">Каталог</a> &rsaquo; <a href="/oem">OEM</a> &rsaquo; <span>{query}</span></nav>

    <span class="segment-chip">{chip}</span>
    <h1>{h1}</h1>
    <p class="hero-subtitle">{subtitle}</p>
    <span class="badge">HALAL № 614A/2024</span>
    <span class="badge badge-outline">ХАССП + ISO 22000:2018</span>
    <span class="badge badge-outline">от 500 кг/мес</span>

    <p>{intro}</p>

{sections_block}
{faq_block}
{cta}
{related}
{SITE_FOOTER}
</body>
</html>"""
    return _scrub_redundant_pork(html)


def escape_attr(s: str) -> str:
    return (s or "").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


LANDING_REBUILD_DAYS = float(os.environ.get("LANDING_REBUILD_DAYS", "21"))


def build_one(query: str, conn, force: bool = False) -> dict:
    slug = slugify(query)
    if not slug:
        return {"status": "error", "query": query, "error": "empty slug"}
    out_path = LANDING_DIR / f"{slug}.html"
    url = f"https://pepperoni.tatar/landing/{slug}"

    # Idempotency guard: rebuilding the same landing from scratch on every
    # re-queue burns the Opus-advisor budget for no gain (rankings don't move
    # from identical regeneration). Skip if it already exists and is recent.
    if not force and out_path.exists():
        try:
            age_days = (time.time() - out_path.stat().st_mtime) / 86400
        except OSError:
            age_days = 0
        if age_days < LANDING_REBUILD_DAYS:
            return {"status": "skipped_fresh", "query": query, "slug": slug,
                    "url": url, "age_days": round(age_days, 1)}

    system, prompt = build_prompt(query)
    # Flagship landing: Sonnet + advisor for highest quality (not a GEO template).
    raw, tokens = call_claude(prompt, system=system, max_tokens=MAX_TOKENS,
                              advisor=True)
    data = _parse_content(raw)
    if not data or not data.get("sections"):
        return {"status": "error", "query": query, "slug": slug,
                "error": "LLM returned no usable content JSON"}

    html = _assemble(query, slug, data)

    if not is_valid_page(html):
        return {"status": "error", "query": query, "slug": slug,
                "error": "assembled HTML failed validation — not saved"}

    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    add_to_sitemap([url])
    record_experiment(conn, url, str(out_path.relative_to(ROOT)), query)
    return {"status": "ok", "query": query, "slug": slug, "url": url,
            "path": str(out_path), "tokens": tokens}


# ---------------------------------------------------------------- sitemap

def add_to_sitemap(urls: list[str]) -> None:
    if not SITEMAP.exists():
        return
    content = SITEMAP.read_text(encoding="utf-8")
    existing = set(re.findall(r"<loc>(.*?)</loc>", content))
    new = []
    for u in urls:
        if u not in existing:
            new.append(
                f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
                f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>")
    if new:
        content = content.replace("</urlset>", "\n".join(new) + "\n</urlset>")
        SITEMAP.write_text(content, encoding="utf-8")
        print(f"  ✅ sitemap += {len(new)} url")


# ---------------------------------------------------------------- experiments

def _homepage_pos_for_query(conn, query: str) -> tuple[float, float, int]:
    """Current position/ctr/impr the homepage gets for this query — our baseline."""
    try:
        row = conn.execute("""
            SELECT SUM(impressions) impr, SUM(clicks) clk,
                   SUM(position*impressions)/NULLIF(SUM(impressions),0) wpos
            FROM gsc_queries
            WHERE query=? AND date >= date('now','-30 days')
        """, (query,)).fetchone()
        if row and row["impr"]:
            return (row["wpos"] or 0.0,
                    (row["clk"] or 0) / row["impr"],
                    int(row["impr"]))
    except Exception:
        pass
    return (0.0, 0.0, 0)


def record_experiment(conn, url: str, rel_path: str, query: str) -> None:
    try:
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8")) if LEDGER_PATH.exists() else []
    except Exception:
        ledger = []
    pos, ctr, impr = _homepage_pos_for_query(conn, query)
    ledger.append({
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "change_type": "new_landing",
        "page": url,
        "file_path": rel_path,
        "query": query,
        "before_pos": round(pos, 2) if pos else None,
        "before_ctr": round(ctr, 5) if impr else None,
        "before_impr": impr,
        "before_title": "(none — homepage only)",
        "before_desc": "",
        "after_title": f"landing:{query}",
        "verdict": "pending",
        "measured_at": None,
        "after_pos": None,
        "after_ctr": None,
        "after_impr": None,
    })
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- notify

def notify_built(results: list) -> None:
    ok = [r for r in results if r["status"] == "ok"]
    if not ok:
        return
    lines = ["<b>🏗 Landing-Builder — построены лендинги</b>"]
    for r in ok:
        lines.append(f"  ✅ «{r['query']}» → {r['url']}")
    lines.append("\n<i>Добавлены в sitemap и в контур экспериментов — оптимизатор "
                 "измерит прирост трафика через ~14 дней.</i>")
    try:
        import daily_ledger
        daily_ledger.append_event("done", "\n".join(lines))
    except Exception as e:
        print(f"· ledger unavailable: {e}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Build approved landing pages (Scout→approve→page)")
    ap.add_argument("--query", help="Build one landing ad-hoc, bypassing the approval queue")
    ap.add_argument("--max", type=int, default=int(os.environ.get("LANDING_MAX", "5")),
                    help="Max landings to build this run")
    args = ap.parse_args()

    if not DEEPSEEK_API_KEY:
        print("❌ DEEPSEEK_API_KEY not set — cannot build.", file=sys.stderr)
        return 1

    init_db()
    conn = get_conn()
    results = []

    if args.query:
        print(f"🏗 ad-hoc landing: «{args.query}»")
        results.append(build_one(args.query, conn, force=True))
    else:
        try:
            import approvals
        except Exception as e:
            print(f"❌ approvals module unavailable: {e}", file=sys.stderr)
            return 1
        approved = approvals.take_approved("create_landing")
        if not approved:
            print("· no approved create_landing requests")
            conn.close()
            return 0
        print(f"🏗 {len(approved)} approved landing request(s)")
        for a in approved[: args.max]:
            q = (a.get("payload") or {}).get("query") or a.get("title", "")
            if not q:
                continue
            print(f"  → building «{q}»")
            results.append(build_one(q, conn))

    conn.close()

    for r in results:
        if r["status"] == "ok":
            print(f"✅ {r['url']} ({r.get('tokens','?')} tokens)")
        else:
            print(f"⚠️  {r.get('query')}: {r.get('error')}", file=sys.stderr)
    notify_built(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
