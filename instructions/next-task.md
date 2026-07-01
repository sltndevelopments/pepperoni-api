# next-task.md — Architect → Worker handoff

## Goal
Зафиксировать новые рельсы как реальность и валидировать автономный цикл на
вылеченной среде VPS — не выходя за рамки гейта, бюджета и лимита итераций.

## Current step — ЖДЁТ ВЛАДЕЛЬЦА

**Данные для `sosiki-v-teste`** — предоставить числовые характеристики продукта:
- длина (мм)
- диаметр (мм)
- вес единицы / упаковки (г)
- MOQ (шт / кг)

После получения данных:
1. Внести в `data/products_geo.json` (поле `usp_ru` продукта `sosiki-v-teste`).
2. Перегенерить карантинные страницы (~360 стр.), где причина hold — отсутствие числовых данных.
3. Ожидаемый результат: карантин частично разблокируется → новые страницы проходят гейт.

## Log

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
  **Ещё не подтверждено**: реальный успешный вызов Opus с новой схемой (нужен
  следующий прогон brain на VPS — сам вызов из диагностики использовал старую
  схему и упал на этой же ошибке до фикса).
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
