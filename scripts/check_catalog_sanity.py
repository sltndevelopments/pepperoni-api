#!/usr/bin/env python3
"""Catalog sanity gate for public/products.json (runs right after sync).

Born from the 2026-09-12 audit: LLM description overrides keyed by stale SKU
numbers put «говядина» into muffins and croissants, gave 20 SKUs another
product's description, and bakery export prices were published per box next to
per-piece rouble prices ($34.68 for a 100 g pastry). None of that is caught by
the field-shape validator, so this gate checks *meaning*:

  FAIL  sweet/dessert bakery whose ingredients mention meat
  FAIL  seoDescription whose leading segment names a different product
  FAIL  export USD outside a plausible per-unit range (0.1 … 50)
  WARN  GTIN-13 with a bad check digit (Sheet typo — owner fixes in Sheets;
        reported so it is not silently pushed to Merchant Center)

Exit 1 on any FAIL. Usage: python3 scripts/check_catalog_sanity.py [--quiet]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "public" / "products.json"

SWEET_RE = re.compile(
    r"маффин|круассан|сочник|сырник|чак-?чак|ватрушк|булочк|с вишней|с яблоком|с творогом|улитк|штрудел|кекс",
    re.I,
)
MEAT_RE = re.compile(
    r"говядин|конин|баранин|мясо|куриц|курин|кур\.|индейк|филе|фарш|окорочк|грудк", re.I
)


# Product-type vocabulary: a description whose leading segment names a different
# product type than the SKU itself is the signature of a mis-keyed override.
# (Sheet-authored prose may paraphrase the name — that is fine — but «Сосиски»
# never become «Филе бедра в кубике».)
TYPES = [
    ("сосиск", "сосиски"), ("сардельк", "сардельки"), ("котлет", "котлета"),
    ("пепперони", "пепперони"), ("ветчин", "ветчина"), ("сервелат", "сервелат"),
    ("казылык", "казылык"), ("варен", "варёная колбаса"), ("полукопчен", "полукопчёная колбаса"),
    ("в/к", "варёно-копчёная"), ("варёно-копч", "варёно-копчёная"), ("варено-копч", "варёно-копчёная"),
    ("грудк", "грудка"), ("филе", "филе"), ("кубик", "филе"), ("говядина 1", "филе"),
    ("фарш", "фарш"), ("губади", "губадия"), ("эчпочмак", "эчпочмак"), ("самса", "самса"),
    ("чебурек", "чебурек"), ("перемяч", "перемяч"), ("элеш", "элеш"), ("чак", "чак-чак"),
    ("сочник", "сочник"), ("сырник", "сырник"), ("пирож", "пирожок"), ("маффин", "маффин"),
    ("круассан", "круассан"), ("в тесте", "сосиска в тесте"),
]


def product_type(s: str) -> str | None:
    low = (s or "").lower()
    # «сосиска в тесте» must win over «сосиски»; «пепперони» over «варёно-копчёная»
    for key, label in (("в тесте", "сосиска в тесте"), ("пепперони", "пепперони"), ("казылык", "казылык")):
        if key in low:
            return label
    for key, label in TYPES:
        if key in low:
            return label
    return None


def gtin13_ok(g: str) -> bool | None:
    d = re.sub(r"\D", "", g or "")
    if len(d) != 13:
        return None
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d[:12]))
    return (10 - total % 10) % 10 == int(d[12])


def main() -> int:
    quiet = "--quiet" in sys.argv
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    products = data.get("products", [])
    fails: list[str] = []
    warns: list[str] = []

    for p in products:
        sku, name = p.get("sku", "?"), p.get("name", "")
        ingr = p.get("ingredientsRU") or ""
        ingr_meat = re.sub(r"яйц\w*\s+курин\w*|меланж\w*", "", ingr, flags=re.I)  # eggs are not meat
        if SWEET_RE.search(name) and MEAT_RE.search(ingr_meat):
            fails.append(f"{sku} «{name}»: dessert with meat in ingredients → «{ingr[:70]}»")

        seo = (p.get("seoDescriptionRU") or "").split("|")[0].strip()
        if seo:
            t_name, t_seo = product_type(name), product_type(seo)
            if t_name and t_seo and t_name != t_seo:
                fails.append(f"{sku} «{name}» ({t_name}): seoDescriptionRU describes a {t_seo} — «{seo[:60]}»")

        usd = (p.get("offers", {}).get("exportPrices") or {}).get("USD")
        if usd is not None:
            try:
                usd_f = float(usd)
            except (TypeError, ValueError):
                usd_f = -1
            if not (0.1 <= usd_f <= 50):
                fails.append(f"{sku} «{name}»: export USD={usd} outside per-unit range 0.1…50")

        ok = gtin13_ok(p.get("barcode") or "")
        if ok is False:
            warns.append(f"{sku} «{name}»: GTIN {p.get('barcode')} has a bad check digit (fix in Sheets)")

    if not quiet or fails or warns:
        for w in warns:
            print(f"WARN  {w}")
        for f in fails:
            print(f"FAIL  {f}")
    print(f"catalog sanity: {len(products)} SKU, {len(fails)} fail, {len(warns)} warn")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
