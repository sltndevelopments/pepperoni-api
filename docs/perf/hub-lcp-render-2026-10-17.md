# Mobile LCP on three wholesale hubs — 17.10.2026

LCP element is the **hero text**. Lab traces on these pages show most of LCP
as **render delay**, not font or image download.

## What blocked first paint

On a clean `main` checkout the three hubs shared the same head:

1. **GTM inline at the top of `<head>`** — the snippet runs before charset,
   then fetches `gtm.js` (async) which still contends for the main thread.
2. **12–18 KB of JSON-LD in `<head>`** (Organization + ItemList + FAQ +
   breadcrumbs) — the parser does not reach the hero until those scripts are
   tokenized.
3. **Render-blocking `/assets/kd-landing.css`** plus a **large inline
   `<style>`** (`BASE_STYLE` + commercial/jerks extras) — CSSOM must finish
   before first paint of the H1.
4. **Yandex Metrika** was already at `</body>` with `async=1`; **lead-form.js**
   was already `defer`. Both stay that way. GTM/Metrika now load in the first
   idle slot after `load` (same gate as `/`).

There is no opacity/transform animation on the hero in `kd-landing.css`;
the generators now emit an explicit `animation:none; transform:none; opacity:1`
rule so a later stylesheet cannot fade the H1 in.

## Fix (generators, not HTML-only)

`scripts/landing_chrome.py` + `scripts/gen_category_pages.py` for
`sosiski-dlya-hotdog`, `kotlety-dlya-burgerov`, `sosiski-halyal-optom`:

- Inline `#kd-hero-critical` (hero/H1/topbar min-height only).
- Load `kd-landing.css` as `media="print"` + `onload="this.media='all'"`.
- Move page CSS, JSON-LD, GTM, Metrika to after the hero / `load`.
- Keep `<script src="/assets/lead-form.js" defer>` — tracking still fires,
  just not on the first paint path.

## Lab method

```
npx lighthouse http://127.0.0.1:3000/<file>.html \
  --only-categories=performance --form-factor=mobile \
  --screenEmulation.mobile --throttling-method=simulate \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage"
```

Median of 3 runs against the local `public/` tree (same HTML the generators
emit). Simulated Slow 4G + 4× CPU. First-party TTFB is local, so numbers are
lower than the live ~5 s field LCP; the delta is the render-delay work.

Raw JSON: `/opt/cursor/artifacts/lcp-before/`, `/opt/cursor/artifacts/lcp-after/`.
