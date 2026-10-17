#!/usr/bin/env python3
"""Blog «За шт» / Per piece cells must equal products.json pricePerPiece."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
sys.path.insert(0, str(ROOT / "scripts"))
from stamp_catalog_prices import (  # noqa: E402
    catalog,
    en_money,
    main as stamp_main,
    num,
    ru_money,
)

fail = 0
PIECE_HEADERS = ("за шт", "per piece", "per pc")
TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
TR_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.S)
TH_RE = re.compile(r"<th\b[^>]*>(.*?)</th>", re.S | re.I)
TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
SKU_RE = re.compile(r'href="(?:/en)?/products/(kd-\d{3})"', re.I)


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
        return
    fail += 1
    print("  FAIL", msg)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).replace("\xa0", " ").strip()


def _piece_col(table: str) -> int | None:
    thead = re.search(r"<thead\b[^>]*>.*?</thead>", table, re.S | re.I)
    block = thead.group(0) if thead else table
    first = TR_RE.search(block)
    if not first:
        return None
    headers = [_text(h).lower() for h in TH_RE.findall(first.group(0))]
    for i, h in enumerate(headers):
        if any(key in h for key in PIECE_HEADERS):
            return i
    return None


def _cell_amount(cell: str) -> float | None:
    text = _text(cell)
    m = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)", text)
    if not m:
        return None
    return num(m.group(1))


def main() -> int:
    rc = stamp_main()
    check(rc == 0, "stamp_catalog_prices.main() rebuilds")
    prices = catalog()
    products = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    by_sku = {p["sku"]: p for p in products.get("products") or [] if p.get("sku")}

    tables_checked = 0
    cells_checked = 0
    roots = [PUBLIC / "blog", PUBLIC / "en" / "blog"]
    pages = []
    for root in roots:
        if root.is_dir():
            pages.extend(sorted(root.glob("*.html")))
    for path in pages:
        html = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(PUBLIC)).replace("\\", "/")
        for table in TABLE_RE.findall(html):
            col = _piece_col(table)
            if col is None:
                continue
            tables_checked += 1
            for tr in TR_RE.findall(table):
                sku_m = SKU_RE.search(tr)
                if not sku_m:
                    continue
                sku = sku_m.group(1).upper()
                tds = TD_RE.findall(tr)
                if col >= len(tds):
                    check(False, f"{rel} {sku}: piece column out of range")
                    continue
                sheet = by_sku.get(sku, {}).get("offers") or {}
                want = num(sheet.get("pricePerPiece"))
                if want is None:
                    continue
                got = _cell_amount(tds[col])
                cells_checked += 1
                check(
                    got is not None and abs(got - want) < 0.011,
                    f"{rel} {sku} За шт/Per piece {got} == pricePerPiece {want}",
                )
                check(
                    f'data-price-field="pricePerPiece"' in tr
                    or f"data-price-field='pricePerPiece'" in tr,
                    f"{rel} {sku} piece cell tagged pricePerPiece",
                )
                cat = prices.get(sku) or {}
                check(cat.get("per_piece") == want,
                      f"{rel} {sku} stamper catalog per_piece matches Sheet")

    check(tables_checked >= 1, "found at least one blog table with a per-piece column")
    check(cells_checked >= 2, "checked at least two per-piece cells")
    kot = (PUBLIC / "blog" / "kotlety-dlya-burgerov-optom.html").read_text(encoding="utf-8")
    p009 = prices["KD-009"]["per_piece"]
    p010 = prices["KD-010"]["per_piece"]
    check(f"{ru_money(p009)} \u20bd" in kot, "RU kotlety KD-009 За шт is pricePerPiece")
    check(f"{ru_money(p010)} \u20bd" in kot, "RU kotlety KD-010 За шт is pricePerPiece")
    en = (PUBLIC / "en" / "blog" / "burger-patties-wholesale-halal.html").read_text(
        encoding="utf-8")
    check(f"RUB {en_money(p009)}" in en, "EN burger KD-009 Per piece is pricePerPiece")
    check(f"RUB {en_money(p010)}" in en, "EN burger KD-010 Per piece is pricePerPiece")

    if fail:
        print(f"test_blog_price_per_piece: {fail} FAIL")
        return 1
    print(f"test_blog_price_per_piece: ok ({tables_checked} tables, {cells_checked} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
