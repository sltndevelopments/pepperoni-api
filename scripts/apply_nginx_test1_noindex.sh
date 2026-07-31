#!/usr/bin/env bash
# Install /test1 X-Robots-Tag: noindex on Selectel VPS and reload nginx.
# Invoked by deploy-vps.yml (runs ON the VPS) or manually:
#   bash scripts/apply_nginx_test1_noindex.sh /var/www/pepperoni/repo
set -euo pipefail
ROOT="${1:-}"
if [[ -z "$ROOT" ]]; then
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi
SRC="$ROOT/deploy/nginx/test1-noindex.conf"
SNIPPET="/etc/nginx/snippets/test1-noindex.conf"
SITE_CONF="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"

if [[ ! -f "$SRC" ]]; then
  echo "❌ missing $SRC"
  exit 1
fi
if [[ ! -f "$SITE_CONF" ]]; then
  # Fallback common paths
  for c in /etc/nginx/sites-enabled/pepperoni.tatar.conf /etc/nginx/conf.d/pepperoni.tatar.conf; do
    if [[ -f "$c" ]]; then SITE_CONF="$c"; break; fi
  done
fi
if [[ ! -f "$SITE_CONF" ]]; then
  echo "❌ pepperoni.tatar nginx site conf not found"
  exit 1
fi

cp "$SRC" "$SNIPPET"
if ! grep -q 'test1-noindex.conf' "$SITE_CONF"; then
  if grep -q 'snippets/pepperoni-blog-redirects.conf' "$SITE_CONF"; then
    sed -i 's|include /etc/nginx/snippets/pepperoni-blog-redirects.conf;|include /etc/nginx/snippets/pepperoni-blog-redirects.conf;\n    include /etc/nginx/snippets/test1-noindex.conf;|' "$SITE_CONF"
  elif grep -q 'snippets/pepperoni-halyal-redirects.conf' "$SITE_CONF"; then
    sed -i 's|include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;|include /etc/nginx/snippets/pepperoni-halyal-redirects.conf;\n    include /etc/nginx/snippets/test1-noindex.conf;|' "$SITE_CONF"
  else
    # Insert before the last closing brace of the first server block — last resort
    awk 'BEGIN{done=0} /^}/ && !done { print "    include /etc/nginx/snippets/test1-noindex.conf;"; done=1 } { print }' "$SITE_CONF" > "$SITE_CONF.tmp"
    mv "$SITE_CONF.tmp" "$SITE_CONF"
  fi
fi

nginx -t
systemctl reload nginx
echo "OK: test1 noindex snippet installed → $SNIPPET"
