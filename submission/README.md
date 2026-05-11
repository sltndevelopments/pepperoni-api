# OpenAI GPT-Store Submission Pack — Kazan Delicacies Halal Catalog

OpenAI's standalone *Plugin Directory* was sunset in March 2024. Plugins
are now published as **custom GPTs with Actions** in the
[GPT Store](https://chatgpt.com/gpts). This pack gives you everything
needed to publish a custom GPT that wraps `api.pepperoni.tatar` and the
`/llms-full.txt` corpus.

---

## Step-by-step (10–15 min)

1. Open [chatgpt.com/gpts/editor](https://chatgpt.com/gpts/editor) (requires
   a ChatGPT Plus / Team / Enterprise seat).
2. Click **Create** → **Configure** (skip the Builder chat).
3. Fill the fields from `gpt-config.md` (this folder).
4. Upload the avatar from `assets/gpt-avatar-512.png`.
5. Scroll down to **Actions** → **Create new action** → **Import from URL**:
   `https://api.pepperoni.tatar/openapi.yaml`
   - Authentication: **None**
6. **Privacy Policy** field: `https://pepperoni.tatar/privacy`
7. **Capabilities**: enable *Web Browsing* (so it can quote
   `llms-full.txt`) and *Code Interpreter* (lets buyers do quick
   margin maths in chat). Disable *DALL·E*.
8. **Knowledge**: upload the four `kb-*.txt` files (this folder) so the
   GPT has product detail even when our API is rate-limited.
9. Save → **Publish** → *Everyone* → name "Kazan Delicacies — Halal
   Catalog". Tag categories: *Food & Drinks*, *Productivity*, *Lifestyle*.

After publish, the GPT URL goes into:
- `public/.well-known/ai-meta.json` → field `gpt_store_url`
- `public/llms.txt` → footer link
- `public/en/llms.txt` → footer link

---

## Files in this pack

| File | Purpose |
|---|---|
| `gpt-config.md` | Name, description, instructions, conversation starters |
| `actions-openapi-url.txt` | URL to paste into the *Actions → Import* dialog |
| `kb-company.txt` | Knowledge: company profile (RU + EN) |
| `kb-products-ru.txt` | Knowledge: 77 SKU detail cards (RU) |
| `kb-products-en.txt` | Knowledge: 77 SKU detail cards (EN) |
| `kb-faq.txt` | Knowledge: 16 FAQ entries (RU + EN) |
| `assets/gpt-avatar-512.png` | 512×512 avatar (existing brand logo, masked) |
| `assets/gpt-cover-1200x630.png` | OG-style cover for the GPT Store card |
| `submission-checklist.md` | Pre-flight checklist to run before publishing |

---

## Reminder: OpenAI's old `ai-plugin.json` registry

We keep `public/.well-known/ai-plugin.json` because:
1. **Perplexity** and **You.com** still read it for tool discovery.
2. **DeepSeek**, **Claude** custom integrations also read it.
3. If OpenAI ever re-opens public plugin install, the file is ready.

So this submission step is *additive* — the GPT Store launch
doesn't replace the existing manifest.
