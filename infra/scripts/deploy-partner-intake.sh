#!/usr/bin/env bash
# Deploy Partner Intake Server — single script for GitHub Actions
set -e
cd /var/www/pepperoni/repo
echo "=== Deploy Partner Intake Server ==="

echo "[1/6] Installing Python deps..."
pip3 install --break-system-packages -r infra/scripts/requirements-partner.txt 2>/dev/null || \
pip3 install -r infra/scripts/requirements-partner.txt 2>/dev/null || \
pip3 install --user -r infra/scripts/requirements-partner.txt || {
  echo "  pip3 failed; trying apt..."
  apt-get update -qq && apt-get install -y -qq python3-flask python3-dotenv 2>/dev/null || true
}
echo "  done"

echo "[2/6] Installing nginx snippet..."
cp -f infra/nginx/partner-intake.conf /etc/nginx/snippets/partner-intake.conf
NGINX_CONF=""
for f in /etc/nginx/sites-enabled/api.pepperoni.tatar.conf /etc/nginx/sites-enabled/api.pepperoni.tatar /etc/nginx/sites-enabled/default; do
  [ -f "$f" ] && NGINX_CONF="$f" && break
done
[ -z "$NGINX_CONF" ] && NGINX_CONF=$(grep -rl "api.pepperoni.tatar" /etc/nginx/ 2>/dev/null | head -1)
if [ -n "$NGINX_CONF" ] && ! grep -q "partner-intake.conf" "$NGINX_CONF" 2>/dev/null; then
  cp "$NGINX_CONF" "$NGINX_CONF.bak"
  awk '/^}/ { print "    include /etc/nginx/snippets/partner-intake.conf;" } { print }' "$NGINX_CONF" > "$NGINX_CONF.tmp"
  mv "$NGINX_CONF.tmp" "$NGINX_CONF"
  echo "  include added to $NGINX_CONF"
else
  echo "  nginx ok (already configured or config not found)"
fi

echo "[3/6] Creating directories..."
mkdir -p /var/www/pepperoni/data/partner-catalogs
chown www-data:www-data /var/www/pepperoni/data/partner-catalogs 2>/dev/null || true

echo "[4/6] Checking .env..."
if [ ! -f /var/www/pepperoni/.env ]; then
  printf '%s\n' '# Partner Intake Server config' 'GOOGLE_SHEET_ID=' 'GOOGLE_SERVICE_ACCOUNT=/var/www/pepperoni/google-sa.json' 'DEEPSEEK_API_KEY=' 'UPLOAD_DIR=/var/www/pepperoni/data/partner-catalogs' > /var/www/pepperoni/.env
  chmod 600 /var/www/pepperoni/.env
  echo "  created (fill in values!)"
fi

echo "[5/6] Creating systemd service..."
printf '%s\n' '[Unit]' 'Description=Partner Intake Server' 'After=network.target' '' '[Service]' 'Type=simple' 'User=www-data' 'WorkingDirectory=/var/www/pepperoni/repo' 'ExecStart=/usr/bin/python3 /var/www/pepperoni/repo/infra/scripts/partner-intake-server.py' 'Restart=always' 'RestartSec=5' 'EnvironmentFile=-/var/www/pepperoni/.env' '' '[Install]' 'WantedBy=multi-user.target' > /etc/systemd/system/partner-intake.service
systemctl daemon-reload 2>/dev/null || true
systemctl enable partner-intake 2>/dev/null || true

echo "[6/6] Starting server..."
systemctl stop partner-intake 2>/dev/null || true
pkill -f "partner-intake-server.py" 2>/dev/null || true
sleep 1
cd /var/www/pepperoni/repo
nohup python3 infra/scripts/partner-intake-server.py > /var/log/partner-intake.log 2>&1 &
PID=$!
sleep 3
if kill -0 $PID 2>/dev/null; then
  echo "  Server running (PID $PID)"
else
  echo "  nohup failed, log:"
  cat /var/log/partner-intake.log 2>/dev/null || true
  echo "  trying systemd..."
  systemctl start partner-intake 2>&1 || true
  sleep 2
  journalctl -u partner-intake --no-pager -n 20 2>/dev/null || true
fi

echo ""
echo "=== Reloading nginx ==="
nginx -t 2>/dev/null && { systemctl reload nginx 2>/dev/null || nginx -s reload 2>/dev/null; echo "  nginx reloaded"; } || echo "  nginx -t failed"

echo ""
echo "=== Verifying ==="
sleep 1
curl -s -o /dev/null -w "  Local:  HTTP %{http_code}\n" http://127.0.0.1:5001/partner-submit 2>/dev/null || echo "  Local:  NOT REACHABLE"
curl -s -o /dev/null -w "  Public: HTTP %{http_code}\n" https://api.pepperoni.tatar/partner-submit 2>/dev/null || echo "  Public: NOT REACHABLE"
echo "=== Deploy complete ==="
