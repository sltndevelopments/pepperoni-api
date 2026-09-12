# Auth.md

Yaratu catalog APIs are public. Agents do not create accounts and do not receive tokens.

## Supported flows
- **Public read** — no registration. Fetch the catalog without credentials.

## Scopes
- `read:catalog` — already granted to every client. No bearer token.

## How to register
GET https://yaratu.com/agents/register

This returns `registration: not-required` and the canonical catalog URL. There is no OTP, no client secret and no checkout.

OAuth metadata: /.well-known/oauth-protected-resource

Machine endpoints:
- https://yaratu.com/data/products.json
- https://yaratu.com/llms.txt
- https://yaratu.com/.well-known/mcp/server-card.json
