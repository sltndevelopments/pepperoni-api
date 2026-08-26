#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TMP="$(mktemp -d)"
cleanup() {
  rm -rf -- "$TMP"
}
trap cleanup EXIT

bash -n "$REPO_ROOT/scripts/deploy-yaratu-vps.sh"
python3 -m py_compile "$REPO_ROOT/scripts/render-yaratu-nginx.py"

DIST="$REPO_ROOT/yaratu/site/dist"

for forbidden in internal label; do
  [[ ! -e "$DIST/$forbidden" ]] || {
    echo "FAIL: forbidden path present in dist: $forbidden" >&2
    exit 20
  }
done

python3 - "$DIST" "$REPO_ROOT/yaratu" <<'PY'
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

dist = Path(sys.argv[1])
source = Path(sys.argv[2])
texts = [*dist.rglob("*.html"), *dist.rglob("*.css"), *dist.rglob("*.js")]
pattern = re.compile(r"""(?:src|href)=["']([^"'#]+)|url\(["']?([^"')]+)|fetch\(["']([^"']+)""")
missing = set()
for path in texts:
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        raw = next(group for group in match.groups() if group)
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            continue
        candidate = parsed.path.lstrip("/")
        target = dist / candidate
        exists = target.is_file() or (candidate.endswith("/") and (target / "index.html").is_file())
        if candidate and not exists:
            missing.add(candidate)
if missing:
    raise SystemExit(f"public references missing from dist: {sorted(missing)}")
print("Yaratu public references: OK")
PY

CERT="$TMP/fullchain.pem"
KEY="$TMP/privkey.pem"
if command -v openssl >/dev/null 2>&1; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
    -subj "/CN=yaratu.test" -keyout "$KEY" -out "$CERT" \
    >/dev/null 2>&1
else
  : > "$CERT"
  : > "$KEY"
fi

RENDERED="$TMP/yaratu.conf"
python3 "$REPO_ROOT/scripts/render-yaratu-nginx.py" \
  "$REPO_ROOT/deploy/nginx/yaratu.conf" \
  "$RENDERED" \
  --root "$DIST" \
  --certificate "$CERT" \
  --certificate-key "$KEY"

if grep -q '__YARATU_' "$RENDERED"; then
  echo "FAIL: unrendered nginx placeholder" >&2
  exit 21
fi
if ! grep -Fq 'try_files $uri/index.html $uri =404;' "$RENDERED"; then
  echo "FAIL: clean directory URLs are not mapped to index.html" >&2
  exit 22
fi

if command -v nginx >/dev/null 2>&1 && command -v openssl >/dev/null 2>&1; then
  # GitHub-hosted runners execute this gate without root. Keep the production
  # template unchanged, but validate it on unprivileged ports so modern nginx
  # builds that bind during `nginx -t` do not fail with EACCES.
  python3 - "$RENDERED" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("listen 80;", "listen 8080;")
text = text.replace("listen [::]:80;", "listen [::]:8080;")
text = text.replace("listen 443 ssl;", "listen 8443 ssl;")
text = text.replace("listen [::]:443 ssl;", "listen [::]:8443 ssl;")
path.write_text(text, encoding="utf-8")
PY
  mkdir -p "$TMP/nginx-prefix"
  HARNESS="$TMP/nginx-test.conf"
  cat > "$HARNESS" <<EOF
pid $TMP/nginx.pid;
error_log stderr;
events {}
http {
    access_log off;
    include $RENDERED;
}
EOF
  nginx -t -p "$TMP/nginx-prefix" -c "$HARNESS"
  echo "Yaratu nginx syntax: OK"
else
  echo "Yaratu nginx syntax: SKIP (nginx or openssl unavailable)"
fi

if command -v ruby >/dev/null 2>&1; then
  ruby -e '
    require "yaml"
    ARGV.each { |path| YAML.load_file(path) }
    puts "Yaratu workflow YAML: OK"
  ' \
    "$REPO_ROOT/.github/workflows/deploy-yaratu-vps.yml" \
    "$REPO_ROOT/.github/workflows/yaratu-aio-visibility.yml" \
    "$REPO_ROOT/.github/workflows/yaratu-index.yml"
else
  echo "Yaratu workflow YAML: SKIP (ruby unavailable)"
fi

(
  cp -a -- "$REPO_ROOT/yaratu/." "$TMP/yaratu-build/"
  cd -- "$TMP/yaratu-build"
  npm run check
)

if ! diff -qr -- "$REPO_ROOT/yaratu/site/dist" "$TMP/yaratu-build/site/dist"; then
  echo "FAIL: committed Yaratu dist is stale; run npm run build" >&2
  exit 19
fi

echo "Yaratu infrastructure static tests: OK"
