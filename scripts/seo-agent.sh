#!/usr/bin/env bash
# =============================================================
# Legacy measurement-only SEO Agent for pepperoni.tatar
#
# Flow:
#   1. fetch_gsc_queries.py     — pull data from Google Search Console
#   2. fetch_yandex_queries.py  — pull data from Yandex Webmaster
#   3. analyze_queries.py       — find opportunities in DB
#   4. send_report.py           — email daily summary
# Autonomous page generation and page commits were retired in the trust reset.
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

# ---- Step 4: Report (no page mutation) ----
log "Step 4: Autonomous page generation is disabled; sending measurement report …"
python3 scripts/send_report.py >> "$LOG_FILE" 2>&1 || log "⚠️  Report failed (non-fatal)"

log "=== SEO Agent finished ==="
