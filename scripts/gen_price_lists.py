#!/usr/bin/env python3
"""Generate wholesale price lists from products.json — the same data the
cards, the static catalog and the API serve.

Until 2026-09 `public/wholesale-price-list*.{txt,md}` were hand-made snapshots.
This script is the only writer. HTML / Excel / PDF are rebuilt in the same
sync cycle (scripts/sync-vps.sh) so a downloaded file cannot drift from the
cards.

Price shown = the figure the product card already shows:
  * meat/sausage SKUs — offers.price (pack, RUB incl. VAT)
  * bakery SKUs — offers.pricePerUnit (piece, RUB incl. VAT) plus box price

Outputs:
  public/wholesale-price-list-ru.{txt,md}
  public/wholesale-price-list.{txt,md}
  public/price.html          public/en/price.html
  public/prices.xlsx         public/prices.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRODUCTS = PUBLIC / "products.json"
TRANSLATIONS = ROOT / "scripts" / "translations.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from commercial_page import page as wrap_page  # noqa: E402
from site_facts import FACTS, certs_price_en, certs_price_ru  # noqa: E402

SECTION_ORDER = ["Заморозка", "Охлаждённая продукция", "Выпечка"]
SECTION_EN = {"Заморозка": "Frozen", "Охлаждённая продукция": "Chilled", "Выпечка": "Bakery"}

CONTACT = f"{FACTS['company']['email']} | {FACTS['company']['phone']}"
CERTS_RU = certs_price_ru()
CERTS_EN = certs_price_en()
MOQ_RU = FACTS["terms"]["moq"]
MOQ_EN = "1 pallet (mixed pallet possible)"
BASIS_RU = FACTS["terms"]["basis"]


def num(v) -> float | None:
    try:
        f = float(str(v).replace(",", ".").replace(" ", "").replace("\u00a0", ""))
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def fmt(v: float | None, dec: int = 2, dash: str = "—") -> str:
    if v is None:
        return dash
    s = f"{v:,.{dec}f}".replace(",", " ")
    return s.rstrip("0").rstrip(".") if dec and "." in s else s


def fmt_card(v: float | None) -> str:
    """Same grouping as product cards: 2 876,54"""
    if v is None:
        return "—"
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def weight_kg(p: dict) -> float | None:
    raw = str(p.get("weight") or "").strip()
    if re.search(r"\bг\b|\bg\b", raw, re.I) and "кг" not in raw.lower() and "kg" not in raw.lower():
        # First gram figure only: "80 г х 6" is 80 g, not 806.
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:г|g)\b", raw, re.I)
        grams = num(m.group(1) if m else None)
        return (grams / 1000.0) if grams else None
    return num(raw)


def weight_label(p: dict) -> str:
    w = str(p.get("weight") or "").strip()
    if not w:
        return "—"
    if re.search(r"г|кг|g|kg", w, re.I):
        return w
    return w + " кг"


def en_name(p: dict, tr: dict) -> str:
    clean = " ".join(str(p.get("name") or "").split())
    return tr.get("products", {}).get(clean.lower()) or clean


def site_prices(p: dict) -> dict:
    """Prices exactly as the product card renders them."""
    o = p.get("offers") or {}
    bakery = bool(o.get("pricePerUnit"))
    if bakery:
        return {
            "bakery": True,
            "price": num(o.get("pricePerUnit")),
            "price_ex_vat": num(o.get("pricePerUnitExclVAT") or o.get("priceExclVAT")),
            "per_piece": num(o.get("pricePerUnit")),
            "per_box": num(o.get("pricePerBox")),
            "unit": "шт",
        }
    return {
        "bakery": False,
        "price": num(o.get("price")),
        "price_ex_vat": num(o.get("priceExclVAT")),
        "per_piece": num(o.get("pricePerPiece")),
        "per_box": None,
        "unit": "уп.",
    }


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
        sp = site_prices(p)
        out.append({
            "sku": p["sku"],
            "name": " ".join(str(name).split()),
            "section": p.get("section") or "",
            "category": p.get("category") or "",
            "weight": weight_kg(p),
            "weight_label": weight_label(p),
            "price": sp["price"],
            "price_ex_vat": sp["price_ex_vat"],
            "per_piece": sp["per_piece"],
            "per_box": sp["per_box"],
            "bakery": sp["bakery"],
            "unit": sp["unit"],
            "usd": num(ep.get("USD")),
            "min_order": (str(p.get("minOrder") or "").strip() or None),
            "shelf": (str(p.get("shelfLife") or "").strip() or None),
            "storage": (str(p.get("storage") or "").strip() or None),
            "hs": (str(p.get("hsCode") or "").strip() or None),
            "href": f"/en/products/{p['sku'].lower()}" if lang == "en" else f"/products/{p['sku'].lower()}",
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
            "Цены: как на карточках сайта — RUB за единицу продажи "
            "(упаковка для мясной линейки, штука для выпечки), с НДС; "
            "«без НДС» — расчётная; USD — ориентир для экспорта, фиксируется в инвойсе.",
            f"Минимальный заказ: {MOQ_RU}. Базис: {BASIS_RU}.",
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
        "Prices match the product cards: RUB per sales unit "
        "(pack for meat lines, piece for bakery), incl. VAT; "
        "“excl. VAT” is derived; USD is an export reference fixed in the invoice.",
        f"Minimum order: {MOQ_EN}. Basis: EXW Kazan.",
        f"Catalog data: {synced} (Google Sheets → api.pepperoni.tatar/api/products). "
        "Generated from the same source as the product cards and catalog.",
        f"Contact: {CONTACT}",
        "",
    ]


COLS_RU = ["SKU", "Наименование", "Масса нетто, кг", "Цена, ₽ с НДС", "Без НДС, ₽",
           "За шт, ₽", "USD", "Мин. заказ, ед.", "Срок годности", "Хранение", "ТН ВЭД"]
COLS_EN = ["SKU", "Product", "Net weight, kg", "Price, RUB incl. VAT", "Excl. VAT, RUB",
           "Per piece, RUB", "USD", "Min order, units", "Shelf life", "Storage", "HS code"]


def _shelf(r: dict, lang: str) -> str:
    shelf = r["shelf"] or "—"
    if lang == "en" and shelf != "—":
        shelf = shelf.replace("суток", "days").replace("сут.", "days").replace("дней", "days").replace("дн.", "days")
    return shelf


def cell_values(r: dict, lang: str) -> list[tuple[object, bool]]:
    """Typed cells for xlsx: (value, is_numeric). None numeric → em dash text."""
    return [
        (r["sku"], False),
        (r["name"], False),
        (r["weight"], True),
        (r["price"], True),
        (r["price_ex_vat"], True),
        (r["per_piece"], True),
        (r["usd"], True),
        (r["min_order"] or "—", False),
        (_shelf(r, lang), False),
        (r["storage"] or "—", False),
        (r["hs"] or "—", False),
    ]


def cells(r: dict, lang: str) -> list[str]:
    out = []
    for i, (val, numeric) in enumerate(cell_values(r, lang)):
        if numeric:
            out.append(fmt(val, 3 if i == 2 else 2))
        else:
            out.append("—" if val in (None, "") else str(val))
    return out


def sections_of(rows: list[dict]) -> list[str]:
    sections = [s for s in SECTION_ORDER if any(r["section"] == s for r in rows)]
    sections += sorted({r["section"] for r in rows} - set(sections))
    return sections


def render_md(meta: dict, rows: list[dict], lang: str) -> str:
    cols = COLS_EN if lang == "en" else COLS_RU
    lines = header(meta, lang, len(rows))
    for sec in sections_of(rows):
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
    for sec in sections_of(rows):
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


def _xlsx_cell(ref: str, val, numeric: bool) -> str:
    if numeric:
        n = float(val) if isinstance(val, (int, float)) else num(val)
        if n is not None:
            v = f"{n:.6f}".rstrip("0").rstrip(".")
            return f'<c r="{ref}" t="n"><v>{v}</v></c>'
        val = "—"
    text = xml_escape(str(val if val not in (None, "") else "—"))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _zip_datetime(synced: str) -> tuple[int, int, int, int, int, int]:
    """Deterministic ZipInfo date from products.json lastSynced, not now()."""
    raw = str(synced or "").strip()
    try:
        if "T" in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
        return (dt.year, dt.month, dt.day, getattr(dt, "hour", 0),
                getattr(dt, "minute", 0), getattr(dt, "second", 0))
    except (ValueError, TypeError):
        return (2026, 1, 1, 0, 0, 0)


def _zip_writestr(z: zipfile.ZipFile, name: str, data: str | bytes, dt) -> None:
    info = zipfile.ZipInfo(name, date_time=dt)
    info.compress_type = zipfile.ZIP_DEFLATED
    if isinstance(data, str):
        data = data.encode("utf-8")
    z.writestr(info, data)


def _xlsx_sheet(name: str, headers: list[str], body: list[list[tuple[object, bool]]], idx: int) -> str:
    rows_xml = []
    header_cells = []
    for c_i, val in enumerate(headers):
        header_cells.append(_xlsx_cell(f"{chr(65 + c_i)}1", val, False))
    rows_xml.append(f'<row r="1">{"".join(header_cells)}</row>')
    for r_i, row in enumerate(body, 2):
        cells_xml = []
        for c_i, (val, numeric) in enumerate(row):
            cells_xml.append(_xlsx_cell(f"{chr(65 + c_i)}{r_i}", val, numeric))
        rows_xml.append(f'<row r="{r_i}">{"".join(cells_xml)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rows_xml)}</sheetData></worksheet>'
    )


def write_xlsx(meta: dict, products: list[dict], tr: dict, dest: Path) -> None:
    """Office Open XML workbook, no extra Python deps."""
    ru_rows = rows_for(products, "ru", tr)
    en_rows = rows_for(products, "en", tr)
    synced = meta.get("lastSynced", "")
    sheets: list[tuple[str, str]] = []

    def pack(lang: str, rows: list[dict]) -> list[tuple[str, list[str], list[list[tuple[object, bool]]]]]:
        cols = COLS_EN if lang == "en" else COLS_RU
        out = []
        for sec in sections_of(rows):
            title = SECTION_EN.get(sec, sec) if lang == "en" else sec
            body = [cell_values(r, lang) for r in rows if r["section"] == sec]
            out.append((title[:31], cols, body))
        return out

    packed = [("RU " + n, h, b) for n, h, b in pack("ru", ru_rows)]
    packed += [("EN " + n, h, b) for n, h, b in pack("en", en_rows)]
    # Excel sheet names must be unique and ≤31 chars
    used = set()
    named: list[tuple[str, list[str], list[list[tuple[object, bool]]]]] = []
    for name, headers, body in packed:
        base = re.sub(r"[\\/?*\\[\\]]", " ", name)[:31]
        candidate = base
        n = 2
        while candidate.lower() in used:
            suffix = f" {n}"
            candidate = (base[: 31 - len(suffix)] + suffix)
            n += 1
        used.add(candidate.lower())
        named.append((candidate, headers, body))

    dt = _zip_datetime(synced)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        _zip_writestr(z, "[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + "".join(
                       f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                       f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                       for i in range(1, len(named) + 1)
                   )
                   + "</Types>", dt)
        _zip_writestr(z, "_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   "</Relationships>", dt)
        sheets_xml = "".join(
            f'<sheet name="{xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _, _) in enumerate(named, 1)
        )
        _zip_writestr(z, "xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   f'<sheets>{sheets_xml}</sheets></workbook>', dt)
        _zip_writestr(z, "xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(
                       f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                       for i in range(1, len(named) + 1)
                   )
                   + "</Relationships>", dt)
        for i, (name, headers, body) in enumerate(named, 1):
            _zip_writestr(z, f"xl/worksheets/sheet{i}.xml", _xlsx_sheet(name, headers, body, i), dt)
        _zip_writestr(z, "docProps/core.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   f'<dc:title>Kazan Delicacies price list {xml_escape(synced)}</dc:title>'
                   "<dc:creator>pepperoni.tatar</dc:creator></cp:coreProperties>", dt)
    dest.write_bytes(buf.getvalue())


def render_html(meta: dict, rows: list[dict], lang: str) -> str:
    synced = meta.get("lastSynced", "")
    n = len(rows)
    if lang == "ru":
        title = "Оптовый прайс-лист халяль продукции — Казанские Деликатесы"
        desc = (
            f"Прайс {n} SKU с ценами как на карточках сайта, данные каталога {synced}. "
            f"Скачать Excel и PDF. Минимальный заказ — {MOQ_RU}. {BASIS_RU}."
        )
        h1 = "Оптовый прайс-лист"
        lead = (
            f"Цены совпадают с карточками на pepperoni.tatar: за упаковку с НДС "
            f"для мясной линейки и за штуку с НДС для выпечки. Каталог синхронизирован "
            f"{escape(synced)} из Google Sheets. Минимальный заказ — {escape(MOQ_RU)}. "
            f"Базис поставки — {escape(BASIS_RU)}; доставку оплачивает покупатель, "
            f"срок отгрузки подтверждает отдел продаж по заявке."
        )
        dl_xlsx, dl_pdf = "Скачать Excel", "Скачать PDF"
        how = "Как заказать"
        unit_h, vat_h, piece_h, box_h = "Ед.", "₽ с НДС", "₽ / шт", "₽ / короб"
        nav = (
            '<div class="topnav">'
            '<a href="/">Каталог</a><a href="/kak-zakazat">Как заказать</a>'
            '<a href="/delivery">Доставка</a><a href="/about">О компании</a>'
            '<span class="here">Прайс</span>'
            '<a href="/en/price" style="margin-left:auto;color:#888">English</a></div>'
        )
        crumb = '<nav class="crumb"><a href="/">Главная</a> → Прайс</nav>'
        th_name, th_w = "Наименование", "Масса"
    else:
        title = "Wholesale halal price list — Kazan Delicacies"
        desc = (
            f"Price list of {n} SKUs at the same figures as the product cards, catalog {synced}. "
            f"Download Excel and PDF. Minimum order: {MOQ_EN}. EXW Kazan."
        )
        h1 = "Wholesale price list"
        lead = (
            f"Prices match the product cards: pack incl. VAT for meat lines and "
            f"per piece incl. VAT for bakery. Catalog synced {escape(synced)} from Google Sheets. "
            f"Minimum order — {escape(MOQ_EN)}. Basis EXW Kazan; the buyer pays freight; "
            f"lead time is confirmed by sales for each order."
        )
        dl_xlsx, dl_pdf = "Download Excel", "Download PDF"
        how = "How to order"
        unit_h, vat_h, piece_h, box_h = "Unit", "RUB incl. VAT", "RUB / pc", "RUB / case"
        nav = (
            '<div class="topnav">'
            '<a href="/en/">Catalog</a><a href="/en/kak-zakazat">How to order</a>'
            '<a href="/en/delivery">Delivery</a><a href="/en/about">About</a>'
            '<span class="here">Price list</span>'
            '<a href="/price" style="margin-left:auto;color:#888">Русский</a></div>'
        )
        crumb = '<nav class="crumb"><a href="/en/">Home</a> → Price list</nav>'
        th_name, th_w = "Product", "Weight"

    tables = []
    for sec in sections_of(rows):
        sec_rows = [r for r in rows if r["section"] == sec]
        title_s = SECTION_EN.get(sec, sec) if lang == "en" else sec
        trs = []
        for r in sec_rows:
            unit = ("шт" if r["bakery"] else "уп.") if lang == "ru" else ("pc" if r["bakery"] else "pack")
            trs.append(
                "<tr>"
                f'<td><a href="{r["href"]}">{escape(r["sku"])}</a></td>'
                f"<td>{escape(r['name'])}</td>"
                f"<td>{escape(r['weight_label'])}</td>"
                f"<td>{escape(unit)}</td>"
                f'<td class="num">{fmt_card(r["price"])}</td>'
                f'<td class="num">{fmt_card(r["price_ex_vat"])}</td>'
                f'<td class="num">{fmt_card(r["per_piece"])}</td>'
                f'<td class="num">{fmt_card(r["per_box"])}</td>'
                f'<td class="num">{fmt(r["usd"]) if r["usd"] is not None else "—"}</td>'
                "</tr>"
            )
        tables.append(
            f"<h2>{escape(title_s)} — {len(sec_rows)} SKU</h2>"
            "<table><thead><tr>"
            f"<th>SKU</th><th>{th_name}</th><th>{th_w}</th><th>{unit_h}</th>"
            f"<th>{vat_h}</th><th>{'без НДС' if lang == 'ru' else 'excl. VAT'}</th>"
            f"<th>{piece_h}</th><th>{box_h}</th><th>USD</th>"
            "</tr></thead><tbody>"
            + "".join(trs)
            + "</tbody></table>"
        )

    how_href = "/kak-zakazat" if lang == "ru" else "/en/kak-zakazat"
    extra = (
        '<script type="application/ld+json">'
        + json.dumps({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "name": "Главная" if lang == "ru" else "Home",
                 "item": "https://pepperoni.tatar/" if lang == "ru" else "https://pepperoni.tatar/en/"},
                {"@type": "ListItem", "position": 2,
                 "name": "Прайс" if lang == "ru" else "Price list",
                 "item": "https://pepperoni.tatar/price" if lang == "ru" else "https://pepperoni.tatar/en/price"},
            ],
        }, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )
    body = (
        crumb
        + f"<h1>{h1}</h1>"
        + f'<p>{lead}</p>'
        + '<div class="dl">'
        + f'<a href="/prices.xlsx">{escape(dl_xlsx)}</a>'
        + f'<a href="/prices.pdf">{escape(dl_pdf)}</a>'
        + f'<a class="ghost" href="{how_href}">{escape(how)}</a>'
        + "</div>"
        + "".join(tables)
        + f'<p class="note">{escape(CONTACT)} · {escape(CERTS_RU if lang == "ru" else CERTS_EN)}</p>'
    )
    return wrap_page(
        lang=lang,
        robots="noindex, follow" if lang == "en" else "index, follow",
        title=title,
        description=desc,
        canonical="https://pepperoni.tatar/price" if lang == "ru" else "https://pepperoni.tatar/en/price",
        hreflang_ru="https://pepperoni.tatar/price",
        hreflang_en="https://pepperoni.tatar/en/price",
        nav_html=nav,
        body=body,
        extra_head=extra,
    )


def _is_snap(path: str) -> bool:
    try:
        real = os.path.realpath(path)
    except OSError:
        real = path
    return "/snap/" in real.replace("\\", "/")


def _is_chrome_wrapper(path: str) -> bool:
    """Skip PATH wrappers that inject --remote-debugging-port (hang on PDF).

    A shebang launcher is fine as long as it does not add that flag.
    Snap binaries are rejected separately: confinement breaks --print-to-pdf.
    """
    p = Path(path)
    try:
        if p.stat().st_size > 100_000:
            return False
        head = p.read_bytes()[:4000]
    except OSError:
        return False
    return b"remote-debugging-port" in head


def _chrome_candidates() -> list[str]:
    """Non-snap Chrome/Chromium binaries, real files first."""
    candidates = [
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/lib/chromium-browser/chromium-browser",
        "/usr/lib/chromium/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for which in ("google-chrome-stable", "chromium-browser", "chromium"):
        found = shutil.which(which)
        if found:
            candidates.append(found)
    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if _is_snap(candidate):
            continue
        if not (Path(candidate).is_file() and os.access(candidate, os.X_OK)):
            continue
        if _is_chrome_wrapper(candidate):
            continue
        out.append(candidate)
    return out


def _chrome_print(chrome: str, html_path: Path, dest: Path) -> bool:
    tmp = dest.with_suffix(".pdf.tmp")
    if tmp.exists():
        tmp.unlink()
    user_dir = Path("/tmp/pepperoni-price-pdf-chrome")
    user_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--no-pdf-header-footer",
        "--no-first-run", "--no-default-browser-check",
        f"--user-data-dir={user_dir}",
        f"--print-to-pdf={tmp}", html_path.resolve().as_uri(),
    ]
    env = os.environ.copy()
    env.setdefault("HOME", "/tmp")
    err_log = Path("/tmp/pepperoni-price-pdf-chrome.err")
    try:
        with err_log.open("wb") as errf:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=errf, env=env,
            )
    except OSError as exc:
        print(f"ERROR: prices.pdf: failed to launch {chrome}: {exc}", file=sys.stderr)
        return False
    deadline = time.time() + 15
    ok = False
    try:
        while time.time() < deadline:
            if tmp.is_file() and tmp.stat().st_size > 1000:
                time.sleep(0.4)
                if tmp.is_file() and tmp.stat().st_size > 1000:
                    ok = True
                    break
            if proc.poll() is not None:
                ok = tmp.is_file() and tmp.stat().st_size > 1000
                break
            time.sleep(0.2)
    finally:
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    if ok:
        tmp.replace(dest)
        return True
    hint = ""
    try:
        hint = err_log.read_text(errors="replace")[-300:].strip()
    except OSError:
        pass
    extra = f" — {hint}" if hint else ""
    print(f"ERROR: prices.pdf: print-to-pdf failed ({chrome}){extra}", file=sys.stderr)
    if tmp.exists():
        tmp.unlink()
    return False


def _python_pdf(meta: dict, products: list[dict], tr: dict, dest: Path) -> bool:
    """Catalog table PDF when Chromium cannot print. Same rows as xlsx."""
    try:
        from price_pdf import DEJAVU, write_catalog_pdf  # noqa: E402
    except Exception as exc:
        print(f"ERROR: prices.pdf: python fallback import failed: {exc}", file=sys.stderr)
        return False
    if not DEJAVU.is_file():
        print(f"ERROR: prices.pdf: missing font {DEJAVU}", file=sys.stderr)
        return False
    rows_ru = rows_for(products, "ru", tr)
    headers = COLS_RU
    table = []
    for r in rows_ru:
        cells = cell_values(r, "ru")
        table.append([
            "" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))
            for v, _n in cells
        ])
    synced = meta.get("lastSynced") or ""
    subtitle = [
        f"Позиций: {len(products)} SKU · {BASIS_RU} · {MOQ_RU} · каталог {synced}",
        f"Сертификаты: {CERTS_RU}",
        f"Контакт: {CONTACT}",
    ]
    try:
        write_catalog_pdf(
            dest,
            "Казанские Деликатесы — оптовый прайс-лист (халяль)",
            subtitle,
            headers,
            table,
        )
    except Exception as exc:
        print(f"ERROR: prices.pdf: python fallback failed: {exc}", file=sys.stderr)
        return False
    return dest.is_file() and dest.stat().st_size > 1000


def write_pdf(html_path: Path, dest: Path, meta=None, products=None, tr=None) -> bool:
    """Rebuild prices.pdf from catalog rows (DejaVu). Optional non-snap Chrome.

    Snap Chromium is skipped: --print-to-pdf fails under confinement.
    Python table PDF is the VPS-reliable writer so a Sheet price change
    still refreshes prices.pdf when Chrome is missing or confined.
    """
    if meta is not None and products is not None:
        if _python_pdf(meta, products, tr or {}, dest):
            print("prices.pdf: rebuilt with DejaVu table (no snap Chromium)")
            return True
    chromes = _chrome_candidates()
    for chrome in chromes:
        if _chrome_print(chrome, html_path, dest):
            print(f"prices.pdf: printed with {chrome}")
            return True
    print("ERROR: prices.pdf: DejaVu writer failed and no non-snap Chrome print",
          file=sys.stderr)
    return False


def _strip_runtime(html: str) -> str:
    """Ignore inject_site_links / LocalBusiness blocks when deciding if /price changed."""
    for start, end in (
        ("<!-- site-links:start -->", "<!-- site-links:end -->"),
        ("<!-- company-footer:start -->", "<!-- company-footer:end -->"),
        ("<!-- localbusiness-ld:start -->", "<!-- localbusiness-ld:end -->"),
    ):
        html = re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\n?", "", html, flags=re.S)
    return html


def _write_if_changed(path: Path, text: str) -> bool:
    if path.is_file() and _strip_runtime(path.read_text(encoding="utf-8")) == _strip_runtime(text):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def write_pdf_only() -> int:
    """Rebuild prices.pdf after inject_site_links so PDF mtime is not older than price.html."""
    meta, products, tr = load()
    pdf_path = PUBLIC / "prices.pdf"
    before = pdf_path.stat().st_mtime if pdf_path.is_file() else 0
    ok = write_pdf(
        PUBLIC / "price.html", pdf_path, meta=meta, products=products, tr=tr,
    )
    after = pdf_path.stat().st_mtime if pdf_path.is_file() else 0
    if ok and after > before:
        print(f"prices.pdf: refreshed after inject ({pdf_path.stat().st_size} bytes)")
        return 0
    print("ERROR: prices.pdf: --pdf-only did not rewrite the file", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pdf-only",
        action="store_true",
        help="rebuild prices.pdf from the catalog (run after inject_site_links)",
    )
    args = ap.parse_args(argv)
    if args.pdf_only:
        return write_pdf_only()

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

    ru_rows = rows_for(products, "ru", tr)
    en_rows = rows_for(products, "en", tr)
    ru_changed = _write_if_changed(PUBLIC / "price.html", render_html(meta, ru_rows, "ru"))
    en_changed = _write_if_changed(PUBLIC / "en" / "price.html", render_html(meta, en_rows, "en"))
    write_xlsx(meta, products, tr, PUBLIC / "prices.xlsx")
    pdf_path = PUBLIC / "prices.pdf"
    catalog_newer = (
        pdf_path.is_file()
        and PRODUCTS.stat().st_mtime > pdf_path.stat().st_mtime + 1
    )
    need_pdf = ru_changed or en_changed or not pdf_path.is_file() or catalog_newer
    rc = 0
    if need_pdf:
        pdf_ok = write_pdf(
            PUBLIC / "price.html", pdf_path, meta=meta, products=products, tr=tr,
        )
        if pdf_ok:
            extra = "prices.xlsx + prices.pdf"
        else:
            extra = "prices.xlsx; prices.pdf NOT updated"
            rc = 1
    else:
        extra = "prices.xlsx; prices.pdf unchanged (price.html identical)"
        pdf_ok = False
    print(f"price lists: {len(products)} SKU → txt/md/html/xlsx"
          f"{' /pdf' if pdf_ok else ''} (data {meta.get('lastSynced')}); {extra}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
