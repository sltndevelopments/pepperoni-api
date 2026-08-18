#!/usr/bin/env bash
# Origin Agent Readiness: Link headers beside CSP (nginx inheritance),
# markdown Accept rewrite, well-known content-types.
# Does not enable Cloudflare proxy.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
MAP_SRC="$REPO/deploy/nginx/agent-discovery.map.conf"
SNIPPET_SRC="$REPO/deploy/nginx/agent-discovery.snippet"
MAP_DST="/etc/nginx/conf.d/00-pepperoni-agent-map.conf"
SNIPPET_DST="/etc/nginx/snippets/pepperoni-agent-discovery.conf"
INCLUDE_LINE='include snippets/pepperoni-agent-discovery.conf;'
LINK='</.well-known/api-catalog>; rel="api-catalog", </.well-known/mcp.json>; rel="describedby"; type="application/json", </.well-known/mcp/server-card.json>; rel="describedby"; type="application/json", </.well-known/agent-card.json>; rel="describedby"; type="application/json", </llms.txt>; rel="alternate"; type="text/markdown", </openapi.yaml>; rel="service-desc"; type="application/yaml", </.well-known/agent-skills/index.json>; rel="describedby"; type="application/json", </.well-known/oauth-protected-resource>; rel="describedby"'

if [[ ! -f "$MAP_SRC" || ! -f "$SNIPPET_SRC" ]]; then
  echo "❌ missing nginx snippets under $REPO/deploy/nginx/"
  exit 1
fi

mkdir -p /etc/nginx/snippets /etc/nginx/conf.d
cp -a "$MAP_SRC" "$MAP_DST"
cp -a "$SNIPPET_SRC" "$SNIPPET_DST"

# 1) Link header next to every CSP add_header — same inheritance as CSP.
python3 - "$LINK" <<'PY'
import re, sys
from pathlib import Path
link = sys.argv[1]
pat_csp = re.compile(
    r'^([ \t]*add_header[ \t]+Content-Security-Policy[ \t]+".*?"[ \t]*(?:always)?;)[ \t]*$',
    re.M,
)
pat_link = re.compile(r'^[ \t]*add_header[ \t]+Link[ \t]+', re.M)
root = Path("/etc/nginx")
changed = 0
for path in root.rglob("*.conf"):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Content-Security-Policy" not in text:
        continue
    indent_m = re.search(r'^([ \t]*)add_header[ \t]+Content-Security-Policy', text, re.M)
    indent = indent_m.group(1) if indent_m else "    "
    link_line = f'{indent}add_header Link "{link}" always;'
    if pat_link.search(text):
        text2, n = re.subn(
            r'^[ \t]*add_header[ \t]+Link[ \t]+".*?"[ \t]*(?:always)?;[ \t]*$',
            link_line,
            text,
            flags=re.M,
        )
        if n:
            path.write_text(text2, encoding="utf-8")
            print(f"✅ refreshed Link in {path} ({n})")
            changed += 1
        continue
    text2, n = pat_csp.subn(r"\1\n" + link_line, text)
    if n:
        path.write_text(text2, encoding="utf-8")
        print(f"✅ inserted Link after CSP in {path} ({n})")
        changed += 1
print(f"link_header_files={changed}")
PY

# 2) Include rewrite/types snippet in the public server if missing.
mapfile -t TARGETS < <(
  grep -rl --include='*.conf' 'pepperoni.tatar' /etc/nginx 2>/dev/null || true
)
for conf in "${TARGETS[@]}"; do
  if grep -q 'pepperoni-agent-discovery.conf' "$conf"; then
    echo "· snippet already included in $conf"
    continue
  fi
  if ! grep -q 'server_name' "$conf"; then
    continue
  fi
  cp -a "$conf" "${conf}.bak.agent.$(date +%Y%m%d%H%M%S)"
  python3 - "$conf" "$INCLUDE_LINE" <<'PY'
import re, sys
path, include = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
pat = re.compile(r'(server\s*\{)', re.M)
if not pat.search(text):
    sys.exit(0)
new, n = pat.subn(r'\1\n    ' + include, text, count=1)
if n == 1:
    open(path, "w", encoding="utf-8").write(new)
    print(f"✅ included snippet in {path}")
PY
done

if ! nginx -t; then
  echo "❌ nginx -t failed — restoring .bak.agent.*"
  for conf in "${TARGETS[@]}"; do
    last=$(ls -1t "${conf}".bak.agent.* 2>/dev/null | head -1 || true)
    [[ -n "$last" ]] && cp -a "$last" "$conf" && echo "  restored $conf"
  done
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
  echo "$hdrs" | head -20
  fail=1
fi
md=$(curl -sI --max-time 5 -H 'Host: pepperoni.tatar' -H 'Accept: text/markdown' \
  --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar/" | tr -d '\r')
if echo "$md" | grep -qi '^content-type:.*text/markdown'; then
  echo "✅ markdown negotiation"
else
  echo "⚠️ markdown negotiation not on yet (Link still counts)"
fi
exit "$fail"
