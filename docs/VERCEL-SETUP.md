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

После добавления доменов в Vercel настройте DNS в Cloudflare:

| Запись | Тип  | Имя | Значение                           | Proxy |
|--------|------|-----|------------------------------------|-------|
| www    | CNAME| www | d1e2847508378433.vercel-dns-017.com| Off   |
| api    | CNAME| api | d1e2847508378433.vercel-dns-017.com| Off   |
| apex   | A    | @   | 76.76.21.21                        | Off   |

Или используйте: `./scripts/setup-cloudflare-dns.sh` (см. DOMAIN-MIGRATION.md)

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
