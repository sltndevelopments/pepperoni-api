# Google Search Console — настройка для автоматизации

## Что уже работает автоматически

- **Indexing API** — каждые 62+ URL отправляются в Google при деплое и пуше
- **Sitemap** — скрипт пытается отправить sitemap в GSC при каждом запуске workflow

## Чтобы sitemap submission работал

### 1. Включить Search Console API в Google Cloud

1. [Google Cloud Console](https://console.cloud.google.com/) → проект `pepperoni-seo`
2. **APIs & Services** → **Library**
3. Найти **Search Console API** → **Enable**

Или через gcloud:
```bash
gcloud services enable webmasters.googleapis.com
```

### 2. Добавить сервис-аккаунт как пользователя в GSC

1. [Google Search Console](https://search.google.com/search-console)
2. Выбрать свойство **pepperoni.tatar** (или sc-domain:pepperoni.tatar)
3. **Settings** → **Users and permissions** → **Add user**
4. Email: `search-console-agent@pepperoni-seo.iam.gserviceaccount.com`
5. Permission: **Restricted** или **Full** → **Add**

Повторить для **api.pepperoni.tatar**, если это отдельное свойство.

## Проверка

После настройки workflow `Google Search Console — Indexing & Sitemap` должен:
- ✅ Отправлять sitemap (шаг 1)
- ✅ Отправлять URL в Indexing API (шаг 2)

Проверить в GSC: **Sitemaps** → должен отображаться `https://pepperoni.tatar/sitemap.xml`.
