# Верификация внешнего аудита pepperoni.tatar (V1)

Дата: 2026-07-03. Метод: только скрипты/curl/git, без LLM.

## 1. Sitemap: 5100 vs 4100

**Вывод: аудит прав, 5100 — актуальное число.**

```
curl -s https://pepperoni.tatar/sitemap.xml | grep -c "<loc>"
→ 5100
```

Файл не является sitemap-индексом (`<sitemap>` count = 0), т.е. это единственный
sitemap. Разница с внутренней цифрой ~4100 объясняется ростом каталога geo-страниц
за счёт автономных тиков (+~1000 URL с момента последнего подсчёта). Внутренний
ledger по sitemap использует устаревшее число — обновить источник, которым мы
считаем URL в sitemap (ledger/strategy.json), синхронизировать с live.

## 2. Битые внутренние ссылки: 1593 vs «0 битых» у аудита

**Вывод: не противоречие — разная методика, обе цифры верны.**

- Внешний аудит проверял 30 URL *из sitemap* — все 200 OK. Это НЕ проверка
  внутренних ссылок на страницах, а проверка что sitemap не содержит мусора.
- Наш `scripts/site_health.py` сканирует HTML **всех 5107 страниц** и ищет
  `<a href>`, которые резолвятся в несуществующие локальные пути.
- Актуальный прогон (`data/site_health.json`, generated_at 2026-07-01T05:31 UTC,
  pages_scanned 5107):
  - `broken_links_total = 1593`
  - `pages_with_broken_links = 1581`
  - `broken_html_total = 20`

Примеры (полный список — top-10 в `broken_links_examples`):
- `/llms-page.html` → ссылается на `/llms.html` (не существует)
- Несколько `/blog/*-en-slug*.html` ссылаются на RU-слаги, которых нет
  (например `kazylyk-horse-meat-sausage.html` → `/blog/kazylyk-konina-kolbasa`)
- `/geo/*-kz.html` и подобные ссылаются на geo-страницы со старым/иным слагом
  (например `sosiski-dlya-hotdog-petropavlovsk-kz.html` →
  `/geo/sosiski-dlya-hotdog-petropavlovsk/` — со слэшем на конце, которого,
  видимо, нет как физического файла)

Данные не устарели относительно сегодняшнего pages_scanned (5107 ≈ live 5100),
но отчёту 2 дня — можно перегнать `site_health.py` заново, если нужен точный
снимок на сегодня. Число 1593 остаётся релевантным ориентиром техдолга.

## 3. products.json: заявленное отставание на 12 дней

**Вывод: аудит прав, и хуже — это баг с двумя разными файлами под одним URL.**

| Источник | lastSynced | count |
|---|---|---|
| Репозиторий `public/products.json` (git) | 2026-07-02 | 72 |
| Live `https://pepperoni.tatar/products.json` | **2026-06-21** ⚠️ | **77** |
| Live `https://api.pepperoni.tatar/api/products` | (нет поля) | 72 |

Корень проблемы найден в `docs/NGINX-REVERSE-PROXY.md`:

- `pepperoni.tatar/products.json` отдаётся из `/var/www/pepperoni/backup/products.json`
  — файл, который обновляется **отдельным cron**-job раз в 30 минут:
  `curl -s https://api.pepperoni.tatar/products.json -o .../backup/products.json`
  (строка 66). Это резервная копия, скачиваемая с самого API, а не с канонического
  sync-pipeline.
- Канонический `sync-vps.sh` пишет актуальный `products.json` в
  `/var/www/pepperoni/data/products.json` (обслуживает `api.pepperoni.tatar/api/products`
  через `location = /api/products { root .../data; }`), а НЕ в `backup/`.
- Т.е. на проде существуют **два физических файла** `products.json` в разных
  директориях, один из которых (`backup/`) не участвует в основном pipeline
  и, судя по live-данным (21.06 vs 72/77 несовпадение SKU), либо cron сломан,
  либо `pepperoni.tatar/products.json` вообще отдаётся не тем location-блоком,
  что описан в доке (возможно, ещё живёт статический артефакт из старого деплоя).
- Подтверждено: `git log -1 --format=%cI -- public/products.json` = `2026-07-02T14:12:45Z`
  — репозиторий свежий, проблема строго в раздаче на VPS/Vercel edge, не в коде sync.

**Это баг, а не просто «медленный снапшот».** ~~Нужно диагностировать на VPS~~ —
**диагностировано и исправлено 2026-07-03** (SSH-доступ восстановлен, ключ
`cursor-agent-pepperoni-vps` добавлен владельцем).

### Подтверждённый root cause

Реальная причина отличается от гипотезы выше (никакого `backup/` cron с
`docs/NGINX-REVERSE-PROXY.md` в реальности не существует — документация
устарела). Факт по `nginx -T` на VPS:

- `/etc/nginx/snippets/pepperoni-static-data.conf` (подключается в `pepperoni.tatar`,
  все 3 server-блока) содержал:
  ```
  location = /products.json  { alias /var/www/pepperoni/static-api/products.json; }
  location = /api/products   { alias /var/www/pepperoni/static-api/api/products.json; }
  ```
- `/var/www/pepperoni/static-api/` — **осиротевшая директория** от старой
  архитектуры (создана 17 апреля, файлы датированы 21 мая / 21 июня).
  `grep -rln static-api` по всему репозиторию и всем cron/systemd-джобам на VPS
  — **ноль совпадений**. Ни один текущий скрипт (`sync-vps.sh`, `seo-agent-vps.sh`
  и т.д.) её не пишет и не знает о её существовании.
- Канонический `sync-vps.sh` (крон каждые 10 минут) корректно пишет свежий
  `products.json` в `/var/www/pepperoni/data/products.json` — этот путь живой,
  сегодняшний, 72 SKU. Но nginx на `pepperoni.tatar` брал данные не оттуда.
- `api.pepperoni.tatar/api/products` (другой хост!) не связан с этим багом
  вообще — там `location /` проксирует на `pepperoni-api.vercel.app`, у
  которого свой независимый sync с Google Sheets. Совпадение «72, сегодня»
  по этому хосту — не результат общего пайплайна, а отдельная реализация.

### Фикс (применён 2026-07-03, живой прод)

```
# /etc/nginx/snippets/pepperoni-static-data.conf, оба location-блока:
- alias /var/www/pepperoni/static-api/products.json;
- alias /var/www/pepperoni/static-api/api/products.json;
+ alias /var/www/pepperoni/data/products.json;   # оба указывают на канонический файл
```
`nginx -t` → OK → `systemctl reload nginx`. Верифицировано сразу после релоада:

```
curl -s https://pepperoni.tatar/products.json  → lastSynced 2026-07-03, count 72
curl -s https://pepperoni.tatar/api/products    → lastSynced 2026-07-03, count 72
```

### Не сделано намеренно (эскалация не нужна, но зафиксировать)

- Осиротевшая директория `/var/www/pepperoni/static-api/` и мёртвый файл
  `/etc/nginx/snippets/pepperoni-api-data.conf` (тот же паттерн, нигде не
  инклюдится) оставлены нетронутыми — правка минимальна и не входила в
  задачу. Кандидат на отдельную уборку.
- Изменение внесено только на живом nginx VPS (это runtime-конфиг, не в
  git-репозитории — `/etc/nginx/` не версионируется этим проектом). Если
  когда-либо появится IaC/ansible для nginx-конфигов — перенести туда.

## Дополнительная находка (не запрошена явно, но relevant к 1.1)

`grep` подтверждает: число «77» захардкожено текстом (не производится из
live-данных) в:
- `public/manifest.json:4` — `"...Каталог халяль мясных изделий... 77 товаров..."`
- `public/.well-known/ai-plugin.json:6,7` — дважды упоминает «77 SKUs» /
  «77 товаров» в статическом описании.

Это подтверждает вывод аудита и расширяет охват задачи 1.1: reconcile должен
покрыть эти два файла (генерировать строку по `jq '.products | length'` из
живых данных), а не только `products.json` / `llms.txt`.

## Итоговые цифры для доверия

| Утверждение аудита | Вердикт | Актуальное значение |
|---|---|---|
| Sitemap ~5100 URL | ✅ подтверждено | 5100 (live) |
| «0 битых ссылок» (по 30 sitemap-URL) | ✅ верно, но не то же самое, что общий health | 1593 внутренних битых ссылок по полному сканированию (site_health.py, 2026-07-01) |
| `products.json` отстал на 12 дней | ✅ подтверждено, хуже чем казалось | Root cause найден и исправлен 2026-07-03: nginx-alias указывал на осиротевший `static-api/`, никем не обновляемый с апреля/мая/июня. Переключён на канонический `data/products.json`. Оба live-эндпоинта (`pepperoni.tatar/products.json`, `pepperoni.tatar/api/products`) сейчас отдают 72 SKU / today. |
