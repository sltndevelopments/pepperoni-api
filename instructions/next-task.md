# next-task.md — Architect → Worker handoff

## Goal
Зафиксировать новые рельсы как реальность и валидировать автономный цикл на
вылеченной среде VPS — не выходя за рамки гейта, бюджета и лимита итераций.

## Current step — выполнить ОДИН, потом остановиться

- [ ] Закоммить рельсы отдельным помеченным коммитом.

- Файлы: `CLAUDE.md`, `.cursor/rules/*.mdc`, `instructions/next-task.md`,
  `instruction_next.md`, `AGENTS.md`, `docs/CURSOR-WORKFLOW.md`.
- Сообщение: `chore(workflow): architect/worker rails + executor gates`.
- Запушь в `main`.
- Отчёт в Log: хеш + `git show --stat <hash>` + проверка
  `git ls-files | grep -E "CLAUDE.md|agent-executor"` ≠ пусто.
- Пилот в этом шаге НЕ запускать.

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
  Корень: нет `set -a`. Чинится в Backlog п.1.
- `98ce1d562` — Haiku migration (Класс А, 11 файлов). CONTENT_MODEL = haiku-4-5-20251001
  в claude_client.py. GEO_MODEL → CONTENT_MODEL в generate_geo_bulk. Reviewer/brain
  остаются на Sonnet. aio_visibility не тронут. Сэмпл ожидает VPS.
- VPS перестал отвечать по SSH после коммита `109cdc54` (auto-update catalog, ~09:53 UTC).
  Скорее всего OOM (несколько Python-процессов одновременно), не наша правка.
  **TODO (watchdog):** добавить systemd watchdog или health-check скрипт + Telegram-алерт
  при недоступности SSH — чтобы не упираться в тишину вслепую. Паркую в Backlog.

## Backlog (watchdog / infra)
- Watchdog: systemd unit с `Restart=always` для telegram_bot.py + cron-check на OOM
  (`journalctl -k | grep -i "oom\|killed"` после перезагрузки → алерт в Telegram).
  Предотвращает повтор ситуации «SSH молчит, причина неизвестна».
