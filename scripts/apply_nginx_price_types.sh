#!/usr/bin/env bash
# Install deploy/nginx/price-file-types.conf so /prices.xlsx and /prices.pdf
# get spreadsheet/pdf Content-Type on the VPS (vercel.json does not apply).
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SNIPPETS="/etc/nginx/snippets"
APEX_SITE="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"
NAME="price-file-types.conf"
mkdir -p "$SNIPPETS" /etc/nginx/disabled-vhosts

src="$REPO/deploy/nginx/$NAME"
[[ -f "$src" ]] || { echo "❌ missing $src"; exit 1; }
[[ -f "$APEX_SITE" ]] || { echo "❌ missing vhost $APEX_SITE"; exit 1; }
install -m 0644 "$src" "$SNIPPETS/$NAME"

python3 - "$APEX_SITE" "$NAME" <<'PY'
from pathlib import Path
import re, sys
from datetime import datetime, timezone

path = Path(sys.argv[1]); name = sys.argv[2]
include = f"include /etc/nginx/snippets/{name};"
text = path.read_text(encoding="utf-8")
if name in text:
    print(f"· {name} already included in {path.name}")
    raise SystemExit(0)

https = re.search(r"listen\s+443\s+ssl", text)
if not https:
    print(f"❌ no HTTPS listen in {path}")
    raise SystemExit(1)
tail = text[https.start():]
m = re.search(r"^([ \t]*)location\s+/\s*\{", tail, flags=re.M)
if not m:
    print(f"❌ no location / after HTTPS listen in {path}")
    raise SystemExit(1)
indent = m.group(1)
pos = https.start() + m.start()
stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
bak = Path("/etc/nginx/disabled-vhosts") / f"{path.name}.bak.price-types.{stamp}"
bak.write_text(text, encoding="utf-8")
path.write_text(text[:pos] + f"{indent}{include}\n\n" + text[pos:], encoding="utf-8")
print(f"✅ included {name} before location / in {path.name}")
PY

if ! nginx -t; then
  echo "❌ nginx -t failed — restoring vhost backup"
  last=$(ls -1t /etc/nginx/disabled-vhosts/"$(basename "$APEX_SITE")".bak.price-types.* 2>/dev/null | head -1 || true)
  if [[ -n "${last}" ]]; then
    cp -a "$last" "$APEX_SITE"
    echo "  restored $APEX_SITE from $last"
  fi
  nginx -t || true
  exit 1
fi
systemctl reload nginx

fail=0
xlsx=$(curl -sI --max-time 8 -H 'Host: pepperoni.tatar' \
  --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar/prices.xlsx" | tr -d '\r')
if echo "$xlsx" | grep -qi '^content-type:.*spreadsheetml'; then
  echo "✅ /prices.xlsx Content-Type spreadsheetml"
else
  echo "❌ /prices.xlsx wrong Content-Type"
  echo "$xlsx" | head -20
  fail=1
fi
pdf=$(curl -sI --max-time 8 -H 'Host: pepperoni.tatar' \
  --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar/prices.pdf" | tr -d '\r')
if echo "$pdf" | grep -qi '^content-type:.*application/pdf'; then
  echo "✅ /prices.pdf Content-Type application/pdf"
else
  echo "❌ /prices.pdf wrong Content-Type"
  echo "$pdf" | head -20
  fail=1
fi
exit "$fail"
