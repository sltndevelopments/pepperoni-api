# Avito product-chat worker

`integrations.avito.worker` processes only product chats, answers using the
canonical Pepperoni catalog, and posts each captured phone lead into the
existing `LEADS_GROUP_ID` group.

## Guarantees

- The worker ignores recruitment chats whose listing URL contains `vakansii`.
- It inspects the last messages in a product chat together, so a phone sent
  before a follow-up city/name message is not lost.
- A phone lead is saved in SQLite before it is sent to Telegram.
- Telegram failures leave the lead in `pending` and are retried on every poll.
- The customer receives `Спасибо! Сейчас с вами свяжется менеджер.` only after
  Telegram confirms delivery.
- The LLM receives matched catalog entries from
  `https://api.pepperoni.tatar/api/products`; it is instructed not to invent
  facts or claim a manager has received a lead.

## Production migration

1. Add values from `deploy/avito-worker.env.example` to
   `/var/www/pepperoni/seo-agent.env`. The existing `LEADS_BOT_TOKEN` and
   `LEADS_GROUP_ID` are reused.
2. Install `deploy/pepperoni-avito-worker.service` under
   `/etc/systemd/system/`, then run `systemctl daemon-reload`.
3. Stop the legacy `avito-bot.service` before starting the new service. Never
   run both: they can send duplicate Avito replies and duplicate leads.
4. Start `pepperoni-avito-worker.service` and verify:

   ```bash
   systemctl status pepperoni-avito-worker
   journalctl -u pepperoni-avito-worker -f
   ```

5. Keep the old `/opt/avito` service disabled for rollback. Restore it only
   after stopping the new service.

## LLM provider

The preferred model is `gpt-4.1-mini`: it is fast enough for short sales chats,
follows instructions more reliably than the low-cost nano tier, and is still
inexpensive. Set its key without placing it in a shell history or chat:

```bash
cd /var/www/pepperoni/repo
python3 scripts/set_avito_openai_key.py
systemctl restart pepperoni-avito-worker
```

The worker selects OpenAI automatically when `OPENAI_API_KEY` exists. For an
explicit override or another compatible provider, use:

```dotenv
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

If direct access to OpenAI is unavailable from the worker host, keep customer
replies available with:

```dotenv
LLM_PROVIDER=deepseek
```

Then point `LLM_BASE_URL` at the phone assistant's supported-region,
OpenAI-compatible endpoint before changing `LLM_PROVIDER` back to `openai`.

Without an OpenAI/explicit provider configuration, the worker uses the legacy
`DEEPSEEK_*` variables already available in the production environment.
