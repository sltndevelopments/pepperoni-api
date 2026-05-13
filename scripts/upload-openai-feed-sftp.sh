#!/bin/bash
# Push OpenAI Commerce product snapshot to OpenAI SFTP (optional).
# Spec: https://developers.openai.com/commerce/specs/file-upload/overview
#
# If OPENAI_COMMERCE_SFTP_HOST is unset, exits 0 (no-op). Credentials are never in git.
#
# On the VPS, create /var/www/pepperoni/openai-commerce.env (chmod 600), e.g.:
#   OPENAI_COMMERCE_SFTP_HOST=sftp.example.openai.com
#   OPENAI_COMMERCE_SFTP_USER=your_login
#   OPENAI_COMMERCE_SFTP_REMOTE_PATH=/incoming/pepperoni-products.tsv.gz
#   OPENAI_COMMERCE_SFTP_IDENTITY=/root/.ssh/openai_commerce_ed25519
#   OPENAI_COMMERCE_SFTP_PORT=22
#
# Optional: OPENAI_COMMERCE_ENV=/path/to.env  (default below)
# Optional: OPENAI_COMMERCE_LOCAL_FEED=/var/www/.../public/products-feed-openai.tsv.gz

set -euo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
ENV_FILE="${OPENAI_COMMERCE_ENV:-/var/www/pepperoni/openai-commerce.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${OPENAI_COMMERCE_SFTP_HOST:-}" ]]; then
  echo "[openai-sftp] skip: OPENAI_COMMERCE_SFTP_HOST not set"
  exit 0
fi

if [[ -z "${OPENAI_COMMERCE_SFTP_USER:-}" ]]; then
  echo "[openai-sftp] skip: OPENAI_COMMERCE_SFTP_USER not set" >&2
  exit 0
fi

if [[ -z "${OPENAI_COMMERCE_SFTP_REMOTE_PATH:-}" ]]; then
  echo "[openai-sftp] skip: OPENAI_COMMERCE_SFTP_REMOTE_PATH not set (full path on SFTP server)" >&2
  exit 0
fi

LOCAL="${OPENAI_COMMERCE_LOCAL_FEED:-$REPO_DIR/public/products-feed-openai.tsv.gz}"
if [[ ! -f "$LOCAL" ]]; then
  LOCAL="$REPO_DIR/public/products-feed-openai.csv.gz"
fi
if [[ ! -f "$LOCAL" ]]; then
  echo "[openai-sftp] error: no local gzip feed (run gen-products-feed.py first)" >&2
  exit 1
fi

PORT="${OPENAI_COMMERCE_SFTP_PORT:-22}"
TARGET="${OPENAI_COMMERCE_SFTP_USER}@${OPENAI_COMMERCE_SFTP_HOST}"

SFTP_BASE_OPTS=(
  -oBatchMode=yes
  -oConnectTimeout=30
  -oStrictHostKeyChecking=accept-new
)
if [[ -n "${OPENAI_COMMERCE_SFTP_IDENTITY:-}" ]]; then
  SFTP_BASE_OPTS+=(-i "$OPENAI_COMMERCE_SFTP_IDENTITY")
fi

BATCH="$(mktemp)"
cleanup() { rm -f "$BATCH"; }
trap cleanup EXIT

{
  echo "put $LOCAL $OPENAI_COMMERCE_SFTP_REMOTE_PATH"
  echo "bye"
} >"$BATCH"

echo "[openai-sftp] uploading $(basename "$LOCAL") -> $TARGET:$OPENAI_COMMERCE_SFTP_REMOTE_PATH"
sftp "${SFTP_BASE_OPTS[@]}" -P "$PORT" -b "$BATCH" "$TARGET"
echo "[openai-sftp] OK $(date -Iseconds)"
