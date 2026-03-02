#!/bin/bash
# Cron: данные из Google Sheets → VPS data/. Без git pull (код доставляет GitHub Actions).
set -e

cd /var/www/pepperoni/repo

# 1. Генерируем данные и файлы
node scripts/sync-sheets.mjs

# 2. Атомарно переносим JSON
if [ -s public/products.json ]; then
    cp public/products.json /var/www/pepperoni/data/products.json.tmp
    mv /var/www/pepperoni/data/products.json.tmp /var/www/pepperoni/data/products.json
fi

# 3. Переносим ИИ-файлы и IndexNow key
cp -f public/*.txt /var/www/pepperoni/data/ 2>/dev/null || true
