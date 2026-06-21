#!/usr/bin/env python3
"""
Загрузка фотографий товаров на Cloudinary и обновление products.json.

Использование:
  # 1. Только показать сопоставление (без загрузки):
  python3 scripts/upload_photos.py --dry-run

  # 2. Загрузить и обновить products.json:
  CLOUDINARY_API_KEY=xxx CLOUDINARY_API_SECRET=yyy python3 scripts/upload_photos.py

  # 3. Только конкретный SKU:
  CLOUDINARY_API_KEY=xxx CLOUDINARY_API_SECRET=yyy python3 scripts/upload_photos.py --sku KD-038

Cloud name: duygfl3vz (захардкожен — это публичный идентификатор, не секрет)
"""
import os
import re
import json
import sys
import argparse
from pathlib import Path

CLOUD_NAME = "duygfl3vz"
REPO_ROOT = Path(__file__).parent.parent
PRODUCTS_JSON = REPO_ROOT / "public" / "products.json"

PHOTO_DIRS = [
    Path("/Users/rinatsultan/Desktop/1 - КД/ФОТО 2026 Колбасная продукция "),
    Path("/Users/rinatsultan/Desktop/2026 Выпечка "),
]

# Ключевые слова для определения типа фото по имени файла
SLICE_KEYWORDS = ["разрез", "нарезка", "срез", "slice"]
PACK_KEYWORDS  = ["упаковка", "pack", "в упаковке", "упак"]


# ─── Маппинг: ключевые слова → SKU + поле ───────────────────────────────────
# Порядок важен: более специфичные паттерны — первыми.
MAPPING = [
    # Котлеты
    {"sku": "KD-008", "field": "imagePack",  "keywords": ["котлета готовая", "котлеты из говядины готов"]},
    {"sku": "KD-008", "field": "imageSlice", "keywords": ["котлета сырая"]},
    {"sku": "KD-009", "field": "imagePack",  "keywords": ["котлета готовая"]},
    {"sku": "KD-009", "field": "imageSlice", "keywords": ["котлета сырая"]},

    # Ветчина из Курицы
    {"sku": "KD-010", "field": "imagePack",  "keywords": ["куриная ветчина", "ветчина из курицы"]},
    {"sku": "KD-010", "field": "imageSlice", "keywords": ["куриная грудка в разрезе"]},
    {"sku": "KD-011", "field": "imagePack",  "keywords": ["куриная ветчина", "ветчина из курицы"]},
    {"sku": "KD-011", "field": "imageSlice", "keywords": ["куриная грудка в разрезе"]},

    # Ветчина из Индейки
    {"sku": "KD-012", "field": "imagePack",  "keywords": ["полукопченая из индейки"]},
    {"sku": "KD-012", "field": "imageSlice", "keywords": ["карпаччо из индейки без упаковки"]},
    {"sku": "KD-013", "field": "imagePack",  "keywords": ["полукопченая из индейки"]},
    {"sku": "KD-013", "field": "imageSlice", "keywords": ["карпаччо из индейки без упаковки"]},

    # Пепперони
    {"sku": "KD-014", "field": "imagePack",  "keywords": ["пепперони цельная", "пепперони.jpg"]},
    {"sku": "KD-014", "field": "imageSlice", "keywords": ["пепперони в разрезе"]},

    # Куриное филе, фарш (нет подходящих разрезов — берём лучшее)
    {"sku": "KD-020", "field": "imagePack",  "keywords": ["куриная грудка.jpg", "куриная грудка 1.jpg"]},
    {"sku": "KD-021", "field": "imagePack",  "keywords": ["котлета сырая.jpg"]},
    {"sku": "KD-022", "field": "imagePack",  "keywords": ["котлета сырая.jpg"]},
    {"sku": "KD-023", "field": "imagePack",  "keywords": ["куриная грудка.jpg"]},
    {"sku": "KD-024", "field": "imagePack",  "keywords": ["куриная грудка.jpg"]},
    {"sku": "KD-025", "field": "imagePack",  "keywords": ["котлеты из говядины.jpg"]},

    # Сосиски казанские с молоком (imageSlice)
    {"sku": "KD-029", "field": "imageSlice", "keywords": ["сосиски казанские молочные"]},

    # Сосиски Сочные
    {"sku": "KD-033", "field": "imagePack",  "keywords": ["сосиски казанские сочные", "казанские сочные.jpg"]},

    # Вареные колбасы
    {"sku": "KD-035", "field": "imagePack",  "keywords": ["колбаса вареная из говядины"]},
    {"sku": "KD-035", "field": "imageSlice", "keywords": ["колбаса вареная из говядины"]},
    {"sku": "KD-036", "field": "imagePack",  "keywords": ["нежная классик", "нежная ск"]},
    {"sku": "KD-036", "field": "imageSlice", "keywords": ["нежная классик"]},
    {"sku": "KD-037", "field": "imagePack",  "keywords": ["нежная классик", "нежная ск"]},
    {"sku": "KD-037", "field": "imageSlice", "keywords": ["нежная классик"]},

    # Ветчина из Индейки (охл.)
    {"sku": "KD-038", "field": "imagePack",  "keywords": ["полукопченая из индейки"]},

    # Ветчина Мраморная
    {"sku": "KD-039", "field": "imagePack",  "keywords": ["мраморная говяжья ветчина", "ветчина мраморная"]},

    # Ветчина из Курицы (охл.)
    {"sku": "KD-040", "field": "imagePack",  "keywords": ["куриная ветчина", "ветчина из курицы"]},

    # Ветчина Филейная
    {"sku": "KD-041", "field": "imagePack",  "keywords": ["ветчина филейная"]},

    # Сервелат Ханский
    {"sku": "KD-042", "field": "imagePack",  "keywords": ["сервелат ханский"]},
    {"sku": "KD-042", "field": "imageSlice", "keywords": ["татарский сервелат все виды нарезки"]},

    # Сервелат по-татарски
    {"sku": "KD-043", "field": "imagePack",  "keywords": ["сервелат по-татарски"]},
    {"sku": "KD-043", "field": "imageSlice", "keywords": ["сервелат по-татарски"]},

    # Полукопченые
    {"sku": "KD-044", "field": "imagePack",  "keywords": ["колбаса полукопченая из индейки"]},
    {"sku": "KD-044", "field": "imageSlice", "keywords": ["полукопченая из индейки"]},
    {"sku": "KD-045", "field": "imagePack",  "keywords": ["колбаса полукопченая из говядины"]},
    {"sku": "KD-045", "field": "imageSlice", "keywords": ["полукопченая из говядины"]},

    # Грудка куриная
    {"sku": "KD-047", "field": "imagePack",  "keywords": ["куриная грудка.jpg"]},
    {"sku": "KD-047", "field": "imageSlice", "keywords": ["куриная грудка в разрезе"]},
    {"sku": "KD-048", "field": "imagePack",  "keywords": ["куриная грудка.jpg"]},
    {"sku": "KD-048", "field": "imageSlice", "keywords": ["куриная грудка в разрезе"]},

    # в/к Рамазан
    {"sku": "KD-049", "field": "imagePack",  "keywords": ["колбаса варено-копченая рамазан", "рамазан .jpg"]},

    # в/к Мраморная
    {"sku": "KD-051", "field": "imagePack",  "keywords": ["колбаса варено-копченая мраморная", "мраморная 1.0.jpg"]},

    # в/к Филейный
    {"sku": "KD-053", "field": "imagePack",  "keywords": ["сервелат варено-копченый филейный"]},
    {"sku": "KD-053", "field": "imageSlice", "keywords": ["сервелат филейный все виды нарезки"]},
    {"sku": "KD-054", "field": "imagePack",  "keywords": ["сервелат варено-копченый филейный"]},
    {"sku": "KD-054", "field": "imageSlice", "keywords": ["сервелат филейный все виды нарезки"]},

    # в/к Княжеская
    {"sku": "KD-055", "field": "imageSlice", "keywords": ["княжеская все виды нарезки"]},
    {"sku": "KD-056", "field": "imageSlice", "keywords": ["княжеская все виды нарезки"]},

    # Выпечка — Самса с курицей
    {"sku": "KD-062", "field": "imagePack",  "keywords": ["самса с курицей 1.0"]},

    # Чак-чак
    {"sku": "KD-066", "field": "imagePack",  "keywords": ["чак чак без упаковки.jpg", "чак чак без упаковки 1.jpg"]},
    {"sku": "KD-066", "field": "imageSlice", "keywords": ["чак чак 1.0.jpg"]},
]


def collect_photos():
    """Собрать все фото из обеих папок → {нижний_регистр_имени_NFC: Path}
    macOS хранит имена файлов в NFD (decomposed Unicode), нормализуем в NFC.
    """
    import unicodedata
    photos = {}
    for d in PHOTO_DIRS:
        if not d.exists():
            print(f"WARN: папка не найдена: {d}")
            continue
        for f in d.iterdir():
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                nfc_name = unicodedata.normalize("NFC", f.name).lower()
                photos[nfc_name] = f
    return photos


def find_photo_for(keywords, photos):
    """Найти первое фото, имя которого содержит любой из keywords."""
    kw_lower = [k.lower() for k in keywords]
    for kw in kw_lower:
        # точное совпадение по имени файла
        if kw in photos:
            return photos[kw]
        # частичное
        for name, path in photos.items():
            if kw in name:
                return path
    return None


def transliterate(text):
    CYR = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e",
           "ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m",
           "н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u",
           "ф":"f","х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch",
           "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"}
    result = []
    for c in text.lower():
        if c in CYR:
            result.append(CYR[c])
        elif c.isalnum() or c == "_":
            result.append(c)
        elif c in " -":
            result.append("_")
    return re.sub(r"_+", "_", "".join(result)).strip("_")


def make_public_id(sku, field):
    field_map = {"imagePack": "pack", "imageSlice": "slice", "imageMain": "main"}
    return f"pepperoni/{sku.lower()}_{field_map.get(field, field)}"


def upload_to_cloudinary(filepath, public_id, api_key, api_secret):
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        print("Установи: pip install cloudinary")
        sys.exit(1)

    cloudinary.config(cloud_name=CLOUD_NAME, api_key=api_key, api_secret=api_secret)
    result = cloudinary.uploader.upload(
        str(filepath),
        public_id=public_id,
        overwrite=True,
        resource_type="image",
    )
    return result["secure_url"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Только показать план, не загружать")
    parser.add_argument("--sku", help="Обработать только этот SKU (например KD-038)")
    args = parser.parse_args()

    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    if not args.dry_run and (not api_key or not api_secret):
        print("Ошибка: задай CLOUDINARY_API_KEY и CLOUDINARY_API_SECRET в окружении.")
        print("  export CLOUDINARY_API_KEY=ваш_ключ")
        print("  export CLOUDINARY_API_SECRET=ваш_секрет")
        print("Или запусти с --dry-run для предварительного просмотра.")
        sys.exit(1)

    # Загружаем products.json
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    products = data.get("products", data) if isinstance(data, dict) else data
    by_sku = {p["sku"]: p for p in products}

    photos = collect_photos()
    print(f"Найдено фотографий: {len(photos)}")
    print(f"Товаров в каталоге: {len(products)}")
    print()

    plan = []  # [(sku, field, photo_path, public_id)]
    for entry in MAPPING:
        sku = entry["sku"]
        if args.sku and sku != args.sku:
            continue
        field = entry["field"]
        product = by_sku.get(sku)
        if not product:
            print(f"WARN: SKU {sku} не найден в products.json")
            continue
        # Пропускаем если поле уже заполнено
        if product.get(field):
            continue
        photo = find_photo_for(entry["keywords"], photos)
        if photo:
            public_id = make_public_id(sku, field)
            plan.append((sku, field, photo, public_id))
        else:
            print(f"  ✗ {sku} {field}: фото не найдено (keywords: {entry['keywords']})")

    print(f"\nПлан загрузки: {len(plan)} фотографий\n")
    for sku, field, photo, public_id in plan:
        name = by_sku[sku]["name"][:45]
        print(f"  {sku} | {field:12} | {photo.name[:50]:55} → {public_id}")

    if args.dry_run:
        print("\n[--dry-run] Загрузка не выполнена.")
        return

    print("\nНачинаю загрузку...")
    uploaded = {}  # sku → {field: url}
    errors = []

    for sku, field, photo, public_id in plan:
        print(f"  Загружаю {sku} {field}: {photo.name[:50]}...", end=" ", flush=True)
        try:
            url = upload_to_cloudinary(photo, public_id, api_key, api_secret)
            print(f"OK → {url}")
            uploaded.setdefault(sku, {})[field] = url
        except Exception as e:
            print(f"ОШИБКА: {e}")
            errors.append((sku, field, str(e)))

    # Обновляем products.json
    if uploaded:
        for sku, fields in uploaded.items():
            product = by_sku.get(sku)
            if product:
                for field, url in fields.items():
                    product[field] = url

        PRODUCTS_JSON.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ products.json обновлён: {sum(len(v) for v in uploaded.values())} полей")

    if errors:
        print(f"\nОшибки ({len(errors)}):")
        for sku, field, err in errors:
            print(f"  {sku} {field}: {err}")
    else:
        print("✓ Ошибок нет.")


if __name__ == "__main__":
    main()
