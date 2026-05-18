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

# 1b. Regenerate rich product pages (RU + EN) with gallery, SEO, Cloudinary images.
# sync-sheets.mjs writes simple single-image pages; gen-ru/en-products.py override
# them with the full gallery (imageMain + imagePack + imageSlice thumbnails).
python3 scripts/gen-ru-products.py 2>&1 || echo "[warn] gen-ru-products.py failed; keeping previous files"
python3 scripts/gen-en-products.py 2>&1 || echo "[warn] gen-en-products.py failed; keeping previous files"

# 1c. Regenerate rich llms.txt for RU and EN (overrides the thin one
# that sync-sheets.mjs writes). This keeps AI crawlers fed with full
# context on every cron tick.
python3 scripts/gen-llms-full.py 2>&1 || echo "[warn] gen-llms-full.py failed; keeping previous files"

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

# 4. GMC + OpenAI Commerce feeds (catalog in public/products.json is valid)
python3 scripts/gen-products-feed.py 2>&1 || echo "[warn] gen-products-feed failed (non-fatal)"
bash scripts/upload-openai-feed-sftp.sh 2>&1 || echo "[warn] OpenAI SFTP upload failed (non-fatal)"

# Опционально: llms, sitemap, IndexNow key для api.pepperoni.tatar
cp -f public/llms-full.txt public/sitemap.xml public/*.txt "$DATA_DIR/" 2>/dev/null || true
