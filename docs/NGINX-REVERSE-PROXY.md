# Nginx reverse proxy: cache + fallback

RU VPS проксирует на Vercel. Рекомендации по устойчивости.

---

## 1. Агрессивный proxy cache

```nginx
# В http { } — определить cache zone
proxy_cache_path /var/cache/nginx/pepperoni
                 levels=1:2
                 keys_zone=pepperoni_cache:64m
                 max_size=512m
                 inactive=24h
                 use_temp_path=off;

# В server { } для api.pepperoni.tatar и www.pepperoni.tatar
location / {
    proxy_pass https://pepperoni-api.vercel.app;  # или ваш Vercel URL
    proxy_ssl_server_name on;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_cache pepperoni_cache;
    proxy_cache_valid 200 301 302 10m;
    proxy_cache_use_stale error timeout updating;
    proxy_cache_lock on;
    add_header X-Cache-Status $upstream_cache_status;
}
```

**Результат:** мгновенная отдача при повторных запросах, сайт работает при кратковременной недоступности Vercel.

---

## 2. Fallback при падении origin

Если Vercel недоступен — отдать локальную копию `products.json`:

```nginx
location = /products.json {
    proxy_pass https://pepperoni-api.vercel.app;
    proxy_ssl_server_name on;
    proxy_set_header Host api.pepperoni.tatar;
    proxy_cache pepperoni_cache;
    proxy_cache_valid 200 1h;
    proxy_cache_use_stale error timeout updating;

    # Fallback: если upstream недоступен — локальный файл
    error_page 502 503 504 = @products_fallback;
}
location @products_fallback {
    default_type application/json;
    root /var/www/pepperoni/backup;
    try_files /products.json =404;
}
```

Локальная копия обновляется cron-задачей:

```bash
# /etc/cron.d/pepperoni-sync
*/30 * * * * root curl -s "https://api.pepperoni.tatar/products.json" -o /var/www/pepperoni/backup/products.json
```

---

## 3. Исключения для кэша (API, поиск)

Не кэшировать live-эндпоинты, где важна свежесть:

```nginx
location ~ ^/api/(search|products) {
    proxy_pass https://pepperoni-api.vercel.app;
    proxy_ssl_server_name on;
    proxy_set_header Host $host;
    # Без proxy_cache или короткий TTL
    proxy_cache_valid 200 1m;
}
```

Статика (HTML, sitemap, images) — кэшировать долго.

---

## 4. Диагностика недоступности

```bash
# nginx
systemctl status nginx

# порт 443
ss -tulpn | grep 443

# DNS
dig www.pepperoni.tatar +short
dig api.pepperoni.tatar +short

# SSL
certbot certificates

# Доступность origin
curl -sI https://pepperoni-api.vercel.app/
```

---

## 5. VPS как data-узел (production, 10 мин)

Схема: Google Sheets → VPS cron → локальный `products.json` → nginx отдаёт напрямую.

**Vercel не участвует в обновлении цен.** GitHub Actions — только для деплоя кода.

### 5.1 Структура на VPS

```
/var/www/pepperoni/
├── repo/           # git clone pepperoni-api
├── data/           # выход sync (products.json и др.)
└── logs/
```

### 5.2 Cron — каждые 10 минут (без git pull)

**Правило:** Cron = доставка данных. GitHub Actions = доставка кода. Не смешивать.

```bash
# crontab -e
*/10 * * * * /bin/bash /var/www/pepperoni/scripts/sync-cron.sh >> /var/log/pepperoni-sync.log 2>&1
```

Скрипт `/var/www/pepperoni/scripts/sync-cron.sh` (вне репо, не перезаписывается rsync):
- запускает `node scripts/sync-sheets.mjs` в `repo/`
- атомарно копирует `products.json` (.tmp → mv)
- копирует `llms*.txt` в `data/`
- **без** `git pull` — код обновляет только GitHub Actions

### 5.3 Nginx — локальный JSON + fallback на Vercel

```nginx
# Сжатие — критично для ~60KB JSON
gzip on;
gzip_types application/json;
gzip_min_length 1000;

# /api/products — локальный файл или fallback на Vercel
location = /api/products {
    root /var/www/pepperoni/data;
    default_type application/json; charset=utf-8;
    add_header X-Data-Source "vps-local";
    add_header X-Data-Version $date_gmt;
    add_header Cache-Control "public, max-age=600, stale-while-revalidate=30";

    try_files /products.json @fallback;
}

location @fallback {
    proxy_pass https://pepperoni-api.vercel.app;
    proxy_set_header Host api.pepperoni.tatar;
    proxy_ssl_server_name on;
    add_header X-Data-Source "vercel-fallback";
}

# Всё остальное — proxy на Vercel
location / {
    proxy_pass https://pepperoni-api.vercel.app;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_ssl_server_name on;
}
```

**Критично:** `try_files /products.json @fallback` — если файла нет или он повреждён, nginx идёт на Vercel. Блок вставлять в `server` для `api.pepperoni.tatar`.

### 5.5 Редирект www → apex (на уровне Nginx)

Трафик сначала попадает на VPS (37.9.4.101). Редирект `www` → `pepperoni.tatar` лучше делать в Nginx — ответ за 10–20 ms, без лишнего прыжка до Vercel.

```nginx
server {
    listen 443 ssl http2;
    server_name www.pepperoni.tatar;

    ssl_certificate /etc/letsencrypt/live/pepperoni.tatar/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pepperoni.tatar/privkey.pem;

    return 301 https://pepperoni.tatar$request_uri;
}
```

**Проверка:** `curl -sI https://www.pepperoni.tatar | grep -iE "HTTP/|Location"` → `HTTP/2 301`, `location: https://pepperoni.tatar/`

### 5.6 Обновление llms-full.txt после деплоя

После `git push` и доставки кода через GitHub Actions новый `sync-sheets.mjs` оказывается на VPS. Чтобы сгенерировать обновлённый `llms-full.txt` с блоком *Company Capabilities*:

- **Автоматически:** cron запустит `sync-vps.sh` в течение 10 минут.
- **Вручную:** `REPO_DIR=/var/www/pepperoni/repo DATA_DIR=/var/www/pepperoni/data /var/www/pepperoni/repo/scripts/sync-vps.sh`

**Проверка:** `curl -s https://api.pepperoni.tatar/llms-full.txt | head -25` — в начале должен быть блок про Private Label, ДУМ РТ, 100% говядина.

**Проверка /api/products:** `curl -sI https://api.pepperoni.tatar/api/products` — `X-Data-Source: vps-local` или `vercel-fallback`

### 5.4 gzip и brotli

```nginx
gzip on;
gzip_types application/json text/css application/javascript text/plain;
gzip_min_length 256;
# brotli (если модуль установлен: apt install nginx-module-brotli)
# brotli on;
# brotli_types application/json text/css application/javascript;
```

### 5.7 Первый запуск sync

```bash
cd /var/www/pepperoni/repo
git pull
node scripts/sync-sheets.mjs
cp -f public/products.json public/llms-full.txt public/sitemap.xml /var/www/pepperoni/data/
mkdir -p /var/www/pepperoni/data
```

### 5.6 Чеклист активации data-узла

1. **Файл:** `ls -la /var/www/pepperoni/data/products.json`
2. **Порядок:** `location = /api/products` выше `location /`
3. **Reload:** `sudo nginx -t && sudo systemctl reload nginx`
4. **Проверка:** `curl -sI https://www.pepperoni.tatar/api/products`

Ожидается: `X-Data-Source: vps-local`, без `x-vercel-cache` / `x-vercel-id`.

**Примечание:** `/api/products?lang=en` — при необходимости можно оставить proxy на Vercel (если API делает перевод). Или отдавать тот же файл — клиентский словарь TR переводит названия.

---

## 6. GitHub Actions — только для кода

После перехода на VPS data-node:

- Убрать или отключить schedule в `.github/workflows/sync-prices.yml`
- Оставить `workflow_dispatch` для ручного sync при необходимости
- Деплой кода — через push в main
