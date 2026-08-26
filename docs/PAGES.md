# Indexable page registry

`data/index_manifest.json` is the machine-readable source of truth for every
URL that pepperoni.tatar submits for indexing. The sitemap is an allowlist
projection of that file; discovering an HTML file under `public/` never makes
it indexable by itself.

## Current canonical surface

- Target: 180–250 indexable URLs.
- Current allowlist: 213 URLs.
- Languages: Russian at the root and English under `/en`.
- Product records: one RU and one EN page for every current `KD-NNN` SKU in
  `public/products.json`.
- Commercial pages: category, audience, private-label, export and catalog
  hubs listed explicitly in `scripts/build_index_manifest.py`.
- Trust pages: `/about`, `/capabilities`, `/certificates`, `/cases`, `/export`
  and `/editorial-policy`, with English counterparts.
- Editorial pages: 25 selected cornerstone guides across RU and EN.
- City × product pages and unsupported locales: never indexable.

The current count is generated, not maintained in this document:

```bash
python3 scripts/build_index_manifest.py
python3 scripts/rebuild_sitemap.py
```

## One URL per intent

- RU contract manufacturing: `/kontraktnoe-proizvodstvo`
- EN private label: `/en/private-label`
- Halal pepperoni commercial hub: `/pepperoni` and `/en/pepperoni`
- Catalog: `/products` and `/en/products`
- Company identity: `/about` and `/en/about`
- Certificate verification: `/certificates` and `/en/certificates`

Legacy `/oem`, `/private-label`, narrow private-label pages, synonym landings
and duplicate articles must resolve through the consolidation map, not compete
with these canonical URLs.

### Cross-domain ownership

`https://pepperoni.tatar/pepperoni` is the commercial pepperoni canonical.
The corporate page `https://kazandelikates.tatar/pepperoni-halal` currently
competes for the same intent and is outside this repository. The corporate
host owner must either:

1. return a 301 to `https://pepperoni.tatar/pepperoni`, or
2. narrow that page to corporate context and set its canonical to the catalog
   hub.

Do not solve this with reciprocal canonicals or duplicate commercial copy.

## Adding an indexable URL

All three conditions are required:

1. Demonstrated search or buyer demand.
2. A user task not already owned by another canonical URL.
3. First-party evidence, owned data or a verifiable primary source.

Add the page to `scripts/build_index_manifest.py`, identify the factual owner
and source, regenerate the manifest and pass the deployment gates. New country
pages also require a real importer or distributor, destination documents,
logistics evidence and human editorial review.

## Retirement states

`data/url_consolidation_map.json` records every retired URL:

- `301`: a materially equivalent canonical page exists.
- `410`: no equivalent useful intent or evidence exists.
- `noindex`: the page remains available for an explicitly non-organic use,
  such as an active advertising landing page.

Do not redirect unrelated retired URLs to the homepage. Redirect and 410
rules are generated into `deploy/nginx/trust-reset-*.conf`.
