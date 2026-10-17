#!/usr/bin/env bash
# One-time VPS cleanup. Public logs: counts and OK/ABORT only.
# Paths may appear in this file. Do not print filenames, file contents,
# env values, crontab text, or unit names.
set -euo pipefail
umask 077

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

if [[ ! -e "$LOCK_FILE" ]]; then
  echo "lock missing" >&2
  exit 1
fi
exec 9<"$LOCK_FILE"
if ! flock -w 900 9; then
  echo "vps-cleanup: lock wait failed" >&2
  exit 1
fi

item_n=(0 0 0 0 0 0 0 0)
item_b=(0 0 0 0 0 0 0 0)
item_st=("OK" "OK" "OK" "OK" "OK" "OK" "OK" "OK")
backup_paths=()
delete_paths=()

entry_size() {
  local path="$1"
  if [[ -L "$path" ]]; then
    stat -c %s "$path" 2>/dev/null || echo 0
  elif [[ -f "$path" ]]; then
    stat -c %s "$path"
  else
    echo 0
  fi
}

add_backup() {
  local path="$1"
  if [[ -e "$path" || -L "$path" ]]; then
    backup_paths+=("$path")
  fi
}

add_delete() {
  local idx="$1" path="$2"
  if [[ -e "$path" || -L "$path" ]]; then
    item_n[idx]=$(( ${item_n[idx]} + 1 ))
    item_b[idx]=$(( ${item_b[idx]} + $(entry_size "$path") ))
    backup_paths+=("$path")
    delete_paths+=("$path")
  fi
}

collect_1() {
  local p="$REPO/scripts/_wtest"
  if [[ -e "$p" || -L "$p" ]]; then
    if [[ -f "$p" && ! -s "$p" ]]; then
      add_delete 1 "$p"
    elif [[ -L "$p" && ! -s "$p" ]]; then
      add_delete 1 "$p"
    fi
  fi
}

collect_2() {
  local d="$REPO/data/tmp"
  [[ -d "$d" ]] || return 0
  local p
  while IFS= read -r -d '' p; do
    if [[ -d "$p" && ! -L "$p" ]]; then
      continue
    fi
    add_delete 2 "$p"
  done < <(find "$d" -mindepth 1 -print0 2>/dev/null || true)
}

collect_3() {
  local d="$REPO/data/quarantine"
  [[ -d "$d" ]] || return 0
  local p
  while IFS= read -r -d '' p; do
    add_delete 3 "$p"
  done < <(find "$d" \( -type f -o -type l \) -mtime +30 -print0 2>/dev/null || true)
}

collect_4() {
  local d="$REPO/sales-agent/data"
  [[ -d "$d" ]] || return 0
  local p
  while IFS= read -r -d '' p; do
    add_delete 4 "$p"
  done < <(find "$d" -maxdepth 1 \( -type f -o -type l \) \( -name 'agent.bak.*.db' -o -name 'agent.db.backup-*' \) -print0 2>/dev/null || true)
}

collect_5() {
  local d="$REPO/data/logs"
  if [[ -d "$d" ]]; then
    local p
    while IFS= read -r -d '' p; do
      add_delete 5 "$p"
    done < <(find "$d" \( -type f -o -type l \) -mtime +30 -print0 2>/dev/null || true)
  fi
  if [[ ! -f "$LOG_CRON" ]] || ! cmp -s "$LOG_CRON" <(printf '%s\n' "$LOG_CRON_LINE"); then
    item_n[5]=$(( ${item_n[5]} + 1 ))
    item_b[5]=$(( ${item_b[5]} + ${#LOG_CRON_LINE} + 1 ))
    add_backup "$LOG_CRON"
  fi
}

collect_6() {
  if [[ -e "$MCP_SRC" || -L "$MCP_SRC" ]]; then
    add_delete 6 "$MCP_SRC"
  fi
  add_backup "$MCP_DST"
  local dir p
  for dir in "$SYSTEMD_DIR" "$CRON_D" "$CRON_SPOOL" "$SUPERVISOR_DIR" "$ROOT_CONFIG"; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r p; do
      [[ -n "$p" ]] || continue
      item_n[6]=$(( ${item_n[6]} + 1 ))
      item_b[6]=$(( ${item_b[6]} + $(entry_size "$p") ))
      add_backup "$p"
    done < <(grep -RIlF -- "$OLD_MCP_PATH" "$dir" 2>/dev/null || true)
  done
}

collect_7() {
  if [[ ! -f "$PARSE_AI_BOTS" ]]; then
    item_st[7]="ABORT"
    return 0
  fi
  add_backup "$AI_BOTS_CRON"
  if [[ -f "$AI_BOTS_CRON" ]] && grep -qF -- "$OLD_REPO_PREFIX" "$AI_BOTS_CRON"; then
    item_n[7]=$(( ${item_n[7]} + 1 ))
    item_b[7]=$(( ${item_b[7]} + $(entry_size "$AI_BOTS_CRON") ))
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

unique_list() {
  local -n src=$1
  local p seen=""
  local -a out=()
  for p in "${src[@]+"${src[@]}"}"; do
    [[ -e "$p" || -L "$p" ]] || continue
    case " $seen " in
      *" $p "*) continue ;;
    esac
    seen+=" $p"
    out+=("$p")
  done
  src=("${out[@]+"${out[@]}"}")
}

collect_cron_globs() {
  local p
  shopt -s nullglob
  for p in "$CRON_D"/pepperoni-*; do
    add_backup "$p"
  done
  shopt -u nullglob
}

probe_crontab() {
  local out rc
  if ! command -v crontab >/dev/null 2>&1; then
    return 2
  fi
  set +e
  out=$(crontab "$@" -l 2>&1 >/dev/null)
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    return 0
  fi
  if [[ "$out" == *"no crontab"* ]]; then
    return 2
  fi
  return 1
}

crontab_dump_count() {
  local n=0 owner rc
  set +e
  probe_crontab
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    n=$(( n + 1 ))
  elif [[ $rc -ne 2 ]]; then
    return 1
  fi
  owner="$(stat -c %U "$REPO" 2>/dev/null || true)"
  if [[ -n "$owner" ]]; then
    set +e
    probe_crontab -u "$owner"
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      n=$(( n + 1 ))
    elif [[ $rc -ne 2 ]]; then
      return 1
    fi
  fi
  echo "$n"
}

dump_one_crontab() {
  local dest="$1"
  shift
  local out rc
  if ! command -v crontab >/dev/null 2>&1; then
    return 0
  fi
  set +e
  out=$(crontab "$@" -l 2>&1)
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    printf '%s\n' "$out" >"$dest" || return 1
    return 0
  fi
  if [[ "$out" == *"no crontab"* ]]; then
    return 0
  fi
  return 1
}

write_crontab_dumps() {
  local dest="$1" owner
  dump_one_crontab "$dest/crontab-root" || return 1
  if [[ -f "$dest/crontab-root" ]]; then
    backup_paths+=("$dest/crontab-root")
  fi
  owner="$(stat -c %U "$REPO" 2>/dev/null || true)"
  if [[ -n "$owner" ]]; then
    dump_one_crontab "$dest/crontab-owner" -u "$owner" || return 1
    if [[ -f "$dest/crontab-owner" ]]; then
      backup_paths+=("$dest/crontab-owner")
    fi
  fi
  return 0
}

do_backup() {
  local stamp dest tmpdest list n got work p
  work="$(mktemp -d)" || return 1
  write_crontab_dumps "$work" || { rm -rf "$work"; return 1; }
  unique_list backup_paths
  list="$work/list"
  : >"$list" || { rm -rf "$work"; return 1; }
  for p in "${backup_paths[@]+"${backup_paths[@]}"}"; do
    if [[ -e "$p" || -L "$p" ]]; then
      printf '%s\n' "$p" >>"$list" || { rm -rf "$work"; return 1; }
    fi
  done
  n="$(wc -l <"$list" | tr -d ' ')"
  if [[ ! -d "$BACKUP_DIR" ]]; then
    mkdir -m 700 "$BACKUP_DIR" || { rm -rf "$work"; return 1; }
  fi
  chmod 700 "$BACKUP_DIR" || { rm -rf "$work"; return 1; }
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$BACKUP_DIR/cleanup-${stamp}.tar.gz"
  tmpdest="${dest}.tmp"
  if [[ "$n" -eq 0 ]]; then
    tar czf "$tmpdest" -C "$work" --files-from /dev/null 2>/dev/null || { rm -f "$tmpdest"; rm -rf "$work"; return 1; }
  else
    tar czf "$tmpdest" -T "$list" 2>/dev/null || { rm -f "$tmpdest"; rm -rf "$work"; return 1; }
  fi
  chmod 600 "$tmpdest" || { rm -f "$tmpdest"; rm -rf "$work"; return 1; }
  gzip -t "$tmpdest" 2>/dev/null || { rm -f "$tmpdest"; rm -rf "$work"; return 1; }
  got="$(tar tzf "$tmpdest" 2>/dev/null | wc -l | tr -d ' ')" || { rm -f "$tmpdest"; rm -rf "$work"; return 1; }
  if [[ "$got" != "$n" ]]; then
    rm -f "$tmpdest"
    rm -rf "$work"
    return 1
  fi
  mv "$tmpdest" "$dest" || { rm -f "$tmpdest"; rm -rf "$work"; return 1; }
  echo "backup: $(stat -c %s "$dest") bytes"
  rm -rf "$work"
  return 0
}

apply_installs() {
  if [[ ! -f "$LOG_CRON" ]] || ! cmp -s "$LOG_CRON" <(printf '%s\n' "$LOG_CRON_LINE"); then
    printf '%s\n' "$LOG_CRON_LINE" >"$LOG_CRON"
    chmod 644 "$LOG_CRON"
  fi
  if [[ -e "$MCP_SRC" || -L "$MCP_SRC" ]]; then
    if [[ ! -d "$ETC_PEPPERONI" ]]; then
      mkdir -m 700 "$ETC_PEPPERONI"
    fi
    chmod 700 "$ETC_PEPPERONI"
    install -m 600 "$MCP_SRC" "$MCP_DST"
    if ! cmp -s "$MCP_SRC" "$MCP_DST"; then
      item_st[6]="ABORT"
      return 0
    fi
  fi
  local dir p
  local -a units=()
  for dir in "$SYSTEMD_DIR" "$CRON_D" "$CRON_SPOOL" "$SUPERVISOR_DIR" "$ROOT_CONFIG"; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r p; do
      [[ -n "$p" ]] || continue
      sed -i "s|${OLD_MCP_PATH}|${NEW_MCP_PATH}|g" "$p"
      if [[ "$p" == "$SYSTEMD_DIR"/* ]]; then
        units+=("$(basename "$p")")
      fi
    done < <(grep -RIlF -- "$OLD_MCP_PATH" "$dir" 2>/dev/null || true)
  done
  if [[ ${#units[@]} -gt 0 ]]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    local u
    for u in "${units[@]}"; do
      systemctl restart "$u" >/dev/null 2>&1 || true
    done
  fi
  if [[ "${item_st[7]}" != "ABORT" && -f "$AI_BOTS_CRON" ]]; then
    sed -i "s|${OLD_REPO_PREFIX}|${NEW_REPO_PREFIX}|g" "$AI_BOTS_CRON"
  fi
}

apply_delete_manifest() {
  local p
  for p in "${delete_paths[@]+"${delete_paths[@]}"}"; do
    rm -f "$p"
  done
  if [[ -d "$REPO/data/tmp" ]]; then
    find "$REPO/data/tmp" -depth -type d -empty -delete
  fi
}

collect_1
collect_2
collect_3
collect_4
collect_5
collect_6
collect_7
unique_list backup_paths
unique_list delete_paths
collect_cron_globs
unique_list backup_paths

print_counts
planned="${#backup_paths[@]}"
cron_extra="$(crontab_dump_count)" || {
  echo "backup failed, no changes" >&2
  exit 1
}
planned=$(( planned + cron_extra ))

if [[ "$MODE" != "apply" ]]; then
  echo "backup would include ${planned} files"
  print_status
  exit 0
fi

set +e
do_backup
backup_rc=$?
set -e
if [[ "$backup_rc" -ne 0 ]]; then
  echo "backup failed, no changes" >&2
  exit 1
fi

apply_installs
apply_delete_manifest

item_n=(0 0 0 0 0 0 0 0)
item_b=(0 0 0 0 0 0 0 0)
backup_paths=()
delete_paths=()
collect_1
collect_2
collect_3
collect_4
collect_5
collect_6
collect_7
print_counts
print_status
