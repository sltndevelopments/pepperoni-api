#!/usr/bin/env python3
"""Read RUB (and Sheet export) prices from public/products.json.

Owner rule 2026-10-17: every public price comes from the Google Sheet via
products.json. Generators import helpers from here — they must not embed
ruble/dollar literals.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "public" / "products.json"


def num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ".").replace("\u00a0", "").replace(" ", "").replace("₽", ""))
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def catalog() -> dict:
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    by_sku = {}
    for p in data.get("products") or []:
        sku = (p.get("sku") or "").upper()
        if sku:
            by_sku[sku] = p
    return {
        "meta": {k: data.get(k) for k in ("lastSynced", "totalProducts", "deliveryTerms", "publisher")},
        "by_sku": by_sku,
        "products": list(data.get("products") or []),
    }


def product(sku: str) -> dict:
    row = catalog()["by_sku"].get(sku.upper())
    if not row:
        raise KeyError(f"SKU {sku} is not in products.json")
    return row


def rub(sku: str) -> float:
    """Sheet offer: bakery uses pricePerUnit, meat lines use price."""
    offers = product(sku).get("offers") or {}
    value = num(offers.get("price")) or num(offers.get("pricePerUnit"))
    if value is None:
        raise KeyError(f"{sku} has no RUB price in products.json")
    return value


def rub_box(sku: str) -> float | None:
    return num((product(sku).get("offers") or {}).get("pricePerBox"))


def export_amount(sku: str, currency: str) -> float | None:
    """Sheet exportPrices.<CCY> — not a locally invented FX conversion."""
    ep = (product(sku).get("offers") or {}).get("exportPrices") or {}
    return num(ep.get(currency))


def rub_str(sku: str, decimals: int = 2) -> str:
    return f"{rub(sku):.{decimals}f}"


def rub_int_if_whole(sku: str) -> str:
    value = rub(sku)
    if abs(value - round(value)) < 0.001:
        return str(int(round(value)))
    return f"{value:.2f}"


def rub_display(sku: str, lang: str = "ru") -> str:
    token = rub_str(sku)
    if lang == "en":
        return f"{token} RUB"
    return f"{token} ₽"


def last_synced() -> str:
    return str(catalog()["meta"].get("lastSynced") or "")


def positive(v) -> float | None:
    """Sheet 'без НДС' cells land as 0.00 — treat that as missing, not a price."""
    n = num(v)
    if n is None or n <= 0:
        return None
    return n


def weight(sku: str) -> str:
    return str(product(sku).get("weight") or "").strip()


def weight_en(sku: str) -> str:
    """Catalog weight as an EN label (0,8 → 0.8 kg, 120 г → 120 g)."""
    raw = weight(sku)
    if not raw:
        return ""
    norm = raw.replace(",", ".")
    m = re.match(r"^([\d.]+)\s*(кг|kg|г|g)?$", norm, re.I)
    if not m:
        return raw
    n, unit = m.group(1), (m.group(2) or "").lower()
    if unit in {"г", "g"}:
        return f"{n} g"
    if unit in {"кг", "kg"}:
        return f"{n} kg"
    try:
        val = float(n)
    except ValueError:
        return raw
    if val >= 20:
        return f"{n} g"
    return f"{n} kg"


def sku_amounts(sku: str) -> set[float]:
    """Every live number that may appear next to this SKU."""
    row = product(sku)
    offers = row.get("offers") or {}
    out: set[float] = set()
    for key in (
        "price",
        "pricePerUnit",
        "pricePerBox",
        "priceExclVAT",
        "pricePerUnitExclVAT",
        "pricePerBoxExclVAT",
        "pricePerPiece",
    ):
        n = positive(offers.get(key))
        if n is not None:
            out.add(round(n, 2))
    for bucket in ("exportPrices", "exportPricesPerBox"):
        for value in (offers.get(bucket) or {}).values():
            n = positive(value)
            if n is not None:
                out.add(round(n, 2))
    return out
