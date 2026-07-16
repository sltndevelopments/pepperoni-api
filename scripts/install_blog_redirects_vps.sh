#!/usr/bin/env bash
# Install blog near-dup 301 snippet on Selectel VPS and reload nginx.
# Run from laptop with SSH access: bash scripts/install_blog_redirects_vps.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/deploy/nginx/pepperoni-blog-redirects.conf"
HOST="${VPS_HOST:-root@37.9.4.101}"
REMOTE_SNIPPET="/etc/nginx/snippets/pepperoni-blog-redirects.conf"
SITE_CONF="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"

if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC — run: python3 scripts/apply_blog_canonicals.py"
  exit 1
fi

scp "$SRC" "$HOST:$REMOTE_SNIPPET"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
if ! grep -q 'pepperoni-blog-redirects.conf' "$SITE_CONF"; then
  # Insert include near other pepperoni snippets if present, else before first server block end
  if grep -q 'pepperoni-halyal-redirects.conf' "$SITE_CONF"; then
    sed -i 's|include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;|include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;\n    include /etc/nginx/snippets/pepperoni-blog-redirects.conf;|' "$SITE_CONF"
  else
    echo "WARNING: add manually: include $REMOTE_SNIPPET;  inside server{} for pepperoni.tatar"
  fi
fi
nginx -t
systemctl reload nginx
echo "OK: blog redirects installed"
EOF
