# Google Search Console — настройка для автоматизации

## Что уже работает автоматически

- **Sitemap** — скрипт отправляет sitemap в GSC при каждом запуске workflow
- **Indexing API — отключён (2026-09-09).** Google принимает через него только
  страницы `JobPosting` / `BroadcastEvent`; каталог, хабы и статьи в его
  scope не входят. `scripts/gsc-index.py` без флага
  `--i-have-jobposting-or-broadcastevent-pages` ничего не отправляет.
  Единичные URL — через URL Inspection в интерфейсе Search Console.

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
2. Выбрать свойство **Domain: pepperoni.tatar** (`sc-domain:pepperoni.tatar`)
3. **Settings** → **Users and permissions** → **Add user**
4. Email: `search-console-agent@pepperoni-seo.iam.gserviceaccount.com`
5. Permission: **Full** / Owner → **Add**

`scripts/gsc-sitemap.py` сабмитит в `sc-domain:pepperoni.tatar` (не в
`https://pepperoni.tatar/` — у SA нет доступа к URL-prefix property, будет 403).

Повторить для **api.pepperoni.tatar** (URL-prefix), если это отдельное свойство.

## Проверка

После настройки workflow `Google Search Console — Indexing & Sitemap` должен:
- ✅ Отправлять sitemap (шаг 1)
- ✅ Яндекс Вебмастер + IndexNow (шаги 2–3)

Проверить в GSC: **Sitemaps** → должен отображаться `https://pepperoni.tatar/sitemap.xml`.
