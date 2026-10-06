# Почему production расходится с git (слепок 2026-10-06 ~20:03 UTC)

Слепок только на чтение: `HEAD=caa4605dd` = `origin/main`, но **185 путей вне git** (157 M + 28 ??; 143 в `public/`).
Синхронизация **не выполнялась**. Ниже — источник каждой группы и предложение, каким должен быть источник истины.

## Кто пишет каждую группу

| Группа | Число | Кто пишет | Расписание |
|---|---|---|---|
| Карточки `public/products/*.html`, `public/en/products/*.html` | 124 | `gen-ru-products.py` / `gen-en-products.py` после `sync-sheets.mjs` | `sync-vps.sh` каждые 10 мин |
| Хабы категорий (`sosiski-dlya-hotdog`, `vetchina-optom`, колбасы, котлеты, выпечка) | 6 | `gen_category_pages.py` | каждые 10 мин |
| `public/products.json`, `about.html`, `rss.xml`, `sitemap.xml` | 4 | sync + `reconcile_sku_count.py` + `rebuild_sitemap.py` | каждые 10 мин |
| `llms.txt` / `llms-full.txt` RU+EN | 4 | `gen-llms-full.py` | каждые 10 мин |
| Прайс `wholesale-price-list*` + `yml.xml` | 5 | `gen_price_lists.py` / фиды | каждые 10 мин |
| `data/*.json` телеметрия (metrika, goals, health, agent_bus, outcomes, …) | 39 | SEO-агент 05:30 UTC, worker, cron `outcome_tracker`, `monitor_seo_health` | ежедневно / каждые 30 мин |
| `data/.pipeline_ok` | 1 | маркер конца `seo-agent-vps.sh` | ежедневно |
| `data/spec_holds_raw-*.json` (??) | 24 | `apply_spec_holds.py` — дневной дамп сырых удержаний | каждые 10 мин |
| `deploy/rinatsultan-mcp.env` (??) | 1 | секрет на сервере | не в git |
| `scripts/_wtest` (??) | 1 | черновик на сервере | не в git |

Дополнительно (не в `git status`, но меняют дерево): `seo-agent-vps.sh` (05:30 UTC) гоняет `fix_pages`, `qa_pages --quarantine`, `build_index_manifest`, `rebuild_sitemap`, `fix_hreflang` и **автокоммитит в main**. `seo-worker.sh` каждые 3 часа сейчас no-op.

## Что именно меняется в HTML

На карточках типичный diff — **курсы экспортных цен** (KZT/UZS/KGS/BYN/AZN) при неизменной рублевой цене. Пример `kd-001`: `1418.99 ₸` → `1402.3 ₸`. Это нормальный runtime каталога, не ручная правка.

`data/index_manifest.json`: `keep` остался 242, `generated_at` и набор **retired/noindex** черновиков выросли (1491 → 1495). Файл пересобирается каждые 10 минут, поэтому всегда «грязный».

## Нормальные runtime-данные (вынести из git или в `.gitignore`)

Не источник истины для сайта. Сейчас часть из них коммитится агентом и создаёт шум:

- `data/.pipeline_ok`, `data/health.json`, `data/daily_ledger.json`
- `data/agent_bus.json`, `data/outcomes.json`, `data/goals.json`, `data/metrika.json`
- `data/llm_costs.json`, `data/opus_budget.json`, `data/operator_experiments.json`
- `data/kazandel_health.json`, `data/seo_health.json`, `data/sitemap_content_state.json`
- `data/spec_holds_raw-*.json` (уже в `.gitignore` этой ветки)
- `data/kazandel_health_alert.json`, `scripts/_wtest`
- **секреты:** `deploy/*.env` (уже в `.gitignore`; не коммитить)

`data/index_manifest.json` — **не runtime**: это политика индекса. Должен меняться только контролируемым коммитом.

## Генерируемый контент, который должен попадать в git контролируемо

- Карточки и хабы: результат генераторов из Sheets/`products.json`
- `public/products.json` — снапшот каталога
- `llms.txt`, прайс, `yml.xml`, `sitemap.xml`, `rss.xml`

Сейчас они пишутся на VPS каждые 10 минут и **не коммитятся**, пока утренний агент не сделает `git add -u public/**/*.html`. Между sync и агентом production ≠ git. После `deploy-vps.yml` (`git reset --hard origin/main`) незакоммиченное на сервере стирается — и через 10 минут sync пишет снова.

## Предложение: источник истины

| Артефакт | Источник истины | Как доставлять |
|---|---|---|
| Ассортимент, цены RUB, фото, ТН ВЭД | Google Sheets | sync в CI или на VPS → `products.json` |
| Экспортные валюты | live FX на sync (runtime) | либо не хранить в git-HTML, либо снапшот раз в день в коммите |
| Индексируемые URL (keep/301/410/noindex) | `data/index_manifest.json` + `url_consolidation_map.json` в git | менять только PR-ом |
| Тексты money/trust/blog | git | генератор в CI, ревью, merge |
| Телеметрия `data/*.json` | диск VPS / вне репо | `.gitignore` + том `/var/www/pepperoni/data` |
| Секреты | `seo-agent.env` вне репо | уже так |

## Безопасный план синхронизации (не выполнять, пока владелец не скажет)

1. После merge PHASE 1: деплой как обычно (`reset --hard`). Ожидать, что 10-минутный sync снова испачкает карточки ценами — это нормально, **не** `git add -A` и не `commit` с сервера.
2. Не копировать 185 грязных путей в git одним коммитом: там runtime, секреты и курсы валют.
3. Когда решите «VPS = main» для HTML: прогон генераторов в CI от того же `products.json`, diff против `public/`, ревью, отдельный PR. Не `rsync` с сервера.
4. Runtime JSON — перестать коммитить агентом (отдельная задача, не PHASE 1).
5. Никогда не `git add deploy/*.env`.

## Что PHASE 1 уже закрывает в коде

Карантин QA не уносит `status=keep`. Автокоммит снимает удаления allowlist со staging. Карточки-сироты не удаляются. A/B не ставит noindex. Массовые `--apply` 301/410 требуют `ALLOW_INDEX_MUTATION=1`.
