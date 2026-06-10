# Google Sheets как приватная CRM

Да — ту же таблицу можно перестроить под CRM и сделать **зеркалом** всей работы агента.  
Агент по-прежнему хранит состояние в `data/agent.db`; таблица нужна вам: фильтры, заметки, мобильный доступ, совместная работа.

## Что нужно от вас (один раз)

| # | Действие | Зачем |
|---|----------|-------|
| 1 | **Снять с публикации** текущий pub CSV | База не должна быть в интернете |
| 2 | **Оставить файл в Google Drive** (или создать копию) | Тот же spreadsheet, но приватный |
| 3 | **Google Cloud: включить Google Sheets API** | Чтение/запись без публичной ссылки |
| 4 | **Service Account** + JSON-ключ | Бот-аккаунт для API |
| 5 | **Расшарить таблицу** на email вида `...@...iam.gserviceaccount.com` с ролью **Редактор** | Иначе API не увидит файл |
| 6 | **Положить в `sales-agent/.env`** (не в git): | |
| | `CRM_SHEET_ID=...` | ID из URL: `https://docs.google.com/spreadsheets/d/{ID}/edit` |
| | `GOOGLE_SHEETS_CREDENTIALS=/абсолютный/путь/service-account.json` | Ключ из п.4 |
| 7 | **Перестроить вкладки** по схеме `config/crm_schema.yaml` | См. ниже |

Публикация в интернете после этого **не нужна**.

### Как создать Service Account (кратко)

1. [console.cloud.google.com](https://console.cloud.google.com) → проект (можно новый, например `kd-sales-agent`).
2. **APIs & Services → Enable APIs** → **Google Sheets API** (при желании **Google Drive API**).
3. **IAM → Service Accounts → Create** → имя `sales-agent-sheets`.
4. **Keys → Add key → JSON** → скачать файл, положить рядом с агентом (в `.gitignore`).
5. Открыть таблицу → **Share** → вставить `client_email` из JSON → **Editor**.

## Как будет устроена таблица

Схема в `config/crm_schema.yaml`. Рекомендуемые вкладки:

### 1. «Лиды» (основная)

- **Вы правите:** `status`, `owner`, `priority`, `last_touch`, `next_action`, `notes`, ЛПР.
- **Агент пишет:** `agent_status`, `agent_temperature`, `lookalike_*`, `last_email_*`, `emails_sent_count`, `escalation_reason`, `escalated_at`, `agent_updated_at`.
- **Ключ строки:** `inn` (не менять, не дублировать).

Заморозить строку 1 и колонки A–C (ИНН, название, статус). Включить фильтр на всю таблицу.

### 2. «Активность» (журнал)

Каждое действие агента — новая строка:

`at | inn | company_short | action | detail | draft_id | model`

Примеры `action`: `draft_created`, `email_sent`, `reply_received`, `hot`, `escalate`, `lookalike`, `qualify`, `hold`, `error`.

Так вы видите **всю** работу, не только последний статус в «Лидах».

### 3. «🔥 Hot»

Вкладка-дашборд (формула `FILTER` / сводная): лиды с `agent_temperature=hot` или `agent_status` in (`hot`, `escalated`).

### 4. «Исключения»

Синк из `config/exclusions.yaml` (Коломенский и др.) — чтобы в таблице было видно, кого агент не трогает.

### 5. «README»

Короткая памятка для команды.

## Поток данных

```
Google Sheet (приватная)  ←—— push ——  agent.db (источник правды)
         ——→ pull ——→   (status, notes, ЛПР от менеджера)
```

- **Импорт базы** (как сейчас): первая загрузка компаний из листа → SQLite.
- **Pull:** раз в N минут или перед циклом — подтянуть ваши правки из колонок CRM.
- **Push:** после `cycle`, отправки письма, эскалации, lookalike — обновить строку лида + дописать «Активность».

Сейчас в коде есть только **read-only** импорт (`sync-sheet` через pub CSV). После шагов 3–6 добавляется **двусторонний** модуль `crm/google_sync.py` (Sheets API).

## Миграция с текущей таблицы

1. Снять публикацию.
2. Переименовать текущий лист в «Лиды» (или импортировать CSV в новый файл).
3. Добавить колонки из схемы (можно вставить пустые заголовки справа — агент заполнит).
4. Создать вкладки «Активность», «🔥 Hot», «Исключения», «README».
5. В `config/deliverability.yaml` убрать или закомментировать `crm_sheet.url` (pub) — перейти на `CRM_SHEET_ID` в `.env`.
6. Запустить:
   ```bash
   cd sales-agent
   python3 -m console.cli init
   python3 -m console.cli sync-sheet    # последний раз через API pull
   python3 -m console.cli crm-push      # после реализации push
   ```

## Что уже есть без таблицы

Пока API не настроен, вся работа видна в:

- **Telegram** `@KDSalesManagerBot` — Hot, Leads, Inbox, Cycle
- **CLI:** `stats`, `leads`, `hot`, `drafts`, `approvals`
- **Веб-консоль:** `python3 -m console.cli serve` → `http://127.0.0.1:8765`
- **SQLite:** `data/agent.db` (таблицы `leads`, `drafts`, `audit_log`, …)

Таблица — удобный **внешний UI**, не замена БД.

## Безопасность

- JSON service account и `.env` — **только локально / на VPS**, не в git.
- Таблица **не публикуется**; доступ только у вас и у service account.
- В таблице можно хранить рабочие email/телефоны лидов; **ваши** контакты для подписи писем — только в `.env` (`OWNER_*`), не в публичном сайте.

## Реализовано в коде

```bash
cd sales-agent
./scripts/setup_google_crm.sh      # проверка credentials + crm-setup
python3 -m console.cli crm-setup   # создать таблицу или перестроить вкладки
python3 -m console.cli crm-pull    # импорт + ваши правки из «Лиды»
python3 -m console.cli crm-push --activity   # запись agent_* + журнал
python3 -m console.cli crm-sync    # всё сразу (и после каждого cycle)
```

### Ключ `AQ.*` vs service account

Ключ формата `AQ.Ab8...` из Google AI Studio / Cloud — **не работает** с Sheets API для приватных таблиц.
Используйте **тот же service account**, что уже стоит на pepperoni SEO (GSC):

```bash
# С VPS (если есть seo-agent.env):
grep GSC_SERVICE_ACCOUNT_KEY_B64 /var/www/pepperoni/seo-agent.env | cut -d= -f2- | base64 -d \
  > sales-agent/secrets/google-service-account.json
```

Либо в GCP → IAM → Service Accounts → Keys → JSON.

### ADC / gcloud

Скрипт `setup_adc.sh` нужен только если работаете через `gcloud auth application-default login`.
На VPS/cron достаточно JSON service account в `secrets/`.
