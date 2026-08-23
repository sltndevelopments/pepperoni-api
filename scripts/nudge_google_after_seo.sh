#!/usr/bin/env bash
# Default post-SEO / post-deploy indexing nudge — Google + Yandex + Bing/IndexNow.
#
# Usage (VPS):
#   set -a; . /var/www/pepperoni/seo-agent.env; set +a
#   bash scripts/nudge_google_after_seo.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# CLAUDE.md §9 tells agents to run this bare after every SEO push, but the
# Google and Yandex clients read credentials from seo-agent.env. Sourced
# nowhere, they print "not set", the wrapper calls it non-fatal, and the run
# still exits 0 — a nudge that silently skipped Google and looked like it
# worked. Load the env ourselves so the documented command does what it says.
# The .env carries the key base64-encoded (GSC_*_B64); only the cron wrapper
# decodes it into the raw form, so check both before deciding we have nothing.
have_gsc() {
  [[ -n "${GSC_SERVICE_ACCOUNT_KEY:-}" || -n "${GSC_SERVICE_ACCOUNT_KEY_B64:-}" \
     || -r "${ROOT}/gsc-key.json" ]]
}
ENV_FILE="${SEO_AGENT_ENV:-/var/www/pepperoni/seo-agent.env}"
if ! have_gsc && [[ -r "$ENV_FILE" ]]; then
  set -a; . "$ENV_FILE"; set +a
  echo "· loaded credentials from $ENV_FILE"
fi
have_gsc || echo "⚠️  no Google credentials — Google steps below will be skipped, not retried"

echo "=== gsc-sitemap (Google) ==="
python3 scripts/gsc-sitemap.py || echo "⚠️  GSC sitemap submit failed (non-fatal)"

echo "=== gsc-index --hot (Google Indexing API) ==="
python3 scripts/gsc-index.py --hot || echo "⚠️  Google Indexing API failed (non-fatal)"

echo "=== yandex-index --hot ==="
python3 scripts/yandex-index.py --hot || echo "⚠️  Yandex indexing failed (non-fatal)"

echo "=== bing-index --hot (IndexNow → Bing/Yandex) ==="
python3 scripts/bing-index.py --hot || echo "⚠️  IndexNow failed (non-fatal)"

echo "=== done (Google + Yandex + Bing) ==="
