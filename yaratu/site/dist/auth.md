# Auth.md

Agent audience: buyers and assistants looking up Yaratu chicken and beef products.
This origin is a **public catalog**. No login, no OAuth dance, no checkout, no consumer prices.

Resource server: `https://yaratu.com/`
Authorization server: `https://yaratu.com` (anonymous / public only)

## Discovery

1. `GET /.well-known/oauth-protected-resource`
2. `GET /.well-known/oauth-authorization-server` — read `agent_auth`
3. Use `identity_types_supported: ["anonymous"]`. Do not invent a user account.

## Supported flows
- **Anonymous / public read** — the only advertised Auth.md registration method. No credential is minted.

## Scopes
- `read:catalog` — already granted. No bearer token.

## How to register
GET https://yaratu.com/agents/register
GET https://yaratu.com/oauth/identity

Both restate `identity_type: anonymous` and `registration: not-required`. There is no OTP claim and no ID-JAG.

## What is public (no credential)
- https://yaratu.com/data/products.json
- https://yaratu.com/llms.txt
- https://yaratu.com/.well-known/mcp/server-card.json
