# next-task.md — Architect → Worker handoff

## Goal
Зафиксировать новые рельсы как реальность и валидировать автономный цикл на
вылеченной среде VPS — не выходя за рамки гейта, бюджета и лимита итераций.

## Current step

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
