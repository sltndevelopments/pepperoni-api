#!/usr/bin/env python3
"""
Переименование Cloudinary-файлов с кириллицей в транслит (латиницу).
Требует: CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET в окружении.
Cloud name: duygfl3vz (зашит в скрипт).

Запуск: python3 scripts/fix-cloudinary-names.py [--dry-run]
--dry-run: только показать что будет переименовано, не менять.
"""
import os
import re
import sys

# Транслитерация RU -> LA
CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
CYR_TO_LAT_U = {k.upper(): v.upper() if len(v) == 1 else v.capitalize() for k, v in CYR_TO_LAT.items()}
CYR_TO_LAT.update(CYR_TO_LAT_U)


def has_cyrillic(s):
    return bool(re.search(r"[\u0400-\u04FF]", s))


def transliterate(text):
    out = []
    for c in text:
        if c in CYR_TO_LAT:
            out.append(CYR_TO_LAT[c])
        elif c.isalnum() or c in "_-./":
            out.append(c)
        elif c == " ":
            out.append("_")
        # остальное пропускаем
    return "".join(out)


def main():
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")
    if not api_key or not api_secret:
        print("Ошибка: задай CLOUDINARY_API_KEY и CLOUDINARY_API_SECRET в окружении.")
        print("Пример: export CLOUDINARY_API_KEY=xxx && export CLOUDINARY_API_SECRET=yyy")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv

    try:
        import cloudinary
        from cloudinary import uploader
        from cloudinary import api
    except ImportError:
        print("Установи: pip install cloudinary")
        sys.exit(1)

    cloudinary.config(
        cloud_name="duygfl3vz",
        api_key=api_key,
        api_secret=api_secret,
    )

    to_rename = []
    next_cursor = None

    print("Сканирование Cloudinary...")
    while True:
        kwargs = {"max_results": 500, "type": "upload", "resource_type": "image"}
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        r = api.resources(**kwargs)
        for item in r.get("resources", []):
            pid = item.get("public_id", "")
            if has_cyrillic(pid):
                new_pid = transliterate(pid)
                if new_pid and new_pid != pid:
                    to_rename.append((pid, new_pid))
        next_cursor = r.get("next_cursor")
        if not next_cursor:
            break

    if not to_rename:
        print("Файлов с кириллицей не найдено.")
        return

    print(f"\nНайдено {len(to_rename)} файлов с кириллицей:\n")
    for old_id, new_id in to_rename:
        print(f"  {old_id}")
        print(f"  -> {new_id}\n")

    if dry_run:
        print("Режим --dry-run: изменения не применены.")
        print("Для реального переименования запусти без --dry-run.")
        return

    print("Переименование...")
    for old_id, new_id in to_rename:
        try:
            uploader.rename(old_id, new_id, invalidate=True)
            print(f"  OK: {old_id} -> {new_id}")
        except Exception as e:
            print(f"  Ошибка {old_id}: {e}")

    print("\nГотово. Обнови ссылки в Google Таблице по списку выше.")


if __name__ == "__main__":
    main()
