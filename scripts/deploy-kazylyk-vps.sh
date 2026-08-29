#!/usr/bin/env bash
# Copy kazylyk.com static files onto the Selectel VPS and enable nginx.
# Does not pull, reset, commit, or push the pepperoni repo.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${VPS_HOST:-pepperoni-vps}"
REMOTE="${KAZYLYK_REMOTE:-/var/www/kazylyk/current}"

rsync -az --delete \
  --exclude '.DS_Store' \
  "$ROOT/kazylyk/" \
  "$HOST:$REMOTE/"

scp -q "$ROOT/deploy/nginx/kazylyk.conf" \
  "$HOST:/etc/nginx/sites-available/kazylyk.conf"

ssh "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
mkdir -p /var/www/kazylyk/current /var/www/letsencrypt
ln -sfn /etc/nginx/sites-available/kazylyk.conf /etc/nginx/sites-enabled/kazylyk.conf
if [[ ! -f /etc/letsencrypt/live/kazylyk.com/fullchain.pem ]]; then
  cat >/etc/nginx/sites-available/kazylyk.conf <<'HTTPONLY'
server {
    listen 80;
    listen [::]:80;
    server_name kazylyk.com www.kazylyk.com;
    root /var/www/kazylyk/current;
    index index.html;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
        default_type text/plain;
    }
    location / {
        try_files $uri $uri/ $uri/index.html =404;
    }
}
HTTPONLY
fi
nginx -t
systemctl reload nginx
REMOTE

echo "Files on $HOST:$REMOTE"
