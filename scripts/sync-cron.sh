#!/bin/bash
# Cron: данные из Google Sheets → VPS data/. Без git pull (код доставляет GitHub Actions).
set -e

cd /var/www/pepperoni/repo

# 1. Генерируем данные и файлы
node scripts/sync-sheets.mjs

# 1b. Генерируем богатые страницы товаров с галереей (переопределяют простые страницы от sync-sheets.mjs)
python3 scripts/gen-ru-products.py 2>&1 || echo "[warn] gen-ru-products.py failed"
python3 scripts/gen-en-products.py 2>&1 || echo "[warn] gen-en-products.py failed"

# 2. Атомарно переносим JSON
if [ -s public/products.json ]; then
    cp public/products.json /var/www/pepperoni/data/products.json.tmp
    mv /var/www/pepperoni/data/products.json.tmp /var/www/pepperoni/data/products.json
fi

# 3. Переносим ИИ-файлы и IndexNow key
cp -f public/*.txt /var/www/pepperoni/data/ 2>/dev/null || true
