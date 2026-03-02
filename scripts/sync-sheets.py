#!/usr/bin/env python3
"""Sync products from Google Sheets to products.json. Python fallback when Node unavailable."""
import csv
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
BASE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pub?output=csv"

SHEETS = [
    {"gid": "1087942289", "section": "Заморозка", "type": "standard", "priceColOffset": 1},
    {"gid": "1589357549", "section": "Охлаждённая продукция", "type": "standard"},
    {"gid": "26993021", "section": "Выпечка", "type": "bakery"},
]


def to_number(s):
    if not s:
        return 0
    return float(str(s).replace(" ", "").replace(",", ".")) or 0


def extract_qty_from_name(name):
    m = re.search(r"[×x]\s*(\d+)\s*шт", str(name or ""), re.I)
    return int(m.group(1)) if m else 0


def parse_standard(lines, section, start_idx, col_offset=0):
    category = ""
    products = []
    idx = start_idx
    o = col_offset
    reader = csv.reader(lines)
    for cols in reader:
        if not cols or len(cols) < 7 + o:
            continue
        name = (cols[0] or "").strip()
        if not name or name == "Наименование" or name == "Номенклатура" or name.startswith("ООО"):
            continue
        price_vat = to_number(cols[2 + o])
        price_no_vat = to_number(cols[3 + o])
        if price_vat == 0 and price_no_vat == 0:
            if name and not cols[1]:
                category = name
            continue
        idx += 1
        qty = extract_qty_from_name(name)
        offers = {
            "priceCurrency": "RUB",
            "price": f"{price_vat:.2f}",
            "priceExclVAT": f"{price_no_vat:.2f}",
            "availability": "https://schema.org/InStock",
            "exportPrices": None,
        }
        if qty > 1:
            offers["pricePerPiece"] = f"{price_vat / qty:.2f}"
        ep = {}
        for i, cur in enumerate(["USD", "KZT", "UZS", "KGS", "BYN", "AZN"]):
            v = to_number(cols[7 + o + i]) if len(cols) > 7 + o + i else 0
            if v:
                ep[cur] = v
        if ep:
            offers["exportPrices"] = ep
        products.append({
            "name": name,
            "sku": f"KD-{idx:03d}",
            "section": section,
            "category": category or section,
            "weight": (cols[1] or "").strip(),
            "brand": "Казанские Деликатесы",
            "offers": offers,
            "shelfLife": (cols[4 + o] or "").strip(),
            "storage": (cols[5 + o] or "").strip(),
            "hsCode": (cols[6 + o] or "").strip(),
        })
    return {"products": products, "next_idx": idx}


def parse_bakery(lines, section, start_idx):
    category = ""
    products = []
    idx = start_idx
    reader = csv.reader(lines)
    for cols in reader:
        if not cols or len(cols) < 5:
            continue
        name = (cols[0] or "").strip()
        if not name or name == "Наименование" or name.startswith("ООО"):
            continue
        price_per_unit = to_number(cols[3])
        price_per_box = to_number(cols[4])
        if price_per_unit == 0 and price_per_box == 0:
            if name and not cols[1]:
                category = name
            continue
        idx += 1
        ep = {}
        for i, cur in enumerate(["USD", "KZT", "UZS", "KGS", "BYN", "AZN"]):
            v = to_number(cols[9 + i]) if len(cols) > 9 + i else 0
            if v:
                ep[cur] = v
        products.append({
            "name": name,
            "sku": f"KD-{idx:03d}",
            "section": section,
            "category": category or section,
            "weight": f"{cols[1]} г" if cols[1] else "",
            "qtyPerBox": (cols[2] or "").strip(),
            "brand": "Казанские Деликатесы",
            "offers": {
                "priceCurrency": "RUB",
                "pricePerUnit": f"{price_per_unit:.2f}",
                "pricePerBox": f"{price_per_box:.2f}",
                "pricePerBoxExclVAT": f"{to_number(cols[5]) if len(cols) > 5 else 0:.2f}",
                "availability": "https://schema.org/InStock",
                "exportPrices": ep if ep else None,
            },
            "shelfLife": (cols[6] or "").strip() if len(cols) > 6 else "",
            "storage": (cols[7] or "").strip() if len(cols) > 7 else "",
            "hsCode": (cols[8] or "").strip() if len(cols) > 8 else "",
        })
    return {"products": products, "next_idx": idx}


def main():
    print("📥 Загрузка данных из Google Sheets...")
    all_products = []
    idx = 0
    for sheet in SHEETS:
        url = f"{BASE_URL}&gid={sheet['gid']}"
        with urllib.request.urlopen(url, timeout=30) as r:
            text = r.read().decode("utf-8")
        lines = text.splitlines()
        if sheet["type"] == "bakery":
            result = parse_bakery(lines, sheet["section"], idx)
        else:
            result = parse_standard(lines, sheet["section"], idx, sheet.get("priceColOffset", 0))
        print(f"  ✅ {sheet['section']}: {len(result['products'])} товаров")
        all_products.extend(result["products"])
        idx = result["next_idx"]
    print(f"\n📊 Всего: {len(all_products)} товаров\n")
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    products_json = {
        "@context": "https://schema.org",
        "source": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pubhtml",
        "liveEndpoint": "https://api.pepperoni.tatar/api/products",
        "publisher": {
            "name": "Казанские Деликатесы",
            "url": "https://kazandelikates.tatar",
            "address": "420061, Республика Татарстан, г Казань, ул Аграрная, дом 2, офис 7",
            "phone": "+79872170202",
            "email": "info@kazandelikates.tatar",
        },
        "lastSynced": today,
        "deliveryTerms": "EXW Kazan Russia",
        "certification": "Halal",
        "sections": ["Заморозка", "Охлаждённая продукция", "Выпечка"],
        "totalProducts": len(all_products),
        "products": all_products,
    }
    out = PUBLIC / "products.json"
    out.write_text(json.dumps(products_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {out}")


if __name__ == "__main__":
    main()
