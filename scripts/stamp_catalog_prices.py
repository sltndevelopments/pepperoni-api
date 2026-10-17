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
ROW_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.S)
TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
PIECE_HEADERS = ("за шт", "per piece", "per pc")


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
        ppu = num(o.get("pricePerUnit"))
        if ppu is not None:
            field, piece = "pricePerUnit", ppu
        else:
            field, piece = "price", num(o.get("price"))
        box = num(o.get("pricePerBox"))
        qty = str(p.get("qtyPerBox") or "").strip() or None
        if piece is None:
            continue
        out[sku] = {
            "piece": piece,
            "box": box,
            "qty": qty,
            "field": field,
            "per_piece": num(o.get("pricePerPiece")),
        }
    return out


def _header_cells(table: str) -> list[str]:
    thead = re.search(r"<thead\b[^>]*>.*?</thead>", table, re.S | re.I)
    block = thead.group(0) if thead else table
    first = re.search(r"<tr\b[^>]*>.*?</tr>", block, re.S)
    if not first:
        return []
    raw = re.findall(r"<th\b[^>]*>(.*?)</th>", first.group(0), re.S | re.I)
    return [re.sub(r"<[^>]+>", "", c).strip().lower() for c in raw]


def _piece_col(headers: list[str]) -> int | None:
    for i, h in enumerate(headers):
        if any(key in h for key in PIECE_HEADERS):
            return i
    return None


def _rewrite_amount(cell: str, amount: float) -> str:
    if re.search(r"RUB\s", cell, re.I):
        return re.sub(r"RUB\s+\d+(?:\.\d+)?", f"RUB {en_money(amount)}", cell, count=1)
    if "₽" in cell:
        return re.sub(r"\d[\d\s]*(?:[.,]\d+)?\s*₽", f"{ru_money(amount)} ₽", cell, count=1)
    return ru_money(amount)


def _apply_td(row: str, target: re.Match, sku: str, amount: float, field: str) -> str:
    cell = target.group(2)
    new_cell = _rewrite_amount(cell, amount)
    start, end = target.span()
    extra = re.sub(
        r"\s+data-(?:catalog-price|price-field)=\"[^\"]*\"",
        "",
        target.group(1),
    )
    extra = re.sub(r"^<td\b", "", extra, count=1)
    extra = extra[:-1] if extra.endswith(">") else extra
    open_td = f'<td data-catalog-price="{sku}" data-price-field="{field}"{extra}>'
    return row[:start] + open_td + new_cell + target.group(3) + row[end:]


def _stamp_row(row: str, prices: dict[str, dict], piece_col: int | None = None) -> str:
    m = re.search(r'href="(?:/en)?/products/(kd-\d{3})"', row, re.I)
    if not m:
        return row
    sku = m.group(1).upper()
    if sku not in prices:
        return row
    tds = list(re.finditer(r"(<td\b[^>]*>)(.*?)(</td>)", row, re.S))
    if piece_col is not None:
        if piece_col >= len(tds):
            return row
        amount = prices[sku].get("per_piece")
        if amount is None:
            return row
        return _apply_td(row, tds[piece_col], sku, amount, "pricePerPiece")
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
    field = prices[sku].get("field") or "price"
    return _apply_td(row, target, sku, prices[sku]["piece"], field)


def _stamp_table(table: str, prices: dict[str, dict]) -> str:
    idx = _piece_col(_header_cells(table))
    return ROW_RE.sub(lambda m: _stamp_row(m.group(0), prices, piece_col=idx), table)


def stamp_text(html: str, prices: dict[str, dict], rel: str = "") -> str:
    html = TABLE_RE.sub(lambda m: _stamp_table(m.group(0), prices), html)
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
