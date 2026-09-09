#!/usr/bin/env bash
# Install canonical-URL snippets:
#   deploy/nginx/canonical-url.conf     → pepperoni.tatar HTTPS server (trailing slash)
#   deploy/nginx/api-host-canonical.conf → api.pepperoni.tatar HTTPS server (no HTML dup)
# Idempotent; validates with nginx -t and reloads; verifies live behaviour.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SNIPPETS="/etc/nginx/snippets"
APEX_SITE="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"
API_SITE="${NGINX_API_SITE:-/etc/nginx/sites-enabled/api.pepperoni.tatar}"
BAK_DIR="/etc/nginx/disabled-vhosts"
mkdir -p "$SNIPPETS" "$BAK_DIR"

include_before_root_location() {
  # $1 = vhost path, $2 = snippet file name
  python3 - "$1" "$2" <<'PY'
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
Path("/etc/nginx/disabled-vhosts").mkdir(parents=True, exist_ok=True)
(Path("/etc/nginx/disabled-vhosts") / f"{path.name}.bak.canonical.{stamp}").write_text(text, encoding="utf-8")
path.write_text(text[:pos] + f"{indent}{include}\n\n" + text[pos:], encoding="utf-8")
print(f"✅ included {name} before location / in {path.name}")
PY
}

for pair in "canonical-url.conf:$APEX_SITE" "api-host-canonical.conf:$API_SITE"; do
  name="${pair%%:*}"; site="${pair#*:}"
  src="$REPO/deploy/nginx/$name"
  [[ -f "$src" ]] || { echo "❌ missing $src"; exit 1; }
  [[ -f "$site" ]] || { echo "❌ missing vhost $site"; exit 1; }
  install -m 0644 "$src" "$SNIPPETS/$name"
  include_before_root_location "$site" "$name"
done

nginx -t
systemctl reload nginx

code() { curl -s -o /dev/null --max-time 8 -w '%{http_code} %{redirect_url}' "$1"; }
echo "apex /products/      → $(code https://pepperoni.tatar/products/)"
echo "apex /en             → $(code https://pepperoni.tatar/en)"
echo "apex /en/            → $(code https://pepperoni.tatar/en/)"
echo "apex /products       → $(code https://pepperoni.tatar/products)"
echo "api  /about          → $(code https://api.pepperoni.tatar/about)"
echo "api  /products/kd-013→ $(code https://api.pepperoni.tatar/products/kd-013)"
echo "api  /api/products   → $(code https://api.pepperoni.tatar/api/products)"
echo "api  /openapi.yaml   → $(code https://api.pepperoni.tatar/openapi.yaml)"
echo "api  /.well-known/ai-plugin.json → $(code https://api.pepperoni.tatar/.well-known/ai-plugin.json)"
echo "api  /               → $(code https://api.pepperoni.tatar/)"
