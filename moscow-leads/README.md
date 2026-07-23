# moscow-leads — контур продаж Москва (Арби)

Заменяет экспериментальные текстовые напоминания OpenClaw («KazDel — Руководитель»)
на рабочий контур: фиксированные статусы, inline-кнопки в два тапа, правило 72ч
у дистрибьютора, пятничный дайджест.

**Не второй CRM.** Битрикс не трогаем. Клиентам ничего не шлём автоматически.
Свободный ввод статуса запрещён — только кнопки (+ опциональная заметка текстом).

## Статусы

```
new → contacted → samples_sent → meeting_done → passed_to_distributor
     → first_shipment → repeat_shipment → won
терминальные: lost (с причиной), no_demand
```

Дистрибьюторы: `GFC` | `SweetLife` | `direct`.

## Env

| Переменная | Назначение |
|---|---|
| `MOSCOW_LEAD_BOT_TOKEN` | токен бота (или fallback `LEADS_BOT_TOKEN`) |
| `MOSCOW_LEAD_GROUP_CHAT_ID` | **рабочая группа** — карточки, кнопки, напоминания, дайджест |
| `MOSCOW_LEAD_OWNER_CHAT_ID` | владелец (эскалация 96ч + копия пятничного дайджеста) |
| `MOSCOW_LEADS_DISABLED=1` | выключить автозаведение из bridge |

Всё полевое общение — только в группе (не личка Арби), чтобы процесс был
виден. Можно использовать текущую группу лидов или завести отдельную и
прописать её id в `MOSCOW_LEAD_GROUP_CHAT_ID`.

## Запуск

```bash
cd moscow-leads
PYTHONPATH=. python3 cli.py path          # тестовый new→first_shipment
PYTHONPATH=. python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 bot.py               # long-poll + callback
PYTHONPATH=. python3 scheduler.py tick    # дедлайны + 72ч
PYTHONPATH=. python3 scheduler.py digest  # пятничный отчёт
```

## Cron (VPS, МСК)

```
5 * * * * cd /var/www/pepperoni/repo/moscow-leads && PYTHONPATH=. python3 scheduler.py tick >> data/scheduler.log 2>&1
0 14 * * 5 cd /var/www/pepperoni/repo/moscow-leads && PYTHONPATH=. python3 scheduler.py digest >> data/scheduler.log 2>&1
```

Пятница 17:00 МСК = 14:00 UTC.

## Автозаведение

- Карточка «📞 Новая заявка — Казанские Деликатесы» (ИИ-ассистент) → `LEAD` / `new` / дедлайн +1 рабочий день
- «🌐 Заявка с сайта» → то же
- Avito / commercial из `lead_userbot` → bridge

После деплоя: выключить текстовые напоминания OpenClaw, чтобы не дублировать.
Проговорить с GFC/SweetLife правило 72ч заранее.
