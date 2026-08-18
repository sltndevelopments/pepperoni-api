#!/usr/bin/env bash
# DNS-AID (draft-mozleywilliams-dnsop-dnsaid) — DNS only, proxied=false.
set -euo pipefail

TOKEN="${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN}"
ZONE="${CLOUDFLARE_ZONE_ID:?set CLOUDFLARE_ZONE_ID}"

api() {
  curl -sf -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"
}

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

PARAMS='alpn="h2,mcp" port=443'
A2A='alpn="h2,a2a" port=443'

upsert_svcb "_index._agents.pepperoni.tatar" "api.pepperoni.tatar" "$PARAMS" SVCB
upsert_svcb "_index._agents.pepperoni.tatar" "api.pepperoni.tatar" "$PARAMS" HTTPS
upsert_svcb "_mcp._agents.pepperoni.tatar" "api.pepperoni.tatar" "$PARAMS" SVCB
upsert_svcb "_mcp._agents.pepperoni.tatar" "api.pepperoni.tatar" "$PARAMS" HTTPS
upsert_svcb "_a2a._agents.pepperoni.tatar" "pepperoni.tatar" "$A2A" SVCB
upsert_svcb "_a2a._agents.pepperoni.tatar" "pepperoni.tatar" "$A2A" HTTPS
upsert_txt "_index._agents.pepperoni.tatar" "mcp=https://api.pepperoni.tatar/api/mcp a2a=https://pepperoni.tatar/.well-known/agent-card.json"

echo "Verify:"
echo "  curl -s 'https://cloudflare-dns.com/dns-query?name=_index._agents.pepperoni.tatar&type=SVCB' -H 'accept: application/dns-json'"
