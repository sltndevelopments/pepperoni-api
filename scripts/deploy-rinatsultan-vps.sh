#!/usr/bin/env bash
# Copy the personal site onto the Selectel VPS and enable nginx.
# Does not pull, reset, commit, or push the pepperoni repo.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${VPS_HOST:-pepperoni-vps}"
REMOTE="${RINAT_REMOTE:-/var/www/rinatsultan/current}"

rsync -az --delete \
  --exclude '.DS_Store' \
  --exclude '_headers' \
  --exclude '_redirects' \
  --exclude '_routes.json' \
  "$ROOT/rinatsultan/" \
  "$HOST:$REMOTE/"

scp -q "$ROOT/deploy/nginx/rinatsultan.conf" \
  "$HOST:/etc/nginx/sites-available/rinatsultan.conf"

ssh "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
mkdir -p /var/www/rinatsultan/current /var/www/letsencrypt
ln -sfn /etc/nginx/sites-available/rinatsultan.conf /etc/nginx/sites-enabled/rinatsultan.conf
# First boot: if TLS files are missing, serve HTTP only so certbot can run.
if [[ ! -f /etc/letsencrypt/live/rinatsultan.com/fullchain.pem ]]; then
  cat >/etc/nginx/sites-available/rinatsultan.conf <<'HTTPONLY'
server {
    listen 80;
    listen [::]:80;
    server_name rinatsultan.com www.rinatsultan.com;
    root /var/www/rinatsultan/current;
    index index.html;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
        default_type text/plain;
    }
    location / {
        try_files $uri $uri/ /index.html =404;
    }
}
HTTPONLY
fi
nginx -t
systemctl reload nginx
REMOTE

echo "Files on $HOST:$REMOTE"
