#!/usr/bin/env python3
"""Generate the wholesale price lists from products.json — the same data the
cards, the static catalog and the API serve.

Until 2026-09 `public/wholesale-price-list*.{txt,md}` were hand-made snapshots
(dated 25.07.2026, one said 62 SKU and another 64, USD prices differed from
the live catalog, "min order" was a dash while the Sheet had it). A buyer who
downloads the price list and then opens a card saw two different numbers.

Columns are kept separate on purpose: net weight (kg) of the sales unit, price
per unit incl. VAT (RUB), price excl. VAT, price per piece where the Sheet
gives one, USD export price, minimum order (units), shelf life, storage, HS
code. No price is ever presented per kilogram unless the Sheet expresses the
weight that way. Commercial terms (Incoterms, VAT basis, certificates) come
from products.json metadata and brand.txt, not from this script.

Outputs (RU + EN, txt + md):
  public/wholesale-price-list-ru.txt  public/wholesale-price-list-ru.md
  public/wholesale-price-list.txt     public/wholesale-price-list.md

Runs in scripts/sync-vps.sh right after the sync.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS = PUBLIC / "products.json"
TRANSLATIONS = ROOT / "scripts" / "translations.json"

SECTION_ORDER = ["Заморозка", "Охлаждённая продукция", "Выпечка"]
SECTION_EN = {"Заморозка": "Frozen", "Охлаждённая продукция": "Chilled", "Выпечка": "Bakery"}

CONTACT = "info@kazandelikates.tatar | +7 987 217-02-02"
CERTS_RU = "Халяль №614A/2024 (ДУМ РТ) | ХАССП | ISO 22000:2018 | ТР ТС 021/2011"
CERTS_EN = "Halal #614A/2024 (DUM RT) | HACCP | ISO 22000:2018 | TR CU 021/2011"


def num(v) -> float | None:
    try:
        f = float(str(v).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def fmt(v: float | None, dec: int = 2, dash: str = "—") -> str:
    if v is None:
        return dash
    s = f"{v:,.{dec}f}".replace(",", " ")
    return s.rstrip("0").rstrip(".") if dec and "." in s else s


def weight_kg(p: dict) -> float | None:
    return num(p.get("weight"))


def en_name(p: dict, tr: dict) -> str:
    clean = " ".join(str(p.get("name") or "").split())
    return tr.get("products", {}).get(clean.lower()) or clean


def load() -> tuple[dict, list[dict], dict]:
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    products = [p for p in data["products"] if p.get("sku")]
    tr = json.loads(TRANSLATIONS.read_text(encoding="utf-8")) if TRANSLATIONS.exists() else {}
    return data, products, tr


def rows_for(products: list[dict], lang: str, tr: dict) -> list[dict]:
    out = []
    for p in products:
        o = p.get("offers") or {}
        ep = o.get("exportPrices") or {}
        name = en_name(p, tr) if lang == "en" else p["name"]
        out.append({
            "sku": p["sku"],
            "name": " ".join(str(name).split()),
            "section": p.get("section") or "",
            "category": p.get("category") or "",
            "weight": weight_kg(p),
            "price": num(o.get("price")),
            "price_ex_vat": num(o.get("priceExclVAT")),
            "per_piece": num(o.get("pricePerPiece")),
            "usd": num(ep.get("USD")),
            "min_order": (str(p.get("minOrder") or "").strip() or None),
            "shelf": (str(p.get("shelfLife") or "").strip() or None),
            "storage": (str(p.get("storage") or "").strip() or None),
            "hs": (str(p.get("hsCode") or "").strip() or None),
        })
    return out


def header(meta: dict, lang: str, n: int) -> list[str]:
    synced = meta.get("lastSynced", date.today().isoformat())
    terms = meta.get("deliveryTerms", "EXW Kazan, Russia")
    if lang == "ru":
        return [
            "# Казанские Деликатесы — оптовый прайс-лист (халяль)",
            "",
            f"Позиций: {n} SKU | Производитель, Казань, Россия | Условия поставки: {terms}",
            f"Сертификаты: {CERTS_RU}",
            "Цены: RUB за единицу продажи (упаковка/штука, см. колонку «Масса нетто»), с НДС; "
            "«без НДС» — расчётная; USD — ориентир для экспорта, фиксируется в инвойсе.",
            f"Данные каталога: {synced} (Google Sheets → api.pepperoni.tatar/api/products). "
            "Прайс формируется автоматически из того же источника, что карточки и каталог.",
            f"Контакт: {CONTACT}",
            "",
        ]
    return [
        "# Kazan Delicacies — wholesale price list (halal)",
        "",
        f"Items: {n} SKUs | Manufacturer, Kazan, Russia | Delivery terms: {terms}",
        f"Certificates: {CERTS_EN}",
        "Prices: RUB per sales unit (pack/piece, see “Net weight”), incl. VAT; "
        "“excl. VAT” is derived; USD is an export reference fixed in the invoice.",
        f"Catalog data: {synced} (Google Sheets → api.pepperoni.tatar/api/products). "
        "Generated from the same source as the product cards and catalog.",
        f"Contact: {CONTACT}",
        "",
    ]


COLS_RU = ["SKU", "Наименование", "Масса нетто, кг", "Цена, ₽ с НДС", "Без НДС, ₽",
           "За шт, ₽", "USD", "Мин. заказ, ед.", "Срок годности", "Хранение", "ТН ВЭД"]
COLS_EN = ["SKU", "Product", "Net weight, kg", "Price, RUB incl. VAT", "Excl. VAT, RUB",
           "Per piece, RUB", "USD", "Min order, units", "Shelf life", "Storage", "HS code"]


def cells(r: dict, lang: str) -> list[str]:
    shelf = r["shelf"] or "—"
    if lang == "en" and shelf != "—":
        shelf = shelf.replace("суток", "days").replace("сут.", "days").replace("дней", "days").replace("дн.", "days")
    return [
        r["sku"], r["name"], fmt(r["weight"], 3), fmt(r["price"]), fmt(r["price_ex_vat"]),
        fmt(r["per_piece"]), fmt(r["usd"]), r["min_order"] or "—", shelf, r["storage"] or "—", r["hs"] or "—",
    ]


def render_md(meta: dict, rows: list[dict], lang: str) -> str:
    cols = COLS_EN if lang == "en" else COLS_RU
    lines = header(meta, lang, len(rows))
    sections = [s for s in SECTION_ORDER if any(r["section"] == s for r in rows)]
    sections += sorted({r["section"] for r in rows} - set(sections))
    for sec in sections:
        sec_rows = [r for r in rows if r["section"] == sec]
        title = SECTION_EN.get(sec, sec) if lang == "en" else sec
        lines += [f"## {title} — {len(sec_rows)} SKU", ""]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join("---" for _ in cols) + "|")
        for r in sec_rows:
            lines.append("| " + " | ".join(c.replace("|", "/") for c in cells(r, lang)) + " |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_txt(meta: dict, rows: list[dict], lang: str) -> str:
    cols = COLS_EN if lang == "en" else COLS_RU
    lines = [ln.lstrip("# ") if ln.startswith("# ") else ln for ln in header(meta, lang, len(rows))]
    sections = [s for s in SECTION_ORDER if any(r["section"] == s for r in rows)]
    sections += sorted({r["section"] for r in rows} - set(sections))
    for sec in sections:
        sec_rows = [r for r in rows if r["section"] == sec]
        title = SECTION_EN.get(sec, sec) if lang == "en" else sec
        lines += ["=" * 72, f"{title} — {len(sec_rows)} SKU", "=" * 72]
        for r in sec_rows:
            c = dict(zip(cols, cells(r, lang)))
            lines.append(f"{c[cols[0]]}  {c[cols[1]]}")
            lines.append(f"    {cols[2]}: {c[cols[2]]} | {cols[3]}: {c[cols[3]]} | {cols[4]}: {c[cols[4]]}"
                         + (f" | {cols[5]}: {c[cols[5]]}" if c[cols[5]] != "—" else "")
                         + f" | {cols[6]}: {c[cols[6]]}")
            lines.append(f"    {cols[7]}: {c[cols[7]]} | {cols[8]}: {c[cols[8]]} | {cols[9]}: {c[cols[9]]} | {cols[10]}: {c[cols[10]]}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    meta, products, tr = load()
    outputs = {
        "wholesale-price-list-ru.md": ("ru", render_md),
        "wholesale-price-list-ru.txt": ("ru", render_txt),
        "wholesale-price-list.md": ("en", render_md),
        "wholesale-price-list.txt": ("en", render_txt),
    }
    for fname, (lang, renderer) in outputs.items():
        rows = rows_for(products, lang, tr)
        (PUBLIC / fname).write_text(renderer(meta, rows, lang), encoding="utf-8")
    print(f"price lists: {len(products)} SKU → {', '.join(outputs)} (data {meta.get('lastSynced')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
