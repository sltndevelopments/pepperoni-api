#!/usr/bin/env python3
"""Generate bespoke deep content (~700 words RU + ~600 EN) for flagship SKUs.

Writes data/product_overrides/<sku>.html (RU) and <sku>.en.html (EN). These are
injected by gen-ru-products.py / gen-en-products.py after the category block, so
top money SKUs carry rich, query-targeted content that survives regeneration.

The content is structured HTML sections in the page's existing classes
(.section-block / .section-title) — no <style>, no schema (the product page
already supplies Product + FAQPage schema). Halal implies no pork: never write it.

Usage:  python3 scripts/gen_sku_deep.py KD-001 KD-014 KD-057 ...
Env:    DEEPSEEK_API_KEY required.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude, CONTENT_MODEL

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "product_overrides"
PRODUCTS = json.load(open(ROOT / "public" / "products.json", encoding="utf-8"))
ITEMS = PRODUCTS if isinstance(PRODUCTS, list) else PRODUCTS.get("products", [])
BY_SKU = {it.get("sku"): it for it in ITEMS}


def _scrub_pork(html: str) -> str:
    for pat in [r"\s*\(?без свинины\)?", r"\s*,?\s*нет свинины", r"\s*\(?no pork\)?",
                r"\s*,?\s*без содержания свинины"]:
        html = re.sub(pat, "", html, flags=re.I)
    return html


def gen(sku: str, lang: str) -> str | None:
    p = BY_SKU.get(sku)
    if not p:
        print(f"  ! {sku} not found", file=sys.stderr)
        return None
    name = p.get("name", "")
    cat = p.get("category", "")
    ing = p.get("ingredientsRU", "")
    is_en = lang == "en"
    from brand_system import brand_block
    sys_p = brand_block("en" if is_en else "ru") + "\n\n" + (
        "You are an SEO + B2B copywriter for halal meat producer 'Kazan Delicacies' "
        "(pepperoni.tatar). Write deep, factual, non-clickbait wholesale/HoReCa content."
        if is_en else
        "Ты SEO + B2B копирайтер халяль-производителя «Казанские Деликатесы» "
        "(pepperoni.tatar). Пишешь глубокий, фактурный, без воды контент про опт/HoReCa."
    )
    rules = (
        "Write 5-6 <div class=\"section-block\"><h2 class=\"section-title\">…</h2><p>…</p></div> "
        "blocks (~600 words total) about this product for wholesale/HoReCa/private-label buyers: "
        "application, who it suits, why it wins, wholesale terms, storage/logistics, halal & docs. "
        "Use the EXACT product name and category as search phrasing. Halal already implies no pork — "
        "NEVER write 'no pork'. Return ONLY the HTML blocks, no <html>/<head>/<style>, no markdown fences."
        if is_en else
        "Напиши 5-6 блоков <div class=\"section-block\"><h2 class=\"section-title\">…</h2><p>…</p></div> "
        "(~700 слов суммарно) про этот товар для оптовых/HoReCa/СТМ покупателей: применение, кому "
        "подходит, чем выигрывает, оптовые условия, хранение/логистика, халяль и документы. "
        "Используй ТОЧНОЕ название и категорию как поисковую формулировку. «Халяль» уже подразумевает "
        "отсутствие свинины — НИКОГДА не пиши «без свинины». Верни ТОЛЬКО HTML-блоки, без "
        "<html>/<head>/<style>, без markdown-обёрток."
    )
    prompt = (f"{rules}\n\nProduct / Товар: «{name}»\nCategory / Категория: «{cat}»\n"
              f"Ingredients / Состав: {ing[:300]}")
    raw, _ = call_claude(prompt, system=sys_p, max_tokens=2200, effort="medium",
                         model=CONTENT_MODEL)
    html = raw.strip()
    html = re.sub(r"^```\w*\s*|\s*```$", "", html).strip()
    if "<div" not in html:
        print(f"  ! {sku}/{lang}: no html returned", file=sys.stderr)
        return None
    return _scrub_pork(html)


def main() -> int:
    args = sys.argv[1:]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if args and args[0] == "--all":
        skus = [it.get("sku") for it in ITEMS if it.get("sku")]
    elif args:
        skus = args
    else:
        print("usage: gen_sku_deep.py [--all | <SKU> ...] [--force]")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0
    for sku in skus:
        for lang, suffix in (("ru", ".html"), ("en", ".en.html")):
            out = OUT / f"{sku.lower()}{suffix}"
            if out.exists() and not force:
                skipped += 1
                continue
            try:
                html = gen(sku, lang)
            except Exception as e:  # network/LLM flake — keep going, resumable
                print(f"  ! {sku}/{lang}: {str(e)[:80]}", file=sys.stderr)
                failed += 1
                continue
            if html:
                out.write_text(html, encoding="utf-8")
                wc = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", html)))
                print(f"  ✓ {sku}/{lang}: {wc} words -> {out.name}", flush=True)
                done += 1
            else:
                failed += 1
    print(f"\nDONE done={done} skipped={skipped} failed={failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
