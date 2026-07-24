#!/usr/bin/env python3
"""Гейт каталожных фото: products.json должен точно соответствовать
data/image_manifest.json, а каждый URL — отвечать HTTP 200.

Запуск: python3 scripts/check_catalog_images.py
Выход 1 = нарушение (не публиковать). Используется вручную/в CI после sync.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_KEYS = ("imageMain", "imagePack", "imageSlice")


def basename(url: str) -> str:
    if not url:
        return ""
    return urllib.parse.unquote(str(url).split("?")[0].rstrip("/").split("/")[-1]).lower()


def head_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "kd-image-gate/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def main() -> int:
    products = json.loads((ROOT / "public" / "products.json").read_text())["products"]
    manifest = json.loads((ROOT / "data" / "image_manifest.json").read_text())
    errors = []

    urls = set()
    for p in products:
        sku = p["sku"]
        pin = manifest.get(sku, "__missing__")
        actual = {k: p.get(k) or None for k in IMG_KEYS}

        if pin == "__missing__":
            errors.append(f"{sku}: отсутствует в image_manifest.json — закрепить фото или null")
        elif pin is None:
            got = [k for k, v in actual.items() if v]
            if got:
                errors.append(f"{sku}: закреплён «без фото», но в products.json есть {got}")
        else:
            for k in IMG_KEYS:
                want = pin.get(k) or None
                if (actual[k] or None) != want:
                    errors.append(f"{sku}.{k}: '{basename(actual[k])}' != манифест '{basename(want)}'")

        for k in IMG_KEYS:
            u = p.get(k)
            if not u:
                continue
            m = re.search(r"/products/kd-(\d{3})\.(?:jpe?g|png|webp)$", u, re.I)
            if m and f"KD-{m.group(1)}" != sku:
                errors.append(f"{sku}.{k}: чужой файл kd-{m.group(1)} (перепутанная нумерация)")
            urls.add(u)

    with ThreadPoolExecutor(max_workers=16) as ex:
        for u, ok in zip(urls, ex.map(head_ok, urls)):
            if not ok:
                errors.append(f"HTTP не-200: {u}")

    no_photo = sorted(p["sku"] for p in products if not any(p.get(k) for k in IMG_KEYS))
    print(f"Проверено: {len(products)} SKU, {len(urls)} уникальных URL")
    if no_photo:
        print(f"Без фото (плейсхолдер, ок по манифесту): {len(no_photo)}: {', '.join(no_photo)}")
    if errors:
        print(f"\nНАРУШЕНИЯ ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print("OK: фото каталога соответствуют манифесту, все URL живые")
    return 0


if __name__ == "__main__":
    sys.exit(main())
