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
modified = False

if name not in text:
    https = re.search(r"listen\s+443\s+ssl", text)
    if not https:
        print(f"❌ no HTTPS listen in {path}"); raise SystemExit(1)
    tail = text[https.start():]
    m = re.search(r"^([ \t]*)location\s+/\s*\{", tail, flags=re.M)
    if not m:
        print(f"❌ no location / after HTTPS listen in {path}"); raise SystemExit(1)
    indent = m.group(1)
    pos = https.start() + m.start()
    text = text[:pos] + f"{indent}{include}\n\n" + text[pos:]
    modified = True
    print(f"✅ included {name} before location / in {path.name}")
else:
    print(f"· {name} already included in {path.name}")

# Eliminate Vercel fallback for 404s: serve local 404 instantly from SSD
if "@vercel" in text:
    new_text = re.sub(
        r"(try_files\s+\$uri\s+\$uri\.html\s+\$uri/index\.html\s+\$uri/)\s+@vercel\s*;",
        r"\1 =404;",
        text
    )
    if new_text != text:
        text = new_text
        modified = True
        print("✅ replaced @vercel fallback in try_files with =404")

if modified:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    (Path("/etc/nginx/disabled-vhosts") / f"{path.name}.bak.errorpages.{stamp}").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(text, encoding="utf-8")
    print("✅ saved updated vhost config")
else:
    print("· no vhost modifications needed")
PY

nginx -t
systemctl reload nginx

out=$(curl -sI --max-time 8 "https://pepperoni.tatar/definitely-missing-$(date +%s)")
code=$(echo "$out" | grep -i "^HTTP/" | head -1 | awk '{print $2}')
has_vercel=$(echo "$out" | grep -i "x-vercel" || true)

echo "apex missing URL status: $code"
if [[ "$code" != "404" ]]; then
  echo "❌ expected 404, got $code" >&2
  exit 1
fi

if [[ -n "$has_vercel" ]]; then
  echo "❌ unexpected Vercel header on 404: $has_vercel" >&2
  exit 1
fi

echo "✅ verified: local branded 404 served directly by nginx without Vercel fallback"
