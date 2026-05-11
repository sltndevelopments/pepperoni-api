#!/bin/bash
# Обновление DNS в Cloudflare для правильной архитектуры:
#   pepperoni.tatar     → Vercel  (HTML/Frontend)
#   www.pepperoni.tatar → Vercel  (HTML/Frontend)
#   api.pepperoni.tatar → VPS     (JSON/API, без изменений)
#
# Использование:
#   export CLOUDFLARE_API_TOKEN="ваш_токен"
#   export CLOUDFLARE_ZONE_ID="zone_id_для_pepperoni.tatar"
#   ./scripts/setup-cloudflare-dns.sh
#
# Zone ID: Cloudflare Dashboard → pepperoni.tatar → Overview → Zone ID (правая колонка)
# API Token: My Profile → API Tokens → Create Token → Edit zone DNS

set -e

TOKEN="${CLOUDFLARE_API_TOKEN:?Укажите CLOUDFLARE_API_TOKEN}"
ZONE="${CLOUDFLARE_ZONE_ID:?Укажите CLOUDFLARE_ZONE_ID}"
VERCEL_CNAME="cname.vercel-dns.com"
VERCEL_IP="76.76.21.21"
VPS_IP="37.9.4.101"

api() { curl -sf -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }

# Получить ID записи по имени и типу
get_record_id() {
  local name="$1" type="$2"
  api "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=$name&type=$type" \
    | python3 -c "import json,sys; rs=json.load(sys.stdin)['result']; print(rs[0]['id'] if rs else '')"
}

upsert_record() {
  local name="$1" type="$2" content="$3"
  local id
  id=$(get_record_id "$name" "$type")
  if [ -n "$id" ]; then
    echo "↻  UPDATE $type $name → $content"
    api -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records/$id" \
      --data "{\"type\":\"$type\",\"name\":\"$name\",\"content\":\"$content\",\"ttl\":1,\"proxied\":false}" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('  OK' if d['success'] else '  ERROR: '+str(d.get('errors')))"
  else
    echo "+  CREATE $type $name → $content"
    api -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" \
      --data "{\"type\":\"$type\",\"name\":\"$name\",\"content\":\"$content\",\"ttl\":1,\"proxied\":false}" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('  OK' if d['success'] else '  ERROR: '+str(d.get('errors')))"
  fi
}

echo "🔧 DNS: pepperoni.tatar → Vercel"
echo ""

# pepperoni.tatar (apex) — A record → Vercel IP
upsert_record "pepperoni.tatar" "A" "$VERCEL_IP"

# www.pepperoni.tatar — CNAME → Vercel
upsert_record "www.pepperoni.tatar" "CNAME" "$VERCEL_CNAME"

# api.pepperoni.tatar — оставляем на VPS (только проверяем)
CURRENT_API=$(api "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=api.pepperoni.tatar&type=A" \
  | python3 -c "import json,sys; rs=json.load(sys.stdin)['result']; print(rs[0]['content'] if rs else 'not found')")
echo ""
echo "✔  api.pepperoni.tatar → $CURRENT_API (VPS, без изменений)"

echo ""
echo "✅ Готово! DNS обновятся за 1–5 минут."
echo ""
echo "Проверить:"
echo "  curl -sI https://pepperoni.tatar/ | grep -E 'HTTP|x-vercel'"
