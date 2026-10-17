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


PACK_FIELDS = (
    "price",
    "pricePerBox",
    "priceExclVAT",
    "pricePerBoxExclVAT",
)
PIECE_FIELDS = (
    "pricePerPiece",
    "pricePerUnit",
    "pricePerUnitExclVAT",
)
_PACK_COUNT = re.compile(
    r"\((\d+(?:[.,]\d+)?)\s*г\s*[×xх]\s*(\d+)\s*шт",
    re.I,
)


def sku_from_url(url: str) -> str:
    m = re.search(r"/products/(kd-\d{3})", str(url or ""), re.I)
    return m.group(1).upper() if m else ""


def iter_jsonld_nodes(node):
    """Every dict in a JSON-LD blob, any depth (ItemList, offers, @graph)."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_jsonld_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_jsonld_nodes(item)


def iter_ld_offers(root):
    """Yield (sku, offer_or_product) for every priced Product/Offer, any depth."""

    def walk(node, sku: str = ""):
        if isinstance(node, list):
            for item in node:
                yield from walk(item, sku)
            return
        if not isinstance(node, dict):
            return
        here = (
            str(node.get("sku") or "").upper()
            or sku_from_url(str(node.get("url") or ""))
            or sku
        )
        types = node.get("@type")
        typeset = {types} if isinstance(types, str) else set(types or [])
        if node.get("price") is not None and (
            typeset & {"Product", "Offer"} or not typeset
        ):
            yield here, node
        for value in node.values():
            yield from walk(value, here)

    yield from walk(root)


def stamp_attr(sku: str, field: str = "price") -> str:
    return f'data-catalog-price="{sku.upper()}" data-price-field="{field}"'


def pack_format_en(sku: str) -> str:
    """'130 g × 5' from the catalog name, else weight_en()."""
    name = str(product(sku).get("name") or "")
    match = _PACK_COUNT.search(name)
    if match:
        return f"{match.group(1).replace(',', '.')} g × {match.group(2)}"
    return weight_en(sku)


def piece_count(sku: str) -> int | None:
    match = _PACK_COUNT.search(str(product(sku).get("name") or ""))
    return int(match.group(2)) if match else None


def weight_kg(sku: str) -> float | None:
    raw = weight(sku).replace(",", ".")
    match = re.match(r"^([\d.]+)\s*(кг|kg|г|g)?$", raw, re.I)
    if not match:
        return None
    value = num(match.group(1))
    if value is None:
        return None
    unit = (match.group(2) or "").lower()
    if unit in {"г", "g"}:
        return value / 1000.0
    if unit in {"кг", "kg"}:
        return value
    return value / 1000.0 if value >= 20 else value


def sku_field_amounts(sku: str, fields: tuple[str, ...]) -> set[float]:
    offers = product(sku).get("offers") or {}
    out: set[float] = set()
    for key in fields:
        n = positive(offers.get(key))
        if n is not None:
            out.add(round(n, 2))
    return out


_UNIT_HINTS = (
    (re.compile(r"(?:/шт|/pc\b|/pcs\b|за\s*шт)", re.I), "piece"),
    (re.compile(r"(?:per\s+pack|за\s*(?:пачк|упак)|/упак|/pack\b|пачку)", re.I), "pack"),
    (re.compile(r"(?:/?\s*короб|за\s*короб|per\s+case)", re.I), "box"),
    (re.compile(r"без\s*ндс|excl", re.I), "excl"),
    (re.compile(r"(?:/кг|/kg\b)", re.I), "kg"),
)
_KG_HINT = re.compile(r"(?:/кг|/kg\b)", re.I)


def infer_unit(ctx: str) -> str | None:
    """Nearest unit suffix in ctx wins (so 'за упаковку · без НДС' is pack)."""
    found: list[tuple[int, str]] = []
    for rx, unit in _UNIT_HINTS:
        match = rx.search(ctx or "")
        if match:
            found.append((match.start(), unit))
    if not found:
        return None
    found.sort()
    return found[0][1]


def header_unit(header: str) -> str | None:
    """Classify a table header. None = not a price column; skip = ignore ≈/кг."""
    text = re.sub(r"<[^>]+>", " ", header or "")
    low = text.lower()
    if re.search(r"штрих|barcode|gtin|ean", low):
        return None
    priced = bool(re.search(r"₽|rub|цена|price", low))
    if not priced:
        return None
    if "≈" in text and _KG_HINT.search(text):
        return "skip"
    if _KG_HINT.search(text):
        return "kg"
    if re.search(r"\busd\b", low) and "rub" not in low:
        return "usd"
    if re.search(r"/шт|/pc\b|/pcs\b|за\s*шт|\bшт\b|piece", low):
        return "piece"
    if re.search(r"короб|box|case", low):
        return "box"
    if re.search(r"без\s*ндс|excl", low):
        return "excl"
    if re.search(r"пачк|упак|pack|за\s*уп", low):
        return "pack"
    return "any"


def sku_amounts_for(sku: str, unit: str | None = None,
                    field: str | None = None) -> set[float]:
    """Unit-strict catalog amounts. field= wins (data-price-field)."""
    if field:
        key = field.split(".")[-1]
        if key.upper() in {"USD", "KZT", "UZS", "KGS", "BYN", "AZN"}:
            n = export_amount(sku, key.upper())
            return {round(n, 2)} if n is not None else set()
        return sku_field_amounts(sku, (field,))
    if unit == "pack":
        return sku_field_amounts(sku, PACK_FIELDS)
    if unit == "piece":
        out = sku_field_amounts(sku, PIECE_FIELDS)
        pack = positive((product(sku).get("offers") or {}).get("price"))
        count = piece_count(sku)
        if pack is not None and count:
            out.add(round(pack / count, 2))
        return out
    if unit == "kg":
        pack = rub(sku)
        kg = weight_kg(sku)
        if kg:
            return {round(pack / kg, 2)}
        return set()
    if unit == "box":
        return sku_field_amounts(sku, ("pricePerBox", "pricePerBoxExclVAT"))
    if unit == "excl":
        return sku_field_amounts(
            sku,
            ("priceExclVAT", "pricePerUnitExclVAT", "pricePerBoxExclVAT"),
        )
    if unit == "usd":
        n = export_amount(sku, "USD")
        return {round(n, 2)} if n is not None else set()
    if unit == "skip":
        return set()
    return sku_amounts(sku)


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
    count = piece_count(sku)
    pack = positive(offers.get("price"))
    if pack is not None and count:
        out.add(round(pack / count, 2))
    return out
