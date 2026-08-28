# auth.md

Agent audience: people and assistants looking up Rinat Sultanov.
This origin is a **public profile**. No login, no OAuth dance, no checkout.

Resource server: `https://rinatsultan.com/`
Authorization server: `https://rinatsultan.com` (anonymous / public only)

## Discovery

1. `GET /.well-known/oauth-protected-resource`
2. `GET /.well-known/oauth-authorization-server` — read `agent_auth`
3. Use `identity_types_supported: ["anonymous"]`. Do not invent a user account.

## What is public (no credential)

- `GET https://rinatsultan.com/`
- `GET https://rinatsultan.com/llms.txt`
- `GET https://rinatsultan.com/index.md`
- Agent skill: `https://rinatsultan.com/.well-known/agent-skills/rinat-profile/SKILL.md`

## Registration

`register_uri` / `claim_uri` return JSON that restates anonymous public access. There is no OTP claim and no ID-JAG — this origin does not create agent accounts.

## Write / commercial

There is no paywall and no x402. To reach Rinat: Telegram https://t.me/TochnoRtutAloe, email 995620@gmail.com.
