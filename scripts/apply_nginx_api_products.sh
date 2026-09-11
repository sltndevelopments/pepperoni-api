#!/usr/bin/env bash
# Serve /api/products and /products.json from the VPS catalog file.
# Do not proxy those paths to Vercel: bot-protection returns 403 to MCP/agents.
# Also move leftover *.bak* vhosts out of sites-enabled (duplicate server_name).
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SRC="$REPO/deploy/nginx/api-products-local.conf"
DST="/etc/nginx/snippets/api-products-local.conf"
VHOST="/etc/nginx/sites-enabled/api.pepperoni.tatar"
INCLUDE_LINE='include /etc/nginx/snippets/api-products-local.conf;'
BAK_DIR="/etc/nginx/disabled-vhosts"

if [[ ! -f "$SRC" ]]; then
  echo "❌ missing $SRC"
  exit 1
fi
if [[ ! -f "$VHOST" ]]; then
  echo "❌ missing $VHOST"
  exit 1
fi

mkdir -p /etc/nginx/snippets "$BAK_DIR"
cp -a "$SRC" "$DST"

python3 - "$VHOST" "$INCLUDE_LINE" <<'PY'
from pathlib import Path
import re, sys
from datetime import datetime, timezone

path = Path(sys.argv[1])
include = sys.argv[2]
text = path.read_text(encoding="utf-8")
if "api-products-local.conf" in text:
    print(f"· snippet already included in {path}")
    raise SystemExit(0)

https = re.search(r"listen\s+443\s+ssl", text)
if not https:
    print("❌ no HTTPS listen 443 ssl in vhost")
    raise SystemExit(1)
# Insert before the first catch-all location / in the HTTPS server
# (the first location / after listen 443).
tail = text[https.start():]
m = re.search(r"^([ \t]*)location\s+/\s*\{", tail, flags=re.M)
if not m:
    print("❌ no location / after HTTPS listen")
    raise SystemExit(1)
indent = m.group(1)
abs_pos = https.start() + m.start()
stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
bak = path.with_name(path.name + f".bak.api-products.{stamp}")
# Keep backup OUT of sites-enabled so nginx does not load a second vhost.
bak = Path("/etc/nginx/disabled-vhosts") / bak.name
bak.parent.mkdir(parents=True, exist_ok=True)
bak.write_text(text, encoding="utf-8")
insert = f"{indent}{include}\n\n"
path.write_text(text[:abs_pos] + insert + text[abs_pos:], encoding="utf-8")
print(f"✅ included snippet before location / in {path}")
PY

shopt -s nullglob
moved=0
for f in /etc/nginx/sites-enabled/*.bak*; do
  base=$(basename "$f")
  mv "$f" "$BAK_DIR/$base"
  echo "moved $f → $BAK_DIR/$base"
  moved=$((moved + 1))
done
if [[ "$moved" -eq 0 ]]; then
  echo "· no *.bak* vhosts in sites-enabled"
fi

if ! nginx -t; then
  echo "❌ nginx -t failed"
  exit 1
fi
systemctl reload nginx

hdrs=$(curl -sI --max-time 8 -H 'Host: api.pepperoni.tatar' \
  --resolve api.pepperoni.tatar:443:127.0.0.1 \
  "https://api.pepperoni.tatar/api/products" | tr -d '\r')
if echo "$hdrs" | grep -qi '^HTTP/.* 200' && echo "$hdrs" | grep -qi 'x-data-source: vps-local'; then
  echo "✅ /api/products is vps-local 200"
else
  echo "❌ /api/products not serving local catalog"
  echo "$hdrs" | head -20
  exit 1
fi
