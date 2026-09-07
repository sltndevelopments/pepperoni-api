#!/usr/bin/env bash
# Proxy POST /api/catalog-chat to the local MCP process.
# Install on both api.pepperoni.tatar and pepperoni.tatar so the widget
# can call same-origin /api/catalog-chat (no CORS).
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SRC="$REPO/deploy/nginx/catalog-chat.conf"
DST="/etc/nginx/snippets/catalog-chat.conf"
INCLUDE_LINE='include /etc/nginx/snippets/catalog-chat.conf;'
BAK_DIR="/etc/nginx/disabled-vhosts"

if [[ ! -f "$SRC" ]]; then
  echo "❌ missing $SRC"
  exit 1
fi

mkdir -p /etc/nginx/snippets "$BAK_DIR"
cp -a "$SRC" "$DST"

include_vhost() {
  local vhost="$1"
  if [[ ! -f "$vhost" ]]; then
    echo "· skip missing $vhost"
    return 0
  fi
  python3 - "$vhost" "$INCLUDE_LINE" <<'PY'
from pathlib import Path
import re, sys
from datetime import datetime, timezone

path = Path(sys.argv[1])
include = sys.argv[2]
text = path.read_text(encoding="utf-8")
if "catalog-chat.conf" in text:
    print(f"· snippet already included in {path}")
    raise SystemExit(0)

https = re.search(r"listen\s+443\s+ssl", text)
if not https:
    print(f"· no HTTPS listen in {path}")
    raise SystemExit(0)
tail = text[https.start():]
m = re.search(r"^([ \t]*)location\s+/\s*\{", tail, flags=re.M)
if not m:
    print(f"· no location / after HTTPS in {path}")
    raise SystemExit(0)
indent = m.group(1)
abs_pos = https.start() + m.start()
bak = Path("/etc/nginx/disabled-vhosts") / f"{path.name}.bak.catalog-chat.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
bak.parent.mkdir(parents=True, exist_ok=True)
bak.write_text(text, encoding="utf-8")
path.write_text(text[:abs_pos] + f"{indent}{include}\n\n" + text[abs_pos:], encoding="utf-8")
print(f"✅ included catalog-chat snippet before location / in {path}")
PY
}

include_vhost /etc/nginx/sites-enabled/api.pepperoni.tatar
include_vhost /etc/nginx/sites-enabled/pepperoni.tatar
include_vhost /etc/nginx/sites-enabled/pepperoni.tatar.conf

if ! nginx -t; then
  echo "❌ nginx -t failed"
  exit 1
fi
systemctl reload nginx

code=$(curl -sS -o /tmp/catalog-chat-health.json -w "%{http_code}" --max-time 8 \
  -H 'Host: api.pepperoni.tatar' \
  --resolve api.pepperoni.tatar:443:127.0.0.1 \
  "https://api.pepperoni.tatar/api/catalog-chat" || true)
if [[ "$code" != "200" ]]; then
  echo "❌ GET /api/catalog-chat returned $code"
  cat /tmp/catalog-chat-health.json 2>/dev/null || true
  echo
  exit 1
fi
echo "✅ GET /api/catalog-chat $code $(tr -d '\n' < /tmp/catalog-chat-health.json)"

acao=$(curl -sS -D - -o /dev/null --max-time 8 \
  -X OPTIONS "https://api.pepperoni.tatar/api/catalog-chat" \
  -H 'Host: api.pepperoni.tatar' \
  --resolve api.pepperoni.tatar:443:127.0.0.1 \
  -H 'Origin: https://pepperoni.tatar' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' \
  | tr -d '\r' | grep -ci '^access-control-allow-origin:' || true)
if [[ "$acao" != "1" ]]; then
  echo "❌ expected 1 Access-Control-Allow-Origin, got ${acao:-0}"
  exit 1
fi
echo "✅ OPTIONS CORS header count=$acao"
