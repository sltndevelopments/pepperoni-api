#!/usr/bin/env bash
# DNS-AID (draft-mozleywilliams-dnsop-dnsaid) — DNS only, proxied=false.
set -euo pipefail

TOKEN="${CLOUDFLARE_API_TOKEN:-}"
EMAIL="${CLOUDFLARE_EMAIL:-}"
KEY="${CLOUDFLARE_API_KEY:-}"
ZONE="${CLOUDFLARE_ZONE_ID:-}"

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
  ZONE=$(api "https://api.cloudflare.com/client/v4/zones?name=pepperoni.tatar" \
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

# Scanner checks SVCB (type 64) and HTTPS (type 65). Spec wants HTTPS ServiceMode
# with alpn + port. Keep DNS-only (proxied=false). Do not orange-cloud apex.
INDEX='alpn="h3,h2" port=443'
MCP='alpn="h3,h2" port=443 mandatory="alpn,port"'

upsert_svcb "_index._agents.pepperoni.tatar" "pepperoni.tatar" "$INDEX" HTTPS
upsert_svcb "_index._agents.pepperoni.tatar" "pepperoni.tatar" "$INDEX" SVCB
upsert_svcb "_mcp._agents.pepperoni.tatar" "api.pepperoni.tatar" "$MCP" HTTPS
upsert_svcb "_mcp._agents.pepperoni.tatar" "api.pepperoni.tatar" "$MCP" SVCB
upsert_svcb "_a2a._agents.pepperoni.tatar" "pepperoni.tatar" "$MCP" HTTPS
upsert_svcb "_a2a._agents.pepperoni.tatar" "pepperoni.tatar" "$MCP" SVCB
upsert_txt "_index._agents.pepperoni.tatar" "mcp=https://api.pepperoni.tatar/api/mcp a2a=https://pepperoni.tatar/.well-known/agent-card.json"
upsert_txt "_catalog._agents.pepperoni.tatar" "url=https://pepperoni.tatar/.well-known/ai-catalog.json"

echo "Verify:"
echo "  curl -s 'https://cloudflare-dns.com/dns-query?name=_index._agents.pepperoni.tatar&type=SVCB' -H 'accept: application/dns-json'"
