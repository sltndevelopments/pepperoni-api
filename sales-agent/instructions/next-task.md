# next-task.md — Architect → Worker handoff (sales-agent / Стив)

Рельсы исполнителя те же, что и для основного репо: `CLAUDE.md` в корне
`pepperoni-api` + `.cursor/rules/agent-executor-gates.mdc`. Готово = строки
в `origin/main`, не проза.

## Goal

Воронка Стива стояла 11 дней (последняя отправка 2026-06-21). Диагностика на
VPS (`agent.db`) дала три факта:
1. Реестровый поток (`feed_agent.py`, воскресенье 00:00 UTC) упал 28.06 на
   транзиентном сетевом сбое (`Errno -3: Temporary failure in name resolution`
   при резолве `bo.nalog.gov.ru`) и **не восстановился** — скрипт не ретраит,
   следующий запуск только через cron (воскресенье). API сейчас отвечает 200
   (проверено вручную) — сбой был временным, не блокировкой по IP.
2. Именной поток (12 targets, 5 tier-S) сидит в `named_target=new` без
   исследования ЛПР — `named_escalation_candidates()` в `outreach.py`
   определена, но нигде не вызывается.
3. Исходящие email не попадают в таблицу `messages` (0 строк `direction=out`
   при 160 `drafts.status=sent`) — воронку нечем измерить в `messages`,
   только через `drafts`/`audit_log`.

Три задачи ниже — один PR, но три независимых, последовательно
верифицируемых шага. Не переписывать `run_cycle.py` целиком, не трогать
`gate.py` decision-логику (`auto_gate.decide_outbound`), не трогать
`page_reviewer.py`/`deploy_check.py`/`data/invariants.json` (это другой
продукт — сайт, не sales-agent).

## Current step

### Шаг A (P2, логирование, делать первым — остальное на нём проверяется)

**Файл:** `channels/email.py` или `core/gate.py::_send_one_draft` (там, где
`send_email()` возвращает `{"ok": True, ...}` после реальной отправки).

Добавить запись исходящего сообщения в `messages` при успешной отправке:
- Новый метод `Store.add_outbound(lead_id, channel, subject, body, *, meta=None) -> str`
  в `core/store.py`, симметричный уже существующему `add_inbound` (тот же
  паттерн: создать/переиспользовать `thread` по `lead_id`+`channel`, вставить
  строку в `messages` с `direction='out'`).
- Вызывать его в `Gate._send_one_draft` сразу после
  `self.store.mark_draft_sent(draft_id)` в ветке `channel == "email"` и
  `result.get("ok")`.
- Не трогать существующий `add_inbound` — только добавить симметричный метод.

**Verify:**
```
grep -n "def add_outbound" core/store.py
grep -n "add_outbound" core/gate.py
python3 -m py_compile core/store.py core/gate.py
```
После следующего живого цикла на VPS (после деплоя):
```sql
SELECT COUNT(*) FROM messages WHERE direction='out';  -- было 0, должно быть >0
```

### Шаг B (P0, реестровый поток — восстановить конвейер)

**Файл:** `sales-intel/scripts/fetch_bo_okved.py::_get_json`

1. Добавить retry с backoff на транзиентные сетевые ошибки (не HTTP 4xx —
   те реальные, ретраить нет смысла): 3 попытки, backoff 5/15/30 сек, ловить
   `urllib.error.URLError` (включая `socket.gaierror`/DNS) и `TimeoutError`.
2. Если после ретраев ошибка сохраняется на конкретном ОКВЭД — **не ронять
   весь прогон** (`break` на этом ОКВЭД уже есть в `feed_agent.py` через
   исключение из `fetch_page`), но залогировать явно `FATAL_OKVED={okved}`
   в stderr, чтобы это было видно в `kd-feed-agent.log` не как молчаливый 0.
3. **Ручной прогон сейчас** (не ждать воскресенья): на VPS
   `cd /var/www/pepperoni && python3 sales-intel/scripts/feed_agent.py`,
   без `--dry-run`, чтобы восстановить поток немедленно. Логировать вывод.
4. Если после ручного прогона `outreach_candidates()` всё ещё пустой —
   прогнать `python3 -m console.cli enrich --limit 100` (в `sales-agent/`)
   на no_email лидах, это отдельно чинит покрытие email, не реестр.

**Не делать:** не снижать пороги выручки в `score_bo_leads.py` без
предварительной проверки, что реестр реально исчерпан (а не просто был
недоступен) — судя по логам сбой был чисто сетевой, пороги трогать рано.

**Verify:**
```
grep -n "for attempt" sales-intel/scripts/fetch_bo_okved.py
python3 -m py_compile sales-intel/scripts/fetch_bo_okved.py
```
На VPS после ручного прогона:
```sql
SELECT COUNT(*) FROM leads WHERE status='new' AND source LIKE 'sales-intel%'
  AND created_at > '2026-07-01';  -- новые свежие лиды после ручного прогона
```
И убедиться, что `python3 -c "from orchestrator.outreach import outreach_candidates; from core.store import Store; print(len(outreach_candidates(Store())))"` > 0.

### Шаг C (P1, named escalation wiring)

**Новый файл:** `workers/named_escalation.py`

Функция `escalate_named_targets(store, *, limit=2) -> dict`:
1. Взять `named_escalation_candidates(store, limit=limit)` из
   `orchestrator/outreach.py` (limit по умолчанию **2**, не 20 — по прямому
   требованию владельца: не больше 1–2 эскалаций за цикл).
2. Дополнительный недельный кулдаун поверх cycle-лимита: пропускать лид, если
   `ap.get(profile, "owner_escalated_at")` не старше 7 дней (использовать уже
   существующий `owner_escalated_at` — НЕ вводить новое поле).
3. Для каждого кандидата (не более `limit` за вызов):
   - `contact_research.research_contacts(lead, deep=True)` → email/сайт.
   - Perplexity-запрос ЛПР: категорийный менеджер по готовой еде/кулинарии
     под конкретный `segment`/`pitch` лида из `named_targets.yaml`
     (`lead["profile"]["_agent"]["named_pitch"]` или аналогичное поле, если
     оно уже прокинуто `import_named.py` — проверить перед добавлением
     нового; если нет — прокинуть `pitch` в profile при импорте).
   - Записать найденное в `profile.lpr_name` / `profile.lpr_email` /
     `profile.lpr_phone` (поля уже определены в `config/crm_schema.yaml`,
     синхронизируются в Google Sheet через `crm/google_sync.py` — их и
     использовать, не изобретать новые).
   - Сформировать draft первого касания через `draft_cold_email`-подобный
     промпт, но **не отправлять** — только текст в эскалации. Оффер должен
     быть конкретным SKU из `pitch` поля named_targets (уже там прописан:
     "сосиска в тесте для готовой еды" и т.п.), не общий текст.
   - Определить канал выхода: если есть публичный портал поставщика для
     этой сети (известно для Магнит/X5 — оставить как TODO-заметку в
     тексте эскалации "Портал поставщика: проверить у Магнит/Перекрёсток",
     не выдумывать URL) — иначе email/телефон.
   - Эскалировать через `workers/escalate.py::escalate_to_owner()` (уже
     существующий, не переписывать) с `reason="named_target_researched"` и
     `context=` включающим ЛПР + канал + draft-текст.
   - Статус лида → `escalated` (не `contacted`, не `hot` — задать явно через
     `store.upsert_lead(..., status="escalated", ...)` перед вызовом
     `escalate_to_owner`, либо расширить `escalate_to_owner` третьим
     необязательным параметром `target_status="hot"` со значением по
     умолчанию `"hot"`, и звать с `target_status="escalated"` отсюда —
     выбрать вариант с меньшим диффом).

**Файл:** `orchestrator/run_cycle.py`

Добавить вызов `escalate_named_targets(store, limit=2)` одним блоком, по
аналогии с существующими try/except обёртками в файле (`bounce_recovery`,
`crm_sync`) — не ронять цикл при ошибке, попасть в `summary`:

```python
try:
    from workers.named_escalation import escalate_named_targets
    summary_named = escalate_named_targets(store, limit=2)
except Exception as e:
    summary_named = {"skipped": str(e)[:200]}
results.append({"worker": "named_escalation", **summary_named})
```

Разместить после блока `bounce_recovery` (строка ~50), до `outreach_pending`.

**Verify:**
```
grep -n "named_escalation" orchestrator/run_cycle.py
python3 -m py_compile workers/named_escalation.py orchestrator/run_cycle.py
```
Ручной прогон на VPS (`python3 -m orchestrator.run_cycle` с `dry_run_send=True`,
чтобы не отправить реальный email по ошибке — эскалация email не шлёт, но
проверить это глазами в выводе) → должен прийти Telegram с одним из 5 tier-S
(Самокат/КУПЕР/Лавка/Газпром/ЛУКОЙЛ), содержащий ЛПР или явную пометку, что
ЛПР не найден, + draft + канал выхода.
```sql
SELECT status, COUNT(*) FROM leads WHERE source='named_targets' GROUP BY status;
-- ожидаем: часть перешла в 'escalated'
```

## Constraints (все три шага)

- Не трогать `core/auto_gate.py` (`decide_outbound`) — decision-логика гейта
  не в скоупе.
- Не трогать `page_reviewer.py`, `data/invariants.json`, `deploy_check.py` —
  это другой продукт (сайт), не sales-agent.
- Не отправлять реальные emails при верификации Шага C — только Telegram-эскалация.
- Лимит эскалаций — 2 за цикл (12 циклов/день × 2 = потолок 24, но реальный
  ограничитель — 7-дневный кулдаун на `owner_escalated_at`, так что по факту
  будет 1-2 в неделю на весь пул из 5, не шторм).
- Макс. 3 попытки на любую проблему в рамках каждого шага → STOP + эскалация
  в Log, не крутить дальше.

## Log

(Architect записей нет — задача новая. Worker пишет сюда: commit hash,
grep/test output, что не получилось.)
