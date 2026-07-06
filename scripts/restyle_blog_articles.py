#!/usr/bin/env python3
"""
restyle_blog_articles.py — convert off-brand blog pages (Bootstrap/red theme)
into the pepperoni.tatar brand shell (green nav, article-wrap, GTM).

Deterministic: no LLM. Preserves article text, tables, FAQ, linker blocks.

Usage:
  python3 scripts/restyle_blog_articles.py          # restyle all off-brand pages
  python3 scripts/restyle_blog_articles.py --dry-run  # report only
  python3 scripts/restyle_blog_articles.py --slug kotlety-dlya-burgerov-kupit-optom
"""
from __future__ import annotations

import argparse
import re
import sys
from html import escape, unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from blog_template import (
    EMAIL,
    PHONE_DISPLAY,
    PHONE_TEL,
    format_date_display,
    short_title,
    wrap_blog_page,
)

CONFIGS = [
    {"lang": "ru", "dir": ROOT / "public" / "blog"},
    {"lang": "en", "dir": ROOT / "public" / "en" / "blog"},
]

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
DESC_RE = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', re.I | re.S)
DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
JSONLD_RE = re.compile(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
LEAD_RE = re.compile(r'<p[^>]*class=["\'][^"\']*lead[^"\']*["\'][^>]*>(.*?)</p>', re.I | re.S)
MAIN_RE = re.compile(r"<main[^>]*>(.*?)</main>", re.I | re.S)
LINKER_RE = re.compile(r"<section[^>]*data-linker[^>]*>.*?</section>", re.I | re.S)
FAQ_SECTION_RE = re.compile(r'<section[^>]*class=["\'][^"\']*faq-section[^"\']*["\'][^>]*>.*?</section>', re.I | re.S)


def needs_restyle(html: str) -> bool:
    if "article-wrap" in html and ".nav__inner" in html and "bootstrap" not in html.lower():
        return False
    if "bootstrap" in html.lower():
        return True
    if "hero-section" in html or "#c0392b" in html or "c0392b" in html:
        return True
    if "article-wrap" not in html or ".nav__inner" not in html:
        return True
    return False


def strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_article_schema(html: str) -> tuple[str, str | None]:
    date_iso = None
    article_schema = ""
    for block in JSONLD_RE.findall(html):
        block = block.strip()
        if '"FAQPage"' in block:
            continue
        if '"BreadcrumbList"' in block:
            continue
        if '"Article"' in block or '"BlogPosting"' in block:
            article_schema = f'<script type="application/ld+json">\n{block}\n</script>'
            m = DATE_RE.search(block)
            if m:
                date_iso = m.group(1)
            break
    if not date_iso:
        m = DATE_RE.search(html)
        if m:
            date_iso = m.group(1)
    return article_schema, date_iso


def extract_faq_schema(html: str) -> str:
    for block in JSONLD_RE.findall(html):
        if '"FAQPage"' in block:
            return f'<script type="application/ld+json">\n{block.strip()}\n</script>'
    return ""


def unwrap_layout_divs(html: str) -> str:
    """Remove Bootstrap layout wrappers but keep semantic blocks (info-box, cta-block, card)."""
    layout = r"(?:container|row|col(?:-\w+)*|justify-content-\w+|align-items-\w+|gy-\d+|my-\d+|mb-\d+|mt-\d+|py-\d+|px-\d+|text-center|text-md-end|d-flex|flex-wrap|gap-\d+|opacity-\d+|small|fw-bold|table-responsive)"
    prev = None
    cur = html
    for _ in range(30):
        prev = cur
        cur = re.sub(
            rf'<div[^>]*class=["\'][^"\']*{layout}[^"\']*["\'][^>]*>\s*(.*?)\s*</div>',
            r"\1",
            cur,
            flags=re.S | re.I,
        )
        if cur == prev:
            break
    return cur


def clean_content_html(html: str) -> str:
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    html = re.sub(r"<noscript[^>]*>.*?</noscript>", "", html, flags=re.S)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.S)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.S)
    html = re.sub(
        r'<section[^>]*class=["\'][^"\']*hero-section[^"\']*["\'][^>]*>.*?</section>',
        "",
        html,
        flags=re.S,
    )
    html = re.sub(r'<ol[^>]*class=["\'][^"\']*breadcrumb[^"\']*["\'][^>]*>.*?</ol>', "", html, flags=re.S)

    html = html.replace("tip-box", "info-box")
    html = html.replace("cta-section", "cta-block")
    html = unwrap_layout_divs(html)

    html = re.sub(r'\sclass=["\'][^"\']*["\']', "", html)
    html = re.sub(r'\sstyle=["\'][^"\']*["\']', "", html)
    html = re.sub(r'\sid=["\'][^"\']*["\']', "", html)

    html = re.sub(r"<h3([^>]*)>", r"<h2\1>", html)
    html = re.sub(r"</h3>", "</h2>", html)

    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def default_cta(lang: str) -> str:
    if lang == "en":
        return f"""<div class="cta-block">
  <h2>Request a wholesale price list</h2>
  <p>Contact our sales team for catalog, samples, and export terms.</p>
  <a href="tel:{PHONE_TEL}" class="btn-cta">{PHONE_DISPLAY}</a>
  <a href="mailto:{EMAIL}" class="btn-cta">{EMAIL}</a>
</div>"""
    return f"""<div class="cta-block">
  <h2>Получить оптовый прайс-лист</h2>
  <p>Свяжитесь с отделом продаж — пришлём каталог, образцы и условия поставки.</p>
  <a href="tel:{PHONE_TEL}" class="btn-cta">{PHONE_DISPLAY}</a>
  <a href="mailto:{EMAIL}" class="btn-cta">{EMAIL}</a>
</div>"""


def extract_content(html: str, lang: str) -> tuple[str, str, str]:
    body_m = BODY_RE.search(html)
    body = body_m.group(1) if body_m else html

    tail = ""
    linker = LINKER_RE.search(body)
    if linker:
        tail += linker.group(0)
        body = body.replace(linker.group(0), "")

    faq_sec = FAQ_SECTION_RE.search(body)
    if faq_sec:
        tail += faq_sec.group(0)
        body = body.replace(faq_sec.group(0), "")

    h1_m = H1_RE.search(body)
    h1 = strip_tags(h1_m.group(1)) if h1_m else ""
    lead_m = LEAD_RE.search(body)
    lead = lead_m.group(1).strip() if lead_m else ""

    main_m = MAIN_RE.search(body)
    content = main_m.group(1) if main_m else body
    content = clean_content_html(content)

    if h1:
        content = re.sub(r"<h1[^>]*>.*?</h1>", "", content, count=1, flags=re.S | re.I)
    if lead_m:
        content = re.sub(
            r'<p[^>]*class=["\']lead["\'][^>]*>.*?</p>',
            "",
            content,
            count=1,
            flags=re.S | re.I,
        )
    content = re.sub(r"<h1[^>]*>.*?</h1>", "", content, flags=re.S | re.I)

    cta_m = re.search(r'<div[^>]*class=["\']cta-block["\'][^>]*>.*?</div>', content, flags=re.S | re.I)
    cta_html = cta_m.group(0) if cta_m else default_cta(lang)
    if cta_m:
        content = content.replace(cta_m.group(0), "").strip()

    parts = []
    if lead:
        parts.append(f'<p class="lead">{lead}</p>')
    if content:
        parts.append(content)
    parts.append(cta_html)
    return h1, "\n\n".join(p for p in parts if p), tail


def restyle_file(path: Path, lang: str, dry_run: bool = False) -> bool:
    html = path.read_text(encoding="utf-8")
    if not needs_restyle(html):
        return False

    slug = path.stem
    title_m = TITLE_RE.search(html)
    desc_m = DESC_RE.search(html)
    title = strip_tags(title_m.group(1)) if title_m else slug.replace("-", " ").title()
    desc = desc_m.group(1).strip() if desc_m else title[:160]

    article_schema, date_iso = extract_article_schema(html)
    faq_schema = extract_faq_schema(html)
    h1, body_main, tail = extract_content(html, lang)
    if not h1:
        h1 = short_title(title)

    meta_line = (
        f"{format_date_display(date_iso, lang)} · "
        + ("Казанские Деликатесы" if lang == "ru" else "Kazan Delicacies")
    )
    main_block = f"""<h1>{escape(h1)}</h1>
<div class="meta">{meta_line}</div>
{body_main}"""

    new_html = wrap_blog_page(
        lang=lang,
        slug=slug,
        title=title,
        description=desc,
        body_main=main_block,
        article_schema=article_schema,
        extra_head=faq_schema,
        tail_sections=tail,
        date_iso=date_iso,
    )

    if dry_run:
        print(f"  would restyle: {path.relative_to(ROOT)}")
        return True

    path.write_text(new_html, encoding="utf-8")
    print(f"  ✅ {path.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--slug", help="Restyle one slug (ru/en both if exist)")
    args = parser.parse_args()

    changed = 0
    for cfg in CONFIGS:
        d = cfg["dir"]
        if not d.exists():
            continue
        files = sorted(d.glob("*.html"))
        if args.slug:
            files = [d / f"{args.slug}.html"]
        print(f"[{cfg['lang']}] scanning {len(files)} articles …")
        for f in files:
            if not f.exists():
                continue
            if restyle_file(f, cfg["lang"], dry_run=args.dry_run):
                changed += 1

    print(f"done — {changed} article(s) {'would be ' if args.dry_run else ''}restyled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
