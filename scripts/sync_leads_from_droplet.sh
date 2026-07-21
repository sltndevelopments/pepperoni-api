#!/usr/bin/env bash
# Pull leads.json from the leadbot droplet (MTProto userbot lives there because
# Telegram MTProto is network-blocked from this Selectel VPS). The droplet is
# the single source of truth for leads; we mirror its file into the repo so the
# brain digest (lead_listener.digest) reads real leads. Idempotent, atomic.
set -euo pipefail
DROPLET="root@178.62.250.104"
SRC="/opt/leadbot/data/leads.json"
DST="/var/www/pepperoni/repo/data/leads.json"
TMP="$(mktemp)"
if scp -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new "$DROPLET:$SRC" "$TMP" 2>/dev/null; then
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$TMP"  # validate
  mv "$TMP" "$DST"
  echo "leads synced: $(python3 -c "import json;print(len(json.load(open('$DST'))['leads']))") leads"
else
  rm -f "$TMP"; echo "leads sync failed (droplet unreachable)"; exit 1
fi
