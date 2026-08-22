#!/usr/bin/env bash
# Origin Agent Readiness. Homepage is location = / with its own add_header,
# so Link must live in pepperoni-security-headers.conf (same file as CSP).
# Do not enable Cloudflare proxy.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
MAP_SRC="$REPO/deploy/nginx/agent-discovery.map.conf"
SNIPPET_SRC="$REPO/deploy/nginx/agent-discovery.snippet"
MAP_DST="/etc/nginx/conf.d/00-pepperoni-agent-map.conf"
SNIPPET_DST="/etc/nginx/snippets/pepperoni-agent-discovery.conf"
VHOST="/etc/nginx/sites-enabled/pepperoni.tatar"
SEC="/etc/nginx/snippets/pepperoni-security-headers.conf"
STATIC="/etc/nginx/snippets/pepperoni-static-data.conf"
INCLUDE_LINE='include /etc/nginx/snippets/pepperoni-agent-discovery.conf;'
# Single-quoted nginx string: inner "rel=..." must stay intact.
LINK_LINE='add_header Link '\''</.well-known/api-catalog>; rel="api-catalog", </.well-known/mcp.json>; rel="describedby"; type="application/json", </.well-known/mcp/server-card.json>; rel="describedby"; type="application/json", </.well-known/agent-card.json>; rel="describedby"; type="application/json", </llms.txt>; rel="alternate"; type="text/markdown", </openapi.yaml>; rel="service-desc"; type="application/yaml", </.well-known/agent-skills/index.json>; rel="describedby"; type="application/json", </.well-known/oauth-protected-resource>; rel="describedby"'\'' always;'

if [[ ! -f "$MAP_SRC" || ! -f "$SNIPPET_SRC" || ! -f "$VHOST" || ! -f "$SEC" ]]; then
  echo "❌ missing nginx sources"
  exit 1
fi

mkdir -p /etc/nginx/snippets /etc/nginx/conf.d
cp -a "$MAP_SRC" "$MAP_DST"
cp -a "$SNIPPET_SRC" "$SNIPPET_DST"

python3 - "$SEC" "$LINK_LINE" <<'PY'
from pathlib import Path
import re, sys
path, link_line = Path(sys.argv[1]), sys.argv[2]
text = path.read_text(encoding="utf-8")
# Drop any previous Link (including the broken unquoted one).
text = re.sub(r'^[ \t]*add_header[ \t]+Link[ \t]+.+\n?', '', text, flags=re.M)
if not text.endswith("\n"):
    text += "\n"
path.write_text(text + link_line + "\n", encoding="utf-8")
print(f"✅ Link in {path}")
PY

STATIC_BAK=""
if [[ -f "$STATIC" ]]; then
  STATIC_BAK="${STATIC}.bak.agent.$(date -u +%Y%m%d%H%M%S)"
  cp -a "$STATIC" "$STATIC_BAK"
  python3 "$REPO/scripts/patch_llms_txt_location.py" "$STATIC"
fi

python3 - "$VHOST" "$INCLUDE_LINE" <<'PY'
import re, sys
from datetime import datetime, timezone
path, include = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
if "pepperoni-agent-discovery.conf" in text:
    print(f"· snippet already included in {path}")
    raise SystemExit(0)
pat = re.compile(
    r'^([ \t]*add_header[ \t]+Content-Security-Policy[ \t]+".*?"[ \t]*always;)[ \t]*$',
    re.M,
)
m = pat.search(text)
if not m:
    print("❌ no CSP add_header in vhost")
    raise SystemExit(1)
indent = re.match(r'[ \t]*', m.group(1)).group(0)
stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
bak = f"{path}.bak.agent.{stamp}"
open(bak, "w", encoding="utf-8").write(text)
text = text[: m.end()] + "\n" + indent + include + text[m.end():]
open(path, "w", encoding="utf-8").write(text)
print(f"✅ included snippet after CSP in {path}")
PY

if ! nginx -t; then
  echo "❌ nginx -t failed — restoring backups"
  last=$(ls -1t "${VHOST}".bak.agent.* 2>/dev/null | head -1 || true)
  if [[ -n "${last}" ]]; then
    cp -a "$last" "$VHOST"
    echo "  restored $VHOST from $last"
  fi
  if [[ -n "${STATIC_BAK}" && -f "${STATIC_BAK}" ]]; then
    cp -a "$STATIC_BAK" "$STATIC"
    echo "  restored $STATIC from $STATIC_BAK"
  fi
  nginx -t || true
  exit 1
fi
systemctl reload nginx

fail=0
hdrs=$(curl -sI --max-time 5 -H 'Host: pepperoni.tatar' \
  --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar/" | tr -d '\r')
if echo "$hdrs" | grep -qi '^link:.*api-catalog'; then
  echo "✅ / has Link api-catalog"
else
  echo "❌ / missing Link"
  echo "$hdrs" | head -25
  fail=1
fi
md=$(curl -sI --max-time 5 -H 'Host: pepperoni.tatar' -H 'Accept: text/markdown' \
  --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar/" | tr -d '\r')
if echo "$md" | grep -qi '^content-type:.*text/markdown'; then
  echo "✅ markdown negotiation"
else
  echo "⚠️ markdown negotiation not on yet"
  echo "$md" | head -15
fi
exit "$fail"
