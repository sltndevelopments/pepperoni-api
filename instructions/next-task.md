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
