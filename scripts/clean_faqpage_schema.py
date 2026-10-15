#!/usr/bin/env python3
"""Keep FAQPage JSON-LD only where the page has a real visible FAQ.

Templated copies on every SKU card (two identical questions) are removed
together with the visible boilerplate; a short order/price link stays.
Pages with a unique visible FAQ (details, .faq-item, «Частые вопросы») keep
both the HTML and the schema.

Usage: clean_faqpage_schema.py [--check]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

LD_RE = re.compile(
    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
PRODUCT_RE = re.compile(r"(?:^|/)(?:en/)?products/kd-\d{3}\.html$")
# Identical two-question block injected by gen-ru/en-products.py
RU_FAQ_BLOCK = re.compile(
    r'<div class="section-block"><h2 class="section-title">Частые вопросы</h2>'
    r".*?</div>",
    re.S,
)
EN_FAQ_BLOCK = re.compile(
    r'<div class="section-block"><h2 class="section-title">FAQ</h2>'
    r".*?</div>",
    re.S,
)
VISIBLE_FAQ_RE = re.compile(
    r'<(?:h1|h2|h3)[^>]*>\s*(?:Частые вопросы|Вопросы и ответы|FAQ|Frequently asked)\s*<'
    r'|<details\b[^>]*>\s*<summary\b'
    r'|<div class="faq-(?:item|q|a)"'
    r'|<p class="faq-q"',
    re.I,
)
QA_MARKUP_RE = re.compile(
    r'<details\b|<div class="faq-(?:item|q|a)"|<p class="faq-q"',
    re.I,
)
FAQ_HEADING_RE = re.compile(
    r'<(?:h1|h2|h3)[^>]*>\s*(?:Частые вопросы|Вопросы и ответы|FAQ|Frequently asked)',
    re.I,
)

RU_ORDER = (
    '<div class="section-block"><h2 class="section-title">Заказ</h2>'
    '<p style="font-size:.95rem;color:#333;line-height:1.7;margin:0">'
    'Оптовый заказ — по инструкции <a href="/kak-zakazat">«Как заказать»</a>. '
    'Прайс: <a href="/price">/price</a> · '
    '<a href="/prices.xlsx">Excel</a> · <a href="/prices.pdf">PDF</a>. '
    'Халяль — <a href="/halal">/halal</a>.</p></div>'
)
EN_ORDER = (
    '<div class="section-block"><h2 class="section-title">Order</h2>'
    '<p style="font-size:.95rem;color:#333;line-height:1.7;margin:0">'
    'Wholesale orders follow <a href="/en/kak-zakazat">How to order</a>. '
    'Price list: <a href="/en/price">/en/price</a> · '
    '<a href="/prices.xlsx">Excel</a> · <a href="/prices.pdf">PDF</a>. '
    'Halal — <a href="/en/halal">/en/halal</a>.</p></div>'
)


def _kinds(node) -> list[str]:
    if not isinstance(node, dict):
        return []
    kind = node.get("@type")
    if isinstance(kind, list):
        return [str(k) for k in kind]
    return [str(kind)] if kind else []


def _is_faqpage(node) -> bool:
    if isinstance(node, list):
        return any(_is_faqpage(item) for item in node)
    if not isinstance(node, dict):
        return False
    if "FAQPage" in _kinds(node):
        return True
    if "@graph" in node:
        return _is_faqpage(node["@graph"])
    return False


def _strip_faq_from_graph(node):
    if isinstance(node, list):
        return [item for item in (_strip_faq_from_graph(x) for x in node) if item is not None]
    if isinstance(node, dict):
        if "FAQPage" in _kinds(node):
            return None
        return {k: _strip_faq_from_graph(v) for k, v in node.items()}
    return node


def remove_faqpage_scripts(html: str) -> str:
    def repl(match: re.Match) -> str:
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return match.group(0)
        if not _is_faqpage(data):
            return match.group(0)
        if isinstance(data, dict) and "@graph" in data:
            graph = _strip_faq_from_graph(data["@graph"])
            if not graph:
                return ""
            data = dict(data)
            data["@graph"] = graph
            dumped = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            return f'<script type="application/ld+json">{dumped}</script>'
        if isinstance(data, list):
            cleaned = _strip_faq_from_graph(data)
            if not cleaned:
                return ""
            dumped = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
            return f'<script type="application/ld+json">{dumped}</script>'
        return ""

    return LD_RE.sub(repl, html)


def has_visible_faq(html: str) -> bool:
    """True only when the page shows a real FAQ (heading + Q/A), not a stray class."""
    body = html.split("<body", 1)[-1] if "<body" in html.lower() else html
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.I | re.S)
    heading = bool(FAQ_HEADING_RE.search(body))
    qa = bool(QA_MARKUP_RE.search(body))
    return heading and qa


def clean_product(html: str, is_en: bool) -> str:
    html = remove_faqpage_scripts(html)
    block = EN_FAQ_BLOCK if is_en else RU_FAQ_BLOCK
    repl = EN_ORDER if is_en else RU_ORDER
    if block.search(html):
        html = block.sub(repl, html, count=1)
    return html


def clean_file(path: Path) -> str | None:
    html = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(PUBLIC)).replace("\\", "/")
    if PRODUCT_RE.search(rel):
        new = clean_product(html, rel.startswith("en/"))
    elif _is_faqpage_in(html) and not has_visible_faq(html):
        new = remove_faqpage_scripts(html)
    else:
        new = html
    return new if new != html else None


def _is_faqpage_in(html: str) -> bool:
    for raw in LD_RE.findall(html):
        try:
            if _is_faqpage(json.loads(raw.strip())):
                return True
        except (ValueError, TypeError):
            continue
    return False


def main() -> int:
    check = "--check" in sys.argv
    changed = 0
    for path in sorted(PUBLIC.rglob("*.html")):
        new = clean_file(path)
        if new is None:
            continue
        changed += 1
        if not check:
            path.write_text(new, encoding="utf-8")
    print(f"faqpage: {changed} page(s) {'need update' if check else 'cleaned'}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
