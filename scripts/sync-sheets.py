#!/usr/bin/env python3
"""
Sync products from Google Sheets to products.json and related files.
Python version — works when Node.js is unavailable.
Fully replicates sync-sheets.mjs with B2B column mapping.
"""
import csv
import io
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
BASE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pub?output=csv"

SHEETS = [
    {"gid": "1087942289", "section": "Заморозка", "type": "standard", "priceColOffset": 0},
    {"gid": "1589357549", "section": "Охлаждённая продукция", "type": "standard"},
    {"gid": "26993021", "section": "Выпечка", "type": "bakery"},
]

# B2B: A=0 Name, B=1 Weight, C=2 Price/1pc, D=3 Price VAT, E=4 NoVAT, F=5 ShelfLife, G=6 Storage,
# H=7 HS, I-N=8-13 currencies, O=14 Cooking, P=15 MinOrder, Q=16 BoxWeight, R=17 Article,
# S=18 Barcode, T=19 SEO_RU, U=20 SEO_EN, V=21 Diameter, W=22 Casing, X=23 IngrRU, Y=24 IngrEN,
# Z=25 Nutrition, AA=26 PkgType, AB=27 MainPhoto, AC=28 PackPhoto, AD=29 SlicePhoto


def to_number(s):
    if not s:
        return 0
    try:
        return float(str(s).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0


def extract_qty_from_name(name):
    m = re.search(r"[×x]\s*(\d+)\s*шт", str(name or ""), re.I)
    return int(m.group(1)) if m else 0


def parse_standard(lines, section, start_idx, col_offset=0):
    category = ""
    products = []
    idx = start_idx
    o = col_offset

    reader = csv.reader(io.StringIO(lines))
    for cols in reader:
        if not cols or len(cols) < 7 + o:
            continue
        cols = [c.strip() if isinstance(c, str) else str(c or "").strip() for c in cols]
        name = cols[0]
        if not name or name == "Наименование" or name == "Номенклатура" or name.startswith("ООО"):
            continue

        price_vat = to_number(cols[3 + o]) if len(cols) > 3 + o else 0
        if not price_vat and len(cols) > 2 + o:
            price_vat = to_number(cols[2 + o])
        price_no_vat = to_number(cols[4 + o]) if len(cols) > 4 + o else 0
        if not price_no_vat and len(cols) > 3 + o:
            price_no_vat = to_number(cols[3 + o])

        if price_vat == 0 and price_no_vat == 0:
            if name and not (cols[1] if len(cols) > 1 else ""):
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
        price_per_piece_val = to_number(cols[2 + o]) if len(cols) > 2 + o else 0
        if qty > 1:
            offers["pricePerPiece"] = f"{(price_per_piece_val or price_vat / qty):.2f}"
        elif price_per_piece_val:
            offers["pricePerPiece"] = f"{price_per_piece_val:.2f}"

        ep = {}
        for i, cur in enumerate(["USD", "KZT", "UZS", "KGS", "BYN", "AZN"]):
            ci = 8 + o + i
            if len(cols) > ci:
                v = to_number(cols[ci])
                if v:
                    ep[cur] = v
        if ep:
            offers["exportPrices"] = ep

        article = (cols[17 + o] or "").strip() if len(cols) > 17 + o else ""
        sku = f"KD-{idx:03d}"

        main_photo = (cols[27 + o] or "").strip() if len(cols) > 27 + o else ""
        pack_photo = (cols[28 + o] or "").strip() if len(cols) > 28 + o else ""
        slice_photo = (cols[29 + o] or "").strip() if len(cols) > 29 + o else ""
        image = main_photo or pack_photo or slice_photo

        def cell(i):
            return (cols[i + o] or "").strip() if len(cols) > i + o else ""

        p = {
            "name": name,
            "sku": sku,
            "section": section,
            "category": category or section,
            "weight": cols[1] if len(cols) > 1 else "",
            "brand": "Казанские Деликатесы",
            "offers": offers,
            "shelfLife": cell(5),
            "storage": cell(6),
            "hsCode": cell(7),
        }
        if article:
            p["articleNumber"] = article
        if cell(14):
            p["cookingMethods"] = cell(14)
        if cell(15):
            p["minOrder"] = cell(15)
        if cell(16):
            p["boxWeightGross"] = cell(16)
        if cell(18):
            p["barcode"] = cell(18)
        if cell(19):
            p["seoDescriptionRU"] = cell(19)
        if cell(20):
            p["seoDescriptionEN"] = cell(20)
        if cell(21):
            p["diameter"] = cell(21)
        if cell(22):
            p["casing"] = cell(22)
        if cell(23):
            p["ingredientsRU"] = cell(23)
        if cell(24):
            p["ingredientsEN"] = cell(24)
        if cell(25):
            p["nutrition"] = cell(25)
        if cell(26):
            p["packageType"] = cell(26)
        if image:
            p["image"] = image
        if main_photo:
            p["imageMain"] = main_photo
        if pack_photo:
            p["imagePack"] = pack_photo
        if slice_photo:
            p["imageSlice"] = slice_photo

        products.append(p)

    return {"products": products, "next_idx": idx}


def parse_bakery(lines, section, start_idx):
    category = ""
    products = []
    idx = start_idx

    reader = csv.reader(io.StringIO(lines))
    for cols in reader:
        if not cols or len(cols) < 5:
            continue
        cols = [c.strip() if isinstance(c, str) else str(c or "").strip() for c in cols]
        name = cols[0]
        if not name or name == "Наименование" or name.startswith("ООО"):
            continue

        price_per_unit = to_number(cols[3])
        price_per_box = to_number(cols[4])
        if price_per_unit == 0 and price_per_box == 0:
            if name and not (cols[1] if len(cols) > 1 else ""):
                category = name
            continue

        idx += 1
        ep = {}
        for i, cur in enumerate(["USD", "KZT", "UZS", "KGS", "BYN", "AZN"]):
            if len(cols) > 9 + i:
                v = to_number(cols[9 + i])
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


def generate_products_json(all_products):
    today = datetime.now().strftime("%Y-%m-%d")
    return {
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


def main():
    print("📥 Загрузка данных из Google Sheets...")

    all_products = []
    idx = 0

    for sheet in SHEETS:
        url = f"{BASE_URL}&gid={sheet['gid']}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8")

        if sheet["type"] == "bakery":
            result = parse_bakery(text, sheet["section"], idx)
        else:
            result = parse_standard(text, sheet["section"], idx, sheet.get("priceColOffset", 0))

        print(f"  ✅ {sheet['section']}: {len(result['products'])} товаров")
        all_products.extend(result["products"])
        idx = result["next_idx"]

    print(f"\n📊 Всего: {len(all_products)} товаров\n")

    products_json = generate_products_json(all_products)
    out_path = PUBLIC / "products.json"
    out_path.write_text(json.dumps(products_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {out_path}")

    # IndexNow ping
    try:
        urllib.request.urlopen(
            "https://www.bing.com/indexnow?url=https://pepperoni.tatar/&key=2164b9a639c7455aad8651dc19e48641",
            timeout=5,
        )
        print("✅ IndexNow ping sent")
    except Exception:
        pass

    print("\n🎉 Синхронизация завершена!")
    print("\nЗапусти для генерации страниц:")
    print("  python3 scripts/gen-ru-products.py")
    print("  python3 scripts/gen-en-products.py")


if __name__ == "__main__":
    main()
