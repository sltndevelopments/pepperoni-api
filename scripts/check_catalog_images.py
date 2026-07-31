#!/usr/bin/env python3
"""Гейт каталожных фото.

Схема: Google Sheets (источник правды) → sync валидирует ссылки и снапшотит
принятые в data/image_manifest.json → sync зеркалирует файлы с Cloudinary в
public/images/products/ (same-origin: Cloudinary за Cloudflare недоступен части
РФ-провайдеров) → products.json отдаёт ссылки pepperoni.tatar/images/products/.

Проверяем:
  - каждое поле в products.json — same-origin зеркало, и файл лежит локально;
  - зеркало собрано из того же источника, что в манифесте (image_mirror.json);
  - исходники в манифесте живые (HTTP 200) и не ссылаются на чужой kd-NNN.

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
MIRROR_DIR = ROOT / "public" / "images" / "products"
MIRROR_PREFIX = "https://pepperoni.tatar/images/products/"
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
    try:
        mirror_map = json.loads((ROOT / "data" / "image_mirror.json").read_text())
    except Exception:
        mirror_map = {}
    errors = []
    source_urls = set()

    for p in products:
        sku = p["sku"]
        pin = manifest.get(sku)
        if isinstance(pin, dict):
            for k in IMG_KEYS:
                src = pin.get(k)
                if not src:
                    continue
                source_urls.add(src)
                m = re.search(r"/products/kd-(\d{3})\.(?:jpe?g|png|webp)$", src, re.I)
                if m and f"KD-{m.group(1)}" != sku:
                    errors.append(f"{sku}.{k} (источник): чужой файл kd-{m.group(1)} (старая нумерация)")

        for k in IMG_KEYS:
            u = p.get(k)
            if not u:
                if isinstance(pin, dict) and pin.get(k):
                    errors.append(f"{sku}.{k}: в манифесте есть источник, в products.json пусто — прогнать sync")
                continue
            if u.startswith(MIRROR_PREFIX):
                fname = basename(u)
                f = MIRROR_DIR / fname
                if not f.is_file() or f.stat().st_size < 1000:
                    errors.append(f"{sku}.{k}: зеркало {fname} отсутствует/битое в public/images/products/")
                src = mirror_map.get(fname) or ""
                # Кэш-ключ зеркала: "wm1|<cloudinary-url>" (версия трансформа) или голый URL.
                if "|" in src:
                    src = src.split("|", 1)[1]
                want = (pin or {}).get(k) if isinstance(pin, dict) else None
                if want and src and src != want:
                    errors.append(f"{sku}.{k}: зеркало {fname} собрано из '{basename(src)}', а в манифесте '{basename(want)}'")
            elif u.startswith("https://res.cloudinary.com/"):
                errors.append(f"{sku}.{k}: не зазеркалено, отдаётся Cloudinary напрямую ({basename(u)}) — часть РФ не увидит")
            else:
                errors.append(f"{sku}.{k}: неожиданный URL {u[:80]}")

    with ThreadPoolExecutor(max_workers=16) as ex:
        for u, ok in zip(source_urls, ex.map(head_ok, source_urls)):
            if not ok:
                errors.append(f"Источник не отвечает 200: {u}")

    no_photo = sorted(p["sku"] for p in products if not any(p.get(k) for k in IMG_KEYS))
    print(f"Проверено: {len(products)} SKU, {len(source_urls)} исходников на Cloudinary")
    if no_photo:
        print(f"Без фото (плейсхолдер): {len(no_photo)}: {', '.join(no_photo)}")
    if errors:
        print(f"\nНАРУШЕНИЯ ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print("OK: все фото зазеркалены на pepperoni.tatar, исходники живые")
    return 0


if __name__ == "__main__":
    sys.exit(main())
