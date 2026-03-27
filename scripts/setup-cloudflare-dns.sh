#!/bin/bash
# Настройка DNS в Cloudflare для pepperoni.tatar
# Использование:
#   export CLOUDFLARE_API_TOKEN="ваш_токен"
#   export CLOUDFLARE_ZONE_ID="zone_id_для_pepperoni.tatar"
#   ./scripts/setup-cloudflare-dns.sh
#
# Zone ID: Cloudflare Dashboard → pepperoni.tatar → Overview → Zone ID (справа)
# API Token: My Profile → API Tokens → Create Token (Edit zone DNS)

set -e

TOKEN="${CLOUDFLARE_API_TOKEN:?Set CLOUDFLARE_API_TOKEN}"
ZONE="${CLOUDFLARE_ZONE_ID:?Set CLOUDFLARE_ZONE_ID}"
VERCEL_TARGET="d1e2847508378433.vercel-dns-017.com"

echo "🔧 Настройка DNS для pepperoni.tatar..."

# www.pepperoni.tatar → CNAME
echo "Добавляю www.pepperoni.tatar (CNAME)..."
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"CNAME\",\"name\":\"www\",\"content\":\"$VERCEL_TARGET\",\"ttl\":1,\"proxied\":false}" | jq .

# api.pepperoni.tatar → CNAME
echo "Добавляю api.pepperoni.tatar (CNAME)..."
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"CNAME\",\"name\":\"api\",\"content\":\"$VERCEL_TARGET\",\"ttl\":1,\"proxied\":false}" | jq .

# pepperoni.tatar (apex) → A или CNAME flatten
# Для apex домена в Cloudflare: либо A record 76.76.21.21, либо CNAME Flattening
echo "Добавляю pepperoni.tatar (A record для apex)..."
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"@","content":"76.76.21.21","ttl":1,"proxied":false}' | jq .

echo ""
echo "✅ Готово. Подождите 2–5 минут и нажмите Refresh в Vercel."
echo ""
echo "Если записи уже есть — обновите их вручную в Cloudflare:"
echo "  www  CNAME  →  $VERCEL_TARGET  (Proxy: off)"
echo "  api  CNAME  →  $VERCEL_TARGET  (Proxy: off)"
echo "  @    A      →  76.76.21.21     (Proxy: off)"
