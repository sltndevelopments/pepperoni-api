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

## Повторный аудит 2026-07-03 21:53 — 5 «призрачных» SKU (kd-073…077)

### Диагноз (не гипотеза — подтверждено по коду и данным)

`scripts/sync-sheets.mjs` присваивает SKU **позиционно**: `KD-${index}` от
порядка строк в Google Sheets, а не стабильным ID. Когда 5 строк выше по
списку были удалены/переставлены в Sheets, все нижестоящие товары
"выпечка" сдвинулись на -5 позиций (было 073–077, стало 068–072 для тех
же 5 товаров по названию — подтверждено `diff` HTML и сверкой имён).

Старые статические файлы `public/products/kd-073…077.html` (и EN-версии)
остались на диске без удаления — генератор карточек (`gen-ru-products.py`)
только создаёт/перезаписывает файлы по текущему списку, не подчищает
orphan-файлы для SKU, которых больше нет. Отсюда 77 HTML-страниц при 72
живых товарах.

Более серьёзная находка: категорийная страница `public/vyipechka-halyal.html`
генерируется скриптом `scripts/gen_category_pages.py` с **захардкоженным
списком** `"skus": ["KD-059", ..., "KD-077"]` (19 позиций). Из-за того же
сдвига -5 **все 19 ссылок** на этой странице указывали на неправильный
товар (не 404 — на другой существующий товар). Пример: карточка
«Губадия с кортом» вела на `/products/kd-059/`, где сейчас отображается
«Самса с говядиной».

### Фикс

1. Удалены 10 orphan-файлов: `public/products/kd-073…077.html` +
   `public/en/products/kd-073…077.html`.
2. Убраны 10 `<url>` блоков (RU+EN) для kd-073…077 из `public/sitemap.xml`,
   XML валидность подтверждена (`ET.parse`), счётчик `<url>`/`</url>` совпадает
   (5090/5090).
3. Захардкоженный список SKU в `scripts/gen_category_pages.py` (задача
   `vyipechka-halyal`) пересчитан на `KD-054…KD-072` — сверено по имени
   товара 1:1 с `products.json` (все 19 совпадают).
4. `public/vyipechka-halyal.html` пропатчен точечным regex-скриптом (сдвиг
   номеров SKU на -5 только в JSON-LD `itemListElement` и карточках
   `<div class="sku">`/`<a href="/products/kd-0NN/">`), а не полной
   регенерацией — прогон `gen_category_pages.py --main` откатывал более
   свежие правки в 7 остальных страницах (устаревшие контакты
   `info@pepperoni.tatar`/`+7 843 203-03-39` вместо канонiчных
   `info@kazandelikates.tatar`/`+7 987 217-02-02`, пропадал
   `hreflang="en"` и `<link rel="llms">`). Полная регенерация этих 8
   страниц через текущую версию генератора **не готова к прод-запуску** —
   отдельная находка, генератор надо актуализировать перед следующим
   использованием.
5. Поправлены 2 внутренних ссылки на призрачные SKU вне категорийной
   страницы: `public/sosiska-v-teste.html` (`kd-074`→`kd-069`).
6. Исправлен реальный источник хардкода count=77 в активно используемом
   коде — `scripts/sync-sheets.py::generate_llms_full_txt`,
   `generate_llms_full_txt_en`, `generate_kb_files` (3 f-string с
   буквальным «77» вместо `len(all_products)`; этот файл не мёртвый —
   импортируется как модуль в `scripts/gen-llms-full.py`, который реально
   гоняется на VPS).
7. `scripts/reconcile_sku_count.py` расширен: добавлены
   `public/.well-known/ai-meta.json` (9 паттернов, включая `576 = 72×8`
   для CIS/Arab feed-описаний) и `public/openapi.yaml`. `--check` теперь
   покрывает 6 файлов вместо 4.
8. Точечно поправлены оставшиеся текстовые упоминания "77" в
   `public/faq.html`, `public/search.html`, `public/blog/api.html`
   (4 вхождения) — найдены `grep`, не покрываются reconcile-паттернами
   (разные формы склонения/контекста, разовая правка достаточна).
9. `public/llms.txt`, `llms-full.txt`, EN-версии и все product feeds
   (CSV/XML/JSON, включая AE/CIS/Arab) перегенерированы через
   `python3 scripts/gen-llms-full.py` — теперь везде 72, «77» встречается
   только в легитимных ценах (68.77 ₽, 77.84 ₽ и т.п. — не count).

### Проверка

```
grep -c "<url>" public/sitemap.xml   # 5090, совпадает с </url>
python3 scripts/reconcile_sku_count.py --check   # all files in sync
python3 scripts/fix_pages.py && python3 scripts/qa_pages.py --quarantine   # 0 FAIL
```

Все 19 SKU на `vyipechka-halyal.html` сверены по имени 1:1 с
`products.json` — 100% совпадение после фикса.
