#!/usr/bin/env bash
# Install origin Agent Readiness bits (Link headers, Markdown Accept, types).
# Safe on DNS-only pepperoni.tatar — does not enable Cloudflare proxy.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
MAP_SRC="$REPO/deploy/nginx/agent-discovery.map.conf"
SNIPPET_SRC="$REPO/deploy/nginx/agent-discovery.snippet"
MAP_DST="/etc/nginx/conf.d/00-pepperoni-agent-map.conf"
SNIPPET_DST="/etc/nginx/snippets/pepperoni-agent-discovery.conf"
INCLUDE_LINE='include snippets/pepperoni-agent-discovery.conf;'

if [[ ! -f "$MAP_SRC" || ! -f "$SNIPPET_SRC" ]]; then
  echo "❌ missing nginx snippets under $REPO/deploy/nginx/"
  exit 1
fi

mkdir -p /etc/nginx/snippets /etc/nginx/conf.d
cp -a "$MAP_SRC" "$MAP_DST"
cp -a "$SNIPPET_SRC" "$SNIPPET_DST"

mapfile -t TARGETS < <(
  grep -rl --include='*.conf' 'server_name' /etc/nginx 2>/dev/null \
    | xargs grep -l 'pepperoni\.tatar' 2>/dev/null || true
)

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "❌ no nginx server conf mentioning pepperoni.tatar"
  exit 1
fi

changed=0
for conf in "${TARGETS[@]}"; do
  if grep -q 'pepperoni-agent-discovery.conf' "$conf"; then
    echo "· already included in $conf"
    continue
  fi
  cp -a "$conf" "${conf}.bak.agent.$(date +%Y%m%d%H%M%S)"
  python3 - "$conf" "$INCLUDE_LINE" <<'PY'
import re, sys
path, include = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
# Insert include after the first server { that looks like the public site.
pat = re.compile(r'(server\s*\{)', re.M)
if not pat.search(text):
    sys.exit(f"no server block in {path}")
new, n = pat.subn(r'\1\n    ' + include, text, count=1)
if n != 1:
    sys.exit(f"failed to insert include in {path}")
open(path, "w", encoding="utf-8").write(new)
print(f"✅ included snippet in {path}")
PY
  changed=$((changed + 1))
done

if ! nginx -t; then
  echo "❌ nginx -t failed — restoring latest .bak.agent.*"
  for conf in "${TARGETS[@]}"; do
    last=$(ls -1t "${conf}".bak.agent.* 2>/dev/null | head -1 || true)
    if [[ -n "$last" ]]; then
      cp -a "$last" "$conf"
      echo "  restored $conf from $last"
    fi
  done
  nginx -t
  exit 1
fi
systemctl reload nginx
echo "✅ nginx reloaded (agent discovery snippet; files updated=$changed)"

fail=0
for spec in \
  "https://pepperoni.tatar/|Link" \
  "https://pepperoni.tatar/.well-known/api-catalog|200" \
  "https://pepperoni.tatar/auth.md|200"; do
  url="${spec%%|*}"
  want="${spec##*|}"
  hdrs=$(curl -sI --max-time 5 -H 'Host: pepperoni.tatar' \
    --resolve pepperoni.tatar:443:127.0.0.1 "$url" 2>/dev/null | tr -d '\r')
  if [[ "$want" == "Link" ]]; then
    if echo "$hdrs" | grep -qi '^link:.*api-catalog'; then
      echo "✅ $url has Link: api-catalog"
    else
      echo "❌ $url missing Link api-catalog"
      fail=1
    fi
  else
    if echo "$hdrs" | grep -q '^HTTP/.* 200'; then
      echo "✅ $url 200"
    else
      echo "❌ $url not 200"
      fail=1
    fi
  fi
done

md=$(curl -sI --max-time 5 -H 'Host: pepperoni.tatar' -H 'Accept: text/markdown' \
  --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar/" 2>/dev/null | tr -d '\r')
if echo "$md" | grep -qi '^content-type:.*text/markdown'; then
  echo "✅ GET / Accept: text/markdown → text/markdown"
else
  echo "❌ markdown negotiation failed"
  echo "$md" | head -15
  fail=1
fi

exit "$fail"
