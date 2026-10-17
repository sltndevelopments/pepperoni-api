#!/usr/bin/env bash
# Install the generated 301/410 policy and reload nginx atomically.
# Snippet list is scripts/index_safety.py::NGINX_INSTALL (single source).
# pepperoni-halyal-redirects.conf is copied here and kept as the one include
# marker — do not insert a second include of that file.
#
# SITE may be a symlink (sites-enabled → sites-available). Backup and restore
# the real file via readlink -f and cp -aL so rollback cannot replace the
# symlink with a regular file.
set -euo pipefail

REPO="${1:-/var/www/pepperoni/repo}"
SITE="${NGINX_SITE:-/etc/nginx/sites-enabled/pepperoni.tatar}"
SNIPPETS="/etc/nginx/snippets"

resolve_site() {
  readlink -f "$1"
}

copy_site_file() {
  cp -aL "$1" "$2"
}

if [[ "${1:-}" == "--symlink-rollback-test" ]]; then
  work="${2:?}"
  site="$work/site"
  real="$(resolve_site "$site")"
  bak="$work/backup-site"
  copy_site_file "$real" "$bak"
  printf 'CHANGED\n' > "$real"
  copy_site_file "$bak" "$real"
  if [[ ! -L "$site" ]]; then
    echo "symlink-rollback-test: site is no longer a symlink" >&2
    exit 1
  fi
  if [[ "$(resolve_site "$site")" != "$real" ]]; then
    echo "symlink-rollback-test: symlink target changed" >&2
    exit 1
  fi
  if [[ "$(cat "$real")" != "$(cat "$bak")" ]]; then
    echo "symlink-rollback-test: real file not restored" >&2
    exit 1
  fi
  echo "OK: symlink rollback restored the real file"
  exit 0
fi

SITE_REAL="$(resolve_site "$SITE")"
if [[ ! -f "$SITE_REAL" ]]; then
  echo "missing nginx site: $SITE" >&2
  exit 1
fi

# Refuse to install a snippet that would 301 or 410 an allowlisted URL.
if ! python3 "$REPO/scripts/index_safety.py" --check-nginx-install; then
  echo "refusing to install nginx snippets: a keep URL would receive 301 or 410" >&2
  exit 1
fi

mapfile -t INSTALL_NAMES < <(python3 -c "import sys; sys.path.insert(0, '$REPO/scripts'); from index_safety import NGINX_INSTALL; print('\n'.join(NGINX_INSTALL))")
if [[ ${#INSTALL_NAMES[@]} -eq 0 ]]; then
  echo "empty NGINX_INSTALL" >&2
  exit 1
fi

backup_dir="$(mktemp -d)"
cleanup() { rm -rf "$backup_dir"; }
trap cleanup EXIT
copy_site_file "$SITE_REAL" "$backup_dir/site"
copied=0

rollback() {
  if [[ -f "$backup_dir/site" ]]; then
    copy_site_file "$backup_dir/site" "$SITE_REAL"
  fi
  if [[ "$copied" -eq 1 ]]; then
    for name in "${INSTALL_NAMES[@]}"; do
      if [[ -f "$backup_dir/$name" ]]; then
        cp -a "$backup_dir/$name" "$SNIPPETS/$name"
      else
        rm -f "$SNIPPETS/$name"
      fi
    done
  fi
}

for name in "${INSTALL_NAMES[@]}"; do
  src="$REPO/deploy/nginx/$name"
  if [[ ! -f "$src" ]]; then
    echo "missing generated snippet: $src" >&2
    exit 1
  fi
  if [[ -f "$SNIPPETS/$name" ]]; then
    cp -a "$SNIPPETS/$name" "$backup_dir/$name"
  fi
  install -m 0644 "$src" "$SNIPPETS/$name"
  copied=1
done

if ! python3 - "$REPO" "$SITE_REAL" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from index_safety import patch_site_includes

path = Path(sys.argv[2])
path.write_text(patch_site_includes(path.read_text(encoding="utf-8")), encoding="utf-8")
PY
then
  rollback
  echo "nginx trust-reset include patch rolled back" >&2
  exit 1
fi

if ! nginx -t; then
  rollback
  nginx -t || true
  echo "nginx trust-reset install rolled back" >&2
  exit 1
fi

systemctl reload nginx
echo "OK: trust-reset redirects and 410 policy installed"
