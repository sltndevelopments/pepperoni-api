#!/usr/bin/env bash
# Default post-SEO / post-deploy indexing nudge.
# 1) Resubmit sitemap to GSC
# 2) Hot Indexing API: money URLs + nginx 301 URL_DELETED/UPDATED
#
# Usage (VPS):
#   set -a; . /var/www/pepperoni/seo-agent.env; set +a
#   bash scripts/nudge_google_after_seo.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== gsc-sitemap ==="
python3 scripts/gsc-sitemap.py || echo "⚠️  sitemap submit failed (non-fatal)"

echo "=== gsc-index --hot ==="
python3 scripts/gsc-index.py --hot

echo "=== done ==="
