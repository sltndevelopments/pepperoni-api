#!/usr/bin/env bash
# Install / update jerky 301 snippet on Selectel VPS and reload nginx.
# Run from laptop: bash scripts/install_jerky_redirects_vps.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/deploy/nginx/jerky-redirects.conf"
HOST="${VPS_HOST:-pepperoni-vps}"
REMOTE_SNIPPET="/etc/nginx/snippets/jerky-redirects.conf"
SITE_CONF="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"

if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC"
  exit 1
fi

ssh "$HOST" "cat > /tmp/jerky-redirects.conf" < "$SRC"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
cp /tmp/jerky-redirects.conf "$REMOTE_SNIPPET"
if ! grep -q 'jerky-redirects.conf' "$SITE_CONF"; then
  if grep -q 'pepperoni-halyal-redirects.conf' "$SITE_CONF"; then
    sed -i 's|include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;|include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;\n    include /etc/nginx/snippets/jerky-redirects.conf;|' "$SITE_CONF"
  else
    echo "WARNING: add manually: include $REMOTE_SNIPPET; inside server{} for pepperoni.tatar"
  fi
fi
nginx -t
systemctl reload nginx
echo "OK: jerky redirects installed"
EOF
