#!/usr/bin/env bash
# Install blog near-dup 301 snippet on Selectel VPS and reload nginx.
# Run from laptop with SSH access: bash scripts/install_blog_redirects_vps.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/deploy/nginx/pepperoni-blog-redirects.conf"
HOST="${VPS_HOST:-pepperoni-vps}"
REMOTE_SNIPPET="/etc/nginx/snippets/pepperoni-blog-redirects.conf"
SITE_CONF="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"

if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC — run: python3 scripts/apply_blog_canonicals.py"
  exit 1
fi

ssh "$HOST" "cat > /tmp/pepperoni-blog-redirects.conf" < "$SRC"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
cp /tmp/pepperoni-blog-redirects.conf "$REMOTE_SNIPPET"
if ! grep -q 'pepperoni-blog-redirects.conf' "$SITE_CONF"; then
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
