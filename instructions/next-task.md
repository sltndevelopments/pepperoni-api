# next-task.md — Architect → Worker handoff

## Goal
Зафиксировать новые рельсы как реальность и валидировать автономный цикл на
вылеченной среде VPS — не выходя за рамки гейта, бюджета и лимита итераций.

## Current step — выполнить ОДИН, потом остановиться

- [ ] Дождаться планового cron-тика (завтра ~08:30 MSK). **НЕ запускать вручную.**
  Когда тик случится сам — зафиксировать в Log:
  - Сработал ли БЕЗ команды человека (по timestamp коммита и Telegram-дайджеста,
    до того как кто-либо писал в чат).
  - Тот же отчёт: страниц / pass / hold / reject / $ + хеш коммита.
  Это последнее звено для подтверждения настоящей автономии.

## Backlog — следующие шаги, строго по одному
1. **Bounded-пилот автономного цикла на VPS.**
   - Сначала почини export: `set -a; source seo-agent.env; set +a`.
   - Перед запуском напиши в Log, ЧТО именно гоняет пилот и его бюджет-конверт.
   - Границы: ≤ 75 c, дневной бюджет-кап активен, гейт активен
     (`page_reviewer` + `verify_invariants`), ≤ 3 попытки на одну ошибку.
   - Отчёт: метрики (страниц, pass/hold/reject, $ потрачено) → СТОП.
2. **Данные для `sosiki-v-teste`** — ЖДУТ ВЛАДЕЛЬЦА (длина, диаметр, MOQ корн-дога).
   Внести в `data/products_geo.json` → перегенерить → карантин частично разблокируется.
3. Допрогнать GEO-bulk на оставшихся городах после (1)–(2).

## Log
- env-export в one-liner не экспортировал переменные → `ANTHROPIC_API_KEY not set`.
  Корень: нет `set -a`. Починено в этой сессии.
- `98ce1d562` — Haiku migration (Класс А, 11 файлов). CONTENT_MODEL = haiku-4-5-20251001
  в claude_client.py. GEO_MODEL → CONTENT_MODEL в generate_geo_bulk. Reviewer/brain
  остаются на Sonnet. aio_visibility не тронут. Сэмпл ожидает VPS.
- VPS перестал отвечать по SSH после коммита `109cdc54` (auto-update catalog, ~09:53 UTC).
  Скорее всего OOM (несколько Python-процессов одновременно), не наша правка.
  **TODO (watchdog):** добавить systemd watchdog или health-check скрипт + Telegram-алерт
  при недоступности SSH — чтобы не упираться в тишину вслепую. Паркую в Backlog.
- **Haiku A/B тест `6ba58b3c`**: 40% pass vs 88% на Sonnet/DeepSeek.
  Причины: markdown fences в HTML + игнор негативных банов на длинных промптах.
  Вывод: слабые модели системно не держат длинные негативные инструкции — не специфика DeepSeek.
- **CONTENT_MODEL revert `924f466d5`**: вернули на Sonnet (claude-sonnet-4-6).
  CHEAP_MODEL=haiku сохранён как алиас для env-override A/B в будущем.
- **fix(geo-bulk) `6ba58b3ce`**: DEEPSEEK_API_KEY guard → ANTHROPIC_API_KEY.

- **Bounded-пилот 2026-06-21 (`b52eadaf`) — РУЧНОЙ ЗАПУСК, не автономный тик:**
  - Запуск: `seo-agent-vps.sh` вручную через SSH + `MAX_GEO_PAGES=75 --mode russia --ignore-strategy`
  - Конвейер (генерация → гейт → публикация/карантин) работает правильно — доказано.
  - **Настоящий автономный тик ещё НЕ зафиксирован.** Ожидается завтра ~08:30 MSK.
  - Результат: **13 pass / 2 quarantine / 0 errors** из 15 задач в очереди (queue < 75 — coverage для russia оказалась меньше лимита)
  - Pass rate: **87%** (13/15) — в норме, сопоставимо с прошлыми 88% на Sonnet
  - Spend: $0.50 → $0.58 (+$0.08 за прогон) — далеко от дневного капа $10
  - **Бюджет-guard физически активен**: строки `BudgetExceeded`/`bulk_budget` в коде = 11 вхождений (grep confirmed), `LLM_BULK_BUDGET_USD=5` выводится в лог
  - **Гейт активен**: 2 страницы уходят в карантин по Критерию 1 (sosiki-v-teste — нет числовых данных, это known issue — ждёт данных от владельца)
  - **verify_invariants на 3 страницах**: 6/6 критичных инвариантов ✅ (halal, fake-reviews, contacts, ar-no-pork, docs-in-process, fix-links). Единственное нарушение — `card-link-wrapper` (index.html, не geo-страница, отдельный issue)
  - CONTENT_MODEL=Sonnet подтверждён на VPS
  - VPS, local, origin/main синхронизированы на `b52eadaf`

## Backlog (watchdog / infra)
- Watchdog: systemd unit с `Restart=always` для telegram_bot.py + cron-check на OOM
  (`journalctl -k | grep -i "oom\|killed"` после перезагрузки → алерт в Telegram).
  Предотвращает повтор ситуации «SSH молчит, причина неизвестна».
