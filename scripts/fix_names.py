#!/usr/bin/env python3
"""
Массовое переименование Cloudinary-файлов с кириллицей в латиницу.
Требует: CLOUDINARY_API_KEY и CLOUDINARY_API_SECRET в окружении.

Запуск:
  export CLOUDINARY_API_KEY=362485142348652
  export CLOUDINARY_API_SECRET=твой_секрет
  python3 scripts/fix_names.py

Опционально: --dry-run — только показать, не менять.
"""
import os
import re
import sys

try:
    import cloudinary
    import cloudinary.api
    import cloudinary.uploader
except ImportError:
    print("Установи: pip install cloudinary")
    sys.exit(1)

cloud_name = "duygfl3vz"


def translit(text):
    """Упрощённый транслит для имён файлов."""
    symbols = str.maketrans(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя ",
        "abvgdeezzijklmnoprstufhzcss_y_eua_",
    )
    return text.lower().translate(symbols)


def fix_all_images():
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    if not api_key or not api_secret:
        print("Ошибка: задай CLOUDINARY_API_KEY и CLOUDINARY_API_SECRET в окружении.")
        sys.exit(1)

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
    )

    dry_run = "--dry-run" in sys.argv
    log_file = os.path.join(os.path.dirname(__file__), "..", "docs", "cloudinary-rename-log.txt")
    renames = []  # для сохранения в файл
    print("--- Поиск файлов с кириллицей ---")

    next_cursor = None
    total = 0
    while True:
        kwargs = {"type": "upload", "max_results": 500}
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        resources = cloudinary.api.resources(**kwargs)

        for res in resources.get("resources", []):
            old_id = res["public_id"]
            if re.search(r"[а-яА-Я]", old_id):
                new_id = translit(old_id)
                renames.append((old_id, new_id))
                print(f"Переименую: {old_id} -> {new_id}")
                total += 1
                if not dry_run:
                    try:
                        cloudinary.uploader.rename(old_id, new_id)
                        print("  Успешно!")
                    except Exception as e:
                        print(f"  Ошибка: {e}")

        next_cursor = resources.get("next_cursor")
        if not next_cursor:
            break

    if total == 0:
        print("Файлов с кириллицей не найдено.")
    elif dry_run:
        print(f"\nРежим --dry-run: найдено {total} файлов, изменения не применены.")

    if renames:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("# Старое имя -> Новое имя\n# Используй для обновления Google Таблицы\n\n")
            for old_id, new_id in renames:
                f.write(f"{old_id}\t->\t{new_id}\n")
        print(f"\nСписок сохранён в {log_file}")


if __name__ == "__main__":
    fix_all_images()
