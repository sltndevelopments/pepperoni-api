#!/usr/bin/env python3
"""
rebuild_blog_index.py — regenerate public/blog.html and public/en/blog.html
from the actual article files on disk.

Problem it fixes: the SEO agent (generate_content.py / seo-agent-vps.sh)
creates and commits new articles into public/blog/*.html and
public/en/blog/*.html every day, but nothing ever updated the index pages
(public/blog.html, public/en/blog.html) that list them for humans. The
index pages were hand-written once in February 2026 and never touched
again, so ~95% of published articles were unreachable via /blog navigation
even though they were live and indexed by search engines.

This script is deterministic (no LLM): it reads <title>, <meta
description>, and JSON-LD datePublished from each article file, sorts by
date (newest first), and re-renders the two index pages, preserving their
existing look (same CSS/nav/footer as before).

Run manually:      python3 scripts/rebuild_blog_index.py
Run in pipeline:    called from scripts/seo-agent-vps.sh after content gen.
"""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://pepperoni.tatar"

CONFIGS = [
    {
        "lang": "ru",
        "articles_dir": ROOT / "public" / "blog",
        "index_path": ROOT / "public" / "blog.html",
        "url_prefix": "/blog",
        "html_lang": "ru",
        "count_word": lambda n: f"{n} стат{'ья' if n % 10 == 1 and n % 100 != 11 else ('ьи' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'ей')}",
        "read_more": "Читать полностью →",
        "nofollow_prefixes": (),
    },
    {
        "lang": "en",
        "articles_dir": ROOT / "public" / "en" / "blog",
        "index_path": ROOT / "public" / "en" / "blog.html",
        "url_prefix": "/en/blog",
        "html_lang": "en",
        "count_word": lambda n: f"{n} article{'s' if n != 1 else ''}",
        "read_more": "Read more →",
        "nofollow_prefixes": (),
    },
]

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESC_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']\s*/?>',
    re.IGNORECASE | re.DOTALL,
)
DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
MOD_RE = re.compile(r'"dateModified"\s*:\s*"([^"]+)"')


def clean(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    return text


def truncate(text, limit=170):
    text = clean(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def parse_article(path: Path):
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    title_match = TITLE_RE.search(html)
    title = clean(title_match.group(1)) if title_match else path.stem
    # Strip common " — Kazan Delicacies" / " | pepperoni.tatar" suffixes for card display.
    title = re.split(r"\s*[|—–]\s*(Казанские Деликатесы|Kazan Delicacies|pepperoni\.tatar)\s*$", title)[0].strip()

    desc_match = DESC_RE.search(html)
    desc = truncate(desc_match.group(1)) if desc_match else ""

    date_match = DATE_RE.search(html)
    mod_match = MOD_RE.search(html)
    raw_date = (date_match.group(1) if date_match else None) or (mod_match.group(1) if mod_match else None)

    dt = None
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError:
            dt = None
    if dt is None:
        dt = datetime.fromtimestamp(path.stat().st_mtime)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)

    return {
        "slug": path.stem,
        "title": title or path.stem,
        "desc": desc,
        "date": dt,
        "date_display": dt.strftime("%d.%m.%Y") if raw_date else dt.strftime("%d.%m.%Y"),
    }


def render_index(cfg, articles):
    path = cfg["index_path"]
    html = path.read_text(encoding="utf-8")

    count_text = cfg["count_word"](len(articles))
    html = re.sub(r'<div class="count">.*?</div>', f'<div class="count">{count_text}</div>', html, count=1)

    cards = []
    for art in articles:
        url = f"{cfg['url_prefix']}/{art['slug']}"
        cards.append(
            "    <article class=\"article-card\">\n"
            f"      <div class=\"article-date\">{art['date_display']}</div>\n"
            f"      <h2 class=\"article-title\"><a href=\"{url}\">{art['title']}</a></h2>\n"
            f"      <p class=\"article-desc\">{art['desc']}</p>\n"
            f"      <a href=\"{url}\" class=\"read-more\">{cfg['read_more']}</a>\n"
            "    </article>"
        )
    grid_html = "  <div class=\"articles-grid\">\n" + "\n".join(cards) + "\n  </div>\n"

    html = re.sub(
        r'  <div class="articles-grid">.*?</div>\n(?=</div>\s*<footer)',
        grid_html,
        html,
        count=1,
        flags=re.DOTALL,
    )

    path.write_text(html, encoding="utf-8")
    return len(articles)


def main():
    total = 0
    for cfg in CONFIGS:
        articles = []
        for f in sorted(cfg["articles_dir"].glob("*.html")):
            parsed = parse_article(f)
            if parsed:
                articles.append(parsed)
        articles.sort(key=lambda a: a["date"], reverse=True)
        n = render_index(cfg, articles)
        total += n
        print(f"[{cfg['lang']}] rebuilt {cfg['index_path'].relative_to(ROOT)} — {n} articles")
    print(f"done — {total} articles total across all indexes")


if __name__ == "__main__":
    main()
