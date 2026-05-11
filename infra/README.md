# `infra/` — VPS configuration & monitoring

Pieces that live on the **api.pepperoni.tatar VPS**, not on Vercel.

```
infra/
├── nginx/
│   ├── ai-bots-logging.conf      # nginx snippet: filter AI crawlers → /var/log/nginx/ai-bots.log
│   └── logrotate-ai-bots         # daily rotation, 90-day retention
└── scripts/
    ├── install-ai-bots-logging.sh  # one-shot installer (run as root on the VPS)
    └── parse-ai-bots.py            # daily digest generator (cron at 06:05)
```

## What it does

1. Adds a `map` block that classifies every request by `User-Agent`
   into one of 25 named AI crawlers (GPTBot, PerplexityBot, ClaudeBot,
   Google-Extended, Gemini, Applebot-Extended, Bytespider, DeepSeek,
   CCBot, etc.).
2. Writes a JSON line for every matched request to
   `/var/log/nginx/ai-bots.log`.
3. Rotates that log daily, keeping 90 days of `.gz` history.
4. Each morning at **06:05 server time**, generates a Markdown digest
   with hits per bot, top 20 paths, status-code distribution, and
   per-bot top paths. Saved to
   `/var/log/nginx/ai-bots-digest-YYYY-MM-DD.md` plus a
   `ai-bots-digest-latest.md` symlink.

## Install on the VPS

```bash
# 1. Sync the latest repo to /opt/pepperoni-api on the VPS (already
#    done by scripts/sync-vps.sh or your CI workflow).
# 2. Install nginx snippet, logrotate, parser, cron:
sudo bash /opt/pepperoni-api/infra/scripts/install-ai-bots-logging.sh

# 3. Edit your api.pepperoni.tatar server block and add inside server{}:
#       include snippets/ai-bots-logging.conf;
# 4. Reload nginx:
sudo nginx -t && sudo systemctl reload nginx

# 5. Verify:
curl -A "GPTBot/1.0 (+https://openai.com/gptbot)" -s -o /dev/null \
  https://api.pepperoni.tatar/llms-full.txt
sudo tail -n 1 /var/log/nginx/ai-bots.log | jq .
```

You should see a JSON line like:

```json
{"ts":"2026-05-11T11:43:21+03:00","bot":"openai-gptbot",
 "ip":"...","host":"api.pepperoni.tatar","method":"GET",
 "path":"/llms-full.txt","status":200,"bytes":117420,...}
```

## Manual digest (anytime)

```bash
python3 /opt/pepperoni-api/infra/scripts/parse-ai-bots.py --today
cat /var/log/nginx/ai-bots-digest-latest.md
```

## Mailing the digest

The cron job currently writes a file; if you want it mailed daily, edit
`/etc/cron.d/pepperoni-ai-bots`:

```
5 6 * * * root /usr/bin/python3 /opt/pepperoni-api/infra/scripts/parse-ai-bots.py | \
  xargs -I{} cat {} | mail -s "AI-bot digest $(date +%F)" admin@kazandelikates.tatar
```

Or pipe to a Telegram bot:

```
5 6 * * * root /usr/bin/python3 /opt/pepperoni-api/infra/scripts/parse-ai-bots.py | \
  xargs cat | curl -s -X POST https://api.telegram.org/bot$TOKEN/sendMessage \
  -d chat_id=$CHAT_ID --data-urlencode text@-
```

## Why this matters

When buyers ask ChatGPT / Perplexity / Claude about halal pepperoni
suppliers, we want to **prove** our `/llms-full.txt` is being fetched.
The digest gives a daily KPI:

- **Crawler diversity** — how many distinct AI vendors hit us.
- **Citation coverage** — which paths the bots actually pull.
- **404 / 5xx leakage** — any AI-bot-facing breakage shows up
  immediately in the bots' `4xx`/`5xx` columns.
