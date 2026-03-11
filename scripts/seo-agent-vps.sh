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

# Pull latest code from git (deploy already does rsync, but ensure data is fresh)
git pull origin main --quiet 2>/dev/null || log "⚠️  git pull failed (non-fatal)"

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

# ---- Step 5: Git commit & push ----
log "Step 5: Committing generated content …"
git config user.email "seo-agent@pepperoni.tatar"
git config user.name  "SEO Agent"
git add public/geo/*.html public/blog/*.html public/sitemap.xml 2>/dev/null || true
git add public/index.html public/pepperoni.html public/en/index.html 2>/dev/null || true

if ! git diff --cached --quiet; then
    git commit -m "chore(seo): auto-update by SEO agent $(date +%Y-%m-%d)" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    log "✅ Pushed new content to GitHub"
else
    log "ℹ️  No new content generated"
fi

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
