#!/bin/bash
# Phase 2: VPS Data Node — атомарное обновление products.json
# Использование: sync-vps.sh (из /var/www/pepperoni/repo)
set -e

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${DATA_DIR:-/var/www/pepperoni/data}"
TMP_FILE="$DATA_DIR/products.json.tmp"
FINAL_FILE="$DATA_DIR/products.json"

mkdir -p "$DATA_DIR"

# 1. Sync пишет в repo/public/
cd "$REPO_DIR"
node scripts/sync-sheets.mjs

# 1b. Перегенерируем llms-full.txt расширенным Python-генератором
#     (Node-версия отдаёт усечённую таблицу; Python добавляет per-SKU карточки,
#     buyer-personas, FAQ и AIO-ответы — всего ~90 KB вместо 16 KB).
python3 scripts/gen-llms-full.py || echo "⚠️  gen-llms-full.py failed (non-fatal)"

# 2. Копируем во временный файл
cp -f public/products.json "$TMP_FILE"

# 3. Валидация JSON (jq)
if command -v jq &>/dev/null; then
  if jq -e . "$TMP_FILE" >/dev/null 2>&1; then
    mv "$TMP_FILE" "$FINAL_FILE"
    echo "[$(date -Iseconds)] Sync OK: $FINAL_FILE"
  else
    echo "[$(date -Iseconds)] Sync FAIL: Invalid JSON, keeping old file"
    rm -f "$TMP_FILE"
    exit 1
  fi
else
  # Без jq — просто mv (рекомендуется установить: apt install jq)
  mv "$TMP_FILE" "$FINAL_FILE"
  echo "[$(date -Iseconds)] Sync OK (no jq validation)"
fi

# Опционально: llms, sitemap, IndexNow key для api.pepperoni.tatar
cp -f public/llms-full.txt public/sitemap.xml public/*.txt "$DATA_DIR/" 2>/dev/null || true
