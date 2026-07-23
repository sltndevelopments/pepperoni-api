#!/usr/bin/env bash
# Install / update pepperoni-halyal 301 snippet on Selectel VPS and reload nginx.
# Run from laptop: bash scripts/install_halyal_redirects_vps.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/deploy/nginx/pepperoni-halyal-redirects.conf"
HOST="${VPS_HOST:-pepperoni-vps}"
REMOTE_SNIPPET="/etc/nginx/snippets/pepperoni-halyal-redirects.conf"
SITE_CONF="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"

if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC"
  exit 1
fi

# Prefer ssh+stdin over scp (IdentityFile Host alias is more reliable).
ssh "$HOST" "cat > /tmp/pepperoni-halyal-redirects.conf" < "$SRC"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
cp /tmp/pepperoni-halyal-redirects.conf "$REMOTE_SNIPPET"
if ! grep -q 'pepperoni-halyal-redirects.conf' "$SITE_CONF"; then
  echo "WARNING: add manually: include $REMOTE_SNIPPET; inside server{} for pepperoni.tatar"
fi
nginx -t
systemctl reload nginx
echo "OK: pepperoni-halyal redirects installed"
EOF
