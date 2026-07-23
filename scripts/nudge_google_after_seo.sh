#!/usr/bin/env bash
# Default post-SEO / post-deploy indexing nudge — Google + Yandex + Bing/IndexNow.
#
# Usage (VPS):
#   set -a; . /var/www/pepperoni/seo-agent.env; set +a
#   bash scripts/nudge_google_after_seo.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== gsc-sitemap (Google) ==="
python3 scripts/gsc-sitemap.py || echo "⚠️  GSC sitemap submit failed (non-fatal)"

echo "=== gsc-index --hot (Google Indexing API) ==="
python3 scripts/gsc-index.py --hot || echo "⚠️  Google Indexing API failed (non-fatal)"

echo "=== yandex-index --hot ==="
python3 scripts/yandex-index.py --hot || echo "⚠️  Yandex indexing failed (non-fatal)"

echo "=== bing-index --hot (IndexNow → Bing/Yandex) ==="
python3 scripts/bing-index.py --hot || echo "⚠️  IndexNow failed (non-fatal)"

echo "=== done (Google + Yandex + Bing) ==="
