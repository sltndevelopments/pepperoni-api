#!/usr/bin/env bash
# Read-only snapshot of the Selectel VPS git tree vs origin.
# Writes ONLY under an output directory that must sit outside the repo.
# Inspect only: no index or HEAD mutation, no fetch from origin.
set -euo pipefail

REPO="${REPO_DIR:-/var/www/pepperoni/repo}"
OUT="${1:-/tmp/pepperoni-git-recon}"

if [[ ! -d "$REPO/.git" ]]; then
  echo "vps_git_recon_readonly: $REPO is not a git repo" >&2
  exit 1
fi

# Refuse to write into the working tree (or any path that resolves inside it).
repo_real="$(cd "$REPO" && pwd -P)"
mkdir -p "$OUT"
out_real="$(cd "$OUT" && pwd -P)"
case "$out_real" in
  "$repo_real"|"$repo_real"/*)
    echo "vps_git_recon_readonly: OUTDIR must not be inside $repo_real" >&2
    exit 1
    ;;
esac

rm -rf "$OUT"
mkdir -p "$OUT"
{
  echo "# pepperoni VPS git reconciliation (READ-ONLY)"
  echo "collected_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "repo=$repo_real"
  echo "pwd_at_collect=$(pwd)"
} > "$OUT/meta.txt"

cd "$REPO"

git rev-parse HEAD > "$OUT/HEAD.txt"
git rev-parse --abbrev-ref HEAD > "$OUT/branch.txt"
git status --porcelain=v1 -uall > "$OUT/git-status-porcelain.txt"
git status --porcelain=v1 --ignored -uall > "$OUT/git-status-porcelain-ignored.txt"
git ls-files --others --exclude-standard > "$OUT/untracked.txt"
git ls-files --others --ignored --exclude-standard > "$OUT/ignored.txt"
git diff --stat > "$OUT/git-diff-stat.txt"
git diff --numstat > "$OUT/git-diff-numstat.txt"
git diff --name-only > "$OUT/git-diff-names.txt"

{
  echo "=== crontab -l ==="
  crontab -l 2>&1 || true
  echo
  echo "=== /etc/cron.d (pepperoni / seo / sync) ==="
  if compgen -G "/etc/cron.d/*" > /dev/null; then
    grep -HEn 'pepperoni|sync-vps|seo-agent|seo-worker|seo-agent-vps' /etc/cron.d/* 2>/dev/null || true
  else
    echo "(no /etc/cron.d files)"
  fi
} > "$OUT/crontab.txt"

{
  echo "=== systemctl list-timers --all ==="
  systemctl list-timers --all --no-pager 2>&1 || true
  echo
  echo "=== pepperoni / seo / sync units ==="
  systemctl list-units --type=service --all --no-pager 2>&1 | grep -Ei 'pepperoni|seo-agent|seo-worker|sync-vps' || true
  echo
  echo "=== unit files under /etc/systemd/system ==="
  shopt -s nullglob
  for unit in /etc/systemd/system/pepperoni* /etc/systemd/system/*seo* /etc/systemd/system/*sync*; do
    echo "----- $unit -----"
    # Paths only: do not cat env files that may hold secrets.
    grep -E '^(Description|WorkingDirectory|ExecStart|ExecStartPre|EnvironmentFile)=' "$unit" 2>/dev/null || true
  done
  echo
  echo "=== units whose WorkingDirectory or ExecStart mention the repo ==="
  grep -Rl '/var/www/pepperoni/repo' /etc/systemd/system /lib/systemd/system 2>/dev/null | sort -u || true
} > "$OUT/systemd.txt"

{
  echo "# last-modified times of dirty / untracked / ignored paths"
  echo "# format: mtime_utc  size  path"
  # Paths from porcelain (XY path / rename "old -> new")
  awk '
    {
      line = $0
      sub(/^../, "", line)
      sub(/^ /, "", line)
      if (line ~ / -> /) {
        split(line, a, / -> /)
        print a[2]
      } else {
        print line
      }
    }
  ' "$OUT/git-status-porcelain-ignored.txt" | sed '/^$/d' | sort -u > "$OUT/dirty-paths.txt"
  if [[ ! -s "$OUT/dirty-paths.txt" ]]; then
    echo "(working tree clean)"
  else
    while IFS= read -r rel; do
      if [[ -e "$rel" || -L "$rel" ]]; then
        stat --printf='%y\t%s\t%n\n' "$rel" 2>/dev/null || true
      else
        printf 'MISSING\t-\t%s\n' "$rel"
      fi
    done < "$OUT/dirty-paths.txt"
  fi
} > "$OUT/mtimes.txt"

{
  echo "path_count=$(wc -l < "$OUT/dirty-paths.txt" | tr -d ' ')"
  echo "untracked_count=$(wc -l < "$OUT/untracked.txt" | tr -d ' ')"
  echo "ignored_count=$(wc -l < "$OUT/ignored.txt" | tr -d ' ')"
  echo "modified_tracked_count=$(wc -l < "$OUT/git-diff-names.txt" | tr -d ' ')"
} >> "$OUT/meta.txt"

echo "READ-ONLY report written to $out_real"
ls -la "$out_real"
