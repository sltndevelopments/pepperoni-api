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

Нет открытого шага. Следующий цикл `enrich`/`run_cycle` на VPS начнёт
использовать оба фикса автоматически (deep research по 170 лидам,
open-tracking на всех новых письмах). Через несколько дней стоит
посмотреть `Store.email_open_stats()` — если open-rate высокий, но
reply-rate всё равно ноль, проблема в оффере/канале, не в доставке.
Если open-rate низкий — проблема в спам-фильтрах/теме/домене.

Оценка миграции на Claude Agent SDK — отложена, ждём владельца.
