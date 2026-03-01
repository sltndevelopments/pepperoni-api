# AGENTS.md

## Cursor Cloud specific instructions

This is a Vercel-deployed static site + serverless API for Kazan Delicacies (pepperoni.tatar).

### Project structure
- `public/` — Static HTML pages (Russian at root, English under `en/`)
- `api/` — Vercel serverless functions (`products.js` fetches live data from Google Sheets)
- `vercel.json` — Vercel config with `cleanUrls: true` (pages served without `.html` extension)
- `package.json` — Only dependency is `exceljs` (used by the export API)

### Running locally
- Serve static pages: `npx serve public -l 3000`
- No build step required; all HTML pages are standalone with inline/embedded CSS
- API functions (`api/products.js`) are Vercel serverless and cannot be run locally without `vercel dev`
- To test catalog loading via API locally, you need a server that handles both static files and `/api/products`

### Russia accessibility setup
- Both `api.pepperoni.tatar` and `pepperoni.tatar` use a Russian reverse proxy (37.9.4.101) to bypass ISP blocks
- DNS in Cloudflare points both domains to `37.9.4.101` (no Cloudflare proxy, direct A record)
- nginx on the Russian server proxies requests to `pepperoni-api.vercel.app`
- Catalog pages (`index.html`, `en/index.html`) fetch data from `/api/products` (not Google Sheets directly), so the browser never contacts `docs.google.com`
- nginx config reference: `nginx/pepperoni.tatar.conf`

### HTML page conventions
- All pages share the same `<style>` block (copy from `public/pepperoni.html`)
- Navigation uses inline styles in a flex div (not a `<nav>` element)
- Green accent: `#1b7a3d`, blue links: `#0066cc`
- Every page must include: hreflang tags, Schema.org JSON-LD, CTA buttons (phone + email), footer
- Russian pages link to `/en/*`, English pages link back to `/*` (without `/en/`)

### Testing
- No automated test suite exists (`npm test` is a no-op)
- Validate pages by serving locally and checking HTTP 200 responses
- Check for required elements: DOCTYPE, hreflang, JSON-LD, CTA buttons
