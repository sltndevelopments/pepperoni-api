#!/usr/bin/env python3
"""Render the SKU catalog into static HTML so crawlers and AI agents see it.

Before this, the homepage catalog was an empty `#catalog-inner` filled by JS
after an IntersectionObserver fired, and `/products` was a link list pointing at
JSON. Googlebot renders JS but never scrolls, so the money content (62 SKUs with
prices) was invisible in the HTML snapshot, and non-rendering agents saw only
"Загрузка каталога..". This script injects a grouped, linked SKU list into:

  public/index.html            #catalog-inner  (RU)
  public/en/index.html         #catalog-inner  (EN)
  public/products/index.html   .wrap           (RU hub)
  public/en/products/index.html .wrap          (EN hub)

The homepage JS still replaces the block with the interactive grid on load, so
UX is unchanged. Idempotent: content sits between explicit markers. Runs after
sync in scripts/sync-vps.sh so prices in the static HTML follow the Sheet.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS = PUBLIC / "products.json"

SECTION_ORDER = ["Заморозка", "Охлаждённая продукция", "Выпечка"]
SECTION_EN = {
    "Заморозка": "Frozen",
    "Охлаждённая продукция": "Chilled",
    "Выпечка": "Bakery",
}
TRANSLATIONS = ROOT / "scripts" / "translations.json"
START = "<!--catalog-static:start-->"
END = "<!--catalog-static:end-->"

STYLE = (
    "<style>"
    ".cs-sec{margin:18px 0 6px;font-size:1.05rem}"
    ".cs-cat{margin:12px 0 4px;font-size:.95rem;color:#444}"
    ".cs-list{list-style:none;margin:0;padding:0;display:grid;"
    "grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:6px 18px}"
    ".cs-list li{display:flex;justify-content:space-between;gap:10px;"
    "padding:6px 0;border-bottom:1px solid #eee;font-size:.9rem}"
    ".cs-list a{color:inherit;text-decoration:none}"
    ".cs-list a:hover{text-decoration:underline}"
    ".cs-meta{white-space:nowrap;color:#555}"
    ".cs-price{font-weight:600;color:#1b7a3d}"
    "</style>"
)


def fmt_rub(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v <= 0:
        return ""
    s = f"{v:,.0f}".replace(",", " ")
    return f"{s} ₽"


def weight_text(p: dict, lang: str) -> str:
    w = str(p.get("weight") or "").strip()
    if not w:
        return ""
    if lang == "en":
        w = w.replace(" г", " g").replace(" кг", " kg").replace(",", ".")
        if not re.search(r"\b(g|kg)\b", w):
            w += " kg"
    else:
        if " г" not in w and " кг" not in w:
            w += " кг"
    return w


def load_translations() -> dict:
    if TRANSLATIONS.exists():
        return json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    return {}


def en_name(p: dict, tr: dict) -> str:
    """Same lookup as gen-en-products.py: normalized lowercase RU name → EN."""
    clean = " ".join(str(p.get("name") or "").split())
    return tr.get("products", {}).get(clean.lower()) or clean


def en_category(cat: str, tr: dict) -> str:
    return tr.get("categories", {}).get(cat) or cat


def group(products: list[dict]) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = {}
    for p in products:
        sec = p.get("section") or "Прочее"
        cat = p.get("category") or sec
        out.setdefault(sec, {}).setdefault(cat, []).append(p)
    return out


def render(products: list[dict], lang: str, hub: bool) -> str:
    grouped = group(products)
    tr = load_translations() if lang == "en" else {}
    sections = [s for s in SECTION_ORDER if s in grouped] + \
               [s for s in grouped if s not in SECTION_ORDER]
    prefix = "/en" if lang == "en" else ""
    total = len(products)
    if lang == "en":
        lead = f"{total} SKUs · prices incl. VAT, EXW Kazan · each SKU has its own page"
    else:
        lead = f"{total} SKU · цены с НДС, EXW Казань · у каждой позиции своя карточка"
    parts = [START, STYLE, f'<p class="cs-lead" style="font-size:.85rem;color:#595959;margin:0 0 6px">{lead}</p>']
    for sec in sections:
        sec_label = SECTION_EN.get(sec, sec) if lang == "en" else sec
        parts.append(f'<h3 class="cs-sec">{escape(sec_label)}</h3>')
        for cat, items in grouped[sec].items():
            cat_label = en_category(cat, tr) if lang == "en" else cat
            if cat_label != sec_label:
                parts.append(f'<h4 class="cs-cat">{escape(str(cat_label))}</h4>')
            parts.append('<ul class="cs-list">')
            for p in items:
                sku = str(p.get("sku") or "").strip()
                name = en_name(p, tr) if lang == "en" else (p.get("name") or sku)
                href = f"{prefix}/products/{sku.lower()}" if sku else "#"
                price = fmt_rub((p.get("offers") or {}).get("price") or (p.get("offers") or {}).get("pricePerUnit"))
                w = weight_text(p, lang)
                meta = " · ".join(x for x in (sku, w) if x)
                parts.append(
                    f'<li><a href="{href}">{escape(str(name))}</a>'
                    f'<span class="cs-meta">{escape(meta)}'
                    f'{(" · <span class=cs-price>" + price + "</span>") if price else ""}</span></li>'
                )
            parts.append("</ul>")
    parts.append(END)
    return "\n".join(parts)


def replace_between(text: str, block: str, open_re: str, close_literal: str) -> str:
    """Insert/replace block right after the element opened by open_re."""
    if START in text and END in text:
        return text[: text.index(START)] + block + text[text.index(END) + len(END):]
    m = re.search(open_re, text)
    if not m:
        raise SystemExit(f"anchor not found: {open_re}")
    return text[: m.end()] + "\n" + block + "\n" + text[m.end():]


def inject_home(path: Path, products: list[dict], lang: str) -> None:
    text = path.read_text(encoding="utf-8")
    block = render(products, lang, hub=False)
    if START not in text:
        # Keep #loading for the JS error path, but never show its placeholder text.
        text = re.sub(
            r'<div id="loading"[^>]*>[^<]*</div>',
            '<div id="loading" hidden></div>',
            text, count=1,
        )
    text = replace_between(text, block, r'<div id="catalog-inner"[^>]*>', "")
    path.write_text(text, encoding="utf-8")


def inject_hub(path: Path, products: list[dict], lang: str) -> None:
    text = path.read_text(encoding="utf-8")
    block = render(products, lang, hub=True)
    if START in text:
        text = replace_between(text, block, "", "")
    else:
        # After the quick-links <ul>, before the closing note.
        anchor = re.search(r'</ul>\s*\n\s*<p class="note">', text)
        if not anchor:
            raise SystemExit(f"hub anchor not found in {path}")
        text = text[: anchor.start() + len("</ul>")] + "\n" + block + text[anchor.start() + len("</ul>"):]
    path.write_text(text, encoding="utf-8")


def main() -> int:
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    products = data["products"] if isinstance(data, dict) else data
    products = [p for p in products if p.get("sku")]
    inject_home(PUBLIC / "index.html", products, "ru")
    inject_home(PUBLIC / "en" / "index.html", products, "en")
    inject_hub(PUBLIC / "products" / "index.html", products, "ru")
    inject_hub(PUBLIC / "en" / "products" / "index.html", products, "en")
    print(f"static catalog: {len(products)} SKU → index.html, en/index.html, "
          f"products/index.html, en/products/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
