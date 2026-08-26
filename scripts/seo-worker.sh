#!/usr/bin/env bash
# =============================================================
# SEO WORKER (HANDS) for pepperoni.tatar — runs frequently (e.g. every 2h)
# Cheap DeepSeek-only loop: generates pages per the brain's strategy.json,
# commits & pushes. NO Opus, NO GSC fetch, NO indexing (those are daily).
# =============================================================
set -euo pipefail

REPO_DIR="/var/www/pepperoni/repo"
ENV_FILE="/var/www/pepperoni/seo-agent.env"
LOG_DIR="$REPO_DIR/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/worker-$(date +%Y%m%d-%H%M%S).log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

TICK_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PUSHED=0

# Single-instance lock so overlapping cron ticks don't pile up.
LOCK="/tmp/seo-worker.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    log "Another worker is running — skip this tick."
    exit 0
fi

cd "$REPO_DIR"
log "=== SEO Worker tick ==="
log "⏸ autonomous page generation retired by SEO trust reset"
log "Catalog sync, measurement and deterministic QA run through the daily pipeline."
log "=== Worker tick done (no mutation) ==="
exit 0
