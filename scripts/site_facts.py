#!/usr/bin/env python3
"""Load data/site_facts.json — the single registry of public company facts.

Generators import FACTS / helpers from here instead of hardcoding SKU counts,
KD-014 weight, export countries or requisites.
"""
from __future__ import annotations
import json
import re
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


def certificates_for_api() -> list[dict]:
    """Public certificate list matching live /halal (number, scope, validity)."""
    c = FACTS["certificates"]
    keys = ("halal_0008", "halal_614a", "halal_bakery", "iso_22000", "made_in_russia")
    out = []
    for key in keys:
        item = c[key]
        row = {k: item[k] for k in (
            "number", "scope_ru", "scope_en", "valid_from", "valid_until",
            "issuer_ru", "registry", "status",
        ) if k in item}
        out.append(row)
    return out


def phone_digits() -> str:
    return re.sub(r"\D", "", str(FACTS["company"]["phone"]))


def phone_tel() -> str:
    digits = phone_digits()
    return f"tel:+{digits}" if digits else ""


def phone_wa() -> str:
    digits = phone_digits()
    return f"https://wa.me/{digits}" if digits else ""


def street_address() -> str:
    """Street line parsed from company.address_ru — not a second hardcoded address."""
    addr = str(FACTS["company"]["address_ru"])
    m = re.search(r"(ул\.\s*[^,]+,\s*д\.\s*\d+,\s*офис\s*\d+)", addr, re.I)
    return m.group(1) if m else addr


def postal_code() -> str:
    m = re.match(r"(\d{6})", str(FACTS["company"]["address_ru"]))
    return m.group(1) if m else ""


def meat_halal_number() -> str:
    return str(FACTS["certificates"]["halal_0008"]["number"])


def certs_price_ru() -> str:
    c = FACTS["certificates"]
    return (
        f"Халяль №{c['halal_0008']['number']} (ДУМ РТ, основной) | "
        f"№{c['halal_614a']['number']} | №{c['halal_bakery']['number']} | "
        f"ХАССП | {c['iso_22000']['number']} | ТР ТС 021/2011"
    )


def certs_price_en() -> str:
    c = FACTS["certificates"]
    return (
        f"Halal No. {c['halal_0008']['number']} (DUM RT, primary) | "
        f"No. {c['halal_614a']['number']} | No. {c['halal_bakery']['number']} | "
        f"HACCP | {c['iso_22000']['number']} | TR CU 021/2011"
    )


def certs_category_ru() -> str:
    c = FACTS["certificates"]
    return (
        f"Халяль ДУМ РТ № {c['halal_0008']['number']} · "
        f"№ {c['halal_614a']['number']} · № {c['halal_bakery']['number']} · "
        f"ХАССП · ISO 22000:2018 · ТР ТС 021/2011"
    )


def certs_category_en() -> str:
    c = FACTS["certificates"]
    return (
        f"Halal DUM RT No. {c['halal_0008']['number']} · "
        f"No. {c['halal_614a']['number']} · No. {c['halal_bakery']['number']} · "
        f"HACCP · ISO 22000:2018 · TR CU 021/2011"
    )


def cert_line_ru() -> str:
    return (
        "Халяль ДУМ РТ №0008 (мясо, птица, колбасы, пепперони, полуфабрикаты; "
        "02.10.2026–01.10.2029), №614A/2024 (мясо; 17.02.2024–16.02.2027), "
        "№884A/2025 (выпечка и готовые блюда; 27.12.2025–26.12.2026), "
        "HACCP, ISO 22000:2018 (FSMS-2351/А), «Сделано в России» №СС.003181 "
        "(до 23.10.2028), ТР ТС 021/2011"
    )


def cert_line_en() -> str:
    return (
        "Halal DUM RT No. 0008 (meat, poultry, sausages, pepperoni, semi-finished; "
        "2 Oct 2026–1 Oct 2029), No. 614A/2024 (meat; 17 Feb 2024–16 Feb 2027), "
        "No. 884A/2025 (bakery and ready meals; 27 Dec 2025–26 Dec 2026), "
        "HACCP, ISO 22000:2018 (FSMS-2351/A), Made in Russia No. SS.003181 "
        "(until 23 Oct 2028), TR CU 021/2011"
    )


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Russian plural ending: 1 позиция, 2 позиции, 5 позиций, 21 позиция."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many
