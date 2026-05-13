# Cloudflare + Vercel: сайт не открывается из России

После переноса DNS в Cloudflare типичные причины: **не те записи**, **прокси Cloudflare включён** (оранжевое облако), **конфликт старых A/CNAME**, **SSL**.

## 1. Взять эталон из Vercel (обязательно)

1. [Vercel](https://vercel.com) → ваш проект → **Settings** → **Domains**.
2. Откройте **pepperoni.tatar** и **www.pepperoni.tatar** (если используете).
3. Скопируйте **точно** те значения, которые просит Vercel (A для apex и/или CNAME для `www` — они **могут меняться**, не ориентируйтесь на «старый» IP из памяти).

Проверка с вашего ПК:

```bash
dig +short pepperoni.tatar A
dig +short www.pepperoni.tatar CNAME
```

Результат должен совпадать с тем, что показывает Vercel после сохранения записей в Cloudflare (подождите 1–10 минут, TTL).

## 2. Cloudflare: режим «Только DNS» (серое облако)

Для записей, которые указывают на **Vercel** (`pepperoni.tatar`, `www`):

- **Proxy status: DNS only** (серое облако), **не** Proxied.

Почему:

- При **Proxied** трафик идёт через сеть Cloudflare; до Vercel доходит другой TLS/маршрут. В части сетей РФ это даёт таймауты, «сайт недоступен», хотя из Европы всё ок.
- Документация репозитория для **api.pepperoni.tatar** на VPS — там тоже обычно **DNS only**, если API не за прокси CF.

После переключения на DNS-only подождите пару минут и проверьте с мобильного интернета РФ.

## 3. Убрать дубликаты и мусор

В Cloudflare → **DNS** → **Records**:

- Один набор записей для apex (часто **две A** с разными IP от Vercel — так и должно быть, если Vercel так выдал).
- Для `www` — один **CNAME** на указанный Vercel-хост (например `…vercel-dns-….com` с **точкой** в конце значения, если CF так требует).
- Удалите **лишние** старые A/CNAME на другой хостинг или неверные IP.
- **AAAA** на Vercel для apex не используйте (Vercel IPv6 для стороннего DNS не даёт в классической схеме).

## 4. SSL в Cloudflare

- Если запись **DNS only** — сертификат отдаёт **Vercel**, настройки SSL в CF на этот хост почти не влияют.
- Если по ошибке оставили **Proxied**: **SSL/TLS** → режим **Full (strict)** и корректный сертификат на стороне Vercel; но для стабильности из РФ всё равно лучше **DNS only** для фронта.

## 5. CAA

Если в зоне уже есть **CAA**, добавьте разрешение для Let’s Encrypt (Vercel выпускает сертификаты через него):

```text
0 issue "letsencrypt.org"
```

Иначе сертификат может не обновиться.

## 6. api.pepperoni.tatar (не путать с фронтом)

Архитектура проекта: **HTML на Vercel** (`pepperoni.tatar`), **API часто на VPS** (`api.pepperoni.tatar`).  
Не указывайте `api` CNAME на Vercel, если API должен оставаться на своём сервере — см. `scripts/setup-cloudflare-dns.sh` и `docs/HEADLESS-ARCHITECTURE.md`.

## 7. Автоматизация (опционально)

При наличии `CLOUDFLARE_API_TOKEN` и `CLOUDFLARE_ZONE_ID`:

```bash
./scripts/setup-cloudflare-dns.sh
```

Перед запуском проверьте в скрипте переменные `VERCEL_CNAME` / IP apex — при необходимости замените на значения из п.1.

## Быстрый тест «починилось ли»

```bash
curl -sI --connect-timeout 10 https://pepperoni.tatar/ | head -5
```

Ожидается `HTTP/2 200` и заголовки `server: Vercel` / `x-vercel-*`.

Проверка из РФ: [check-host.net](https://check-host.net/check-http?host=https://pepperoni.tatar) — выберите узлы **ru1 / ru2 / ru3 / ru4**.
