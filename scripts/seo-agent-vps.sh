#!/usr/bin/env bash
# =============================================================
# SEO Agent for pepperoni.tatar — VPS version
# Runs daily at 08:30 MSK via cron on 37.9.4.101
#
# Loads secrets from /var/www/pepperoni/seo-agent.env
# (written by deploy-vps.yml GitHub Actions workflow)
# =============================================================

set -euo pipefail

REPO_DIR="/var/www/pepperoni/repo"
ENV_FILE="/var/www/pepperoni/seo-agent.env"
LOG_DIR="$REPO_DIR/data/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/agent-$(date +%Y%m%d-%H%M%S).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Load secrets from env file
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    # GSC key is base64-encoded (JSON contains newlines/spaces that break shell vars)
    if [ -n "${GSC_SERVICE_ACCOUNT_KEY_B64:-}" ]; then
        export GSC_SERVICE_ACCOUNT_KEY
        GSC_SERVICE_ACCOUNT_KEY=$(echo "$GSC_SERVICE_ACCOUNT_KEY_B64" | base64 -d)
    fi
    log "✅ Env loaded from $ENV_FILE"
else
    log "⚠️  $ENV_FILE not found — secrets missing"
fi

cd "$REPO_DIR"
log "=== SEO Agent started ==="

# ---- Step 1: Fetch GSC data ----
log "Step 1: Fetching GSC queries …"
python3 scripts/fetch_gsc_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  GSC fetch failed (non-fatal)"

# ---- Step 2: Fetch Yandex data ----
log "Step 2: Fetching Yandex queries …"
python3 scripts/fetch_yandex_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  Yandex fetch failed (non-fatal)"

# ---- Step 3: Analyze ----
log "Step 3: Analyzing opportunities …"
python3 scripts/analyze_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  Analyze failed (non-fatal)"

# ---- Step 4: Generate content via Claude API ----
log "Step 4: Generating content …"
python3 scripts/generate_content.py >> "$LOG_FILE" 2>&1 || log "⚠️  Content generation failed (non-fatal)"

# ---- Step 5: Trigger GitHub Actions deploy via API ----
# New/updated HTML files are in /var/www/pepperoni/repo/public/ — trigger a deploy
# GitHub Actions handles git commit + publish via seo-agent.yml workflow_dispatch
log "Step 5: Triggering GitHub Actions deploy …"
GITHUB_REPO="sltndevelopments/pepperoni-api"
GITHUB_WORKFLOW="seo-agent.yml"
# Only trigger if new files were generated (check for recently modified HTML)
NEW_FILES=$(find public/geo public/blog -name "*.html" -newer data/.last_run 2>/dev/null | wc -l || echo 0)
if [ "$NEW_FILES" -gt 0 ]; then
    log "  $NEW_FILES new HTML files found — triggering GitHub Actions …"
    # Use GitHub API to dispatch seo-agent workflow (it will commit generated files)
    # Requires GITHUB_TOKEN in env (set via repo secret or PAT)
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        curl -s -X POST \
          -H "Authorization: token $GITHUB_TOKEN" \
          -H "Accept: application/vnd.github.v3+json" \
          "https://api.github.com/repos/$GITHUB_REPO/actions/workflows/$GITHUB_WORKFLOW/dispatches" \
          -d '{"ref":"main"}' && log "  ✅ Workflow dispatched" || log "  ⚠️  Workflow dispatch failed"
    else
        log "  ℹ️  GITHUB_TOKEN not set, skipping dispatch"
    fi
else
    log "  ℹ️  No new content generated"
fi
touch data/.last_run 2>/dev/null || true

# ---- Step 6: GSC indexing ----
log "Step 6: Submitting URLs to Google …"
python3 scripts/gsc-index.py >> "$LOG_FILE" 2>&1 || log "⚠️  GSC indexing failed (non-fatal)"

# ---- Step 7: Yandex indexing ----
log "Step 7: Submitting URLs to Yandex …"
python3 scripts/yandex-index.py >> "$LOG_FILE" 2>&1 || log "⚠️  Yandex indexing failed (non-fatal)"

# ---- Step 8: Daily report ----
log "Step 8: Sending daily report …"
python3 scripts/send_report.py >> "$LOG_FILE" 2>&1 || log "⚠️  Report failed (non-fatal)"

# ---- Rotate old logs (keep 30 days) ----
find "$LOG_DIR" -name "agent-*.log" -mtime +30 -delete 2>/dev/null || true

log "=== SEO Agent finished ==="
