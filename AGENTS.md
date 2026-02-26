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
