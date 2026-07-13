# next-task.md — Architect → Worker handoff (sales-agent / Стив)

## Done — 2026-07-05: дедуп-баг лидов (закрыто)

См. предыдущую запись в git history этого файла (коммит `ac5ee7673`) —
`upsert_lead` дедуп по name/region при пустом inn, cleanup 549756→2110 лидов.

## Done — 2026-07-05 (вечер): спам уведомлений + слепая холодная рассылка

### Проблема 1: Telegram-спам одним и тем же списком

`apply_lookalike_scores()` перезаписывал `profile`/`updated_at` всех лидов
каждый 2ч-цикл даже без реального изменения скора → 5 named targets
(Самокат, КУПЕР, Яндекс Лавка, Газпром Нефть, ЛУКОЙЛ) вечно наверху
`ORDER BY updated_at DESC` → `proactive.hot_leads` пересылал один и тот же
список каждые 2 часа с 02.07 по 05.07 без единого нового события.

**Фикс** (коммит `5841656cc`):
- `apply_lookalike.py` — не пишет в БД (не трогает updated_at), если
  score/reasons/fit_score не изменились.
- `proactive.py` — `hot_leads` уведомление теперь сравнивает текущий топ
  с составом предыдущей отправки, шлёт только реально новых.

**Verify на VPS:** первый запуск после деплоя (переход на новый формат
хэша) дал разовую отправку, второй запуск сразу после — `fired: []`.

### Проблема 2: 216 холодных писем, 0% ответов от людей

Диагноз по факту (audit_log, messages): агент реально пишет и исследует —
216 писем за месяц, персонализированные, MX-проверенные адреса, bounce
корректно отфильтрован (32 hard + 14 soft). Но реальных ответов от людей
за всё время — 0 (только 2 автоответа: "получили", "мы переехали").

Корень: `enrich_contacts._needs_enrich` проверял только "есть ли хоть
какой-то email", не его качество. Реестровые email (`ok@`, `sbyt@`,
`lab@`, `marketing@` — общие функциональные ящики из ЕГРЮЛ/сайта) всегда
проходили эту проверку → Perplexity-поиск персонального контакта закупщика
никогда не запускался для обычного потока, даже при высоком lookalike
score (до 160) без тира.

**Фикс** (коммит `272b1cc6e`):
1. `enrich_contacts.py`: `_needs_enrich` теперь смотрит на
   `_agent.email_quality` — `generic`/`freemail`/нет email → нужен deep
   research; `procurement`/`corporate` → уже достаточно хороший адрес,
   пропустить. Затронуло 170 из 331 новых лидов с ИНН (готовы к
   Perplexity-поиску персонального контакта на следующем `enrich`-цикле).
2. Email open-tracking: новая таблица `email_opens` + методы Store
   (`create_email_open_token`/`record_email_open`/`email_open_stats`),
   1×1 пиксель в HTML-альтернативе письма (`channels/email.py`), отдельный
   stdlib HTTP-сервер `channels/track_server.py` за nginx
   `/sales-track/` → `127.0.0.1:8081`, systemd unit `kd-sales-track.service`
   (enabled, active).

**Verify на VPS:**
- `kd-sales-track.service` активен, `curl https://api.pepperoni.tatar/sales-track/health` → 200.
- Сквозной тест: создан токен → пиксель дёрнут через публичный HTTPS URL →
  `email_opens.open_count=1`, `last_ip`/`last_ua` записаны корректно.
  Тестовые строки удалены после проверки.
- `_needs_enrich`/`_is_deep` пересчитаны на реальных данных: 170 лидов
  из 330 «needs_enrich» качуют дальше в deep research.

## Current step

Нет открытого шага. Следующий ежедневный enrichment обработает ещё 5 компаний;
письмо появится в очереди только если найден реальный buyer contact.

## Log — 2026-07-13: ремонт воронки развёрнут

- Доказано: enrichment не запускался с 09.06 (`data/enrich.log`), cron содержал
  только cycle/fetch-mail; queue=0 при 1850 new; follow-up 0/217; Telegram
  notification counter достиг 95 из-за скользящего top-20.
- Исправлено:
  - ежедневный bounded enrichment (5/день, 30-дневный cooldown);
  - очередь сканирует всю базу и допускает B, но отправляет только на
    procurement/персональный corporate email, исключая HR/kadry/sales/info;
  - один follow-up через 5 дней при отсутствии ответа, максимум 2 за цикл;
  - permanent handoff dedup по lead_id+kind вместо top-20;
  - крупный лид называется приоритетным, «заинтересован» только при реальном inbound;
  - старые warm inbound восстанавливаются в persistent leads; supplier offers
    больше не считаются price requests;
  - LLM morning promises заменены дайджестом только по фактам цикла.
- Коммиты в `origin/main`: `903ee644c`, `1ddabee9a`, `f8a5e1959`.
- Проверка на VPS (`HEAD=f8a5e1959`):
  - `PYTHONPATH=. python3 -m unittest discover -s tests -v` → 8/8 OK;
  - live-cycle завершён exit 0, `proactive.fired=[]`, старый spam-counter
    остался 95 (не вырос);
  - восстановлены ровно 3 явных покупателя: запрос прайса, «Чизерия», запрос
    цены/образца ветчины; supplier/quoted-history не восстановлены;
  - daily enrichment: attempted=5, enriched=5, found_email=5;
  - все 5 адресов оказались freemail/generic, поэтому queue=0 и агент корректно
    не отправил ни одного письма не-ЛПР.
- Blockers: нет. Нулевая отправка в этом цикле — результат quality gate, а не
  остановка процесса.

## Log — 2026-07-13: recovery-план проверен bounded live

- Production recovery-код: `origin/main` и VPS были синхронизированы на
  `aa830036a` после коммитов `138d476bb`, `bf41174fc`, `82bac7c0a`,
  `ce4e0d561`, `8eeca2394`, `aa830036a`.
- Перед live создан online backup:
  `data/agent.db.backup-20260713T135322Z` (594 MiB).
- Гейты:
  - deployed `unittest discover -s tests -v` → 23/23 OK;
  - `py_compile` всех изменённых модулей и `git diff --check` → OK;
  - dry-cycle: `external_actions=0`, IMAP/bounce/named/CRM/Telegram не запускались.
- Bounded live (лимит 3 первых + 2 follow-up):
  - первых писем: 0 — buyer-contact queue осталась пустой, gate не ослаблялся;
  - follow-up: 2 `sent`, адреса `olonetshleb@onego.ru` и `bek@znakhleba.ru`,
    оба `corporate`, `recipient_verified=true`;
  - `drafts sent` 217→219, outbound messages 57→59;
  - у обоих сообщений сохранены фактический recipient, quality, `sent_at` и
    tracking token; `email_opens`: 5 токенов, открытий пока 0.
- Live-проверка выявила и закрыла два дополнительных корня:
  - SQL применял per-cycle LIMIT до quality filter, поэтому 12 buyer-контактов
    скрывались за старыми generic — теперь фильтрация идёт до лимита;
  - два первых кандидата были в deliverability blacklist; теперь blacklist
    проверяется selector-ом, failed-send получает статус `failed`.
- Чизерия: lead `20623d50dc2a4684` пережил два CRM pull,
  `source=inbound`, `status=hot`, canonical escalation reason сохранён.
  Два последовательных inbox scan дали 0/0 handoff, notification count
  остался 2→2.
- Bounded enrichment: attempted=5, enriched=3, found_email=1; найденный адрес
  не прошёл buyer gate. Текущий cold queue=0: основные причины
  `missing_email=1515`, `email_quality=41`; следующий ежедневный enrichment
  продолжит по 5 компаний без отправки на generic/freemail.
