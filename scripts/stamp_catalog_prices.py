#!/usr/bin/env python3
"""Stamp bakery piece/box prices in blog HTML from products.json.

Hardcoded bakery piece/box figures in blog FAQ and hubs go stale after a Sheets sync.
This rewriter is the only place those numbers are updated.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS = PUBLIC / "products.json"
ROW_RE = re.compile(r"<tr>.*?</tr>", re.S)


def num(v) -> float | None:
    try:
        f = float(str(v).replace(",", ".").replace(" ", "").replace("\u00a0", ""))
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def ru_money(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def en_money(v: float) -> str:
    return f"{v:.2f}"


def catalog() -> dict[str, dict]:
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    out = {}
    for p in data.get("products") or []:
        sku = p.get("sku")
        if not sku:
            continue
        o = p.get("offers") or {}
        piece = num(o.get("pricePerUnit") or o.get("price"))
        box = num(o.get("pricePerBox"))
        qty = str(p.get("qtyPerBox") or "").strip() or None
        if piece is None:
            continue
        out[sku] = {"piece": piece, "box": box, "qty": qty}
    return out


def _stamp_row(row: str, prices: dict[str, dict]) -> str:
    m = re.search(r'href="(?:/en)?/products/(kd-\d{3})"', row, re.I)
    if not m:
        return row
    sku = m.group(1).upper()
    if sku not in prices:
        return row
    tds = list(re.finditer(r"(<td>)(.*?)(</td>)", row, re.S))
    if len(tds) < 4:
        return row
    target = None
    for td in reversed(tds[2:]):
        cell = td.group(2)
        if re.search(r"°|сут|day|дн\b", cell, re.I):
            continue
        if "₽" in cell or re.search(r"RUB\s", cell, re.I):
            target = td
            break
        if re.fullmatch(r"\d+,\d{2}", cell.strip()) or re.fullmatch(r"\d+\.\d{2}", cell.strip()):
            target = td
            break
    if target is None:
        return row
    cell = target.group(2)
    piece = prices[sku]["piece"]
    if re.search(r"RUB\s", cell, re.I):
        new_cell = re.sub(r"RUB\s+\d+(?:\.\d+)?", f"RUB {en_money(piece)}", cell, count=1)
    elif "₽" in cell:
        new_cell = re.sub(r"\d[\d\s]*(?:[.,]\d+)?\s*₽", f"{ru_money(piece)} ₽", cell, count=1)
    else:
        new_cell = ru_money(piece)
    start, end = target.span()
    open_td = target.group(1)
    if "data-catalog-price" not in open_td:
        open_td = f'<td data-catalog-price="{sku}" data-price-field="pricePerUnit">'
    return row[:start] + open_td + new_cell + target.group(3) + row[end:]


def stamp_text(html: str, prices: dict[str, dict], rel: str = "") -> str:
    html = ROW_RE.sub(lambda m: _stamp_row(m.group(0), prices), html)
    for sku, row in prices.items():
        ru_p = ru_money(row["piece"])
        en_p = en_money(row["piece"])
        html = re.sub(
            rf"({re.escape(sku)} )\d+(?:[.,]\d+)? ₽",
            rf"\g<1>{ru_p} ₽",
            html,
        )
        html = re.sub(
            rf"({re.escape(sku)} RUB )\d+(?:\.\d+)?",
            rf"\g<1>{en_p}",
            html,
        )
        ru_b = ru_money(row["box"]) if row["box"] is not None else None
        qty = row["qty"] or "48"
        if sku == "KD-050" and ru_b and "echpochmak" in rel:
            html = re.sub(
                r"\d+,\d+ ₽ / шт · \d[\d\s]*,\d+ ₽ / короб",
                f"{ru_p} ₽ / шт · {ru_b} ₽ / короб",
                html,
            )
            html = re.sub(
                r"\d+,\d+ ₽ за штуку, \d[\d\s]*,\d+ ₽ за короб",
                f"{ru_p} ₽ за штуку, {ru_b} ₽ за короб",
                html,
            )
            html = re.sub(
                rf"\d+,\d+ ₽/шт, короб {re.escape(qty)} шт — \d[\d\s]*,\d+ ₽",
                f"{ru_p} ₽/шт, короб {qty} шт — {ru_b} ₽",
                html,
            )
    return html


def main() -> int:
    prices = catalog()
    roots = [PUBLIC / "blog.html", PUBLIC / "en" / "blog.html",
             PUBLIC / "blog", PUBLIC / "en" / "blog"]
    files: list[Path] = []
    for r in roots:
        if r.is_file():
            files.append(r)
        elif r.is_dir():
            files.extend(sorted(r.glob("*.html")))
    changed = 0
    for path in files:
        html = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(PUBLIC)).replace("\\", "/")
        new = stamp_text(html, prices, rel)
        if new != html:
            path.write_text(new, encoding="utf-8")
            changed += 1
    print(f"stamp_catalog_prices: {changed} file(s) updated from products.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
