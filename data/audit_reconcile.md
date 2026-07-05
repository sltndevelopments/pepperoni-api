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

## 2026-07-05 — Agentic Engineering follow-up: orphan-cleanup, category-page
## drift (systemic, не только vyipechka-halyal), invariant-детектор

Продолжение работы по плану "агентная инженерия для сайта": добавить
недостающие механические гейты вместо полагания на ручные аудиты.

### 1. Автоочистка orphan product-файлов

`scripts/gen-ru-products.py` и `scripts/gen-en-products.py` теперь после
генерации сравнивают файлы на диске (`public/products/*.html`,
`public/en/products/*.html`) с живым `products.json` и удаляют HTML-файлы
для SKU, которых больше нет в каталоге (`remove_orphan_pages()`). Это тот
же класс бага, что и ghost-SKU инцидент 2026-07-03 (kd-073…077) — теперь он
не может повториться молча: каждый прогон генератора сам чистит хвосты.

Побочный эффект прогона генераторов вскрыл **ещё один** класс инвариантного
нарушения: 14 продуктовых страниц (RU+EN) содержали `gtin13`/«Штрих-код»,
испорченный номером телефона (`46+7 987 217-02-02`) — генератор корректно
подставил настоящий EAN-13 штрихкод из `products.json` при перегенерации.

### 1b. Баг в `fix_pages.py`: `PHONE_TEXT_RE` ложно матчил штрихкоды

`PHONE_TEXT_RE` (`(?:\+7|8)[\s\-‑–()]*\d(?:[\s\-‑–()]*\d){9}`) без
границ по цифрам матчил подстроку `80638720035` внутри валидного 13-значного
EAN-13 (`4680638720035`) и **переписывал его обратно** на канонический
телефон — откатывая только что исправленный штрихкод. Добавлены
`(?<!\d)`/`(?!\d)` вокруг паттерна. Без этого фикса orphan-cleanup-прогон
выше был бы бесполезен: `fix_pages.py` откатывал бы штрихкоды на каждом
цикле sync-vps.sh.

После фикса: `fix_pages.py` перепрогнан на все изменённые страницы —
0 repaired (баркоды больше не трогает). Дополнительно найдены и точечно
исправлены те же испорченные штрихкоды на **18 geo-страницах**
(`pepperoni-{city}.html`) — общий для всех шаблон, захардкоженный в
`gen-geo-pages.py` (уже был правильным в генераторе — эти 18 файлов
устарели относительно него).

### 2. Категорийные landing-страницы: дрейф SKU↔контент — не единичный случай

Сверка всех 8 страниц `gen_category_pages.py` (`sosiski-halyal`,
`sosiski-dlya-hotdog`, `vetchina-optom`, `kolbasy-kopchyonye`,
`kolbasy-varenye`, `kotlety-dlya-burgerov`, `vyipechka-halyal`,
`myasnyie-zagotovki`) по именам товаров, зашитым в prose-текст каждой
страницы (intro/features/faq), против live `products.json` показала: та же
позиционная SKU-нумерация, что вызвала ghost-SKU инцидент, сдвинула SKU-
привязку **на 5 из 8 страниц**, не только на `vyipechka-halyal`:

| Страница | Было (SKU) | Стало (правильно) | Сдвиг |
|---|---|---|---|
| `sosiski-halyal` | KD-026…034 | KD-021…029 | −5 |
| `vetchina-optom` | KD-038…041 | KD-033…036 | −5 |
| `kolbasy-kopchyonye` | KD-042…056 | KD-037…051 | −5 |
| `kolbasy-varenye` | KD-035…037 | KD-030…032 | −5 |
| `vyipechka-halyal` | KD-059…077 | KD-054…072 | −5 (фикс 07-03) |
| `sosiski-dlya-hotdog` | KD-001…007 | KD-001…007 | без изменений |
| `kotlety-dlya-burgerov` | KD-008…009 | KD-008…009 | без изменений |

Каждая карточка/JSON-LD/ссылка сверена **по имени товара 1:1** (не только
по числу элементов) перед фиксом — например `vetchina-optom` заявляет в
FAQ «говядины (KD-034), индейки (KD-033)…», и это должно совпадать с
именем товара на живом сайте, а не просто с количеством SKU. Применён тот
же single-pass regex-сдвиг (-5), что и для `vyipechka-halyal` 07-03, ко
всем 4 файлам. `fix_pages.py`/`qa_pages.py` — 0 FAIL после фикса.

`scripts/gen_category_pages.py` переведён с хардкоженных позиционных
SKU-списков на lookup по стабильному полю `category` из `products.json`
(`get_products_by_category()`) — устраняет источник бага на будущее для
всех 7 оставшихся страниц. Старая `get_products_by_skus()` оставлена
(deprecated, с комментарием) для обратной совместимости, если понадобится.

### 3. `myasnyie-zagotovki` — товарная линейка снята с ассортимента

`myasnyie-zagotovki` (заявлен как «фарш говяжий, фарш из куриной кожи,
филе бедра куриного в кубике») не сдвинут — он **не существует** в живом
`products.json` вообще (category "Мясные заготовки" отсутствует; товар
был в каталоге ранее — 429 совпадений «фарш» в git-истории
`products.json` — и снят с продажи). Карточки на живой странице ссылались
на KD-021…025 (сосиски), т.е. показывали случайный чужой товар.

Решение (подтверждено владельцем): страница переведена на HTTP 410 Gone
(RU+EN) через явный `location = /myasnyie-zagotovki { return 410; }` в
`/etc/nginx/snippets/pepperoni-static-data.conf` на VPS (до общего
category-regex, exact-match location имеет приоритет). Убрана из
`public/sitemap.xml` (2 url-блока), убраны прямые ссылки на неё из
`vyipechka-halyal.html`/`en/vyipechka-halyal.html`. Блок страницы удалён
из `PAGES` в `gen_category_pages.py` с комментарием, чтобы генератор не
пересоздал её.

**Не в скоупе (эскалировано, не тронуто):** обнаружен смежный кластер
**560 geo-страниц** (`public/geo/farsh-*.html` ×182, `pelmeni-*.html` ×197,
`syroje-myaso-*.html` ×181) — весь контент про тот же несуществующий товар
«фарш». Решение по ним требует данных о трафике/индексации (Metrika/Search
Console) прежде чем массово применять 410/редиректы — оставлено для
отдельного захода.

### 4. `scripts/check_stale_counts.py` — новый инвариант-детектор

Новый самостоятельный скрипт (не встроен в защищённые `deploy_check.py`/
`page_reviewer.py`) сканирует `public/**/*.{html,json,yaml,txt}` и
`scripts/*.py` на числа рядом со словами-счётчиками (SKU/товар(ов)/product(s))
и сверяет их с живым `totalProducts`. В отличие от `reconcile_sku_count.py`
это детектор, а не автофиксер — репортит находки для ручного/агентного
разбора, поддерживает `--check` (exit 1 при находках, для CI).

Первый прогон на текущем состоянии сайта нашёл **51 реальную находку**
хардкоженного «77», не покрытую прошлым bulk-фиксом 07-03: включая
`scripts/gen-en-segments.py`, `scripts/gen-og-images.py`,
`scripts/gen_export_pages.py`, `scripts/gen-products-feed.py`,
`public/about.html`+EN, `public/en/faq.html`, `public/en/blog/production.html`,
`public/wholesale-price-list*.txt`, `public/llm.txt`, `public/faq-ai.txt` и
др. — не исправлялись в рамках этой сессии (отдельный bulk-фикс, требует
подтверждения объёма аналогично прошлому разу).

Подключён non-blocking в `scripts/sync-vps.sh` (шаг 1e, после
`reconcile_sku_count.py`) — логирует warning на каждый cron-тик, не роняет
синхронизацию.

### Проверка (07-05)

```
python3 scripts/check_stale_counts.py --check   # 51 находка (см. выше), задокументировано
python3 scripts/fix_pages.py && python3 scripts/qa_pages.py --quarantine   # 0 FAIL (52 файла)
python3 -c "import xml.etree.ElementTree as ET; ET.parse('public/sitemap.xml')"  # valid
curl -s -o /dev/null -w '%{http_code}' https://pepperoni.tatar/myasnyie-zagotovki      # 410
curl -s -o /dev/null -w '%{http_code}' https://pepperoni.tatar/en/myasnyie-zagotovki   # 410
curl -s -o /dev/null -w '%{http_code}' https://pepperoni.tatar/sosiski-halyal          # 200 (не задет)
```

### Не в скоупе / эскалировано владельцу

- 560 geo-страниц про несуществующий товар «фарш» (farsh-*/pelmeni-*/
  syroje-myaso-*) — решение отложено до данных по трафику/индексации.
- 51 находка `check_stale_counts.py` — не исправлены, задокументированы
  для отдельного bulk-фикса.
