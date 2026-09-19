#!/usr/bin/env bash
# Install the generated 301/410 policy and reload nginx atomically.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SITE="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"
SNIPPETS="/etc/nginx/snippets"

if [[ ! -f "$SITE" ]]; then
  echo "missing nginx site: $SITE" >&2
  exit 1
fi

for name in \
  jerky-redirects.conf karmin-e120-redirects.conf \
  pepperoni-blog-redirects.conf \
  geo-cleanup-redirects.conf geo-cleanup-gone.conf \
  en-geo-cleanup-redirects.conf en-geo-cleanup-gone.conf \
  trust-reset-redirects.conf trust-reset-gone.conf
do
  src="$REPO/deploy/nginx/$name"
  if [[ ! -f "$src" ]]; then
    echo "missing generated snippet: $src" >&2
    exit 1
  fi
  install -m 0644 "$src" "$SNIPPETS/$name"
done

backup="$(mktemp)"
cp -a "$SITE" "$backup"

python3 - "$SITE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
names = [
    "jerky-redirects.conf",
    "karmin-e120-redirects.conf",
    "pepperoni-blog-redirects.conf",
    "geo-cleanup-redirects.conf",
    "geo-cleanup-gone.conf",
    "en-geo-cleanup-redirects.conf",
    "en-geo-cleanup-gone.conf",
    "trust-reset-redirects.conf",
    "trust-reset-gone.conf",
]
remove = {*names, "test1-noindex.conf"}
lines = [
    line for line in text.splitlines()
    if not any(f"/etc/nginx/snippets/{name}" in line for name in remove)
]
marker = next(
    (i for i, line in enumerate(lines)
     if "/etc/nginx/snippets/pepperoni-halyal-redirects.conf" in line),
    None,
)
if marker is None:
    raise SystemExit("pepperoni HTTPS include marker not found")
indent = lines[marker][:len(lines[marker]) - len(lines[marker].lstrip())]
block = [f"{indent}include /etc/nginx/snippets/{name};" for name in names]
lines[marker + 1:marker + 1] = block
path.write_text("\n".join(lines) + "\n")
PY

if ! nginx -t; then
  cp -a "$backup" "$SITE"
  rm -f "$backup"
  nginx -t || true
  echo "nginx trust-reset install rolled back" >&2
  exit 1
fi

rm -f "$backup"
systemctl reload nginx
echo "OK: trust-reset redirects and 410 policy installed"
