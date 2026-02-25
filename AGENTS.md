# AGENTS.md

## Cursor Cloud specific instructions

This is **Pepperoni.tatar API** — a purely static site deployed to Vercel. There is no build step, no package manager, no dependencies, and no automated tests.

### Running locally

Serve the `public/` directory with any static file server:

```bash
python3 -m http.server 3000 -d public
```

### Key endpoints

| Path | Content |
|---|---|
| `/` | HTML landing page |
| `/products.json` | Product catalog JSON |
| `/openapi.yaml` | OpenAPI 3.0.3 specification |
| `/.well-known/ai-plugin.json` | AI plugin manifest |
| `/.well-known/ai-meta.json` | AI metadata / dataset discovery |

### Notes

- No `package.json`, `requirements.txt`, or dependency manifest exists — no install step is needed.
- No linter, test framework, or build tooling is configured.
- Deployment is configured via `vercel.json` (static site, clean URLs).
- The OpenAPI spec references `https://api.pepperoni.tatar` as the production server.
