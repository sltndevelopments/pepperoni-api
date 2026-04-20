#!/usr/bin/env python3
"""
Генерирует файл с новыми Cloudinary-ссылками (латиница вместо кириллицы).
Запуск: python3 scripts/generate-corrected-urls.py

Результат: docs/urls-for-google-sheet.csv — скопируй колонки MainPhoto, PackPhoto, SlicePhoto
в соответствующие колонки AB, AC, AD в Google Таблицу.
"""
import csv
import json
import os
import re
import urllib.parse

ROOT = os.path.join(os.path.dirname(__file__), "..")
PRODUCTS_JSON = os.path.join(ROOT, "public", "products.json")
OUTPUT_CSV = os.path.join(ROOT, "docs", "urls-for-google-sheet.csv")


def translit(text):
    """Тот же транслит, что в fix_names.py."""
    symbols = str.maketrans(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя ",
        "abvgdeezzijklmnoprstufhzcss_y_eua_",
    )
    return text.lower().translate(symbols)


def has_cyrillic(s):
    return bool(re.search(r"[а-яА-Я]", s))


def fix_cloudinary_url(url):
    """Заменяет кириллицу на латиницу в пути Cloudinary URL."""
    if not url or "cloudinary.com" not in url:
        return url
    try:
        # Находим часть после /upload/ — v12345/filename.jpg
        parts = url.split("/upload/", 1)
        if len(parts) != 2:
            return url
        rest = parts[1]
        m = re.search(r"(v\d+)/(.+)", rest)
        if not m:
            return url
        version, filename = m.group(1), m.group(2)
        # Декодируем URL-encoding
        filename_decoded = urllib.parse.unquote(filename)
        if not has_cyrillic(filename_decoded):
            return url
        # Транслит: отделяем расширение
        base, ext = os.path.splitext(filename_decoded)
        new_base = translit(base)
        new_filename = new_base + ext
        new_path = f"{version}/{urllib.parse.quote(new_filename)}"
        return parts[0] + "/upload/" + new_path
    except Exception:
        return url


def main():
    with open(PRODUCTS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    products = data.get("products", [])

    rows = [["sku", "name", "mainPhoto", "packPhoto", "slicePhoto"]]
    for p in products:
        main = fix_cloudinary_url(p.get("imageMain") or p.get("image") or "")
        pack = fix_cloudinary_url(p.get("imagePack") or "")
        slice_url = fix_cloudinary_url(p.get("imageSlice") or "")
        rows.append([p.get("sku", ""), p.get("name", ""), main, pack, slice_url])

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"✅ Сохранено: {OUTPUT_CSV}")
    print("\nКак использовать:")
    print("1. Открой файл в Excel или Google Sheets")
    print("2. Скопируй колонки mainPhoto, packPhoto, slicePhoto")
    print("3. Вставь в колонки AB, AC, AD в своей таблице (по строкам товаров)")


if __name__ == "__main__":
    main()
