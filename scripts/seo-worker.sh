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

# Single-instance lock so overlapping cron ticks don't pile up.
LOCK="/tmp/seo-worker.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    log "Another worker is running — skip this tick."
    exit 0
fi

# Load secrets
if [ -f "$ENV_FILE" ]; then
    eval "$(python3 - "$ENV_FILE" << 'PYEOF'
import sys
with open(sys.argv[1]) as f:
    for line in f:
        line = line.rstrip('\n')
        if '=' not in line or line.startswith('#'):
            continue
        key, val = line.split('=', 1)
        val_escaped = val.strip().replace("'", "'\\''")
        print(f"export {key.strip()}='{val_escaped}'")
PYEOF
)"
fi

cd "$REPO_DIR"
log "=== SEO Worker tick ==="

# Per-tick budget (small; brain sets geo_daily_target, here we cap per tick)
GEO_PER_TICK="${GEO_PER_TICK:-30}"

log "Generating geo pages (strategy-driven, up to $GEO_PER_TICK) …"
MAX_GEO_PAGES="$GEO_PER_TICK" GEO_WORKERS="${GEO_WORKERS:-4}" \
    python3 scripts/generate_geo_bulk.py --mode all --max-pages "$GEO_PER_TICK" \
    >> "$LOG_FILE" 2>&1 || log "⚠️  geo bulk failed (non-fatal)"

log "Executing blog / Private-Label strategy …"
python3 scripts/generate_from_strategy.py >> "$LOG_FILE" 2>&1 || log "⚠️  strategy exec failed (non-fatal)"

# Commit & push whatever was produced
shopt -s nullglob
STAGE=(public/geo/*.html public/*/geo/*.html public/blog/*.html public/*/blog/*.html public/private-label/*.html public/*/private-label/*.html public/sitemap.xml)
shopt -u nullglob
[ ${#STAGE[@]} -gt 0 ] && git add "${STAGE[@]}" 2>/dev/null || true

if ! git diff --cached --quiet 2>/dev/null; then
    CHANGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
    git commit -q -m "chore(seo-worker): +$CHANGED pages $(date '+%H:%M')" >> "$LOG_FILE" 2>&1 || true
    git pull --rebase --autostash --quiet origin main >> "$LOG_FILE" 2>&1 || log "  ⚠️ rebase issue"
    if git push --quiet origin HEAD:main >> "$LOG_FILE" 2>&1; then
        log "  ✅ pushed $CHANGED files"
    else
        log "  ⚠️ push failed"
    fi
else
    log "  ℹ️ nothing new this tick"
fi

log "=== Worker tick done ==="
