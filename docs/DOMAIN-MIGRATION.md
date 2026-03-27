# Миграция: pepperoni.tatar (основной) + api.pepperoni.tatar (API)

## Канонический URL: www.pepperoni.tatar

**pepperoni.tatar** редиректит на **www.pepperoni.tatar**. Каноническим считается **https://www.pepperoni.tatar**.

Везде в коде: canonical, og:url, hreflang, sitemap, vercel redirects, API-ответы — используется www.pepperoni.tatar.

**Редирект apex→www должен быть 301** (постоянный), а не 307. Для SEO: 301 передаёт «вес», 307 считается временным. Проверить: `curl -I https://pepperoni.tatar/`. Настроить: Vercel Dashboard → Domains → Redirect, или Cloudflare Page Rules.

## Что сделано

### 1. Редиректы api.pepperoni.tatar → www.pepperoni.tatar
При обращении к **api.pepperoni.tatar** по путям для людей выполняется 301-редирект на **www.pepperoni.tatar**:

- `/` → https://www.pepperoni.tatar/
- `/en/`, `/about`, `/faq`, `/delivery`, `/pepperoni`
- `/en/about`, `/en/faq`, `/en/delivery`, `/en/pepperoni`
- `/for-kazandelikates`, `/for-kazandelikates/*`
- `/product/*`, `/en/product/*` — страницы товаров

### 2. Что остаётся на api.pepperoni.tatar (без редиректа)
Редиректы в vercel.json применяются только к путям для людей. **API и машинные эндпоинты не редиректятся:**

- `/api/*` — products, search, product/:sku, feed, catalog
- `/products.json`
- `/openapi.yaml`
- `/llms.txt`, `/llms-full.txt`
- `/sitemap.xml`, `/robots.txt`
- `/.well-known/*` (ai-plugin.json, ai-meta.json)
- `/yml.xml` (Yandex.Market)

### 3. Обновления в HTML
- Canonical, og:url, hreflang — везде www.pepperoni.tatar
- Ссылки на API — на https://api.pepperoni.tatar/...
- Ссылка на llms.txt — на https://api.pepperoni.tatar/llms.txt

### 4. Sitemap и robots.txt
- HTML-страницы → www.pepperoni.tatar
- API и технические ресурсы → api.pepperoni.tatar
- В robots.txt указаны оба sitemap

---

## Что нужно сделать вручную

### 1. Добавить pepperoni.tatar в Vercel
1. Vercel Dashboard → проект pepperoni-api → Settings → Domains
2. Добавить **pepperoni.tatar**
3. Настроить DNS: A/CNAME на Vercel (если ещё не настроено)

Оба домена должны указывать на один и тот же deployment.

### 2. Проверить DNS pepperoni.tatar
Если pepperoni.tatar сейчас ведёт на другой хостинг, замените запись на Vercel. После этого этот репозиторий будет обслуживать оба домена.

### 3. После деплоя
- https://pepperoni.tatar/ — каталог и главная
- https://api.pepperoni.tatar/ — редирект на pepperoni.tatar/
- https://api.pepperoni.tatar/api/products — API, без редиректа

---

## Схема

```
pepperoni.tatar        → 301 на www.pepperoni.tatar (проверить!)
www.pepperoni.tatar    → HTML (каталог, about, faq, delivery, pepperoni) — canonical
api.pepperoni.tatar    → API (машинно) + редиректы только /, /about, /faq… на www
```
