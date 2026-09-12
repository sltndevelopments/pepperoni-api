#!/usr/bin/env bash
# Install deploy/nginx/error-pages.conf (branded 404) into the pepperoni.tatar
# HTTPS server block. Idempotent; validates with nginx -t, reloads, verifies live.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SNIPPETS="/etc/nginx/snippets"
APEX_SITE="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"
NAME="error-pages.conf"
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
    print(f"❌ no HTTPS listen in {path}"); raise SystemExit(1)
tail = text[https.start():]
m = re.search(r"^([ \t]*)location\s+/\s*\{", tail, flags=re.M)
if not m:
    print(f"❌ no location / after HTTPS listen in {path}"); raise SystemExit(1)
indent = m.group(1)
pos = https.start() + m.start()
stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
(Path("/etc/nginx/disabled-vhosts") / f"{path.name}.bak.errorpages.{stamp}").write_text(text, encoding="utf-8")
path.write_text(text[:pos] + f"{indent}{include}\n\n" + text[pos:], encoding="utf-8")
print(f"✅ included {name} before location / in {path.name}")
PY

nginx -t
systemctl reload nginx

code=$(curl -s -o /tmp/pep404.html --max-time 8 -w '%{http_code}' "https://pepperoni.tatar/definitely-missing-$(date +%s)")
size=$(wc -c </tmp/pep404.html | tr -d ' ')
echo "apex missing URL → HTTP $code, ${size} bytes, title: $(grep -o '<title>[^<]*' /tmp/pep404.html | head -1)"
[[ "$code" == "404" && "$size" -gt 1000 ]] || { echo "❌ branded 404 not served"; exit 1; }
