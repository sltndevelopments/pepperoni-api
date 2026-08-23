# next-task.md — Architect → Worker handoff

## Goal
Зафиксировать новые рельсы как реальность и валидировать автономный цикл на
вылеченной среде VPS — не выходя за рамки гейта, бюджета и лимита итераций.

## Current step

**30-дневный эксперимент внешнего авторитета (не SEO).** Сайт заморожен.
Контроль: `52f963634`. Журнал узлов: `data/external_authority_30d.json`.
Цель к 2026-09-18: **+5 независимых B2B-узлов, из них ≥1 GCC/UAE**.
Повтор тех же 20 промптов (PPLX+Gemini+ChatGPT Search). Не выдумывать
JAKIM/GCC. Новые номера ДУМ с реестра — не на сайт без решения владельца.
VPS/redsocks не трогать. После окна — класс «СТМ от 500 кг».

Старый measuring window 3 commercial exp (до 2026-08-11) — истёк; pulse
как был: `python3 scripts/commercial_pulse.py`.

Активные эксперименты (measuring → measure_at 2026-08-11):
1. котлеты для бургеров оптом → `/private-label/kotlety-dlya-burgerov-optom`
2. сосиски для хот догов оптом → `/private-label/sosiski-dlya-hotdog-optom`
3. казылык → `/private-label/kazylyk-premium-optom`

P0–P2 (гео / CWV / Speculation+VT) закрыты. WebMCP на `/`+`/en/` — не расширять.

**Pepperoni #1 (консолидация, не 4-й experiment):** money hub `/pepperoni`.
301 landings/v2/commercial-blog → hub; home title demoted; info-blog
`pepperoni-halal-ili-net` без commercial title. Pulse:
`data/commercial_watchlist.json` + блок «Pepperoni #1» в
`scripts/commercial_pulse.py`. Success gate 21д: `/pepperoni` = sitewide
top по «пепперони халяль»; к 2026-09-30 — pos ≤3 и выше kazan/pepperoni-halal.

После 2026-08-11: вердикт 3 exp → при необходимости promote `/pepperoni`
в `operator_experiments` / решение по `/x/`.


---

**Архив: Задача 0.4 CLOSED (2026-07-17).**

- RU+EN по `sosiski-v-teste` / `sosiski-hotdog` опубликованы шаблоном
  (`scripts/generate_geo_template.py`), без Anthropic.
- Очередь: `data/geo_0.4_tasks.json` очищена; архив —
  `data/geo_0.4_closed.json` (48 published, 54 non-ru/en dropped).
- Sitemap пересобран: `python3 scripts/rebuild_sitemap.py` → 5127 URL.
- SSH: `pepperoni-vps` (`~/.ssh/pepperoni_vps`).

**Архив: GEO answer-first backfill — DONE (2026-07-17).**

- Добавлен `scripts/backfill_geo_tldr.py`: детерминированно вставляет
  `<div class="tldr-answer">` из `data/products_geo.json` + город
  (`data-city` или slug из имени файла). Без LLM, без выдуманных claim'ов.
- Покрытие после прогона: **4113 / 4119** geo HTML (99.85%) с tldr-answer
  (`public/geo`, `en/geo`, `ar/geo`, `kk/geo`). Было ~663/2975 на RU.
- Осталось 6 битых stub-файлов без `<body>` (некуда вставить блок) —
  нужна полная регенерация, не backfill.
- Задача 0.4 (карантин `sosiski-v-teste` / `sosiski-hotdog`): локально
  `ssh root@37.9.4.101` → Permission denied; `ANTHROPIC_API_KEY` в среде
  агента пуст. Команда на VPS после восстановления доступа — та же, что
  ниже в архиве 0.4, с `export LLM_BULK_BUDGET_USD=3` перед батчем.

---

**Архив: Задача 0.4 продолжение — регенерация карантинных страниц (Batch API).**

- SSH-доступ восстановлен 2026-07-03 (ключ `cursor-agent-pepperoni-vps` добавлен
  владельцем в `authorized_keys`).
- Диагностика: `page_exists()` в `generate_geo_bulk.py` проверяет файл в `public/`,
  а при отсутствии — падает на SQLite (`data/seo_data.db`, таблица `geo_pages`).
  121 запись в этой таблице указывала на слаги карантинных/квалифицированных
  страниц, чьи файлы физически не существуют в `public/` (только в
  `data/quarantine/`) — это блокировало повторную генерацию тем же движком
  дедупликации, который защищает от повторной траты токенов на уже
  опубликованные страницы. Смысла в этих записях не было: генератор никогда
  не «публиковал» эти страницы (они были quarantined/held), значит запись в
  БД была создана раньше в потоке, но соответствующий файл так и не появился
  в `public/`.
  - Бэкап перед изменением: `data/seo_data.db.bak.<timestamp>` на VPS.
  - Удалены только строки, где `file_path` не существует на диске — 121 из
    645, все относятся к классу `sosiki-v-teste`/`sosiki-dlya-hotdog` (в т.ч.
    `kk`/`be`/`uz`/`az`-локали, не только RU). Проверка: SQL `SELECT slug,
    file_path FROM geo_pages` + `os.path.exists()` на каждый путь, дельта
    ровно 121 → 524 осталось.
- **Реальный охват задачи оказался шире 73 RU-страниц**: dry-run в `--mode
  world` после чистки БД показал **107 задач** (RU 1 город Королёв + KZ/BY/UZ/AZ
  города в разных локалях — kk/be/uz/az/ru), потому что многие карантинные
  файлы были не только по России, но и по СНГ-городам с других языков.
  Это тот же класс проблемы (отсутствие usp_ru данных), не новый охват —
  продолжил без отдельного подтверждения владельца, т.к. это то же исправление
  для того же продукта, просто более полное дедуплицированное покрытие,
  которое скрывалось багом БД.
- Пилотный прогон (mode russia, 1 задача — Королёв) прошёл гейт `page_reviewer.py`
  с первого раза с новым `usp_ru` (7089 токенов, $0.336 → без существенного
  прироста бюджета; дневной кап $5, использовано $1.75 до старта).
- **Полный прогон запущен** (`--mode world --products sosiski-v-teste
  sosiski-hotdog --max-pages 107 --workers 4`) в фоне на VPS
  (`nohup ... > /tmp/geo_bulk_run.log 2>&1 &`), использует Anthropic **Message
  Batches API** (−50% cost) — может занять от нескольких минут до нескольких
  часов (SLA батчей — не гарантированно быстрый, до 24ч по документации
  Anthropic). Прогон переживёт закрытие этой сессии, т.к. запущен через
  `nohup` от VPS-процесса, не привязан к SSH-сессии агента.
- **Результат прогона (2026-07-03 17:34–17:42 MSK)**: батч 107/107 запросов
  сгенерировал контент успешно на стороне Anthropic, но ревью-гейт
  (`page_reviewer.py`, отдельные вызовы LLM на каждую страницу) упёрся в
  **дневной бюджет** ($5/день, `LLM_DAILY_BUDGET_USD`): к моменту прогона
  уже было потрачено $1.75, сам батч + ревью подняли расход до **$8.86**,
  после чего reviewer стал недоступен для всех оставшихся страниц —
  **100 из 107** ушли в карантин по причине `reviewer unavailable: Дневной
  лимит LLM исчерпан`, ещё **7** (все — не по нашей задаче, `sujuk-*`
  Ближний Восток/Магриб) упали на `incomplete/invalid HTML`, это
  побочная находка, не блокер текущей задачи.
  **Только 1 страница реально опубликована**: `sosiski-v-teste-korolev.html`
  — прошла гейт до исчерпания бюджета.
  Закоммичено и запушено на VPS напрямую (`git commit` + `git push`, т.к.
  на VPS не git repo для нашей текущей сессии, а прод-репо):
  коммит `f7e27a449`, `origin/main`.
  Проверка после пуша: `git log -1 --format=%H` на VPS == `f7e27a449` ==
  верхний коммит `origin/main` (git push вывел `69b0b2d9a..f7e27a449`,
  без reject/conflict).
- **Не сделано (осталось на завтра, когда обнулится дневной бюджет)**:
  оставшиеся ~99 задач (KZ/BY/UZ/AZ/GE/TR/... города для `sosiski-v-teste` и
  `sosiski-hotdog`, разные локали) — они НЕ потеряны, `page_exists()`
  корректно пропустит уже готовую `korolev`, а карантинные копии остальных
  70+ файлов в `data/quarantine/*sosiki(-v-teste|dlya-hotdog)*` остаются на
  диске нетронутыми (не удалялись). Команда для повтора завтра:
  ```
  cd /var/www/pepperoni/repo && set -a && . /var/www/pepperoni/seo-agent.env && set +a \
    && python3 scripts/generate_geo_bulk.py --ignore-strategy --mode world \
       --products sosiski-v-teste sosiski-hotdog --max-pages 107 --workers 4
  ```
  Сначала стоит либо дождаться сброса `LLM_DAILY_BUDGET_USD` в новый день,
  либо явно согласовать с владельцем временное повышение дневного капа —
  **не делать это самостоятельно**, это порог из `CLAUDE.md` §7/§8
  (бюджет = предохранитель, эскалировать, а не менять произвольно).
- **Побочная находка не по задаче 0.4**: 7 страниц продукта `sujuk-*`
  (Ближний Восток/Магриб гео) падают с `incomplete/invalid HTML — not
  saved` — не входит в эту задачу, зафиксировано здесь для будущего
  Current step, не чинил.

- **Второй прогон (17:16–17:27 МСК, по запросу владельца "давай доделаем
  разово")**: перепроверил живой бюджет через `today_spend_usd()` —
  показал $1.88 (не $8.86, как в логе первого прогона), решил, что первый
  прогон отразил временную гонку данных batch-леджера, и перезапустил тот
  же `--mode world` батч (107 задач) без искусственного повышения капа.
  **Итог оказался хуже, не лучше**: сам батч-вызов (`generate_geo_bulk`,
  107 запросов, длинный `output` на reviewer'е через Sonnet) стоил
  **$7.06** за один проход по леджеру (`data/llm_costs.json` →
  `scripts.generate_geo_bulk.usd`), реальный дневной расход поднялся
  до **$8.94** — почти вдвое выше лимита $5. Это подтверждает, что первый
  прогон НЕ был гонкой данных — просто сам batch API списывает стоимость
  генерации по факту получения ответа, а не в момент отправки, поэтому
  `today_spend_usd()` в моменте между отправкой батча и его завершением
  показывает заниженное число. **0 новых страниц опубликовано** во втором
  прогоне (все 107 либо quarantined по бюджету, либо `incomplete/invalid
  HTML`). Карантинные файлы на диске не пострадали (74 осталось как было).
  **Урок для будущего**: `LLM_BULK_BUDGET_USD` per-run guard в
  `generate_geo_bulk.py` существует, но не был использован ни разу —
  нужно ставить его явно (`export LLM_BULK_BUDGET_USD=X`) перед батч-
  прогонами, чтобы не полагаться на устаревающий в реальном времени
  `today_spend_usd()`. **Задача 0.4 остаётся открытой на "завтра"** —
  реальный дневной бюджет сегодня исчерпан почти вдвое, продолжать нельзя
  без явного решения владельца о повышении дневного капа (эскалация по
  `CLAUDE.md` §7/§8, самостоятельно не меняю).

---

**Архив: изначальная постановка задачи (для контекста).**

**Задача 0.4 (владелец) — данные `sosiski-v-teste` получены и внесены.**
- Диаметра у этого продукта нет (не нормируется для сосиски в тесте).
- Длина сосиски: 12 см. Вес сосиски: 45 г. Вес готового изделия (сосиска + тесто): 120 г.
- Опечатка в id/slug исправлена: было `sosiki-v-teste`, правильно `sosiski-v-teste`
  (сам продукт в `data/products_geo.json` уже был на верном id/slug_ru; опечатка
  жила только в `_CAT_PRIORITY` внутри `scripts/generate_geo_bulk.py` — исправлена).
  Легаси-геостраницы на диске (`public/geo/sosiski-v-teste-*.html`) уже используют
  правильный слаг; карантинные файлы на VPS называются `sosiki-v-teste-*` — это
  имена файлов из старого прогона, не самого продукта, трогать их не будем,
  просто перегенерируем.

Внесено в `data/products_geo.json` → `usp_ru` продукта `sosiski-v-teste`:
> «Сосиска в тесте замороженная, вес готового изделия 120 г (сосиска 45 г +
> тесто), длина сосиски 12 см (диаметр не нормируется). Фасовка 48 шт/коробка
> (5,76 кг). Халяль. Срок годности 360 суток при -18°C. ГОСТ 31805-2018.
> MOQ уточняется у менеджера.»

**Следующий шаг (Worker/Architect)**: перегенерить ~73 карантинные страницы
`sosiki(-v-teste)` на VPS (`data/quarantine/rr_rr_sosiki-v-teste-*.html`),
дав `generate_geo_bulk.py` заново пройти гейт `page_reviewer.py` с новым
`usp_ru`. Ожидаемый результат: страницы, отклонённые по причине «отсутствуют
диаметр/длина/вес», теперь публикуются (диаметр не будет заявлен — его нет
у продукта, — но длина/вес/фасовка/срок годности присутствуют).

## Log

- **2026-08-23 брейн был мёртв 5 недель; чинил корни, не симптомы** (владелец:
  «делай всё по очереди»):
  Done:
  1. **Брейн (`9d5bb21cb`).** Причина — не «модель врёт JSON», а `max_tokens=4000`:
     adaptive thinking Opus 5 съедал лимит, ответ обрывался на 2.8 КБ от нужных
     ~12 КБ, а `_extract_json` резал обрывок по `rfind("}")` и выдавал
     `Expecting ',' delimiter`. Доказательство: `stop_reason=max_tokens`,
     `output_tokens=4000`. Поднял до 16000 (потолок ≠ трата), клиент теперь
     возвращает `stop_reason`, непарсибельный ответ падает в `data/logs/`.
     Проверка: `✅ Strategy written → data/strategy.json`, 12 495 байт,
     `cost $0.1728`, `web_search ok ran=4 cited_us=4`. Первая стратегия с
     18 июля, закоммичена `5b78664a0`.
  2. **Счётчики бюджета (`6fe121812`).** `reset --hard` откатывал *отслеживаемые*
     `daily_ledger/opus_budget/llm_costs/health` — предохранитель бюджета
     обнулялся при каждом деплое. Видел вживую дважды: `opus_budget` прыгнул на
     июльский снимок, `llm_costs` потерял $0.41. Деплой теперь переносит их
     через reset. Проверено на живом `workflow_dispatch`: файл остался
     августовским, при том что в HEAD лежит июльский.
  3. **Вердикты экспериментов (`b785b1258`).** `/private-label/kotlety-…` был
     признан worse и скрыт `noindex` 2026-08-11 (`58862ec91`), но
     `data/operator_experiments.json` **никогда** не входил в `git add` агента
     (`grep -c` = 0) → статус откатывался в `measuring`. Побочный эффект жил,
     решение — нет. Добавил контур управления в whitelist, статус восстановил по
     коммиту-следствию. `result` не выдумывал. Два других эксперимента не
     трогал: их вердикт = правка коммерческих страниц, а сайт заморожен.
  4. **CTR — диагноз сменился (`62d75c493`).** Не сниппеты: commercial 0.23% и
     information 0.24% кликают одинаково, но стоят на разных местах —
     money-запросы на позиции 25.2 (page-one share 10.4%), информационные на
     16.0 (36.8%). Топ page-one без кликов — определения («пепперони из какого
     мяса»), на которые Google отвечает сам. Кластер «сосиски для хот догов
     оптом» — 214 показов доказанного спроса на позициях 16–30. Правка тайтлов
     оптимизировала бы половину, которая не платит.
  5. **Локали — посылка не подтвердилась (`79e7a3365`).** «463 URL без показов»
     — шум 28-дневного окна. На 90 днях показы есть у *каждой* локали, `ar/geo`
     дал 18 кликов (больше, чем весь коммерческий пул). Sitemap не резал.
     Зато нашлась настоящая причина единственной полностью молчащей секции:
     5 страниц (`ar/private-label` ×3, `en/private-label` ×2) канонизировались
     на `kazandelikates.tatar`, **все 5 целей отдают 404**. Вернул на свой
     домен; `info@kazandelikates.tatar` не тронут. `qa_pages: 5 checked, 0 FAIL`.
  6. **Nudge (`ef26eed2d`).** Команда из CLAUDE.md §9 запускалась «голой» и
     молча пропускала Google: скрипт не подхватывал `seo-agent.env` и выходил с
     кодом 0. Теперь грузит сам (и `_B64`-форму тоже).
  Nudge после SEO-правки: IndexNow ✅ 8 URL (Bing+Yandex, 200/200); Google
  Indexing API и Yandex Webmaster — квота исчерпана моими же деплоями за день
  (`Daily quota reached`, `monthly_quota 10/10`), sitemap в Google подан ✅.
  Blockers: нет. Не делал: вердикты по 2 оставшимся экспериментам (заморозка),
  `x-robots-tag: index, follow` на скрытой kotlety-странице противоречит её
  `noindex` — Google берёт строгий сигнал, чинить в заморозку не стал.

- **2026-08-23 деплой лежал 5 дней + гигиена sitemap** (владелец: «разберись
  что не так, найди дыры, чтобы сайт лучше индексировался»):
  Done:
  - `a5f30b1e3` — корень падения `Deploy to VPS`. `apply_nginx_agent_discovery.sh`
    ловил блок `/llms.txt` регексом `\{[^}]+\}`, который останавливается на
    внутренней `}` строки `types { text/markdown txt; }`, добавленной этим же
    патчем. Каждый деплой оставлял хвост `default_type ...; }`; накопилось **29**
    → `nginx -t`: `[emerg] unexpected "}" in
    /etc/nginx/snippets/pepperoni-static-data.conf:45`. Замена по подсчёту скобок
    + вычистка накопленных хвостов + no-op, если блок уже верен.
    Проверка на копии прод-файла: `removed orphans: 29`, скобки `open 36 close 36`,
    прогоны 2 и 3 → `· already correct` (идемпотентность).
    На проде: `nginx -t ... test is successful`, `✅ / has Link api-catalog`,
    `✅ markdown negotiation`.
  - Тот же коммит: шаг nginx-заголовков перенесён в **конец** job'а. GitHub
    пропускает все шаги после упавшего, поэтому косметический патч заголовков
    убивал `Nudge Google index`. Последний зелёный деплой до фикса — **2026-08-18
    12:26**, за 60 последних прогонов `success 26 / failure 34`.
    Побочный урон: `gsc-index.yml` висит на `workflow_run` с
    `conclusion == 'success'` → все запуски по деплою были `skipped`
    (выживал только push-триггер по `public/sitemap.xml`).
    После фикса run `32626126442` — все 13 шагов `success`.
  - `0258c683f` — `rebuild_sitemap.py` больше не рекламирует мёртвые URL.
    У 301-страницы файл остаётся на диске с self-canonical, поэтому ни ФС, ни
    canonical о смерти не сообщают — только nginx. Теперь парсим
    `location = /exact` из `deploy/nginx/*redirects.conf` (префиксные `^~` из
    `*gone.conf` не трогаем — там `try_files`) и пропускаем страницы с robots
    `noindex`. Вывод: `excluded: 47 redirected (301), 7 noindex`. Число 47
    совпало с независимым живым замером всех 1472 URL sitemap
    (`1425 × 200`, `47 × 301`).
  - `c014de1fc` — `/x` («experimental homepage», `77653a74c`) убран из sitemap:
    `index, follow`, self-canonical, ниоткуда не слинкован, title совпадает с
    `/5`. Соседи `/1`..`/5` были исключены, `/x` пропустили.
  - `fa31da24f` — sitemap пересобран: **1472 → 1417**. Контроль всех 1417 URL
    против прода: `1417 × 200`, non-200 нет.
  - Nudge выполнен (`scripts/nudge_google_after_seo.sh`): Google sitemaps ✅ ×2
    (`sc-domain:pepperoni.tatar`, `api.pepperoni.tatar`); IndexNow/Bing ✅ 200,
    8 URL; Indexing API `⛔ QUOTA_EXCEEDED` и Яндекс `0/150` — дневную квоту
    съели три моих деплоя за сегодня, не баг.
  - Ложная тревога снята: `<!—` вместо `<!--` (невалидный комментарий, съедает
    содержимое до первого `>`) — правило ремонта в `fix_pages.py` от `02bcbc7aa`
    (2026-08-19), sweep `40a90ddc2` дочистил 887 файлов. Сейчас
    `grep -rl "<!—" public --include=*.html | wc -l` → **0**, закрытых `—>` → **0**.
    `fix_pages` стоит в пайплайне под `fail_hard`, класс закрыт.
  Blockers / решения владельца (сам не делал — bulk + окно измерения):
  1. **683 из 1417 URL sitemap (48%) — ноль показов за 28 дней** (GSC
     Search Analytics, окно 2026-07-25..08-21). Разбивка ровно по непроверенным
     локалям: `ar 209, kk 67, fr 33, uz 28, be 26, ms 21, id 19, az 13, tr 12,
     tg 10, ky 9, ro 9, hy 7` ≈ 463 URL. `pepperoni-infra.mdc` уже говорит
     «непроверенные локали — вне sitemap, не в индекс»; исполнять не стал:
     это bulk на 463+ страниц внутри 30-дневного окна.
     Итог 28д: 21 532 показа / 257 кликов (CTR 1.19%).
  2. **3 commercial experiment просрочены на 12 дней** — `measure_at
     2026-08-11`, статус всё ещё `measuring` в `data/operator_experiments.json`.
     В логе агента: `⚠️ Brain failed; no new operator work will start`,
     `⚠️ Optimizer report failed (non-fatal)`.
  3. **Страница эксперимента №1** `/private-label/kotlety-dlya-burgerov-optom`
     несёт `<meta name="robots" content="noindex,nofollow">` (вставлено
     `experiment_registry._noindex_new_page` перед `</head>`, коммит `58862ec91`),
     при том что строка эксперимента живёт в статусе `measuring` без
     `revert_action`. Запрос «котлеты для бургеров оптом» = 704 показа/90д,
     pos 23.4. Гейт сам не ослаблял — noindex не снимал.
  4. `git reset --hard` в деплое стирает **отслеживаемое** runtime-состояние.
     Комментарий в workflow верен только для untracked. Мой деплой снёс
     `data/{daily_ledger,agent_bus,commercial_pulse,experiments}.json`,
     `data/.pipeline_ok` (были ` M`, не закоммичены). `daily_ledger` — учёт
     бюджета, то есть предохранитель.
- **2026-08-19 baseline commit + два Restarting контейнера**:
  Done: `52f963634` на origin/main — только
  `data/buyer_baseline_{prompts,2026-08-19}.json` + `scripts/buyer_baseline_20.py`.
  Чужой хвост не в коммите. camera-monitor + gateway: диск → overlay fail в
  05:07 UTC; точечный restart, оба healthy. selectel-egress после диска:
  `bind: address already in use` на :12345 — порт держит redsocks 8 дней;
  контейнер stop + restart=no. Docker/gost/VPN не рестартили.
  Blockers: нет. Snap Chromium / архив 620 МБ не трогал.
- **2026-07-17 закрытие 0.4 (владелец: «делай как будет лучше»)**:
  Done: `rebuild_sitemap.py` → 5127 URL (pavlodar/aktobe/jakarta в sitemap);
  `geo_0.4_tasks.json` → `[]`; архив `data/geo_0.4_closed.json`;
  Current step = нет активного шага. Anthropic не вызывался.
  Blockers: нет. Рекомендация владельцу — ротировать Anthropic key (светился
  в чате).
- **2026-07-17 задача 0.4 без Anthropic (владелец: не жги токены / composer?)**:
  Done: `scripts/generate_geo_template.py` → 46 HTML (`public/geo` +
  `public/en/geo`), `is_valid_page` 48/48 ok. Anthropic не вызывался.
  Blockers: non-ru/en хвост очереди (~54) без шаблонов; LLM-reviewer не
  использовали намеренно. Batch `msgbatch_01Bvs1bE…` был в canceling.
- **2026-07-17 GEO answer-first backfill (владелец: «дополни для GEO / делай»)**:
  Done: `scripts/backfill_geo_tldr.py` + прогон по geo-локалям.
  До: RU `579–663` с tldr из ~2975; EN/AR/KK ≈ 0.
  После: `4113/4119` (99.85%). `grep -c tldr-answer` по выборке — см. коммит.
  Blockers: SSH VPS publickey denied; нет локального Anthropic key → карантин
  0.4 не продолжал (бюджетные LLM-батчи без доступа). 6 stub HTML без body
  оставлены без tldr намеренно.
- **Тестовый прогон fail_hard (по запросу владельца после Этапа 0)**:
  ручной запуск `bash scripts/seo-agent-vps.sh` на VPS дошёл до Step 4d и
  **fail_hard реально остановил пайплайн**: `🚨 FATAL: fix_pages crashed —
  QA gate cannot run on unrepaired pages, refusing to commit`, exit code
  ненулевой, никакого коммита не было. Подтверждает, что stop-the-line из
  Task 0.1 не просто проходит `bash -n`, а работает на живом дереве.
  **Побочный эффект — нашли реальный баг**, который `fail_hard` впервые
  сделал видимым: `fix_pages.py` (default no-args режим, вызывается каждый
  день в Step 4d) падал с `AttributeError: 'tuple' object has no attribute
  'read_text'`, потому что `qa_pages.changed_pages()` с коммита `6978b33e3`
  (2026-06-15, "publication gate") возвращает `list[tuple[Path, bool]]`, а
  `fix_pages.py` всё ещё итерировал по нему как по `list[Path]`. **17 дней**
  (15.06–01.07) детерминированный ремонт в Step 4d тихо не работал —
  замаскировано `|| log "⚠️ fix_pages failed (non-fatal)"` до Task 0.1.
  **Фикс**: `files = [p for p, _is_new in changed_pages()]`.
  Проверка: `python3 -m py_compile scripts/fix_pages.py` → OK; ручной запуск
  `python3 scripts/fix_pages.py` на VPS — без трейсбека (см. запись ниже
  после повторного прогона).
  `data/health.json`: НЕ создан этим прогоном — пайплайн упал на Step 4d
  раньше первого некритического `log_degradation` вызова в этом прогоне
  (все шаги до 4d либо прошли, либо их деградации не сработали). Это ожидаемо:
  health.json создаётся `log_degradation`, а не `fail_hard`.
  **Второй прогон** (после фикса `fix_pages.py`) дошёл до `qa_pages.py` и
  **fail_hard снова реально остановил пайплайн** на том же классе бага:
  `NameError: name 'files' is not defined` — тот же коммит `6978b33e3`
  (2026-06-15) переименовал переменную в `pairs` при рефакторинге
  публикационного гейта, но забыл строку `print(f"qa_pages: {len(files)}
  ...")`. Тоже 17 дней тихо падало в Step 4d, замаскировано
  `|| log "non-fatal"`. **Фикс**: `len(files)` → `len(pairs)`.
  Проверка: `python3 -m py_compile scripts/qa_pages.py` → OK; ручной запуск
  `python3 scripts/qa_pages.py --quarantine` на VPS — без трейсбека.
  **Третий прогон** — полный успех end-to-end: Step 4d (QA gate) прошёл без
  crash, Step 5 запушил 208 файлов в main, Step 6/7 (Google/Yandex submit),
  Step 8 (отчёты) — всё отработало, `=== SEO Agent finished ===`.
  Единственная деградация — `⚠️ Optimizer report failed (non-fatal)`
  (Step 8b) — некритический шаг, как и задумано в Task 0.1, не остановил
  пайплайн. `data/health.json` создан и содержит счётчик:
  `{"degradations_total": 1, "last_degradations": [{"ts": "...",
  "msg": "⚠️  Optimizer report failed (non-fatal)"}]}`.
  **Итог по трём прогонам**: `fail_hard` подтверждён на живом дереве (не
  просто `bash -n`) — дважды реально остановил пайплайн на настоящих багах
  (оба от 2026-06-15, коммит `6978b33e3`), которые 17 дней тихо ломали
  Step 4d под старым `|| log "non-fatal"`. `log_degradation`/`health.json`
  подтверждён на живом некритическом сбое. Механизм из Task 0.1 работает
  как задумано в обе стороны.
- **Задача 0.4 (данные `sosiski-v-teste`, владелец)**: диагностика подтвердила
  причину карантина по `data/page_gate_log.json` (VPS): reviewer reject
  `sosiki-v-teste-zheleznogorsk.html` — «Критерий 1 (глубина): отсутствуют
  конкретные технические характеристики продукта — нет диаметра (мм), длины
  (мм), веса единицы (г), фасовки (кг/шт в упаковке)...». На VPS в
  `data/quarantine/` подтверждено 361 файл в карантине, из них 73 —
  `sosiki-v-teste-*`/`sosiki-dlya-hotdog-*`.
  Владелец дал данные: диаметра нет (не нормируется для этого формата),
  длина сосиски 12 см, вес сосиски 45 г, вес готового изделия (сосиска+тесто)
  120 г. Внесено в `data/products_geo.json` → `usp_ru` продукта
  `sosiski-v-teste` (коммит после этой записи).
  Опечатка `sosiki-v-teste` → `sosiski-v-teste` исправлена в
  `scripts/generate_geo_bulk.py` (`_CAT_PRIORITY`); сам продукт в
  `products_geo.json` уже был на верном id/slug — опечатка не влияла на
  публикуемые страницы, только на приоритезацию категории при bulk-генерации.
  Проверка: `python3 -c "import json; ..."` → JSON валиден, `usp_ru` содержит
  новые данные; `python3 -m py_compile scripts/generate_geo_bulk.py` → OK;
  `grep -n "sosiki-v-teste" scripts/generate_geo_bulk.py` → 0 совпадений
  (было 1), `grep -n "sosiski-v-teste" scripts/generate_geo_bulk.py` → 1.
  **Не сделано в этом шаге (следующий Current step)**: перегенерация 73
  карантинных страниц через `generate_geo_bulk.py` + повторный прогон
  `page_reviewer.py` — это отдельная задача Worker, не блокер владельца.
- **Задача 0.3 (strategy refresh 167ч) — диагностика на VPS логах**:
  Не бюджет (`opus_budget.json`: $0.0054/$30 потрачено), не proxy (не
  ProxyError — то было раньше 27-29.06, сейчас другая ошибка). Корень:
  `⚠️ Opus call failed (Anthropic call failed: HTTP 400: ). Keeping existing
  strategy.` — **каждый день с 20.06** (8+ прогонов подряд), но тело ошибки
  всегда пустое `()`.
  Причина найдена в `opus_brain_client.py`: путь через `requests` (proxy
  chain) на 4xx/5xx создаёт `urllib.error.HTTPError(url, code, r.text, None,
  fp=None)`. Обработчик исключения читает тело через `e.read()`, что для
  `fp=None` кидает `KeyError('file')` внутри `tempfile.py` — это исключение
  ловится внешним `except Exception`, теряя реальный текст ошибки Anthropic
  и подставляя пустую строку. Отсюда "HTTP 400: ()" вместо настоящей причины
  каждый день — brain думал, что не может ничего сделать, escalation считал
  цикл выполненным и пропускал daily brain (Step 3.5 skip).
  **Фикс**: тело ответа теперь кладём в `http_err.body` до `raise`, обработчик
  читает `getattr(e, "body", None)` вместо `e.read()`. Побочный эффект: логика
  auto-retry без `output_config` (строка "output_config" in err_body) тоже
  была сломана тем же багом и теперь заработает, если проблема в нём.
  Проверка: `python3 -m py_compile scripts/opus_brain_client.py` → OK;
  синтетический воспроизводящий тест подтвердил, что тело ошибки теперь
  доходит до `last_err` и retry-триггер срабатывает.
  **Настоящая причина 400 (подтверждена ручным запуском `seo_brain.py` на
  VPS после фикса маскирующего бага):**
  `"Schemas contains too many optional parameters (34), which would make
  grammar compilation inefficient. Reduce the number of optional parameters
  in your tool schemas (limit: 24)."` — `STRATEGY_SCHEMA` в `seo_brain.py`
  накопила 34 опциональных поля по всем вложенным объектам (root 12 +
  memory_ops[] 7 + остальные вложенные), Anthropic считает суммарно по схеме.
  **Фикс**: сделал `required` часть полей в root (`geo_per_day`,
  `landing_per_day`, `expert_per_day`, `rewrite_pages`, `propose_tools`,
  `run_tools`, `questions`, `proactive_message`) и в `memory_ops[]` (`id`,
  `text`, `why`) — модель по-прежнему может слать `""`/`[]`, если нечего
  сказать; такие поля уже читаются через `.get(..., default)` в коде
  (`expert_per_day`, `landing_per_day`, `questions`, `proactive_message` —
  проверено). Итог: 34 → **23** опциональных, под лимитом 24.
  Проверка: скрипт-подсчёт по дереву схемы → `TOTAL: 23`;
  `python3 -m py_compile scripts/seo_brain.py` → OK.
  **Второй 400 после фикса схемы** (тестовый прогон `seo_brain.py` на VPS,
  до этого коммита): `"The compiled grammar is too large ... reduce the
  number of strict tools."` — даже 23 optional недостаточно, structured
  outputs (`json_schema`) для этой схемы вообще не годится по размеру
  грамматики. Системный промпт и так полностью описывает JSON-схему текстом
  (`ВЕРНИ СТРОГО валидный JSON ... по схеме:`), и в коде уже есть надёжный
  fallback-парсер `_extract_json()` — именно так strategy.json генерировался
  месяцами до того, как добавили `json_schema`. **Фикс `ab82e5ee1`**: убрал
  `json_schema=STRATEGY_SCHEMA` из вызова `call_opus()`, полагаемся на
  текстовый промпт + `_extract_json`.
  Проверка: `python3 -m py_compile scripts/seo_brain.py` → OK.
  **Ещё не подтверждено**: реальный успешный вызов brain на VPS после этого
  фикса — следующий шаг.
- **Страховка после отключения json_schema (по запросу владельца)**:
  `_extract_json()` — теперь единственный парсер ответа Opus, а structured
  outputs (schema enforcement на стороне Anthropic) больше нет. Добавлена
  ручная валидация в `seo_brain.py` перед `STRATEGY_FILE.write_text(...)`:
  проверка присутствия всех `STRATEGY_SCHEMA["required"]` ключей + сверка
  типа каждого присутствующего поля с `STRATEGY_SCHEMA["properties"][key]
  ["type"]` (array/object/string/integer). При провале — `strategy.json`
  НЕ трогается, отправляется Telegram-алерт с списком проблем, функция
  возвращает 0 (не валит пайплайн — это данные, не код).
  Синтетический тест (валидный / пропущенный ключ / неверный тип):
  `missing: [] type_errors: [] PASS`; `missing: ['geo_daily_target']`;
  `type_errors: ['new_blog_topics: ожидался array, пришёл str']` — все три
  сценария сработали как задумано.
  Проверка: `python3 -m py_compile scripts/seo_brain.py` → OK.
- **Задача 0.2 (dual scheduling)**: VPS cron — единственный primary канал для
  ежедневного цикла. В GitHub Actions:
  - `seo-agent.yml` (daily 08:30 MSK, дублировал `seo-agent-vps.sh`) → `if: false`
  - `seo-scout.yml` (every 6h, дублировал Step 3.3 на VPS) → `if: false`
  - `update_catalog.yml` (every 6h) и `sync-prices.yml` (daily) → `if: false`
    (оба дублировали `sync-vps.sh`, который уже крутится каждые 10 мин на VPS —
    канонический sync по `pepperoni-infra.mdc`)
  - `competitor-scout.yml` и `aio-visibility.yml` (Mon) — оставлены ACTIVE как
    единственный канал; дублирующий блок (Step 3.48/3.49, `date +%u = 1`)
    убран из `seo-agent-vps.sh`, чтобы не было второго запуска по понедельникам.
  - `deploy-vps.yml`, `gsc-index.yml` — не трогали (не дублируют daily loop).
  Проверка: `grep -rln "if: false" .github/workflows/` → 4 файла
  (`seo-agent.yml`, `seo-scout.yml`, `update_catalog.yml`, `sync-prices.yml`).
  `grep -c "competitor_scout.py\|aio_visibility.py" scripts/seo-agent-vps.sh` → 0.
  Все workflow YAML провалидированы `yaml.safe_load`, `bash -n` на
  `seo-agent-vps.sh` — OK.
- **Задача 0.1 (stop-the-line)**: `seo-agent-vps.sh` — критические шаги
  (`git pull --rebase`, `fix_pages.py`, `qa_pages.py --quarantine`) переведены
  на `fail_hard` (exit 1, пайплайн останавливается). Остальные 38 некритических
  шагов (GSC/Yandex fetch, scout, optimizer, brain, аio-мониторинг и т.д.)
  переведены на `log_degradation` — пишут счётчик + последние 50 записей в
  `data/health.json`, пайплайн продолжается.
  Проверка: `grep -c '|| log "' scripts/seo-agent-vps.sh` → **0** (было 41).
  `grep -c 'fail_hard "' scripts/seo-agent-vps.sh` → **3**.
  `grep -c 'log_degradation "' scripts/seo-agent-vps.sh` → **38**.
  `bash -n scripts/seo-agent-vps.sh` → OK.
- env-export в one-liner не экспортировал переменные → `ANTHROPIC_API_KEY not set`.
  Корень: нет `set -a`. Починено.
- `98ce1d562` — Haiku migration (Класс А, 11 файлов). CONTENT_MODEL = haiku-4-5-20251001
  в claude_client.py. GEO_MODEL → CONTENT_MODEL в generate_geo_bulk. Reviewer/brain
  остаются на Sonnet. aio_visibility не тронут.
- VPS перестал отвечать по SSH после коммита `109cdc54` (auto-update catalog, ~09:53 UTC).
  Скорее всего OOM (несколько Python-процессов одновременно), не наша правка.
- **Haiku A/B тест `6ba58b3c`**: 40% pass vs 88% на Sonnet/DeepSeek.
  Причины: markdown fences в HTML + игнор негативных банов на длинных промптах.
  Вывод: слабые модели системно не держат длинные негативные инструкции.
- **CONTENT_MODEL revert `924f466d5`**: вернули на Sonnet (claude-sonnet-4-6).
  CHEAP_MODEL=haiku сохранён как алиас для env-override A/B в будущем.
- **Bounded-пилот 2026-06-21 (`b52eadaf`) — РУЧНОЙ ЗАПУСК, не автономный тик:**
  - 13 pass / 2 quarantine / 0 errors из 15 задач; pass rate 87%; spend +$0.08
  - Конвейер генерация → гейт → публикация/карантин доказан.
- **✅ Автономный тик 2026-06-22 08:32 MSK — подтверждён без участия человека:**
  - +230 страниц, конкурентная разведка, sweep, AIO-мониторинг — всё автономно.
  - Дайджест пришёл в Telegram до первого сообщения человека в чат.
  - Настоящая автономия зафиксирована.

## Backlog — следующие шаги, строго по одному

1. **Допрогнать GEO-bulk на оставшихся городах** после получения данных sosiki-v-teste.
2. **Watchdog VPS (OOM-алерт):** systemd unit с `Restart=always` для telegram_bot.py
   + cron-check (`journalctl -k | grep -i "oom\|killed"` после перезагрузки → алерт в Telegram).
   Предотвращает повтор ситуации «SSH молчит, причина неизвестна».
3. **Архивация STARTUP-AIO:** переложить старые AIO-отчёты в `data/aio_archive/`
   чтобы рабочий файл не рос бесконечно.
