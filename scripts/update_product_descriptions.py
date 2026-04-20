#!/usr/bin/env python3
"""
Update product card descriptions based on GSC top queries.
For each product page with GSC traffic, Claude rewrites the description
to better match the search intent and improve CTR.

Env: CLAUDE_API_KEY
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

PUBLIC_DIR   = Path(__file__).parent.parent / "public"
MAX_PRODUCTS = int(os.environ.get("MAX_PRODUCT_UPDATES", "5"))
TODAY        = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def call_claude(system: str, prompt: str, max_tokens: int = 2048) -> tuple[str, int]:
    return _claude(prompt, system=system, max_tokens=max_tokens)


def get_top_queries_for_page(conn, page_url: str, limit: int = 5) -> list[str]:
    """Get top GSC queries for a specific product page."""
    rows = conn.execute("""
        SELECT query, SUM(impressions) as impr, AVG(position) as pos
        FROM gsc_queries
        WHERE page = ? AND date >= date('now', '-30 days')
        GROUP BY query
        ORDER BY impr DESC
        LIMIT ?
    """, (page_url, limit)).fetchall()
    return [r["query"] for r in rows]


def get_products_with_traffic(conn) -> list[dict]:
    """Get product pages that have GSC traffic in last 30 days."""
    rows = conn.execute("""
        SELECT page, SUM(clicks) as clicks, SUM(impressions) as impr, AVG(ctr) as ctr
        FROM gsc_queries
        WHERE page LIKE '%/products/%' AND date >= date('now', '-30 days')
        GROUP BY page
        HAVING impr > 10
        ORDER BY impr DESC
        LIMIT ?
    """, (MAX_PRODUCTS,)).fetchall()
    return [dict(r) for r in rows]


def extract_product_description(html: str) -> str:
    """Extract current description from product HTML."""
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    return m.group(1) if m else ""


def extract_product_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1) if m else ""


def rewrite_product_meta(html: str, new_title: str, new_desc: str) -> str:
    """Update title and meta description in product HTML."""
    html = re.sub(r"<title>[^<]*</title>", f"<title>{new_title}</title>", html, count=1)
    html = re.sub(
        r'<meta\s+name=["\']description["\']\s+content=["\'][^"\']*["\']',
        f'<meta name="description" content="{new_desc}"',
        html, count=1, flags=re.IGNORECASE,
    )
    return html


def update_product_page(page_url: str, queries: list[str], conn) -> bool:
    """Rewrite product page meta based on top GSC queries."""
    # Resolve file path
    rel = page_url.replace("https://pepperoni.tatar", "").rstrip("/")
    if not rel.endswith(".html"):
        rel += ".html"

    file_path = PUBLIC_DIR / rel.lstrip("/")
    if not file_path.exists():
        # Try without extension
        file_path = PUBLIC_DIR / (rel.lstrip("/").rstrip(".html"))
        if not file_path.exists():
            print(f"  ⚠️  File not found: {rel}", file=sys.stderr)
            return False

    try:
        html = file_path.read_text(encoding="utf-8")
    except Exception as ex:
        print(f"  ⚠️  Read failed: {ex}", file=sys.stderr)
        return False

    current_title = extract_product_title(html)
    current_desc  = extract_product_description(html)
    queries_str   = ", ".join(f'«{q}»' for q in queries[:5])

    system = (
        "Ты SEO-специалист для B2B сайта производителя халяль мясных изделий pepperoni.tatar. "
        "Улучшаешь title и meta description продуктовых страниц на основе реальных поисковых запросов. "
        "Цель: повысить CTR и релевантность. Язык — русский."
    )
    prompt = f"""Продуктовая страница: {page_url}
Текущий title: «{current_title}»
Текущее описание: «{current_desc}»

Реальные поисковые запросы по этой странице (из Google Search Console):
{queries_str}

Улучши title и meta description, чтобы:
1. Точнее соответствовать поисковым запросам
2. Включить ключевые слова из списка запросов
3. Добавить USP: халяль, HACCP, оптом, доставка
4. Призыв к действию (купить, заказать, получить прайс)

Верни JSON:
{{"title": "новый title (до 65 символов)", "description": "новый meta description (до 160 символов)"}}
Только JSON."""

    try:
        raw, tokens = call_claude(system, prompt)
        m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not m:
            return False
        data = json.loads(m.group(0))
        new_title = data.get("title", "").strip()
        new_desc  = data.get("description", "").strip()

        if not new_title or new_title == current_title:
            return False

        new_html = rewrite_product_meta(html, new_title, new_desc)
        file_path.write_text(new_html, encoding="utf-8")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO generated_content
               (created_at, type, lang, query, slug, file_path, title, status, claude_model, tokens_used)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (now, "product_meta_update", "ru", queries[0] if queries else "", page_url,
             str(file_path), new_title, "published", CLAUDE_MODEL, tokens),
        )
        print(f"  ✅ {file_path.name}: «{new_title[:50]}»")
        return True

    except Exception as ex:
        print(f"  ⚠️  Update failed ({page_url}): {ex}", file=sys.stderr)
        return False


def main():
    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    init_db()
    conn = get_conn()

    print(f"📦 Product Description Updater — {TODAY}")

    products = get_products_with_traffic(conn)

    if not products:
        print("  ℹ️  No product pages with GSC traffic found. Skipping.")
        conn.close()
        return

    print(f"  Found {len(products)} product pages with traffic")
    count = 0

    for product in products:
        page_url = product["page"]
        queries = get_top_queries_for_page(conn, page_url)
        if not queries:
            continue

        print(f"\n  🔍 {page_url} — top queries: {', '.join(queries[:3])}")
        ok = update_product_page(page_url, queries, conn)
        if ok:
            count += 1

    conn.commit()
    conn.close()
    print(f"\n✅ Updated {count} product pages")


if __name__ == "__main__":
    main()
