# Отчёт спринта «после P0»: измерение, достоверность, инвентаризация

Ветка `sprint/post-p0-verification` (8 коммитов над `origin/main` 49f69df5a, 233 файла).
Ничего из ветки **не задеплоено** на сайт, кроме двух nginx-сниппетов для `api.pepperoni.tatar`
(см. «Применено на VPS напрямую»). Деплой остального — после решения владельца.

## 1. Сделано (по задачам задания)

| Задача | Результат | Коммит | Доказательство |
|---|---|---|---|
| Google Indexing API — не использовать для обычных страниц | `gsc-index.py` отказывает без флага JobPosting/BroadcastEvent; убран из `nudge_google_after_seo.sh`, `seo-agent-vps.sh` (cron), `gsc-index.yml`; правило в `agent-executor-gates.mdc`, `docs/GSC_SETUP.md` | 219cd8b85 | `grep -c 'gsc-index.py --hot' scripts/nudge_google_after_seo.sh scripts/seo-agent-vps.sh` → 0, 0 |
| Sitemap `/en` → `/en/` | правило локальных корней в `rebuild_sitemap.py` и `build_index_manifest.py`; `check_trailing_slash_policy` валит сборку при нарушении; тест `test_sitemap_canonical.py` (8 тестов OK) | 4b932d769 | `grep -c '<loc>https://pepperoni.tatar/en</loc>' public/sitemap.xml` → 0 |
| Один hreflang для страниц и sitemap | `hreflang_policy.py` (x-default RU, кроме export/pepperoni → EN); `fix_hreflang.py` в `sync-vps.sh`; `--check` → 0 расхождений | 4b932d769 | `python3 scripts/fix_hreflang.py --check` → `0 page(s) disagree` |
| Проверка всех URL sitemap вживую | `verify_sitemap_live.py` → `sitemap-live.csv`: 239 URL, 239 × 200 (один таймаут перепроверен вручную: 200). 38 hreflang-расхождений на проде исчезнут после деплоя ветки | 4b932d769 | `docs/sprint-2026-09/sitemap-live.csv` |
| Ревизия redirect'ов гео-страниц | `redirect-review.csv`: 363 URL с кликами: 259 × 301 совпадение семьи, 67 × 410 (товар не продаётся), 37 × 301 помечены «family mismatch» на ручную проверку; `geo_target` перестал слать «не продаём» на главную, CIS-локали → RU-хаб | 51f3763ad | `docs/sprint-2026-09/redirect-review.csv` (58 строк `manual_review=yes`) |
| Аналитика: снять 45 с, считать заявку один раз | `armAnalytics` → первый idle после `load`; `form_start` / `generate_lead` + `lead_submit_success` только после `lead_id` от сервера; дедуп клиент (sessionStorage) + сервер (`client_ref`, 6 ч); PII убрана из `dataLayer`; логи без телефона; `version_assets.py` (cache-bust `?v=sha8`) | 255f97fce | `measurement-plan.md`; `grep -c 'lead_id' public/assets/lead-form.js infra/scripts/lead_intake_server.py` → 4, 11 |
| Контакт-клики считались дважды | второй inline-слушатель Метрики на главной RU и 124 карточках удалён (генераторы + HTML) | 95044aaee | `rg -l click_messenger public --glob '*.html' | wc -l` → 0; отправляет только `lead-form.js` |
| Прайсы из одного источника | `gen_price_lists.py` → 4 файла из `products.json` (в `sync-vps.sh`); ручные снапшоты 25.07 (62 vs 64 SKU, другой USD) заменены | 77f33b51f | `grep -c KD-012 public/wholesale-price-list*` → 0 ×4 |
| Согласованность фактов | `check_fact_consistency.py`: 62 SKU × RU/EN карточка, 4 каталога, 2 прайса → **0 расхождений** | 77f33b51f | `fact-consistency.csv` |
| KD-013 «роликовый гриль» + прочие данные | не правлено (данные — ячейка Sheet на всю «Заморозку»); 14 вопросов технологу/продажам | 77f33b51f | `technologist-questions.md` |
| Инвентаризация контента | `content-inventory.csv`: 4573 URL (239 index / 405 301 / 1067 410 / 19 noindex / 2843 мёртвых legacy), клики июль vs август, решение по строке. **Индексируемых статей 25** (RU 13, EN 12) — новые URL не нужны | 8f23fc499 | `python3 scripts/build_content_inventory.py --gsc …` |
| Базовая линия поиска | `weekly-search-baseline.csv`: 14 полных недель, по типу страниц / языку / бренд-небренд; пропуски записаны (нет Яндекс-истории, нет достоверных заявок до 09.09) | 8f23fc499 | клики/нед: 74 → 149 (пик 29.06) → 50 (31.08); гео-страницы дали 52→13 |
| Карта коммерческих страниц | `content-map.csv`: 4 страницы + 6 статей: что есть, чего нет (выбор/условия/доказательства/шаг), владелец фактов | 8f23fc499 | — |
| Брифы | испытание пепперони при выпечке (протокол технологу), подтверждённый кейс клиента (согласие + цифры) | 8f23fc499 | `brief-*.md` |
| Внешние профили | `brand-profile-register.csv`: 2ГИС, Zoon, Fabricators + Яндекс Бизнес, GBP, LinkedIn, подписи, КП; kazandelikates.tatar остаётся | 8f23fc499 | — |
| api.pepperoni.tatar для агентов | `/llms.txt`, `/robots.txt`, `/openapi.yaml`, `/.well-known/ai-plugin.json` отдавали **403 Vercel Security Checkpoint** любому не-браузеру; теперь с VPS; корень api → 301 на apex | 88c8d9fc9 | `curl -sI https://api.pepperoni.tatar/llms.txt` → 200, `X-Data-Source: vps-local` |

## 2. Что показали данные

- Падение кликов июнь→сентябрь почти целиком — гео-страницы (270 → 116 → 10 кликов/мес), которые сняты сознательно. Остальные типы: блог 51→60, хабы 31→32, товары 18→6 (падение товаров — единственное, за чем следить).
- Бренд-запросы: 0–2 клика в неделю. Узнаваемости в поиске практически нет — подтверждает приоритет внешних профилей и кейсов над разметкой.
- Заявки: достоверного ряда до 2026-09-09 нет; всё, что было в GA4, содержало двойной счёт кликов и заявки без подтверждения.

## 3. Применено на VPS напрямую (вне деплоя)

Два nginx-сниппета скопированы в `/etc/nginx/snippets/` и nginx перезагружен (`nginx -t` OK):
`api-products-local.conf` (расширен) и `api-host-canonical.conf`. Содержимое идентично файлам в
ветке; после merge `apply_nginx_api_products.sh` из `deploy-vps.yml` установит те же файлы.
Причина не ждать: 403 на discovery-файлах для всех агентов — прямое противоречие цели проекта.

Обнаруженный дрейф: `deploy-vps.yml` в `main` вызывает `scripts/apply_nginx_api_products.sh`,
которого в `main` нет — файл лежал untracked на VPS и на ноутбуке. Теперь в ветке.

## 4. Гейты (запущены локально на ветке)

```
test_sitemap_canonical.py      Ran 8 tests OK
check_fact_consistency.py      62 SKU → 0 mismatch(es)
fix_hreflang.py --check        0 page(s) disagree with sitemap
fix_pages.py / qa_pages.py     182 changed HTML → 0 repaired / 0 FAIL; 125 (карточки+главная) → 0 / 0
check_catalog_images.py        OK (12 SKU без фото — плейсхолдер, известно)
node --check lead-form.js      OK
```

## 5. Не сделано / ждёт человека

| Что | Кто | Почему не агент |
|---|---|---|
| Ответы на 14 вопросов (`technologist-questions.md`), правки в Sheet | технолог, продажи | факты о продукте |
| EN-названия → колонка Sheet | владелец | утверждение перевода |
| Правки текста 4 коммерческих страниц | агент **после** фактов | без фактов будет очередной SEO-текст |
| Обновление 6 статей, 2 новых материала | агент после брифов | нужны измерения и согласие клиента |
| Смена сайта в 2ГИС/Zoon/Fabricators, проверка Яндекс Бизнес/GBP | владелец (доступы) | — |
| В Метрике/GA4: `form_submit` → «попытка», key event только `generate_lead` | владелец аккаунтов | — |
| Ручная проверка 37 «family mismatch» в `redirect-review.csv` | владелец/продажи | семантика товара |
| Яндекс Вебмастер: история для baseline | после накопления | токен обновлён 09.09 |

## 6. Запрос на деплой

Merge `sprint/post-p0-verification` → `main` запустит `deploy-vps.yml` (reset --hard + nginx-скрипты).
Затронет: главные RU/EN и 124 карточки (аналитика), 182 страницы (hreflang), sitemap, прайсы,
lead-intake сервер (workflow рестартует `lead-intake`, шаг «Restart lead-intake service on VPS»),
`sync-vps.sh` (новые шаги). После деплоя — 5 проверок из `measurement-plan.md` и
`bash scripts/nudge_google_after_seo.sh` (sitemap; Indexing API больше не вызывается).
