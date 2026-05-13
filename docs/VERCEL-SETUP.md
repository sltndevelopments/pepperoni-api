# Vercel — настройка и деплой

## Что уже настроено в репозитории

- **vercel.json** — редиректы api→pepperoni, Cache-Control, rewrites
- **.vercelignore** — исключение лишних файлов из деплоя
- **api/** — serverless-функции (products, search, product/[sku])
- **public/** — статика (HTML, JSON, YAML, sitemap, robots)

## Деплой

### Автоматически (GitHub)
При подключении репозитория к Vercel каждый `git push` вызывает деплой.

### Вручную (CLI)
```bash
npm i -g vercel   # один раз
vercel            # preview
vercel --prod     # production
```

## Домены

После добавления доменов в Vercel настройте DNS в Cloudflare.

**Важно:** значения A/CNAME берите из **Vercel → Project → Settings → Domains** (они персональные и могут обновляться). Ниже — пример из истории проекта; не копируйте слепо, если Vercel показывает другое.

| Запись | Тип  | Имя | Значение (пример)                    | Proxy |
|--------|------|-----|--------------------------------------|-------|
| www    | CNAME| www | `…vercel-dns-017.com` (как в Vercel) | **DNS only** |
| apex   | A    | @   | IP из панели Vercel (часто 2× A)     | **DNS only** |

Если сайт «не открывается из России» после правок в Cloudflare — см. **[CLOUDFLARE-DNS-RU.md](./CLOUDFLARE-DNS-RU.md)** (прокси, дубликаты записей, CAA).

`api.pepperoni.tatar` в этой архитектуре часто указывает на **VPS**, не на Vercel — см. `scripts/setup-cloudflare-dns.sh` и `docs/HEADLESS-ARCHITECTURE.md`.

Или используйте: `./scripts/setup-cloudflare-dns.sh` (проверьте `VERCEL_CNAME` и IP apex внутри скрипта под свою панель Vercel).

## Проверка после деплоя

```bash
# Основной сайт
curl -I https://pepperoni.tatar/
# Редирект с api
curl -I https://api.pepperoni.tatar/
# API
curl -I https://api.pepperoni.tatar/api/products
```

## Важно

- Оба домена (pepperoni.tatar, api.pepperoni.tatar) должны быть добавлены в один проект Vercel
- DNS: Proxy (оранжевое облако) для api — выключить
