#!/usr/bin/env bash
# One-shot installer to enable AI-bot logging on the api.pepperoni.tatar VPS.
#
# Run on the VPS as root:
#   sudo bash /opt/pepperoni-api/infra/scripts/install-ai-bots-logging.sh
#
# Safe to re-run: it overwrites files but does NOT modify your main
# nginx server block — you must include the snippet manually in the
# server { ... } that handles api.pepperoni.tatar.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing nginx snippet for AI-bot logging"
install -D -m 0644 "${ROOT}/nginx/ai-bots-logging.conf" \
    /etc/nginx/snippets/ai-bots-logging.conf

echo "==> Installing logrotate policy"
install -D -m 0644 "${ROOT}/nginx/logrotate-ai-bots" \
    /etc/logrotate.d/nginx-ai-bots

echo "==> Pre-creating log file with correct ownership"
touch /var/log/nginx/ai-bots.log
chown www-data:adm /var/log/nginx/ai-bots.log
chmod 0640 /var/log/nginx/ai-bots.log

echo "==> Installing parser script"
install -D -m 0755 "${ROOT}/scripts/parse-ai-bots.py" \
    /opt/pepperoni-api/infra/scripts/parse-ai-bots.py

echo "==> Installing daily cron job"
cat > /etc/cron.d/pepperoni-ai-bots <<'CRON'
# /etc/cron.d/pepperoni-ai-bots — daily AI-bot digest at 06:05 server time
MAILTO=""
5 6 * * * root /usr/bin/python3 /opt/pepperoni-api/infra/scripts/parse-ai-bots.py > /var/log/nginx/parse-ai-bots.cron 2>&1
CRON

echo "==> Validating nginx snippet (will fail nginx -t if a server block already includes it)"
nginx -t

cat <<HINT

------------------------------------------------------------
INSTALL DONE.

Next, edit your api.pepperoni.tatar server block (typically
/etc/nginx/sites-enabled/api.pepperoni.tatar.conf) and add ONE LINE
inside the server { ... } block:

    include snippets/ai-bots-logging.conf;

Then reload nginx:

    nginx -t && systemctl reload nginx

Daily digest will land at:
    /var/log/nginx/ai-bots-digest-YYYY-MM-DD.md
    /var/log/nginx/ai-bots-digest-latest.md  (symlink)

Trigger a manual digest right now:
    python3 /opt/pepperoni-api/infra/scripts/parse-ai-bots.py --today
------------------------------------------------------------
HINT
