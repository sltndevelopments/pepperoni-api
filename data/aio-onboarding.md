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

**Заявка (живая форма, проверено 2026-07-15):**  
https://perplexity.typeform.com/to/oIcfT8U3  
«Perplexity Merchant Program Interest Form» — Typeform (`isFormClosed: false`). Поля: Merchant URL, contact name/email, shopping vertical.

**Официальный анонс (не форма):**  
https://www.perplexity.ai/hub/blog/shop-like-a-pro  
(старый slug `/hub/blog/introducing-the-perplexity-merchant-program` — 404; отдельного portal `perplexity.ai/merchants` / `merchant.perplexity.ai` нет.)

**ToS / post-accept ingest:**  
https://www.perplexity.ai/hub/legal/merchant-program-terms-of-service  
После одобрения доступ к API / SFTP / CSV→S3 запрашивают у `taz@perplexity.ai`. Feed — Google Shopping–совместимый CSV/XML (наш GMC XML подходит как база).

**Альтернативы без формы:** US Shopify / PayPal / BigCommerce syndication (для нас не основной путь — B2B EXW Kazan, не US DTC).

### Что указать в форме

- **Merchant URL / Domain:** pepperoni.tatar (verified)
- **Contact name / email:** (владелец) · info@kazandelikates.tatar
- **Shopping vertical:** food / halal meat / wholesale deli
- В follow-up (после ответа Perplexity): **Feed URL** `https://pepperoni.tatar/products-feed.xml`, GMC ID `513449343`, тел. +7 987 217-02-02
- **Business model:** B2B wholesale / EXW Kazan / halal manufacturer — честно указать; программа ориентирована на US retail shipping

### Блокер (честно)

| Метрика | Сейчас | Типичный порог программы |
|---|---|---|
| SKU | ~70 | ≥100 (часто) |
| GTIN coverage | ~23% (16/70) | ≥80% |
| US ship-to | нет (EXW Kazan) | программа для продавцов в US |

Подать можно; одобрение могут задержать из‑за GTIN/SKU и отсутствия US shipping.  
Следующий продуктовый шаг: добить штрихкоды в Google Sheets (колонка barcode).

### После одобрения

1. Написать `taz@perplexity.ai` за SFTP/API credentials; отдать HTTPS XML или CSV по их схеме.
2. Следить, что `products-feed.xml` остаётся актуальным (RUB + RU shipping — может не пройти Buy with Pro; discovery всё равно цель).
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

1. [ ] Заполнить Typeform Perplexity Merchants: https://perplexity.typeform.com/to/oIcfT8U3 (feed XML — в follow-up).
2. [ ] Заполнить форму OpenAI Commerce partner; положить SFTP env на VPS.
3. [ ] (Опционально) Добить GTIN в Sheets → поднять покрытие для Perplexity.
