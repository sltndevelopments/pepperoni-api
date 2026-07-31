#!/usr/bin/env python3
"""Backfill missing GEO answer-first blocks (<div class="tldr-answer">).

Many geo landings were published before the answer-first format became
mandatory. This script injects a deterministic TLDR from data/products_geo.json
+ data-city / data-product attributes — no LLM, no invented claims.

Usage:
  python3 scripts/backfill_geo_tldr.py --dry-run
  python3 scripts/backfill_geo_tldr.py
  python3 scripts/backfill_geo_tldr.py --roots public/geo public/en/geo
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_GEO = ROOT / "data" / "products_geo.json"
PHONE_HTML = '<a href="tel:+79872170202">+7 987 217-02-02</a>'

TLDR_CSS = """
    .tldr-answer {
      background: #eaf4ee;
      border-left: 4px solid #1a6b3a;
      border-radius: 6px;
      padding: 1rem 1.25rem;
      margin: 1.25rem 0 1.5rem;
      font-size: 1.05rem;
      line-height: 1.6;
    }
"""

# data-product / filename aliases → products_geo.json id
PRODUCT_ALIASES = {
    "sosiki-hotdog": "sosiski-hotdog",
    "sosiki-v-teste": "sosiski-v-teste",
    "sosiski-dlya-hotdog": "sosiski-hotdog",
    "sosiski-hotdog": "sosiski-hotdog",
    "sosiski-v-teste": "sosiski-v-teste",
    "topping-dlya-pitstsy": "toppings-pizza",
    "toppings-pizza": "toppings-pizza",
    "topping-pizza-halal": "toppings-pizza",
    "kolbasnye-izdeliya": "kolbasnye",
    "kolbasnye": "kolbasnye",
    "kazylyk": "kazylyk-premium",
    "kazylyk-premium": "kazylyk-premium",
    "kazylyk-faakhir": "kazylyk-premium",
    "halal-pelmeni-dumplings": "pelmeni",
    "pelmeni": "pelmeni",
    "vypechka-tatarskaya": "vypechka-tatarskaya",
    "tatar-halal-bakery": "vypechka-tatarskaya",
    "vypechka-klassicheskaya": "vypechka-klassicheskaya",
    "private-label": "private-label",
    "private-label-stm": "private-label",
    "pepperoni": "pepperoni",
    "halal-pepperoni": "pepperoni",
    "pepperoni-govyadina": "pepperoni",
    "pepperoni-kurica": "pepperoni",
    "pepperoni-konina": "pepperoni",
    "pepperoni-miks": "pepperoni",
    "farsh": "farsh",
    "vetchina": "vetchina",
    "kotlety-burgery": "kotlety-burgery",
    "kotlety-dlya-burgerov": "kotlety-burgery",
    "syroje-myaso": "syroje-myaso",
    "kopchenye": "kopchenye",
    "sujuk-hotdog-halal": "sosiski-hotdog",
    "burgir-lahmeh-halal": "kotlety-burgery",
    "ham-halal": "vetchina",
    "lahmeh-niya-halal": "syroje-myaso",
}


def load_products() -> dict[str, dict]:
    data = json.loads(PRODUCTS_GEO.read_text(encoding="utf-8"))
    by_id: dict[str, dict] = {}
    for p in data.get("products", []):
        by_id[p["id"]] = p
        for key in ("slug_ru", "slug_en", "slug_ar"):
            slug = p.get(key)
            if slug:
                by_id.setdefault(slug, p)
        for v in p.get("variants") or []:
            if v.get("slug"):
                by_id.setdefault(v["slug"], p)
    return by_id


def load_city_slug_to_name() -> dict[str, str]:
    out: dict[str, str] = {}
    ru = json.loads((ROOT / "data" / "cities_russia.json").read_text(encoding="utf-8"))
    for c in ru.get("cities", []):
        if c.get("slug") and c.get("name"):
            out[c["slug"]] = c["name"]
    world = json.loads((ROOT / "data" / "cities_world.json").read_text(encoding="utf-8"))
    for country in world.get("countries", []):
        # country-level pages sometimes use country slug
        code = (country.get("code") or "").lower()
        if code and country.get("name_ru"):
            out.setdefault(code, country["name_ru"])
            # common filename forms
            name_en = (country.get("name_en") or "").lower().replace(" ", "-")
            if name_en:
                out.setdefault(name_en, country["name_ru"])
        for c in country.get("cities") or []:
            if c.get("slug") and c.get("name_ru"):
                out[c["slug"]] = c["name_ru"]
    # Extra filename tails seen on legacy pages
    out.setdefault("uzbekistan", "Узбекистан")
    out.setdefault("belarus", "Беларусь")
    out.setdefault("kazakhstan", "Казахстан")
    out.setdefault("spb", "Санкт-Петербург")
    out.setdefault("peterburg", "Санкт-Петербург")
    # Legacy filename spellings / region pages not in cities_*.json
    out.setdefault("mahachkala", "Махачкала")
    out.setdefault("astrahan", "Астрахань")
    out.setdefault("dagestan", "Дагестан")
    out.setdefault("prokopyevsk", "Прокопьевск")
    out.setdefault("nizhny-novgorod", "Нижний Новгород")
    out.setdefault("nizhniy-novgorod", "Нижний Новгород")
    out.setdefault("uae", "ОАЭ")
    out.setdefault("oae", "ОАЭ")
    out.setdefault("medina", "Медина")
    out.setdefault("casablanca", "Касабланка")
    out.setdefault("riyadh", "Эр-Рияд")
    out.setdefault("ajman", "Аджман")
    out.setdefault("giza", "Гиза")
    return out


def resolve_product(raw: str | None, filename: str, by_id: dict[str, dict]) -> tuple[dict | None, str | None]:
    """Return (product, matched_slug_prefix) for city-tail parsing."""
    candidates: list[str] = []
    if raw:
        candidates.append(raw.strip())
        candidates.append(PRODUCT_ALIASES.get(raw.strip(), raw.strip()))
    stem = Path(filename).stem
    candidates.append(stem)
    known = sorted(set(PRODUCT_ALIASES) | set(by_id), key=len, reverse=True)
    matched_prefix = None
    for k in known:
        if stem == k or stem.startswith(k + "-"):
            candidates.append(PRODUCT_ALIASES.get(k, k))
            candidates.append(k)
            matched_prefix = k
            break
    for c in candidates:
        if not c:
            continue
        pid = PRODUCT_ALIASES.get(c, c)
        if pid in by_id:
            return by_id[pid], matched_prefix or pid
        if c in by_id:
            return by_id[c], matched_prefix or c
    return None, matched_prefix


def extract_attr(html: str, name: str) -> str | None:
    m = re.search(rf'\bdata-{name}="([^"]+)"', html, re.I)
    return m.group(1).strip() if m else None


def city_from_filename(stem: str, product_prefix: str | None, city_map: dict[str, str]) -> str | None:
    if product_prefix and stem.startswith(product_prefix + "-"):
        tail = stem[len(product_prefix) + 1 :]
    else:
        # longest known city slug suffix
        tail = stem
    if tail in city_map:
        return city_map[tail]
    # Try longest city slug as suffix
    for slug in sorted(city_map, key=len, reverse=True):
        if stem.endswith("-" + slug) or stem == slug:
            return city_map[slug]
    return None


def build_tldr(product: dict, city: str, lang_hint: str) -> str:
    name = product.get("name_ru") or product.get("name_en") or product["id"]
    usp = (product.get("usp_ru") or product.get("usp_en") or "").strip()
    # Keep first ~2 sentences of USP — already fact-checked in products_geo.
    parts = re.split(r"(?<=[.!?])\s+", usp)
    usp_short = " ".join(parts[:2]).strip()
    if usp_short and not usp_short.endswith("."):
        usp_short += "."
    city = city.strip() or "ваш город"
    if lang_hint == "en" and product.get("usp_en"):
        body = (
            f"<strong>{product.get('name_en', name)}</strong> — {product['usp_en'].strip()} "
            f"Delivery to {city} with cold-chain logistics. Private Label / OEM available. "
            f"Request: {PHONE_HTML}."
        )
    else:
        body = (
            f"<strong>{name}</strong> — {usp_short} "
            f"Производство Казань. Поставка в {city} транспортными компаниями "
            f"с соблюдением холодовой цепи. СТМ/Private Label — доступно. "
            f"Заявка: {PHONE_HTML}."
        )
    return f'<div class="tldr-answer">\n    {body}\n  </div>'


def ensure_css(html: str) -> str:
    if ".tldr-answer" in html:
        return html
    if re.search(r"<style[^>]*>", html, re.I):
        return re.sub(
            r"(<style[^>]*>)",
            r"\1\n" + TLDR_CSS,
            html,
            count=1,
            flags=re.I,
        )
    # No style block — inject before </head>
    if re.search(r"</head>", html, re.I):
        return re.sub(
            r"</head>",
            f"<style>{TLDR_CSS}</style>\n</head>",
            html,
            count=1,
            flags=re.I,
        )
    return html


def inject_tldr(html: str, tldr: str) -> str | None:
    if "tldr-answer" in html:
        return None
    # Prefer immediately after </h1>
    m = re.search(r"</h1\s*>", html, re.I)
    if m:
        pos = m.end()
        return html[:pos] + "\n\n  " + tldr + "\n" + html[pos:]
    # Fallback: after opening <main ...> or first .container / <body>
    for pat in (
        r"(<main\b[^>]*>)",
        r'(<div class="container[^"]*"[^>]*>)',
        r"(<body\b[^>]*>)",
    ):
        m = re.search(pat, html, re.I)
        if m:
            pos = m.end()
            return html[:pos] + "\n  " + tldr + "\n" + html[pos:]
    return None


def lang_hint_for(path: Path) -> str:
    parts = path.parts
    if "en" in parts:
        return "en"
    if "ar" in parts:
        return "ar"
    return "ru"


def process_file(
    path: Path,
    by_id: dict[str, dict],
    city_map: dict[str, str],
    dry_run: bool,
) -> str:
    html = path.read_text(encoding="utf-8", errors="replace")
    if "tldr-answer" in html:
        return "skip-has"
    city = extract_attr(html, "city")
    raw_product = extract_attr(html, "product")
    product, prefix = resolve_product(raw_product, path.name, by_id)
    if not product:
        return "skip-no-product"
    if not city:
        city = city_from_filename(path.stem, prefix, city_map)
    if not city:
        return "skip-no-city"
    tldr = build_tldr(product, city, lang_hint_for(path))
    new_html = inject_tldr(html, tldr)
    if new_html is None:
        return "skip-inject"
    new_html = ensure_css(new_html)
    if not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return "patched"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--roots",
        nargs="+",
        default=["public/geo", "public/en/geo", "public/ar/geo", "public/kk/geo"],
    )
    args = ap.parse_args()
    by_id = load_products()
    city_map = load_city_slug_to_name()
    counts: dict[str, int] = {}
    for root_s in args.roots:
        root = ROOT / root_s
        if not root.exists():
            print(f"[skip] missing {root_s}")
            continue
        files = sorted(root.rglob("*.html"))
        print(f"Scanning {root_s}: {len(files)} files")
        for path in files:
            status = process_file(path, by_id, city_map, args.dry_run)
            counts[status] = counts.get(status, 0) + 1
    print("---")
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {k}: {v}")
    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"{mode}: patched={counts.get('patched', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
