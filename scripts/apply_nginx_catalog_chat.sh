#!/usr/bin/env bash
# Remove the on-site catalog-chat nginx location. The widget was dropped.
set -euo pipefail

INCLUDE_LINE='include /etc/nginx/snippets/catalog-chat.conf;'
SNIPPET="/etc/nginx/snippets/catalog-chat.conf"
BAK_DIR="/etc/nginx/disabled-vhosts"

mkdir -p "$BAK_DIR"

strip_vhost() {
  local vhost="$1"
  if [[ ! -f "$vhost" ]]; then
    echo "· skip missing $vhost"
    return 0
  fi
  if ! grep -q 'catalog-chat.conf' "$vhost"; then
    echo "· no catalog-chat include in $vhost"
    return 0
  fi
  python3 - "$vhost" <<'PY'
from pathlib import Path
import re, sys
from datetime import datetime, timezone

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
bak = Path("/etc/nginx/disabled-vhosts") / f"{path.name}.bak.rm-catalog-chat.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
bak.write_text(text, encoding="utf-8")
new = re.sub(r"^[ \t]*include /etc/nginx/snippets/catalog-chat.conf;[ \t]*\n+", "", text, flags=re.M)
path.write_text(new, encoding="utf-8")
print(f"✅ removed catalog-chat include from {path}")
PY
}

strip_vhost /etc/nginx/sites-enabled/api.pepperoni.tatar
strip_vhost /etc/nginx/sites-enabled/pepperoni.tatar
strip_vhost /etc/nginx/sites-enabled/pepperoni.tatar.conf

if [[ -f "$SNIPPET" ]]; then
  mv "$SNIPPET" "$BAK_DIR/catalog-chat.conf.$(date +%Y%m%d%H%M%S)"
  echo "✅ moved $SNIPPET out of nginx snippets"
fi

if ! nginx -t; then
  echo "❌ nginx -t failed"
  exit 1
fi
systemctl reload nginx
echo "✅ catalog-chat nginx location removed"
