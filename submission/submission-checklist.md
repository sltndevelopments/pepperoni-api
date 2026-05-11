# Pre-publish checklist

> **Status (2026-05-11):** Published.
> Live URL: <https://chatgpt.com/g/g-6a01d8038c088191ae03b2db4e3fccad-kazan-delicacies-halal-catalog>
>
> This document is kept as a re-publish reference — re-run the smoke
> tests below before pushing any breaking change to the OpenAPI spec
> or the knowledge-base files.

Before clicking **Publish** in the GPT Editor, run through this list.
Everything should already be green — these are the items we tested
locally on 2026-05-11.

## API reachable & valid

```bash
curl -fsSL https://api.pepperoni.tatar/openapi.yaml | head -5
curl -fsSL https://api.pepperoni.tatar/api/products | jq '.products | length'  # → 77
curl -fsSL https://api.pepperoni.tatar/.well-known/ai-plugin.json | jq .name_for_human
```

Expected: status `200`, 77 products, name "Kazan Delicacies — Halal Catalog API".

## Public assets reachable

```bash
for u in \
  "https://pepperoni.tatar/llms.txt" \
  "https://pepperoni.tatar/llms-full.txt" \
  "https://pepperoni.tatar/en/llms.txt" \
  "https://pepperoni.tatar/en/llms-full.txt" \
  "https://pepperoni.tatar/.well-known/ai-plugin.json" \
  "https://pepperoni.tatar/.well-known/ai-meta.json" \
  "https://pepperoni.tatar/sitemap-llms.xml" \
  "https://pepperoni.tatar/privacy" \
  "https://pepperoni.tatar/en/privacy" \
  "https://pepperoni.tatar/images/logo.png" \
  "https://pepperoni.tatar/og-default.png" \
  "https://pepperoni.tatar/og-default-en.png" ; do
  printf "  %-65s → " "$u"
  curl -s -o /dev/null -w "%{http_code}  %{size_download}b\n" "$u"
done
```

All should be `200` with non-zero body.

## OpenAPI parses

```bash
npx --yes @apidevtools/swagger-cli validate https://api.pepperoni.tatar/openapi.yaml
```

Or use the [Swagger Editor](https://editor.swagger.io/) and paste the URL.

## Privacy policy live

Open `https://pepperoni.tatar/privacy` and verify all 7 sections are
visible (collection, use, sharing, retention, rights, AI content,
contact).

## GPT Editor → "Try it" smoke tests

Run these from the editor preview pane:

1. *"Сколько стоит халяль пепперони в долларах?"* → must call
   `getProducts`, return USD prices for KD-001/002/003 family.
2. *"What sausages do you have for halal hot dogs?"* → must call
   `getProducts` filtered to sausages, return at least 3 SKUs with
   weights and prices.
3. *"Какие документы у вас есть на халяль?"* → no API call needed,
   answer from instructions: HALAL #614A/2024 (DUM RT), HACCP, ISO
   22000:2018.
4. *"Можете сделать СТМ для пиццерии — пилот 500 кг/мес?"* → confirm
   yes (case: Aslam / OMPK), ask for spec sheet, offer
   `info@kazandelikates.tatar` route.

If all four pass, click **Publish → Everyone**.

## Post-publish actions — completed 2026-05-11

GPT URL: `https://chatgpt.com/g/g-6a01d8038c088191ae03b2db4e3fccad-kazan-delicacies-halal-catalog`

Done in commits `fbfa89cd` (URL added to generator) and `b01f103a` (auto-regen):

- ✅ `public/.well-known/ai-meta.json` → `gpt_store_url`
- ✅ `public/llms.txt` (RU) — footer `Official ChatGPT: …`
- ✅ `public/en/llms.txt` (EN) — footer `Official ChatGPT: …`
- ✅ `public/llms-full.txt` (RU full) — same footer
- ✅ `public/en/llms-full.txt` (EN full) — same footer
- ✅ `scripts/sync-sheets.py` — RU + EN footer templates (regenerates on every CI run)

Monitor with `curl -A "GPTBot" https://pepperoni.tatar/llms.txt -o /dev/null -w "%{http_code}\n"`
or watch `/var/log/nginx/ai-bots.log` on the VPS for `openai-gptbot` /
`openai-chatgpt-user` hits.

## Categories to pick in GPT Store

- **Primary**: Food & Drinks
- **Secondary**: Productivity
- **Tertiary**: Lifestyle

## When to escalate

If publish is blocked by policy review (rare but happens for B2B GPTs
that look "too commercial"), reply in the review thread with the
following message:

> Hi — this is a B2B product catalog assistant for a halal-certified
> food manufacturer in Russia. All product data is publicly accessible
> at api.pepperoni.tatar/openapi.yaml. The assistant performs no
> transactions; it only helps buyers find the right SKU for their
> pizzeria/HoReCa/retail-chain use case and routes them to our sales
> email for quotes. Privacy policy at https://pepperoni.tatar/privacy.

Usually clears within 24–48 h.
