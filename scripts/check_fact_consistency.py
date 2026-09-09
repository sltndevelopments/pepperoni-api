#!/usr/bin/env python3
"""Cross-check the key product facts everywhere they are published.

Source of truth is products.json (Google Sheets → sync). For every SKU the same
price, net weight, shelf life and storage must appear in:
  * RU card  public/products/kd-NNN.html      (JSON-LD Offer price + visible ₽ and кг)
  * EN card  public/en/products/kd-NNN.html   (JSON-LD Offer price + visible kg)
  * static catalog blocks in index.html, en/index.html, products/index.html,
    en/products/index.html                    (weight + ₽ next to the SKU link)
  * price lists public/wholesale-price-list-ru.md / wholesale-price-list.md

A mismatch is reported with the fact's decision owner: price → sales (Sheet),
weight/shelf life/storage/cooking → technologist (Sheet), EN name → owner-
approved translation (scripts/translations.json until it moves into the Sheet).
Exit 1 on any mismatch so it can gate a deploy.

  python3 scripts/check_fact_consistency.py [--csv docs/sprint-2026-09/fact-consistency.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS = PUBLIC / "products.json"

OWNER = {"price": "sales (Sheet)", "weight": "technologist (Sheet)",
         "shelfLife": "technologist (Sheet)", "storage": "technologist (Sheet)",
         "name_en": "owner-approved EN name (translations.json → Sheet)"}


def num(v) -> float | None:
    try:
        return float(str(v).replace(",", ".").replace("\u00a0", "").replace(" ", "").replace("₽", ""))
    except (TypeError, ValueError):
        return None


def close(a: float | None, b: float | None, tol: float = 0.011) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def jsonld_prices(html: str) -> set[float]:
    out = set()
    for m in re.finditer(r'"price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?', html):
        out.add(float(m.group(1)))
    return out


def visible_weights(html: str, lang: str) -> set[float]:
    body = html.split("<body", 1)[-1]
    unit = "кг" if lang == "ru" else "kg"
    return {num(m.group(1)) for m in re.finditer(rf">\s*([0-9]+(?:[.,][0-9]+)?)\s*{unit}\s*<", body)}


def visible_prices_rub(html: str) -> set[float]:
    body = html.split("<body", 1)[-1]
    return {num(m.group(1)) for m in re.finditer(r">\s*([0-9][0-9\s\u00a0]*(?:[.,][0-9]{2})?)\s*₽", body)}


def catalog_rows(html: str, sku: str, lang: str) -> tuple[float | None, float | None]:
    prefix = "/en" if lang == "en" else ""
    m = re.search(rf'<li><a href="{prefix}/products/{sku.lower()}">[^<]*</a><span class="cs-meta">([^<]*)(?:<span class=cs-price>([^<]*)</span>)?', html)
    if not m:
        return None, None
    meta = unescape(m.group(1))
    w = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*(?:кг|kg)", meta)
    price = num(m.group(2)) if m.group(2) else None
    return (num(w.group(1)) if w else None), price


def pricelist_row(md: str, sku: str) -> dict | None:
    for line in md.splitlines():
        if line.startswith(f"| {sku} |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            return {"name": cells[1], "weight": num(cells[2]), "price": num(cells[3]),
                    "shelf": cells[8], "storage": cells[9]}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path)
    ns = ap.parse_args()

    products = [p for p in json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"] if p.get("sku")]
    catalogs = {
        ("ru", "index.html"): (PUBLIC / "index.html").read_text(encoding="utf-8"),
        ("en", "en/index.html"): (PUBLIC / "en" / "index.html").read_text(encoding="utf-8"),
        ("ru", "products/index.html"): (PUBLIC / "products" / "index.html").read_text(encoding="utf-8"),
        ("en", "en/products/index.html"): (PUBLIC / "en" / "products" / "index.html").read_text(encoding="utf-8"),
    }
    pl_ru = (PUBLIC / "wholesale-price-list-ru.md").read_text(encoding="utf-8")
    pl_en = (PUBLIC / "wholesale-price-list.md").read_text(encoding="utf-8")

    issues: list[dict] = []

    def issue(sku, fact, where, expected, found):
        issues.append({"sku": sku, "fact": fact, "where": where, "expected": expected,
                       "found": found, "owner": OWNER.get(fact, "owner")})

    for p in products:
        sku = p["sku"]
        price = num((p.get("offers") or {}).get("price"))
        weight = num(p.get("weight"))
        usd = num(((p.get("offers") or {}).get("exportPrices") or {}).get("USD"))
        shelf = str(p.get("shelfLife") or "").strip()
        storage = str(p.get("storage") or "").strip()

        for lang in ("ru", "en"):
            rel = f"{'en/' if lang == 'en' else ''}products/{sku.lower()}.html"
            path = PUBLIC / rel
            if not path.is_file():
                issue(sku, "card", rel, "file", "missing")
                continue
            html = path.read_text(encoding="utf-8")
            ld = jsonld_prices(html)
            # EN cards quote the USD export price in their Offer; either is the Sheet's number.
            accepted = [price] + ([usd] if lang == "en" and usd is not None else [])
            if price is not None and not any(close(a, x) for a in accepted for x in ld):
                issue(sku, "price", rel + " (JSON-LD)", accepted, sorted(ld))
            vw = visible_weights(html, lang)
            if weight is not None and not any(close(weight, x, 0.0011) for x in vw):
                issue(sku, "weight", rel + " (visible)", weight, sorted(x for x in vw if x))
            if lang == "ru":
                vp = visible_prices_rub(html)
                if price is not None and not any(close(price, x) for x in vp):
                    issue(sku, "price", rel + " (visible ₽)", price, sorted(x for x in vp if x))
                if shelf and shelf not in html:
                    issue(sku, "shelfLife", rel, shelf, "not found")
                if storage and storage not in html:
                    issue(sku, "storage", rel, storage, "not found")

        for (lang, rel), html in catalogs.items():
            w, pr = catalog_rows(html, sku, lang)
            if w is None and pr is None:
                issue(sku, "catalog", rel, "row", "missing")
                continue
            if weight is not None and not close(weight, w, 0.0011):
                issue(sku, "weight", rel, weight, w)
            if price is not None and not close(price, pr, 0.51):  # catalog rounds to whole ₽
                issue(sku, "price", rel, price, pr)

        for rel, md in (("wholesale-price-list-ru.md", pl_ru), ("wholesale-price-list.md", pl_en)):
            row = pricelist_row(md, sku)
            if not row:
                issue(sku, "pricelist", rel, "row", "missing")
                continue
            if price is not None and not close(price, row["price"]):
                issue(sku, "price", rel, price, row["price"])
            if weight is not None and not close(weight, row["weight"], 0.0011):
                issue(sku, "weight", rel, weight, row["weight"])
            if rel.endswith("-ru.md") and shelf and row["shelf"] != shelf:
                issue(sku, "shelfLife", rel, shelf, row["shelf"])
            if storage and row["storage"] != storage:
                issue(sku, "storage", rel, storage, row["storage"])

    print(f"fact consistency: {len(products)} SKU checked across cards, catalogs, price lists → "
          f"{len(issues)} mismatch(es)")
    for i in issues[:60]:
        print(f"  {i['sku']} {i['fact']:<9} {i['where']:<40} expected={i['expected']} found={i['found']}  [{i['owner']}]")
    if ns.csv:
        ns.csv.parent.mkdir(parents=True, exist_ok=True)
        with ns.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["sku", "fact", "where", "expected", "found", "owner"])
            w.writeheader()
            w.writerows(issues)
        print(f"→ {ns.csv}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
