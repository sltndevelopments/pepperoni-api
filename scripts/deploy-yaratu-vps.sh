#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: deploy-yaratu-vps.sh EXPECTED_SHA

The repository must already be synchronized by the primary VPS deploy.
This script never pulls, resets, commits, pushes, or changes DNS.
EOF
}

[[ $# -eq 1 ]] || {
  usage
  exit 2
}

EXPECTED_INPUT="$1"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${YARATU_REPO_ROOT:-$(cd -- "$SCRIPT_DIR/.." && pwd)}"
DEPLOY_ROOT="${YARATU_DEPLOY_ROOT:-/var/www/yaratu}"
NGINX_SITE="${YARATU_NGINX_SITE:-/etc/nginx/sites-available/yaratu.conf}"
NGINX_ENABLED="${YARATU_NGINX_ENABLED:-/etc/nginx/sites-enabled/yaratu.conf}"
CERTIFICATE="${YARATU_CERTIFICATE:-/etc/letsencrypt/live/yaratu.com/fullchain.pem}"
CERTIFICATE_KEY="${YARATU_CERTIFICATE_KEY:-/etc/letsencrypt/live/yaratu.com/privkey.pem}"

cd -- "$REPO_ROOT"
git fetch origin main --quiet
EXPECTED_SHA="$(git rev-parse --verify "${EXPECTED_INPUT}^{commit}")"
LOCAL_SHA="$(git rev-parse HEAD)"
ORIGIN_SHA="$(git rev-parse origin/main)"

if [[ "$LOCAL_SHA" != "$EXPECTED_SHA" || "$ORIGIN_SHA" != "$EXPECTED_SHA" ]]; then
  echo "Refusing Yaratu deploy: repository is not the expected synchronized main" >&2
  echo "expected=$EXPECTED_SHA local=$LOCAL_SHA origin/main=$ORIGIN_SHA" >&2
  exit 10
fi

if [[ -n "$(git status --porcelain -- \
  yaratu \
  deploy/nginx/yaratu.conf \
  scripts/render-yaratu-nginx.py \
  scripts/deploy-yaratu-vps.sh)" ]]; then
  echo "Refusing Yaratu deploy: Yaratu deployment inputs are dirty" >&2
  git status --short -- \
    yaratu \
    deploy/nginx/yaratu.conf \
    scripts/render-yaratu-nginx.py \
    scripts/deploy-yaratu-vps.sh >&2
  exit 11
fi

for required in "$CERTIFICATE" "$CERTIFICATE_KEY"; do
  [[ -r "$required" ]] || {
    echo "Required TLS file is not readable: $required" >&2
    exit 12
  }
done

mkdir -p -- "$DEPLOY_ROOT/releases"
RELEASE="$DEPLOY_ROOT/releases/$EXPECTED_SHA"
if [[ ! -d "$RELEASE" ]]; then
  BUILD_TMP="$(mktemp -d)"
  trap 'rm -rf -- "${BUILD_TMP:-}" "${RELEASE_TMP:-}"' EXIT
  cp -a -- "$REPO_ROOT/yaratu/." "$BUILD_TMP/"
  (
    cd -- "$BUILD_TMP"
    npm run check
  )
  if ! diff -qr -- "$REPO_ROOT/yaratu/site/dist" "$BUILD_TMP/site/dist"; then
    echo "Refusing Yaratu deploy: committed dist is stale; run npm run build" >&2
    exit 13
  fi
  if find "$BUILD_TMP/site/dist" -type l -print -quit | grep -q .; then
    echo "Refusing Yaratu deploy: generated dist contains a symlink" >&2
    exit 13
  fi
  RELEASE_TMP="$(mktemp -d "$DEPLOY_ROOT/releases/.${EXPECTED_SHA}.XXXXXX")"
  cp -a -- "$BUILD_TMP/site/dist/." "$RELEASE_TMP/"
  (
    cd -- "$RELEASE_TMP"
    find . -type f -not -name '.build-manifest.sha256' -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum > .build-manifest.sha256
  )
  mv -- "$RELEASE_TMP" "$RELEASE"
  rm -rf -- "$BUILD_TMP"
  trap - EXIT
elif [[ ! -f "$RELEASE/.build-manifest.sha256" ]]; then
  echo "Existing release is incomplete: $RELEASE" >&2
  exit 13
elif ! (cd -- "$RELEASE" && sha256sum -c .build-manifest.sha256 >/dev/null); then
  echo "Existing release failed integrity verification: $RELEASE" >&2
  exit 13
fi

RENDERED="$(mktemp)"
BACKUP="$(mktemp)"
CURRENT_OLD="$(readlink "$DEPLOY_ROOT/current" 2>/dev/null || true)"
SITE_EXISTED=0
ENABLED_EXISTED=0
ENABLED_OLD=""
cleanup() {
  rm -f -- "$RENDERED" "$BACKUP"
}
trap cleanup EXIT

python3 "$REPO_ROOT/scripts/render-yaratu-nginx.py" \
  "$REPO_ROOT/deploy/nginx/yaratu.conf" \
  "$RENDERED" \
  --root "$DEPLOY_ROOT/current" \
  --certificate "$CERTIFICATE" \
  --certificate-key "$CERTIFICATE_KEY"

if [[ -e "$NGINX_SITE" ]]; then
  cp -a -- "$NGINX_SITE" "$BACKUP"
  SITE_EXISTED=1
fi
if [[ -e "$DEPLOY_ROOT/current" && ! -L "$DEPLOY_ROOT/current" ]]; then
  echo "Refusing to replace non-symlink: $DEPLOY_ROOT/current" >&2
  exit 16
fi
if [[ -L "$NGINX_ENABLED" ]]; then
  ENABLED_EXISTED=1
  ENABLED_OLD="$(readlink "$NGINX_ENABLED")"
elif [[ -e "$NGINX_ENABLED" ]]; then
  echo "Refusing to replace non-symlink: $NGINX_ENABLED" >&2
  exit 16
fi

rollback() {
  echo "Rolling back Yaratu nginx/current state" >&2
  if (( SITE_EXISTED )); then
    cp -a -- "$BACKUP" "$NGINX_SITE"
  else
    rm -f -- "$NGINX_SITE"
  fi
  if (( ENABLED_EXISTED )); then
    ln -sfn -- "$ENABLED_OLD" "$NGINX_ENABLED"
  else
    rm -f -- "$NGINX_ENABLED"
  fi
  if [[ -n "$CURRENT_OLD" ]]; then
    ln -sfn -- "$CURRENT_OLD" "$DEPLOY_ROOT/current"
  else
    rm -f -- "$DEPLOY_ROOT/current"
  fi
  nginx -t >/dev/null 2>&1 || true
  systemctl reload nginx >/dev/null 2>&1 || true
}

if ! install -D -m 0644 -- "$RENDERED" "$NGINX_SITE" \
  || ! ln -sfn -- "$NGINX_SITE" "$NGINX_ENABLED" \
  || ! ln -sfn -- "$RELEASE" "$DEPLOY_ROOT/current"; then
  rollback
  exit 14
fi

if ! nginx -t; then
  rollback
  exit 14
fi
if ! systemctl reload nginx; then
  rollback
  exit 15
fi

echo "Yaratu deployed: $EXPECTED_SHA"
echo "Release: $RELEASE"
