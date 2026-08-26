#!/usr/bin/env bash
# Honest DNS-AID for yaratu.com: index + catalog only. No fake MCP/A2A.
# Requires CLOUDFLARE_API_TOKEN or CLOUDFLARE_EMAIL+CLOUDFLARE_API_KEY.
set -euo pipefail

TOKEN="${CLOUDFLARE_API_TOKEN:-}"
EMAIL="${CLOUDFLARE_EMAIL:-}"
KEY="${CLOUDFLARE_API_KEY:-}"
ZONE="${CLOUDFLARE_ZONE_ID:-}"
DOMAIN="yaratu.com"

if [[ -z "$TOKEN" && ( -z "$EMAIL" || -z "$KEY" ) ]]; then
  echo "set CLOUDFLARE_API_TOKEN or CLOUDFLARE_EMAIL+CLOUDFLARE_API_KEY" >&2
  exit 1
fi

api() {
  if [[ -n "$TOKEN" ]]; then
    curl -sf -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"
  else
    curl -sf -H "X-Auth-Email: $EMAIL" -H "X-Auth-Key: $KEY" -H "Content-Type: application/json" "$@"
  fi
}

if [[ -z "$ZONE" ]]; then
  ZONE=$(api "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['result'][0]['id'])")
fi

upsert_svcb() {
  local name="$1" target="$2" value="$3" type="${4:-SVCB}"
  local id
  id=$(api "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=$name&type=$type" \
    | python3 -c "import json,sys; rs=json.load(sys.stdin).get('result') or []; print(rs[0]['id'] if rs else '')")
  local payload
  payload=$(python3 -c "import json; print(json.dumps({
    'type': '$type', 'name': '$name', 'ttl': 3600, 'proxied': False,
    'data': {'priority': 1, 'target': '$target', 'value': '''$value'''}
  }))")
  if [[ -n "$id" ]]; then
    echo "↻  $type $name"
    api -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records/$id" --data "$payload" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('  OK' if d.get('success') else d)"
  else
    echo "+  $type $name"
    api -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" --data "$payload" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('  OK' if d.get('success') else d)"
  fi
}

upsert_txt() {
  local name="$1" content="$2"
  local id
  id=$(api "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?name=$name&type=TXT" \
    | python3 -c "import json,sys; rs=json.load(sys.stdin).get('result') or []; print(rs[0]['id'] if rs else '')")
  local payload
  payload=$(python3 -c "import json; print(json.dumps({
    'type': 'TXT', 'name': '$name', 'content': '''$content''', 'ttl': 3600, 'proxied': False
  }))")
  if [[ -n "$id" ]]; then
    echo "↻  TXT $name"
    api -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records/$id" --data "$payload" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('  OK' if d.get('success') else d)"
  else
    echo "+  TXT $name"
    api -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" --data "$payload" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print('  OK' if d.get('success') else d)"
  fi
}

INDEX='alpn="h2,h3" port=443'

upsert_svcb "_index._agents.$DOMAIN" "$DOMAIN" "$INDEX" HTTPS
upsert_svcb "_index._agents.$DOMAIN" "$DOMAIN" "$INDEX" SVCB
upsert_txt "_index._agents.$DOMAIN" "url=https://yaratu.com/.well-known/ai-catalog.json"
upsert_txt "_catalog._agents.$DOMAIN" "url=https://yaratu.com/.well-known/ai-catalog.json"

echo "Verify:"
echo "  curl -s 'https://cloudflare-dns.com/dns-query?name=_index._agents.$DOMAIN&type=HTTPS' -H 'accept: application/dns-json'"
echo "  curl -s 'https://cloudflare-dns.com/dns-query?name=_catalog._agents.$DOMAIN&type=TXT' -H 'accept: application/dns-json'"
