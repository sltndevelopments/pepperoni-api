#!/usr/bin/env bash
# =============================================================
# SEO Agent for pepperoni.tatar
# Runs daily at 08:30 MSK on VPS (37.9.4.101) OR via GitHub Actions
#
# Flow:
#   1. fetch_gsc_queries.py     — pull data from Google Search Console
#   2. fetch_yandex_queries.py  — pull data from Yandex Webmaster
#   3. analyze_queries.py       — find opportunities in DB
#   4. generate_content.py      — write new pages / update titles via Claude API
#   5. git commit + push        — auto-deploy new content
#   6. gsc-index.py             — submit new URLs to Google Indexing API
#   7. yandex-index.py          — submit new URLs to Yandex
#   8. send_report.py           — email daily summary
# =============================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/agent-$(date +%Y%m%d-%H%M%S).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

cd "$REPO_DIR"
log "=== SEO Agent started ==="
log "Repo: $REPO_DIR"

# ---- Step 1: Fetch GSC data ----
log "Step 1: Fetching GSC queries …"
python3 scripts/fetch_gsc_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  GSC fetch failed (non-fatal)"

# ---- Step 2: Fetch Yandex data ----
log "Step 2: Fetching Yandex queries …"
python3 scripts/fetch_yandex_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  Yandex fetch failed (non-fatal)"

# ---- Step 3: Analyze ----
log "Step 3: Analyzing opportunities …"
python3 scripts/analyze_queries.py >> "$LOG_FILE" 2>&1

# ---- Step 4: Generate content ----
log "Step 4: Generating content via Claude API …"
python3 scripts/generate_content.py >> "$LOG_FILE" 2>&1 || log "⚠️  Content generation failed (non-fatal)"

# ---- Step 5: Git commit & push ----
log "Step 5: Committing generated content …"
git add public/geo/*.html public/blog/*.html public/index.html public/pepperoni.html 2>/dev/null || true
git add public/en/index.html public/sitemap.xml 2>/dev/null || true

if ! git diff --cached --quiet; then
    git config user.email "seo-agent@pepperoni.tatar"
    git config user.name  "SEO Agent"
    git commit -m "chore(seo): auto-update by SEO agent $(date +%Y-%m-%d)" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    log "✅ Pushed new content"
else
    log "ℹ️  No changes to commit"
fi

# ---- Step 6: GSC indexing ----
log "Step 6: Submitting URLs to Google …"
python3 scripts/gsc-index.py >> "$LOG_FILE" 2>&1 || log "⚠️  GSC indexing failed (non-fatal)"

# ---- Step 7: Yandex indexing ----
log "Step 7: Submitting URLs to Yandex …"
python3 scripts/yandex-index.py >> "$LOG_FILE" 2>&1 || log "⚠️  Yandex indexing failed (non-fatal)"

# ---- Step 8: Send report ----
log "Step 8: Sending daily report …"
python3 scripts/send_report.py >> "$LOG_FILE" 2>&1 || log "⚠️  Report failed (non-fatal)"

log "=== SEO Agent finished ==="
