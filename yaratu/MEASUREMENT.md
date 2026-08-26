# Yaratu measurement and indexing

This directory is an isolated Yaratu-only measurement system. It does not
import Pepperoni scripts, generate pages, edit HTML, commit, or publish.

## AI visibility

`data/aio_questions.json` is a versioned, fixed panel: 20 questions, split
equally across RU/EN and B2C/B2B. Change the panel only by creating a new
`panel_id` and version; otherwise weekly scores are not comparable.

Memory and search are separate layers:

- `openai_memory`, `gemini_memory`
- `openai_search`, `gemini_search`, `perplexity_search`

Defaults follow the repository's working contour: OpenAI search uses `gpt-5.6`,
Gemini uses `gemini-3.7-flash`, and OpenAI memory uses the lower-cost
`gpt-4o-mini` alias. All remain overridable through the documented
`YARATU_*_MODEL` environment variables.

An `ok` score exists only when all 20 questions returned real answers. Missing
credentials produce `status=skip, score=null`. A provider, network, parse, or
partial-panel failure produces `status=fail, score=null`. Failures are never
coerced to zero.

```sh
python3 yaratu/scripts/aio_visibility.py \
  --layers openai_memory,openai_search,gemini_memory,gemini_search,perplexity_search \
  --output /tmp/yaratu-aio.json
```

Use `--dry-run` to validate the panel and output path without network calls.
The snapshot contract is `data/aio_baseline.schema.json`.

## Indexing nudge

Every target is explicit; credentials come only from environment variables or
an explicitly supplied service-account file.

```sh
python3 yaratu/scripts/nudge_indexing.py \
  --domain yaratu.com \
  --gsc-property sc-domain:yaratu.com \
  --sitemap-url https://yaratu.com/sitemap.xml \
  --hot-url https://yaratu.com/ \
  --dry-run
```

Channels:

- Google Search Console sitemap submission
- Yandex Webmaster recrawl queue
- Yandex Webmaster sitemap recrawl, only when the exact sitemap is registered
- IndexNow

Google Indexing API is not intended for ordinary product or content pages, so
it is disabled by default. `--google-indexing` is an explicit opt-in reserved
for URL types eligible under Google's policy; the workflow never enables it.

Scheduled workflow runs perform measurement only and do not invoke the indexing
script, including dry-run. A real sitemap/recrawl/IndexNow nudge is available
through the dedicated `Yaratu — indexing nudge` workflow, or through the AIO
workflow with `run_indexing=true` and `run_measure=false`. Neither path calls
model APIs.

The 30/60/90 measurement contract starts from `data/measurement_30_60_90.json`
(`baseline_date=2026-08-26`). Windows stay `pending` until each end date. GSC
metrics require the Search Console service account to be added as owner of
`sc-domain:yaratu.com` or `https://yaratu.com/`.

## Conversion and expansion

`data/conversion_event.schema.json` is the event contract for
`product_view`, `availability_request`, `phone`, `WhatsApp`, `price`, `spec`,
and `sample`.

`data/measurement_30_60_90.schema.json` defines the three measurement
checkpoints. `data/expansion_policy.json` defines eligibility thresholds for
content, GEO, Merchant, OpenAPI, and MCP. Passing a threshold never executes an
expansion: every gate still requires a named human approval and rollback plan.

## Tests

```sh
python3 -m unittest discover -s yaratu/tests -v
python3 -m py_compile yaratu/scripts/aio_visibility.py yaratu/scripts/nudge_indexing.py
```
