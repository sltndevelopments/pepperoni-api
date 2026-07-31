# moscow-leads — контур территориального менеджера (Москва)

Фиксированные статусы лидов, справочник **точек (АКБ)**, inline-кнопки,
правило 72ч у дистрибьютора, пятничный дайджест по АКБ/sell-out.

**Не второй CRM.** Битрикс не трогаем. Клиентам ничего не шлём автоматически.
Свободный ввод статуса запрещён — только кнопки (+ опциональная заметка текстом).

## Сущности

| Сущность | Смысл |
|---|---|
| **Лид** | Входящий запрос (воронка до первой отгрузки) |
| **Точка** | Торговая точка; лид при `first_shipment` → точка `active` |
| **Контакт** | Звонок/визит с результатом (заказ / думает / отказ / не ЛПР) |
| **Sell-out** | Месячный отчёт дистрибьютора: кг + число точек (`/sellout`) |

Статус точки **вычисляется** от `last_order_at`:
`≤30 active` · `31–60 at_risk` · `>60 churned`.

## Статусы лида

```
new → contacted → samples_sent → meeting_done → passed_to_distributor
     → first_shipment → repeat_shipment → won
терминальные: lost (с причиной), no_demand
```

Дистрибьюторы лида: `GFC` | `SweetLife` | `direct`.

## Env

| Переменная | Назначение |
|---|---|
| `MOSCOW_LEAD_BOT_TOKEN` | токен бота (или fallback `LEADS_BOT_TOKEN`) |
| `MOSCOW_LEAD_ARBI_CHAT_ID` | личка Арби (карточки/напоминания); также пишется после `/start` |
| `MOSCOW_LEAD_GROUP_CHAT_ID` | группа — **только дайджест** |
| `MOSCOW_LEAD_OWNER_CHAT_ID` | владелец (эскалация 96ч + копия дайджеста) |
| `MOSCOW_LEAD_ALLOWED_USER_IDS` | белый список telegram user_id через запятую |
| `MOSCOW_LEADS_DISABLED=1` | выключить автозаведение из bridge |

Карточки и кнопки — в **личку** Арби (после `/start`). Публичные «❌ Не наш»
в группе искажают данные. Группа получает пятничный дайджест.

## Команды бота

- `/start` — зарегистрировать личку
- `/leads` — активные лиды с кнопками
- `/contact` — отметить контакт (точка / новая)
- `/sellout` — ввод отчёта GFC/SweetLife (месяц, кг, точки)
- `/akb` — снимок АКБ
- `/digest` — дайджест сейчас

## Запуск

```bash
cd moscow-leads
PYTHONPATH=. python3 cli.py path
PYTHONPATH=. python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 bot.py
PYTHONPATH=. python3 scheduler.py tick
PYTHONPATH=. python3 scheduler.py digest
```

## Cron (VPS, МСК)

```
5 * * * * cd /var/www/pepperoni/repo/moscow-leads && PYTHONPATH=. python3 scheduler.py tick >> data/scheduler.log 2>&1
0 14 * * 5 cd /var/www/pepperoni/repo/moscow-leads && PYTHONPATH=. python3 scheduler.py digest >> data/scheduler.log 2>&1
```

Пятница 17:00 МСК = 14:00 UTC.

## Автозаведение

- Карточка «📞 Новая заявка — Казанские Деликатесы» → `LEAD` / `new`
- «🌐 Заявка с сайта» → то же
- Avito / commercial из `lead_userbot` → bridge

После деплоя: выключить текстовые напоминания OpenClaw.
Проговорить с GFC/SweetLife правило 72ч **до** включения эскалаций.
Разговор с Арби об условиях — **до** включения эскалаций.
