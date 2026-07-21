#!/usr/bin/env bash
# Leadbot droplet deploy — pull code from origin/main and restart the userbot.
#
# WHY THIS EXISTS
#   The MTProto lead userbot runs on a DigitalOcean droplet (Telegram MTProto is
#   network-blocked from the Selectel VPS). That droplet is NOT covered by the
#   main deploy-vps.yml GitHub Action, so its copy of lead_listener.py /
#   lead_userbot.py used to drift and had to be scp'd by hand. This script makes
#   the droplet a proper git node: code comes ONLY via `git pull` from main,
#   matching the repo rule "канал доставки кода — только git pull".
#
# INVARIANTS (do not break)
#   - Runtime data is NEVER in git and NEVER touched by a pull:
#       /opt/leadbot/data/leads.json      (persistent lead store)
#       /opt/leadbot/tg-state/            (Telethon session)
#     Inside the clone these are symlinks into /opt/leadbot, so a clean checkout
#     cannot wipe them.
#   - We use `git pull --rebase` and NEVER `reset --hard` (would drop the
#     symlinks / any local safety), per CLAUDE.md §6.
#
# USAGE (run on the droplet, or via VPS jump host):
#   bash /opt/leadbot/repo/infra/scripts/leadbot-droplet-deploy.sh
set -euo pipefail

REPO="/opt/leadbot/repo"
SERVICE="leadbot.service"
DATA_LINK="$REPO/data/leads.json"
DATA_REAL="/opt/leadbot/data/leads.json"
STATE_LINK="$REPO/tg-state"
STATE_REAL="/opt/leadbot/tg-state"

cd "$REPO"

echo "→ pulling origin/main"
git fetch --quiet origin main
git pull --rebase --quiet origin main

# Re-assert the runtime symlinks in case a checkout replaced them with tracked
# placeholders. Idempotent.
if [ ! -L "$DATA_LINK" ]; then
  rm -f "$DATA_LINK"
  ln -s "$DATA_REAL" "$DATA_LINK"
  echo "→ restored data/leads.json symlink"
fi
if [ ! -L "$STATE_LINK" ]; then
  rm -rf "$STATE_LINK"
  ln -s "$STATE_REAL" "$STATE_LINK"
  echo "→ restored tg-state symlink"
fi

echo "→ HEAD now $(git rev-parse --short HEAD)"
echo "→ restarting $SERVICE"
systemctl restart "$SERVICE"
sleep 3
state="$(systemctl is-active "$SERVICE" || true)"
echo "→ $SERVICE: $state"
[ "$state" = "active" ] || { echo "✖ service not active after deploy"; exit 1; }
echo "✓ leadbot deploy done"
