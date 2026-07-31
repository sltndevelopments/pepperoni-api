#!/usr/bin/env bash
# Replace the live Content-Security-Policy add_header on the VPS with the
# canonical snippet from the repo. Without youtube in frame-src the /pepperoni
# video iframes are blocked by the browser («Этот контент заблокирован»).
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SNIPPET="$REPO/deploy/nginx/security-headers.csp.snippet"

if [[ ! -f "$SNIPPET" ]]; then
  echo "❌ snippet missing: $SNIPPET"
  exit 1
fi

# Extract the full add_header line (single line expected).
NEW_LINE=$(grep -E '^add_header Content-Security-Policy' "$SNIPPET" | head -1)
if [[ -z "$NEW_LINE" ]]; then
  echo "❌ no add_header Content-Security-Policy line in snippet"
  exit 1
fi

mapfile -t TARGETS < <(
  grep -rl --include='*.conf' 'Content-Security-Policy' /etc/nginx 2>/dev/null || true
)

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  echo "❌ no nginx conf containing Content-Security-Policy under /etc/nginx"
  exit 1
fi

changed=0
for conf in "${TARGETS[@]}"; do
  if grep -q 'Content-Security-Policy' "$conf"; then
    # Backup once per run.
    cp -a "$conf" "${conf}.bak.csp.$(date +%Y%m%d%H%M%S)"
    # Replace every CSP add_header line with the canonical one.
    # Keep indentation of the first match.
    indent=$(grep -m1 'Content-Security-Policy' "$conf" | sed -E 's/^([[:space:]]*).*/\1/')
    python3 - "$conf" "$NEW_LINE" "$indent" <<'PY'
import re, sys
path, newline, indent = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
# Match whole add_header ... Content-Security-Policy ... ; line (possibly wrapped? keep single-line)
pat = re.compile(
    r'^[ \t]*add_header[ \t]+Content-Security-Policy[ \t]+".*?"[ \t]*(?:always)?;[ \t]*$',
    re.M,
)
repl = indent + newline.rstrip()
new, n = pat.subn(repl, text)
if n == 0:
    # Fallback: replace the header value only inside quotes.
    pat2 = re.compile(
        r'(add_header[ \t]+Content-Security-Policy[ \t]+")([^"]*)(")',
        re.M,
    )
    # Extract value from newline: add_header Content-Security-Policy "VALUE" always;
    m = re.search(r'Content-Security-Policy\s+"(.*?)"', newline)
    if not m:
        sys.exit("could not parse CSP value from snippet")
    value = m.group(1)
    new, n = pat2.subn(r'\1' + value + r'\3', text)
if n == 0:
    sys.exit(f"no CSP line replaced in {path}")
open(path, "w", encoding="utf-8").write(new)
print(f"✅ updated {path} ({n} occurrence(s))")
PY
    changed=$((changed + 1))
  fi
done

if [[ "$changed" -eq 0 ]]; then
  echo "❌ nothing updated"
  exit 1
fi

nginx -t
systemctl reload nginx
echo "✅ nginx reloaded with YouTube-capable CSP"

# Prove the live header allows YouTube on BOTH the RU hub (snippet location)
# and a locale path that only gets the server-level add_header (sites-enabled).
# Earlier bug: snippet was patched, sites-enabled was not → /az/pepperoni still blocked.
fail=0
for path in /pepperoni /az/pepperoni /kk/pepperoni /uz/pepperoni; do
  live=$(curl -sI --max-time 5 -H 'Host: pepperoni.tatar' \
    --resolve pepperoni.tatar:443:127.0.0.1 "https://pepperoni.tatar${path}" 2>/dev/null \
    | tr -d '\r' | grep -i '^content-security-policy:' || true)
  frame=$(echo "$live" | grep -oE 'frame-src[^;]+' | head -1 || true)
  if echo "$live" | grep -q 'youtube-nocookie.com'; then
    echo "✅ ${path}: ${frame}"
  else
    echo "❌ ${path}: youtube-nocookie.com missing (frame-src=${frame:-none})"
    fail=1
  fi
done
if [[ "$fail" -ne 0 ]]; then
  echo "⚠️  CSP apply incomplete — locale pages may still block YouTube iframes"
  exit 1
fi
