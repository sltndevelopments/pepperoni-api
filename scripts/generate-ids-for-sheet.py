#!/usr/bin/env python3
"""
Извлекает ID картинок из products.json и создаёт файл для копирования в Google Таблицу.
Запуск: python3 scripts/generate-ids-for-sheet.py

Результат: docs/ids-for-google-sheet.csv
Скопируй колонки mainPhotoID, packPhotoID, slicePhotoID в колонки AB, AC, AD таблицы.
"""
import csv
import json
import os
import re
import urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
PRODUCTS_JSON = os.path.join(ROOT, "public", "products.json")
OUTPUT_CSV = os.path.join(ROOT, "docs", "ids-for-google-sheet.csv")


def translit(text):
    """Тот же транслит, что в fix_names.py."""
    symbols = str.maketrans(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя ",
        "abvgdeezzijklmnoprstufhzcss_y_eua_",
    )
    return text.lower().translate(symbols)


def has_cyrillic(s):
    return bool(re.search(r"[а-яА-Я]", s))


def extract_id(url):
    """Из полной Cloudinary-ссылки извлекает ID (v123/name.jpg или name.jpg)."""
    if not url or "cloudinary.com" not in url:
        return ""
    try:
        parts = url.split("/upload/", 1)
        if len(parts) != 2:
            return ""
        rest = parts[1].split("?")[0]
        m = re.search(r"(v\d+/.+)", rest)
        if m:
            path = m.group(1)
            if has_cyrillic(urllib.parse.unquote(path)):
                version, filename = path.split("/", 1)
                base, ext = os.path.splitext(urllib.parse.unquote(filename))
                new_base = translit(base)
                return f"{version}/{new_base}{ext}"
            return path
        return rest.split("/")[-1] if "/" in rest else rest
    except Exception:
        return ""


def main():
    with open(PRODUCTS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    products = data.get("products", [])

    rows = [["sku", "name", "mainPhotoID", "packPhotoID", "slicePhotoID"]]
    for p in products:
        main = extract_id(p.get("imageMain") or p.get("image") or "")
        pack = extract_id(p.get("imagePack") or "")
        slice_id = extract_id(p.get("imageSlice") or "")
        rows.append([p.get("sku", ""), p.get("name", ""), main, pack, slice_id])

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"✅ Сохранено: {OUTPUT_CSV}")
    print("\nОткуда берутся ID:")
    print("  — из products.json (данные из Google Таблицы)")
    print("\nКак использовать:")
    print("  1. Открой docs/ids-for-google-sheet.csv в Excel или Cursor")
    print("  2. Скопируй колонки mainPhotoID, packPhotoID, slicePhotoID")
    print("  3. Вставь в колонки AB, AC, AD в Google Таблице (по строкам товаров)")


if __name__ == "__main__":
    main()
