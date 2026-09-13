# AIO onboarding — discovery feeds (обновлено 2026-08-27)

Каналы без корзины и без US checkout. Instant Checkout / UCP Buy / Copilot Checkout / x402 — не включать.

Тексты заявок: `data/aio-application-pack.md`.

## Уже в проде

| Ресурс | URL / статус |
|---|---|
| GMC XML (RU) | https://pepperoni.tatar/products-feed.xml |
| OpenAI Commerce snapshot | https://pepperoni.tatar/openai-commerce-kazan-delicacies.tsv.gz |
| MCP (VPS, local catalog) | https://api.pepperoni.tatar/api/mcp |
| Catalog JSON | https://api.pepperoni.tatar/api/products (`X-Data-Source: vps-local`) |
| UCP discovery (no checkout) | https://pepperoni.tatar/.well-known/ucp |
| Google Merchant Center | 513449343 |
| GTIN / barcode | **59/64 (92.2%)**. Нет штрихкода: KD-012, KD-014, KD-015, KD-016, KD-018 |
| Perplexity Typeform | подана 2026-08-27, ждать `taz@perplexity.ai` |
| OpenAI SFTP env | **нет** `/var/www/pepperoni/openai-commerce.env` |

`sync-vps.sh` каждые 10 мин: `gen-products-feed.py` → `upload-openai-feed-sftp.sh` (без env — no-op).

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
| SKU | 64 | ≥100 (часто) |
| GTIN coverage | **59/64 (92.2%)** | ≥80% |
| US ship-to | нет (EXW Kazan) | программа для продавцов в US |

Форма подана 2026-08-27 (B2B / EXW Kazan / no US checkout). Одобрение всё равно могут отказать из‑за модели EXW.  
Пять пустых штрихкодов добить в Sheets (колонка **Barcode** / «Штрихкод»): KD-012, KD-014, KD-015, KD-016, KD-018. Не выдумывать — только с упаковки / GS1. После заполнения cron `sync-vps.sh` сам прогонит sync → `gen-products-feed.py`.

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

1. **Подать заявку (форма, живая 2026-07-15):** https://chatgpt.com/merchants  
   («Apply to share your product feed» — Product Feed / discovery).  
   Официальный гайд (ссылка «here» → форма выше): https://developers.openai.com/commerce/guides/get-started  
   Хаб: https://developers.openai.com/commerce/
2. После одобрения получить SFTP host / user / remote path / key от OpenAI.
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

## 4) Microsoft Merchant Center / Bing (только фид)

Не Copilot Checkout. Тот же XML, что для Google.

1. Войти в [Microsoft Advertising](https://ui.ads.microsoft.com) → Tools → Merchant Center → Create store.
2. Верифицировать домен `pepperoni.tatar`.
3. Feed: scheduled fetch `https://pepperoni.tatar/products-feed.xml` **или** Import from Google Merchant Center `513449343`.
4. Страна/валюта: Russia / RUB. Не включать checkout.

Без аккаунта Microsoft Advertising агент завести магазин не может.

## 5) Claude custom connector

URL уже публичный: `https://api.pepperoni.tatar/api/mcp` (без OAuth).  
Каталог коннекторов: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp  
Покупатель на Pro может вставить URL сам. В каталог — заявка человека.

## Порядок действий владельца (коротко)

1. [x] Perplexity Typeform — подана 2026-08-27. Ждать письмо на info@kazandelikates.tatar.
2. [ ] OpenAI https://chatgpt.com/merchants — форма заполнена в браузере (feed only), **не отправлена**: в списке стран нет России. Не подставлять чужую страну. После одобрения — `/var/www/pepperoni/openai-commerce.env` (chmod 600).
3. [ ] Microsoft Merchant Center — тот же `products-feed.xml` (см. §4).
4. [ ] Реальные GTIN для KD-012, KD-014, KD-015, KD-016, KD-018 в Sheets.
5. [ ] OpenAI Plugins Directory / Claude connector catalog — когда откроют форму; privacy https://pepperoni.tatar/privacy.html ; тесты в application pack.
