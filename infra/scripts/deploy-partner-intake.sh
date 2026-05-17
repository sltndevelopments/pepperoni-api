#!/usr/bin/env bash
# Deploy Partner Intake Server — extracts creds from existing VPS config, sets up everything
set -e
cd /var/www/pepperoni/repo
echo "=== Deploy Partner Intake Server ==="

# ---- 0. Extract credentials from existing VPS config ----
echo "[0/7] Extracting credentials..."
SA_FILE="/var/www/pepperoni/google-sa.json"
ENV_FILE="/var/www/pepperoni/.env"

# Decode GSC service account from seo-agent.env (base64-encoded JSON)
if [ -f /var/www/pepperoni/seo-agent.env ] && [ ! -f "$SA_FILE" ]; then
  GSC_B64=$(grep GSC_SERVICE_ACCOUNT_KEY_B64 /var/www/pepperoni/seo-agent.env | cut -d= -f2-)
  if [ -n "$GSC_B64" ]; then
    echo "$GSC_B64" | base64 -d > "$SA_FILE" 2>/dev/null || true
    chmod 600 "$SA_FILE"
    echo "  Service account extracted to $SA_FILE"
  fi
fi

# Get DeepSeek key from seo-agent.env
DEEPSEEK_KEY="${DEEPSEEK_API_KEY:-}"
if [ -z "$DEEPSEEK_KEY" ] && [ -f /var/www/pepperoni/seo-agent.env ]; then
  DEEPSEEK_KEY=$(grep DEEPSEEK_API_KEY /var/www/pepperoni/seo-agent.env | cut -d= -f2-)
fi
if [ -z "$DEEPSEEK_KEY" ] && [ -f "$ENV_FILE" ]; then
  DEEPSEEK_KEY=$(grep DEEPSEEK_API_KEY "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
fi

echo "  DeepSeek:   $([ -n "$DEEPSEEK_KEY" ] && echo 'found' || echo 'not found')"

# ---- 1. Python dependencies ----
echo "[1/7] Installing Python deps..."
pip3 install --break-system-packages -r infra/scripts/requirements-partner.txt 2>/dev/null || \
pip3 install -r infra/scripts/requirements-partner.txt 2>/dev/null || \
pip3 install --user -r infra/scripts/requirements-partner.txt || {
  echo "  pip3 failed; trying apt..."
  apt-get update -qq && apt-get install -y -qq python3-flask python3-dotenv 2>/dev/null || true
}
echo "  done"

# ---- 2. Nginx ----
echo "[2/7] Nginx setup..."
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
  echo "  ok"
fi

# ---- 3. Directories ----
echo "[3/7] Directories..."
mkdir -p /var/www/pepperoni/data/partner-catalogs
chown www-data:www-data /var/www/pepperoni/data/partner-catalogs 2>/dev/null || true

# ---- 4. .env file ----
echo "[4/7] Writing .env..."
printf '%s\n' \
  "# Partner Intake Server — auto-generated $(date)" \
  "# Google Sheets: auto-creates/finds sheet '${GOOGLE_SHEET_NAME:-Pepperoni Partners}'" \
  "GOOGLE_SHEET_ID=" \
  "GOOGLE_SHEET_NAME=Pepperoni Partners" \
  "GOOGLE_SERVICE_ACCOUNT=$SA_FILE" \
  "DEEPSEEK_API_KEY=${DEEPSEEK_KEY}" \
  "UPLOAD_DIR=/var/www/pepperoni/data/partner-catalogs" \
  > "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "  .env written ($(wc -l < "$ENV_FILE") lines)"

# ---- 5. Systemd ----
echo "[5/7] Systemd service..."
printf '%s\n' \
  '[Unit]' 'Description=Partner Intake Server' 'After=network.target' '' \
  '[Service]' 'Type=simple' 'User=www-data' \
  'WorkingDirectory=/var/www/pepperoni/repo' \
  'ExecStart=/usr/bin/python3 /var/www/pepperoni/repo/infra/scripts/partner-intake-server.py' \
  'Restart=always' 'RestartSec=5' \
  "EnvironmentFile=-$ENV_FILE" \
  'Environment=UPLOAD_DIR=/var/www/pepperoni/data/partner-catalogs' '' \
  '[Install]' 'WantedBy=multi-user.target' \
  > /etc/systemd/system/partner-intake.service
systemctl daemon-reload 2>/dev/null || true
systemctl enable partner-intake 2>/dev/null || true

# ---- 6. Start server ----
echo "[6/7] Starting server..."
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

# ---- 7. Nginx reload + verify ----
echo "[7/7] Reloading nginx..."
nginx -t 2>/dev/null && { systemctl reload nginx 2>/dev/null || nginx -s reload 2>/dev/null; echo "  nginx reloaded"; } || echo "  nginx -t failed"

echo ""
echo "=== Verifying ==="
sleep 1
curl -s -o /dev/null -w "  Local:  HTTP %{http_code}\n" http://127.0.0.1:5001/partner-submit 2>/dev/null || echo "  Local:  FAIL"
curl -s -o /dev/null -w "  Public: HTTP %{http_code}\n" https://api.pepperoni.tatar/partner-submit 2>/dev/null || echo "  Public: FAIL"
echo "=== Done ==="
