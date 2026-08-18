# auth.md

Agent audience: B2B wholesale buyers and their assistants. Catalog, prices, certificates, and MCP read tools are **public**. No login, no OAuth dance, no checkout.

Resource server: `https://api.pepperoni.tatar/`  
Authorization server: `https://pepperoni.tatar` (anonymous / public only)

## Discovery

1. `GET /.well-known/oauth-protected-resource`
2. `GET /.well-known/oauth-authorization-server` — read `agent_auth`
3. Use `identity_types_supported: ["anonymous"]`. Do not invent a user account.

## What is public (no credential)

- `GET https://api.pepperoni.tatar/api/products`
- MCP Streamable HTTP: `https://api.pepperoni.tatar/api/mcp`
- OpenAPI: `https://api.pepperoni.tatar/openapi.yaml`
- Markdown: `https://pepperoni.tatar/llms.txt`

## Registration

`register_uri` / `claim_uri` return JSON that restates anonymous public access. There is no OTP claim and no ID-JAG — this origin does not create agent accounts.

## Write / commercial

MCP tool `submit_inquiry` or email info@kazandelikates.tatar / WhatsApp +7 987 217-02-02. EXW Kazan. No x402 paywall.
