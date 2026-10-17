#!/usr/bin/env bash
# One-time VPS cleanup. Public logs: counts and OK/ABORT only.
# Paths may appear in this file. Do not print filenames, file contents,
# env values, crontab text, or unit names.
set -euo pipefail

MODE="${MODE:-${1:-dry-run}}"
if [[ "$MODE" != "dry-run" && "$MODE" != "apply" ]]; then
  echo "vps-cleanup: mode must be dry-run or apply" >&2
  exit 1
fi

REPO="${REPO:-/var/www/pepperoni/repo}"
LOCK_FILE="${LOCK_FILE:-/var/www/pepperoni/repo/data/sync.lock}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/pepperoni}"
CRON_D="${CRON_D:-/etc/cron.d}"
ETC_PEPPERONI="${ETC_PEPPERONI:-/etc/pepperoni}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
CRON_SPOOL="${CRON_SPOOL:-/var/spool/cron/crontabs}"
SUPERVISOR_DIR="${SUPERVISOR_DIR:-/etc/supervisor}"
ROOT_CONFIG="${ROOT_CONFIG:-/root/.config}"
OLD_ROOT="${OLD_ROOT:-/opt/pepperoni-api}"
MCP_SRC="${MCP_SRC:-$REPO/deploy/rinatsultan-mcp.env}"
MCP_DST="${MCP_DST:-$ETC_PEPPERONI/rinatsultan-mcp.env}"
AI_BOTS_CRON="${AI_BOTS_CRON:-$CRON_D/pepperoni-ai-bots}"
LOG_CRON="${LOG_CRON:-$CRON_D/pepperoni-log-retention}"
LOG_CRON_LINE='17 4 * * * root find /var/www/pepperoni/repo/data/logs -type f -mtime +30 -delete'
PARSE_AI_BOTS="$REPO/infra/scripts/parse-ai-bots.py"
OLD_MCP_PATH="$REPO/deploy/rinatsultan-mcp.env"
NEW_MCP_PATH="/etc/pepperoni/rinatsultan-mcp.env"
OLD_REPO_PREFIX="/opt/pepperoni-api/"
NEW_REPO_PREFIX="/var/www/pepperoni/repo/"

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -w 900 9; then
  echo "vps-cleanup: lock wait failed" >&2
  exit 1
fi

item_n=(0 0 0 0 0 0 0 0)
item_b=(0 0 0 0 0 0 0 0)
item_st=("OK" "OK" "OK" "OK" "OK" "OK" "OK" "OK")
backup_paths=()

add_file() {
  local idx="$1" path="$2"
  if [[ -f "$path" ]]; then
    item_n[idx]=$(( ${item_n[idx]} + 1 ))
    item_b[idx]=$(( ${item_b[idx]} + $(stat -c %s "$path") ))
    backup_paths+=("$path")
  fi
}

collect_1() {
  local p="$REPO/scripts/_wtest"
  if [[ -f "$p" && ! -s "$p" ]]; then
    add_file 1 "$p"
  fi
}

collect_2() {
  local d="$REPO/data/tmp"
  [[ -d "$d" ]] || return 0
  local p
  while IFS= read -r -d '' p; do
    if [[ -f "$p" ]]; then
      add_file 2 "$p"
    elif [[ -e "$p" ]]; then
      item_n[2]=$(( ${item_n[2]} + 1 ))
    fi
  done < <(find "$d" -mindepth 1 -print0 2>/dev/null || true)
}

collect_3() {
  local d="$REPO/data/quarantine"
  [[ -d "$d" ]] || return 0
  local p
  while IFS= read -r -d '' p; do
    add_file 3 "$p"
  done < <(find "$d" -type f -mtime +30 -print0 2>/dev/null || true)
}

collect_4() {
  local d="$REPO/sales-agent/data"
  [[ -d "$d" ]] || return 0
  local p
  while IFS= read -r -d '' p; do
    add_file 4 "$p"
  done < <(find "$d" -maxdepth 1 -type f \( -name 'agent.bak.*.db' -o -name 'agent.db.backup-*' \) -print0 2>/dev/null || true)
}

collect_5() {
  local d="$REPO/data/logs"
  if [[ -d "$d" ]]; then
    local p
    while IFS= read -r -d '' p; do
      add_file 5 "$p"
    done < <(find "$d" -type f -mtime +30 -print0 2>/dev/null || true)
  fi
  if [[ ! -f "$LOG_CRON" ]] || ! cmp -s "$LOG_CRON" <(printf '%s\n' "$LOG_CRON_LINE"); then
    item_n[5]=$(( ${item_n[5]} + 1 ))
    item_b[5]=$(( ${item_b[5]} + ${#LOG_CRON_LINE} + 1 ))
    if [[ -f "$LOG_CRON" ]]; then
      backup_paths+=("$LOG_CRON")
    fi
  fi
}

collect_6() {
  if [[ -f "$MCP_SRC" ]]; then
    add_file 6 "$MCP_SRC"
  fi
  if [[ -f "$MCP_DST" ]]; then
    backup_paths+=("$MCP_DST")
  fi
  local dir p
  for dir in "$SYSTEMD_DIR" "$CRON_D" "$CRON_SPOOL" "$SUPERVISOR_DIR" "$ROOT_CONFIG"; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r -d '' p; do
      add_file 6 "$p"
    done < <(grep -rlFZ -- "$OLD_MCP_PATH" "$dir" 2>/dev/null || true)
  done
}

collect_7() {
  if [[ ! -f "$PARSE_AI_BOTS" ]]; then
    item_st[7]="ABORT"
    return 0
  fi
  if [[ -f "$AI_BOTS_CRON" ]]; then
    backup_paths+=("$AI_BOTS_CRON")
    if grep -qF -- "$OLD_REPO_PREFIX" "$AI_BOTS_CRON"; then
      add_file 7 "$AI_BOTS_CRON"
    fi
  fi
}

print_counts() {
  local i
  for i in 1 2 3 4 5 6 7; do
    echo "${i}: ${item_n[i]} files, ${item_b[i]} bytes"
  done
}

print_status() {
  local i
  for i in 1 2 3 4 5 6 7; do
    echo "${i}: ${item_st[i]}"
  done
  if [[ -e "$OLD_ROOT" ]]; then
    echo "exists=yes"
  else
    echo "exists=no"
  fi
}

unique_backup_paths() {
  local p seen=""
  local -a out=()
  for p in "${backup_paths[@]+"${backup_paths[@]}"}"; do
    [[ -f "$p" ]] || continue
    case " $seen " in
      *" $p "*) continue ;;
    esac
    seen+=" $p"
    out+=("$p")
  done
  backup_paths=("${out[@]+"${out[@]}"}")
}

collect_cron_globs() {
  local p
  shopt -s nullglob
  for p in "$CRON_D"/pepperoni-*; do
    [[ -f "$p" ]] && backup_paths+=("$p")
  done
  shopt -u nullglob
}

crontab_dump_count() {
  local n=0 owner
  if crontab -l >/dev/null 2>&1; then
    n=$(( n + 1 ))
  fi
  owner="$(stat -c %U "$REPO" 2>/dev/null || true)"
  if [[ -n "$owner" ]] && crontab -u "$owner" -l >/dev/null 2>&1; then
    n=$(( n + 1 ))
  fi
  echo "$n"
}

write_crontab_dumps() {
  local dest="$1" owner
  if crontab -l >"$dest/crontab-root" 2>/dev/null; then
    backup_paths+=("$dest/crontab-root")
  else
    rm -f "$dest/crontab-root"
  fi
  owner="$(stat -c %U "$REPO" 2>/dev/null || true)"
  if [[ -n "$owner" ]] && crontab -u "$owner" -l >"$dest/crontab-owner" 2>/dev/null; then
    backup_paths+=("$dest/crontab-owner")
  else
    rm -f "$dest/crontab-owner"
  fi
}

do_backup() {
  local stamp dest list n got work
  work="$(mktemp -d)"
  write_crontab_dumps "$work"
  unique_backup_paths
  list="$work/list"
  : >"$list"
  local p
  for p in "${backup_paths[@]+"${backup_paths[@]}"}"; do
    [[ -f "$p" ]] || continue
    printf '%s\n' "$p" >>"$list"
  done
  n="$(wc -l <"$list" | tr -d ' ')"
  mkdir -p -m 700 "$BACKUP_DIR" || return 1
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$BACKUP_DIR/cleanup-${stamp}.tar.gz"
  if [[ "$n" -eq 0 ]]; then
    if ! tar czf "$dest" -C "$work" --files-from /dev/null 2>/dev/null; then
      rm -rf "$work"
      return 1
    fi
  else
    if ! tar czf "$dest" -T "$list" 2>/dev/null; then
      rm -rf "$work"
      return 1
    fi
  fi
  chmod 600 "$dest"
  if ! gzip -t "$dest" 2>/dev/null; then
    rm -rf "$work"
    return 1
  fi
  got="$(tar tzf "$dest" 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$got" != "$n" ]]; then
    rm -rf "$work"
    return 1
  fi
  echo "backup: $(stat -c %s "$dest") bytes"
  rm -rf "$work"
  return 0
}

apply_1() {
  local p="$REPO/scripts/_wtest"
  if [[ -f "$p" && ! -s "$p" ]]; then
    rm -f "$p"
  fi
}

apply_2() {
  local d="$REPO/data/tmp"
  [[ -d "$d" ]] || return 0
  find "$d" -mindepth 1 -delete
}

apply_3() {
  local d="$REPO/data/quarantine"
  [[ -d "$d" ]] || return 0
  find "$d" -type f -mtime +30 -delete
}

apply_4() {
  local d="$REPO/sales-agent/data"
  [[ -d "$d" ]] || return 0
  find "$d" -maxdepth 1 -type f \( -name 'agent.bak.*.db' -o -name 'agent.db.backup-*' \) -delete
}

apply_5() {
  local d="$REPO/data/logs"
  if [[ -d "$d" ]]; then
    find "$d" -type f -mtime +30 -delete
  fi
  printf '%s\n' "$LOG_CRON_LINE" >"$LOG_CRON"
  chmod 644 "$LOG_CRON"
}

apply_6() {
  if [[ -f "$MCP_SRC" ]]; then
    mkdir -p -m 700 "$ETC_PEPPERONI"
    install -m 600 "$MCP_SRC" "$MCP_DST"
    if ! cmp -s "$MCP_SRC" "$MCP_DST"; then
      item_st[6]="ABORT"
      return 0
    fi
    rm -f "$MCP_SRC"
  fi
  local dir p restarted=0
  local -a units=()
  for dir in "$SYSTEMD_DIR" "$CRON_D" "$CRON_SPOOL" "$SUPERVISOR_DIR" "$ROOT_CONFIG"; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r -d '' p; do
      sed -i "s|${OLD_MCP_PATH}|${NEW_MCP_PATH}|g" "$p"
      if [[ "$p" == "$SYSTEMD_DIR"/* ]]; then
        units+=("$(basename "$p")")
      fi
    done < <(grep -rlFZ -- "$OLD_MCP_PATH" "$dir" 2>/dev/null || true)
  done
  if [[ ${#units[@]} -gt 0 ]]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    local u
    for u in "${units[@]}"; do
      if systemctl restart "$u" >/dev/null 2>&1; then
        restarted=$(( restarted + 1 ))
      fi
    done
  fi
  : "$restarted"
}

apply_7() {
  if [[ "${item_st[7]}" == "ABORT" ]]; then
    return 0
  fi
  if [[ -f "$AI_BOTS_CRON" ]]; then
    sed -i "s|${OLD_REPO_PREFIX}|${NEW_REPO_PREFIX}|g" "$AI_BOTS_CRON"
  fi
}

collect_1
collect_2
collect_3
collect_4
collect_5
collect_6
collect_7
unique_backup_paths
collect_cron_globs
unique_backup_paths

print_counts
planned="${#backup_paths[@]}"
planned=$(( planned + $(crontab_dump_count) ))

if [[ "$MODE" != "apply" ]]; then
  echo "backup would include ${planned} files"
  print_status
  exit 0
fi

if ! do_backup; then
  echo "backup failed, no changes" >&2
  exit 1
fi

apply_1
apply_2
apply_3
apply_4
apply_5
apply_6
apply_7

item_n=(0 0 0 0 0 0 0 0)
item_b=(0 0 0 0 0 0 0 0)
backup_paths=()
collect_1
collect_2
collect_3
collect_4
collect_5
collect_6
collect_7
print_counts
print_status
