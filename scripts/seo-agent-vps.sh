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

# Hard daily spend cap (kill switch in claude_client.py). Once today's logged
# Anthropic cost crosses this, every LLM call raises BudgetExceeded so a runaway
# loop can't drain the balance like the 630-page run on 2026-06-10. Override in
# seo-agent.env; set to 0 to disable.
export LLM_DAILY_BUDGET_USD="${LLM_DAILY_BUDGET_USD:-5}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/agent-$(date +%Y%m%d-%H%M%S).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Load secrets from env file
# Use python to safely parse env (handles GSC multiline base64 value)
if [ -f "$ENV_FILE" ]; then
    eval "$(python3 - "$ENV_FILE" << 'PYEOF'
import sys, os, re

env_file = sys.argv[1]
with open(env_file) as f:
    for line in f:
        line = line.rstrip('\n')
        if '=' not in line or line.startswith('#'):
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()
        # shell-escape the value
        val_escaped = val.replace("'", "'\\''")
        print(f"export {key}='{val_escaped}'")
PYEOF
)"
    # GSC key is base64-encoded — decode to real JSON
    if [ -n "${GSC_SERVICE_ACCOUNT_KEY_B64:-}" ]; then
        export GSC_SERVICE_ACCOUNT_KEY
        GSC_SERVICE_ACCOUNT_KEY=$(echo "$GSC_SERVICE_ACCOUNT_KEY_B64" | base64 -d)
    fi
    log "✅ Env loaded from $ENV_FILE"
else
    log "⚠️  $ENV_FILE not found — secrets missing"
fi

cd "$REPO_DIR"

# ---- Step 0: Sync Asocks proxy (HTTP :9999, not SOCKS :443) ----
# Keeps ANTHROPIC_PROXY fresh from api.asocks.com before any LLM calls.
log "Step 0: Sync Asocks proxy …"
if python3 scripts/sync_asocks_proxy.py >> "$LOG_FILE" 2>&1; then
    export ANTHROPIC_PROXY="$(grep '^ANTHROPIC_PROXY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    export ANTHROPIC_PROXY_FALLBACK="$(grep '^ANTHROPIC_PROXY_FALLBACK=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    export ANTHROPIC_PROXIES="$(grep '^ANTHROPIC_PROXIES=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    log "✅ Asocks proxy synced"
else
    log "⚠️  Asocks sync failed — using existing ANTHROPIC_PROXY"
fi

log "=== SEO Agent started ==="

# ---- Step 1: Fetch GSC data ----
log "Step 1: Fetching GSC queries …"
python3 scripts/fetch_gsc_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  GSC fetch failed (non-fatal)"

# ---- Step 2: Fetch Yandex data ----
log "Step 2: Fetching Yandex queries …"
python3 scripts/fetch_yandex_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  Yandex fetch failed (non-fatal)"

# ---- Step 2.1: Fetch Yandex Metrika (behaviour + leads) — Fable's on-site eyes ----
log "Step 2.1: Fetching Yandex Metrika (visits/sources/leads) …"
python3 scripts/fetch_metrika.py >> "$LOG_FILE" 2>&1 || log "⚠️  Metrika fetch failed (non-fatal)"

# ---- Step 2.2: Lead listener + handoff routing (Orchestrator-Worker bus) ----
# Pull any fresh leads, then route them across the agent bus (commercial lead →
# Steve; cluster-matched lead → Fable). Finally escalate anything stuck.
log "Step 2.2: Lead listener + handoff routing …"
python3 scripts/lead_listener.py >> "$LOG_FILE" 2>&1 || log "⚠️  Lead listener failed (non-fatal)"
python3 scripts/handoff_rules.py >> "$LOG_FILE" 2>&1 || log "⚠️  Handoff routing failed (non-fatal)"
python3 scripts/agent_bus.py --escalate >> "$LOG_FILE" 2>&1 || true

# ---- Step 2.5: ANOMALY-GUARD — watch for sudden traffic/position drops ----
# Runs right after data fetch so a drop (algo update / breakage / deindex) fires
# an instant Telegram alert before anything else. Keeps a git-tracked baseline.
log "Step 2.5: Anomaly-Guard — checking for traffic/position drops …"
python3 scripts/anomaly_guard.py >> "$LOG_FILE" 2>&1 || log "⚠️  Anomaly-Guard failed (non-fatal)"

# ---- Step 2.6: ESCALATION — out-of-band brain re-plan on strong signals ----
# Scout runs before this (3.3) on the previous pass; reads its findings +
# experiments + anomaly to decide if Opus must replan NOW (cooldown+budget gated).
# If it escalates, the regular daily brain (3.5) is skipped to avoid double spend.
BRAIN_ESCALATED=0
log "Step 2.6: Escalation — checking for strong signals …"
# NB: escalate exits 10 as a *signal* (brain already ran). Under `set -e` a bare
# command with rc!=0 kills the whole pipeline, so capture rc via `||`.
ESC_RC=0
python3 scripts/escalate_brain.py >> "$LOG_FILE" 2>&1 || ESC_RC=$?
if [ "$ESC_RC" = "10" ]; then
    BRAIN_ESCALATED=1
    log "  ↳ brain escalated this pass (daily brain will be skipped)"
elif [ "$ESC_RC" != "0" ]; then
    log "⚠️  Escalation check failed (non-fatal, rc=$ESC_RC)"
fi

# ---- Step 3: Analyze ----
log "Step 3: Analyzing opportunities …"
python3 scripts/analyze_queries.py >> "$LOG_FILE" 2>&1 || log "⚠️  Analyze failed (non-fatal)"

# ---- Step 3.1: GOALS — scoreboard "distance to #1" for target queries ----
# Formalizes the mission: per target query, current position, trend and gap to
# #1. Feeds the brain digest and the Telegram «🎯 Цели» button.
log "Step 3.1: Goals — updating distance-to-#1 scoreboard …"
python3 scripts/goals_scoreboard.py >> "$LOG_FILE" 2>&1 || log "⚠️  Goals scoreboard failed (non-fatal)"

# ---- Step 3.14b: FIX LINKS — repair broken internal links (deterministic) ----
# Closes the "see → fix" loop: redirects geo/typo/lang-dup links to the right
# page, removes unrendered template placeholders, unwraps genuinely-dead links.
# Runs BEFORE site_health so the audit below reflects the repair.
log "Step 3.14b: Fix-links — repairing broken internal links …"
python3 scripts/fix_links.py >> "$LOG_FILE" 2>&1 || log "⚠️  Fix-links failed (non-fatal)"

# ---- Step 3.15: SITE HEALTH — technical audit (broken links, dup canonicals) ----
# Deterministic, no LLM. Feeds the brain digest so it fixes the broken
# foundation (8k+ broken links) BEFORE chasing new content.
log "Step 3.15: Site-health — technical audit …"
python3 scripts/site_health.py >> "$LOG_FILE" 2>&1 || log "⚠️  Site-health failed (non-fatal)"

# ---- Step 3.16: CORE WEB VITALS — page speed per template (self-gated 7d) ----
log "Step 3.16: Core Web Vitals — page-speed check …"
python3 scripts/core_web_vitals.py >> "$LOG_FILE" 2>&1 || log "⚠️  CWV failed (non-fatal)"

# ---- Step 3.2: MARKET PULSE — monthly live-web research of export markets ----
# Perplexity Agent API over the 15 target countries. Internally self-gated:
# exits instantly unless data/market_pulse.json is older than 28 days.
log "Step 3.2: Market pulse — monthly export-market research …"
python3 scripts/market_pulse.py >> "$LOG_FILE" 2>&1 || log "⚠️  Market pulse failed (non-fatal)"

# ---- Step 3.3: SCOUT — discover new/rising queries & coverage gaps ----
# Discovery only (no generation). Writes git-tracked findings the brain reads,
# queues high-value landing ideas for approval, and pings Telegram.
log "Step 3.3: Scout — discovering demand signals …"
python3 scripts/scout_seo.py >> "$LOG_FILE" 2>&1 || log "⚠️  Scout failed (non-fatal)"

# ---- Step 3.3b: OUTCOMES — grade past changes, auto-repair, hand misses to Fable ----
# Accountability loop: did each change actually move rankings? Resubmit
# not-indexed pages, queue failing pages for Fable. Runs BEFORE the brain so the
# strategy is forced to face its own misses (outcomes.failing in the digest).
log "Step 3.3b: Outcomes — grading results + auto-repair …"
python3 scripts/outcome_tracker.py >> "$LOG_FILE" 2>&1 || log "⚠️  Outcome tracker failed (non-fatal)"
python3 scripts/repair_outcomes.py >> "$LOG_FILE" 2>&1 || log "⚠️  Repair failed (non-fatal)"

# ---- Step 3.4: OPTIMIZER — measure past experiments, then optimize titles/meta ----
# Data-driven core: success = clicks, not page count. Measures matured
# experiments (auto-reverts regressions), then rewrites near-page-1 low-CTR
# titles. Runs BEFORE the brain so the strategy sees fresh optimizer results.
log "Step 3.4: Optimizer — measure matured experiments …"
python3 scripts/optimize_seo.py --measure >> "$LOG_FILE" 2>&1 || log "⚠️  Optimizer measure failed (non-fatal)"
log "Step 3.4: Optimizer — apply title/meta improvements …"
python3 scripts/optimize_seo.py --apply >> "$LOG_FILE" 2>&1 || log "⚠️  Optimizer apply failed (non-fatal)"

# ---- Step 3.45: LANDING-BUILDER — build pages approved in Telegram ----
# Closes the Scout→approval→page loop: only builds landings the owner approved.
log "Step 3.45: Landing-Builder — building approved landings …"
python3 scripts/build_landing.py >> "$LOG_FILE" 2>&1 || log "⚠️  Landing-Builder failed (non-fatal)"

# ---- Step 3.47: LINKER — semantic internal linking (blog↔landing↔OEM) ----
# Cheapest safe ranking lever. Idempotent: refreshes the "Читайте также" block.
# Runs after Landing-Builder so brand-new landings get linked in the same pass.
log "Step 3.47: Linker — refreshing internal links …"
python3 scripts/link_graph.py >> "$LOG_FILE" 2>&1 || log "⚠️  Linker failed (non-fatal)"

# ---- Step 3.48: COMPETITOR-SCOUT — weekly competitive intelligence (Mon) ----
# Finds queries where competitors outrank us (+ why, if a SERP key is set).
# Discovery only; the brain reads data/competitor_findings.json.
if [ "$(date +%u)" = "1" ]; then
    log "Step 3.48: Competitor-Scout — weekly competitive intelligence …"
    python3 scripts/competitor_scout.py >> "$LOG_FILE" 2>&1 || log "⚠️  Competitor-Scout failed (non-fatal)"

    # ---- Step 3.49: AIO-VISIBILITY — weekly AI-citability check (Mon) ----
    log "Step 3.49: AIO-Visibility — checking AI citability …"
    python3 scripts/aio_visibility.py >> "$LOG_FILE" 2>&1 || log "⚠️  AIO-Visibility failed (non-fatal)"
fi

# ---- Step 3.5: BRAIN — Opus decides strategy (once/day; budget-capped) ----
# Skipped if Step 2.6 already escalated the brain this pass (no double spend).
if [ "$BRAIN_ESCALATED" = "1" ]; then
    log "Step 3.5: Brain — skipped (already escalated in Step 2.6)"
else
    log "Step 3.5: Brain (Fable 5) planning strategy …"
    python3 scripts/seo_brain.py >> "$LOG_FILE" 2>&1 || log "⚠️  Brain failed (non-fatal)"
fi

# ---- Step 3.5b: TOOLSMITH — build & run tools the brain proposed for itself ----
# The brain can request its own analysis tools (propose_tools/run_tools in
# strategy.json); toolsmith generates them (model of the brain's choice) into
# scripts/brain_tools/ after a static safety scan, then runs requested ones
# read-only so their output feeds the NEXT brain digest (block "toolbox").
log "Step 3.5b: Toolsmith — building/running brain's self-made tools …"
python3 scripts/brain_toolsmith.py >> "$LOG_FILE" 2>&1 || log "⚠️  Toolsmith failed (non-fatal)"

# ---- Step 3.6: WORKER — execute the brain's strategy (closes the loop) ----
# Reads data/strategy.json and builds what Fable decided: blog topics,
# PL/OEM pages, rewrites. Without this step the strategy is dead paper.
log "Step 3.6: Worker — executing brain strategy …"
python3 scripts/generate_from_strategy.py >> "$LOG_FILE" 2>&1 || log "⚠️  Strategy worker failed (non-fatal)"

# ---- Step 3b: Clean up any stale temp files in public/ (should be zero, but guard) ----
find public/ -maxdepth 3 -name "tmp*.html" -delete 2>/dev/null || true
find public/ -maxdepth 3 -name "*.tmp" -delete 2>/dev/null || true
# Ensure data/tmp/ workspace exists for generators
mkdir -p data/tmp

# ---- Step 3c: Weekly tech-debt sweep (Sunday or FORCE_SWEEP=1) ----
# Deterministic only (fix_pages, fix_links, repair_truncated, rebuild_sitemap).
# Has its own fail-closed sanity check + rollback; does NOT run every 3h.
# canonical/priceRange/ar-pork are EXCLUDED (separate careful tasks).
if [ "$(date +%u)" = "7" ] || [ "${FORCE_SWEEP:-0}" = "1" ]; then
    log "Step 3c: Tech-debt sweep (weekly/forced) …"
    python3 scripts/tech_debt_sweep.py --run >> "$LOG_FILE" 2>&1
    SWEEP_RC=$?
    if [ $SWEEP_RC -eq 2 ]; then
        log "🚨 Sweep sanity FAILED — rolled back public/; check ledger emergency"
    elif [ $SWEEP_RC -ne 0 ]; then
        log "⚠️  Sweep exited with code $SWEEP_RC (non-fatal)"
    else
        log "✅ Sweep completed — stamp+commit+push handled by sweep itself"
    fi
fi

# ---- Step 4: Generate content via DeepSeek API ----
log "Step 4: Generating content …"
python3 scripts/generate_content.py >> "$LOG_FILE" 2>&1 || log "⚠️  Content generation failed (non-fatal)"

# ---- Step 4b: Bulk geo pages (full assortment × RU + CIS cities) ----
log "Step 4b: Generating bulk geo pages …"
MAX_GEO_PAGES="${MAX_GEO_PAGES:-20}" GEO_WORKERS="${GEO_WORKERS:-4}" \
    python3 scripts/generate_geo_bulk.py --mode coverage --max-pages "${MAX_GEO_PAGES:-20}" \
    >> "$LOG_FILE" 2>&1 || log "⚠️  Geo bulk generation failed (non-fatal)"

# ---- Step 4c: Schema enricher — Product JSON-LD merchant-listing fields ----
# Deterministic (no LLM): image/description/shipping/return on every freshly
# generated page, so GSC never sees missing Merchant-listing fields again.
log "Step 4c: Enriching Product schemas …"
python3 scripts/fix_schema.py >> "$LOG_FILE" 2>&1 || log "⚠️  Schema enricher failed (non-fatal)"

# ---- Step 4d: QA gate — deterministic brand-safety check on changed pages ----
# fix_pages repairs known LLM defects (phones/emails/fences/ar-pork) in place;
# qa_pages quarantines anything still broken so it NEVER reaches the site.
log "Step 4d: QA gate (fix + quarantine) …"
python3 scripts/fix_pages.py >> "$LOG_FILE" 2>&1 || log "⚠️  fix_pages failed (non-fatal)"
python3 scripts/qa_pages.py --quarantine >> "$LOG_FILE" 2>&1 || log "⚠️  qa_pages failed (non-fatal)"
# Product overrides QA (halal/structure) — report only, overrides are durable.
python3 scripts/qa_overrides.py >> "$LOG_FILE" 2>&1 || log "⚠️  qa_overrides found issues (see log)"

# ---- Step 4e: Gate summary → daily ledger (NOT direct Telegram) ----
# Counts go into ledger as a 'done' event — surfaced once per day in digest.
log "Step 4e: Gate summary → ledger …"
python3 - << 'GATE_SUMMARY_EOF' >> "$LOG_FILE" 2>&1 || log "⚠️  gate summary failed (non-fatal)"
import sys
sys.path.insert(0, "scripts")
try:
    import page_reviewer, daily_ledger
    s = page_reviewer.gate_summary()
    total = s["published"] + s["quarantined"] + s["held"]
    if total > 0:
        reasons = "; ".join(s["sample_reasons"][:2]) if s["sample_reasons"] else "—"
        msg = (f"Гейт страниц: ✅{s['published']} опубл / "
               f"🚧{s['quarantined']} карантин / "
               f"⏸{s['held']} удержано. "
               f"Причины: {reasons[:120]}")
        daily_ledger.append_event("done", msg)
        print(msg)
    else:
        print("gate: no new pages in last 25h")
except Exception as e:
    print(f"gate summary error: {e}")
GATE_SUMMARY_EOF

# ---- Step 5: Git commit & push generated content ----
log "Step 5: Committing and pushing generated content …"

# Pull remote changes BEFORE staging/committing so the agent builds on top
# of the latest main (picks up code fixes, invariants.json updates, etc.).
# --autostash tucks away any uncommitted working-tree files so the rebase
# does not abort on a dirty tree, then re-applies them after the rebase.
log "  git pull --rebase origin main …"
git pull --rebase --autostash origin main >> "$LOG_FILE" 2>&1 \
    && log "  ✅ Rebased on origin/main" \
    || log "  ⚠️  Rebase on pull failed — continuing (push may fail later)"

# Inject deploy-stamp into index.html BEFORE git add so the stamp lands in the
# commit and reaches the live site. .deploy_stamp is gitignored (local only).
python3 scripts/deploy_check.py --inject >> "$LOG_FILE" 2>&1 || log "⚠️  deploy stamp inject failed (non-fatal)"

# Stage any new/modified HTML in geo, blog, and key pages
git add public/geo/*.html public/en/geo/*.html public/blog/*.html public/en/blog/*.html 2>/dev/null || true
git add public/index.html public/pepperoni.html public/en/index.html public/sitemap.xml 2>/dev/null || true
# Optimizer edits title/meta across any existing page + its durable ledger.
git add -u 'public/**/*.html' 2>/dev/null || true
git add data/experiments.json 2>/dev/null || true
# Scout discovery state + approval queue (durable, git-tracked).
git add data/scout_state.json data/scout_findings.json data/approvals.json 2>/dev/null || true
# Landing-Builder output (approved landings) + sitemap.
git add public/landing/*.html 2>/dev/null || true
# Competitor-Scout weekly findings (durable, git-tracked).
git add data/competitor_findings.json 2>/dev/null || true
# Anomaly-Guard daily baseline time series (durable, git-tracked).
git add data/anomaly_baseline.json 2>/dev/null || true
# AIO-Visibility weekly citability ledger (durable, git-tracked).
git add data/aio_visibility.json 2>/dev/null || true
# Brain-escalation cooldown/state (durable, git-tracked).
git add data/escalation_state.json 2>/dev/null || true
# Brain strategy + goals scoreboard (durable: Actions/worker must see them too).
git add data/strategy.json data/goals.json 2>/dev/null || true
# Fable's long-term memory (principles/decisions/OKR/facts) — must persist.
git add data/fable_memory.json 2>/dev/null || true
# LLM cost telemetry + monthly market research (both feed the bot/brain).
git add data/llm_costs.json data/market_pulse.json 2>/dev/null || true
git add data/site_health.json data/cwv.json data/brain_questions.json 2>/dev/null || true
git add data/metrika.json 2>/dev/null || true
git add data/leads.json 2>/dev/null || true
git add data/agent_bus.json 2>/dev/null || true
git add data/outcomes.json data/scout_sent.json 2>/dev/null || true
git add data/fable_websearch.json 2>/dev/null || true
git add data/page_gate_log.json 2>/dev/null || true
# Brain's self-made tools registry + the generated tool scripts (durable).
git add data/brain_tools.json 2>/dev/null || true
git add 'scripts/brain_tools/*.py' 2>/dev/null || true
# Brain may have patched core agent code (with backups) — track both.
git add -u 'scripts/*.py' 2>/dev/null || true
git add data/agent_backups/*.bak 2>/dev/null || true
# Worker output (PL/OEM pages from strategy).
git add public/private-label/*.html 2>/dev/null || true

if ! git diff --cached --quiet 2>/dev/null; then
    CHANGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
    if git commit -m "chore(seo): auto-update by SEO agent $(date +%Y-%m-%d)" >> "$LOG_FILE" 2>&1; then
        if git push origin HEAD:main >> "$LOG_FILE" 2>&1; then
            log "  ✅ Pushed $CHANGED file(s) to GitHub — deploy will follow automatically"
            # Verify stamp reaches live site (2 retries × 90s). Fires emergency if not.
            python3 scripts/deploy_check.py --verify >> "$LOG_FILE" 2>&1 &
            # Guard: critical homepage sections (segments + partners) still present.
            python3 scripts/deploy_check.py --check-sections >> "$LOG_FILE" 2>&1 &
        else
            log "  ⚠️  Push failed"
        fi
    else
        log "  ⚠️  Commit failed"
    fi
else
    log "  ℹ️  No new content to commit"
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

# ---- Step 8b: Optimizer report → daily ledger (NOT direct Telegram) ----
log "Step 8b: Optimizer report → ledger …"
python3 scripts/optimize_seo.py --report >> "$LOG_FILE" 2>&1 || log "⚠️  Optimizer report failed (non-fatal)"

# ---- Step 8c: Daily digest flush (once per calendar day) ----
# flush_digest() is guarded by last_flush_date — first run of the day sends
# one Telegram with ✅ done / 🆘 needs_help sections; subsequent runs are no-op.
log "Step 8c: Daily digest flush …"
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import daily_ledger
sent = daily_ledger.flush_digest()
print('digest sent' if sent else 'already flushed today — no-op')
" >> "$LOG_FILE" 2>&1 || log "⚠️  Daily digest flush failed (non-fatal)"

# ---- Step 8d: Status digest (once per calendar day, rich numbers) ----
log "Step 8d: Status digest → Telegram …"
python3 scripts/status_digest.py --daily >> "$LOG_FILE" 2>&1 \
    || log "⚠️  Status digest failed (non-fatal)"

# ---- Rotate old logs (keep 30 days) ----
find "$LOG_DIR" -name "agent-*.log" -mtime +30 -delete 2>/dev/null || true

# Completion marker for the pipeline watchdog (proves we reached the end).
date -u +%Y-%m-%dT%H:%M:%SZ > data/.pipeline_ok 2>/dev/null || true

log "=== SEO Agent finished ==="
