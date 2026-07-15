# AIO onboarding — Perplexity + OpenAI ACP (2026-07-15)

Операционный чеклист после аудита docs (Anthropic / OpenAI / Google UCP / Grok / Copilot / Perplexity / DeepSeek).

## Уже в проде

| Ресурс | URL |
|---|---|
| GMC XML (RU) | https://pepperoni.tatar/products-feed.xml |
| OpenAI Commerce snapshot | https://pepperoni.tatar/openai-commerce-kazan-delicacies.tsv.gz |
| MCP | https://api.pepperoni.tatar/api/mcp |
| UCP discovery (no checkout) | https://pepperoni.tatar/.well-known/ucp |
| Merchant Center | 513449343 |

`sync-vps.sh` каждые 10 мин: `gen-products-feed.py` → `upload-openai-feed-sftp.sh`.

---

## 1) Perplexity Merchants

Заявка: https://www.perplexity.ai/hub/blog/introducing-the-perplexity-merchant-program  
(или актуальный portal: https://perplexity.ai/merchants)

### Что указать в форме

- **Domain:** pepperoni.tatar (verified)
- **Feed URL (HTTPS):** `https://pepperoni.tatar/products-feed.xml`
- **Alt feeds:** CIS / AE / Arab XML (см. ai-meta.json)
- **Merchant Center ID:** 513449343
- **Contact:** info@kazandelikates.tatar · +7 987 217-02-02
- **Business model:** B2B wholesale / EXW Kazan / halal manufacturer

### Блокер (честно)

| Метрика | Сейчас | Типичный порог программы |
|---|---|---|
| SKU | ~70 | ≥100 (часто) |
| GTIN coverage | ~23% (16/70) | ≥80% |

Подать можно; одобрение могут задержать из‑за GTIN/SKU count.  
Следующий продуктовый шаг: добить штрихкоды в Google Sheets (колонка barcode).

### После одобрения

1. Подтвердить, что они тянут наш XML (не нужен отдельный формат).
2. Следить, что `products-feed.xml` остаётся RUB + RU shipping.
3. Прогнать `scripts/aio_visibility.py` с `PPLX_API_KEY` (citability).

---

## 2) OpenAI Agentic Commerce (ACP)

### Статус инфраструктуры

| Шаг | Статус |
|---|---|
| Feed generator (`gen-products-feed.py`) | OK, daily via sync |
| Stable path `openai-commerce-kazan-delicacies.tsv.gz` | OK, live 200 |
| SFTP script `upload-openai-feed-sftp.sh` | OK, wired in sync-vps.sh |
| Credentials `/var/www/pepperoni/openai-commerce.env` | **MISSING** — upload no-op |

### Что нужно от владельца (один раз)

1. Подать заявку партнёра: https://developers.openai.com/commerce/guides/get-started  
2. Получить SFTP host / user / remote path / key от OpenAI.
3. На VPS создать файл (не в git):

```bash
# /var/www/pepperoni/openai-commerce.env  (chmod 600)
OPENAI_COMMERCE_SFTP_HOST=...
OPENAI_COMMERCE_SFTP_USER=...
OPENAI_COMMERCE_SFTP_REMOTE_PATH=/incoming/openai-commerce-kazan-delicacies.tsv.gz
OPENAI_COMMERCE_SFTP_IDENTITY=/root/.ssh/openai_commerce_ed25519
OPENAI_COMMERCE_SFTP_PORT=22
```

Шаблон: `deploy/openai-commerce.env.example`

4. Проверка:

```bash
ssh pepperoni-vps 'bash /var/www/pepperoni/repo/scripts/upload-openai-feed-sftp.sh'
```

Ожидаем `[openai-sftp] OK`, не `skip: OPENAI_COMMERCE_SFTP_HOST not set`.

Instant Checkout / Apps SDK — не цель (B2B EXW). Цель: discovery в ChatGPT.

---

## 3) Google UCP discovery

Файл: `public/.well-known/ucp`

- Объявляет **MCP transport** на наш живой MCP.
- `capabilities` / `payment_handlers` пустые — **checkout не обещаем**.
- Native UCP buy (US/CA/AU) нам не подходит; discovery + Food track — да.

---

## Порядок действий владельца (коротко)

1. [ ] Заполнить форму Perplexity Merchants (feed XML выше).
2. [ ] Заполнить форму OpenAI Commerce partner; положить SFTP env на VPS.
3. [ ] (Опционально) Добить GTIN в Sheets → поднять покрытие для Perplexity.
