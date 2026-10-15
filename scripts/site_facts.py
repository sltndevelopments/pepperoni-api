#!/usr/bin/env python3
"""Load data/site_facts.json — the single registry of public company facts.

Generators import FACTS / helpers from here instead of hardcoding SKU counts,
KD-014 weight, export countries or requisites.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS = json.loads((ROOT / "data" / "site_facts.json").read_text(encoding="utf-8"))


def sku_count() -> int:
    """Live count from products.json when present (Sheets sync), else registry."""
    p = ROOT / "public" / "products.json"
    try:
        return int(json.loads(p.read_text(encoding="utf-8"))["totalProducts"])
    except Exception:
        return int(FACTS["catalog"]["sku_count"])


def kd014_weight(lang: str = "ru") -> str:
    w = FACTS["catalog"]["pepperoni"]["KD-014"]["weight_kg"]
    return (f"{w:g}".replace(".", ",") + " кг") if lang == "ru" else f"{w:g} kg"


def export_current(lang: str = "en") -> list[str]:
    return list(FACTS["export"]["current_" + ("ru" if lang == "ru" else "en")])


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Russian plural ending: 1 позиция, 2 позиции, 5 позиций, 21 позиция."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many
