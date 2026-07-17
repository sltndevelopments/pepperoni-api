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

# 1c. Reconcile hardcoded SKU-count text (manifest, about, faq, faq-ai, llm,
# rss, ai-plugin, mcp, .well-known/llms.txt) against live products.json BEFORE
# gen-llms-full — that step copies FAQ answers from faq.html into llms.txt.
# Assortment source of truth is Google Sheets only — do not edit counts by hand.
python3 scripts/reconcile_sku_count.py 2>&1 || echo "[warn] reconcile_sku_count.py failed; SKU-count text may be stale"

# 1d. Regenerate rich llms.txt for RU and EN (overrides the thin one
# that sync-sheets.mjs writes). Pulls live catalog + reconciled FAQ.
python3 scripts/gen-llms-full.py 2>&1 || echo "[warn] gen-llms-full.py failed; keeping previous files"

# 1d2. Rewrite stale whole-catalog counts (72/77/previous → live N) across
# blog/geo/segment HTML so adds/removes in Sheets stay reflected in prose.
python3 scripts/bulk_fix_stale_content.py --fix-sku-text 2>&1 || echo "[warn] bulk_fix_stale_content failed; SKU prose may be stale"

# 1e. Detect any remaining stale product-count mentions. Non-blocking —
# logs a warning for the SEO agent / a human to triage, doesn't fail the sync.
python3 scripts/check_stale_counts.py --check 2>&1 || echo "[warn] check_stale_counts.py found stale product-count mentions — see output above"

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
