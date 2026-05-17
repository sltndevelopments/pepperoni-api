#!/usr/bin/env bash
# ==========================================================================
# Install Partner Intake Server on VPS
# ==========================================================================
# Run as root or with sudo.
# Assumes the repo is cloned to /opt/pepperoni-api.
#
# What this does:
# 1. Installs Python dependencies
# 2. Installs nginx snippet for /partner-submit proxy
# 3. Creates systemd service for the Python server
# 4. Prints post-install instructions
# ==========================================================================
set -euo pipefail

REPO="/opt/pepperoni-api"
SCRIPT="$REPO/infra/scripts/partner-intake-server.py"
NGINX_SRC="$REPO/infra/nginx/partner-intake.conf"
NGINX_DST="/etc/nginx/snippets/partner-intake.conf"
SYSTEMD_SRC="$REPO/infra/scripts/partner-intake.service"
SYSTEMD_DST="/etc/systemd/system/partner-intake.service"
ENV_EXAMPLE="$REPO/.env.example"

echo "=== Install Partner Intake Server ==="
echo ""

# ---- 1. Python dependencies ----
echo "[1/5] Installing Python dependencies..."
pip3 install -r "$REPO/infra/scripts/requirements-partner.txt"
echo "  ✓ Dependencies installed"

# ---- 2. Nginx snippet ----
echo "[2/5] Installing nginx snippet..."
cp "$NGINX_SRC" "$NGINX_DST"
echo "  ✓ $NGINX_DST"
echo ""
echo "  >>> IMPORTANT: Add this line inside the server {} block"
echo "      in /etc/nginx/sites-enabled/api.pepperoni.tatar.conf"
echo "      (or wherever your api.pepperoni.tatar server block lives):"
echo ""
echo "      include /etc/nginx/snippets/partner-intake.conf;"
echo ""

# ---- 3. Systemd service ----
echo "[3/5] Creating systemd service..."
cat > "$SYSTEMD_DST" << 'SYSTEMDEOF'
[Unit]
Description=Partner Intake Server (pepperoni.tatar/china)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/pepperoni-api
ExecStart=/usr/bin/python3 /opt/pepperoni-api/infra/scripts/partner-intake-server.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/pepperoni-api/.env

[Install]
WantedBy=multi-user.target
SYSTEMDEOF

systemctl daemon-reload
echo "  ✓ $SYSTEMD_DST"

# ---- 4. Create .env.example if missing ----
echo "[4/5] Checking .env..."
if [ ! -f "$ENV_EXAMPLE" ]; then
    cat > "$ENV_EXAMPLE" << 'ENVEOF'
# Partner Intake Server — environment variables
# Copy to /opt/pepperoni-api/.env and fill in the values.

# Google Sheets — create a sheet and copy its ID from the URL
# (https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit)
GOOGLE_SHEET_ID=

# Google Service Account — download JSON key from Google Cloud Console
# (APIs & Services → Credentials → Create Service Account → JSON key)
GOOGLE_SERVICE_ACCOUNT=/opt/pepperoni-api/google-sa.json

# DeepSeek API key — get from https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=

# Upload directory for partner catalogs
UPLOAD_DIR=/opt/pepperoni-api/data/partner-catalogs
ENVEOF
    echo "  ✓ Created .env.example — fill it in and copy to /opt/pepperoni-api/.env"
else
    echo "  ✓ .env.example already exists"
fi

# ---- 5. Verify nginx ----
echo "[5/5] Checking nginx config..."
if nginx -t 2>/dev/null; then
    echo "  ✓ nginx config OK"
else
    echo "  ⚠ nginx config check failed — fix before reloading"
fi

# ---- Done ----
echo ""
echo "=============================================="
echo "  INSTALL COMPLETE"
echo "=============================================="
echo ""
echo "NEXT STEPS (run these commands):"
echo ""
echo "  1. Create .env file:"
echo "     cp $ENV_EXAMPLE /opt/pepperoni-api/.env"
echo "     nano /opt/pepperoni-api/.env  # fill in values"
echo ""
echo "  2. Add nginx include (edit server block):"
echo "     nano /etc/nginx/sites-enabled/api.pepperoni.tatar.conf"
echo "     # Add: include /etc/nginx/snippets/partner-intake.conf;"
echo "     nginx -t && systemctl reload nginx"
echo ""
echo "  3. Start the service:"
echo "     systemctl enable partner-intake"
echo "     systemctl start partner-intake"
echo "     systemctl status partner-intake"
echo ""
echo "  4. Share Google Sheet with service account:"
echo "     # Open .env, find GOOGLE_SERVICE_ACCOUNT path"
echo "     # Open the JSON file, find 'client_email'"
echo "     # Share your Google Sheet (Editor) with that email"
echo ""
echo "  5. Test:"
echo "     curl -X POST https://api.pepperoni.tatar/partner-submit \\"
echo "       -F 'company=TestCo' -F 'email=test@test.com'"
echo ""
