# Sales Agent — автономный B2B-контур Pepperoni.tatar

**Изолированная папка.** Не деплоится на Vercel, не трогает `public/`, не влияет на pepperoni.tatar.

Карта возможностей, из которой собирается ядро, затем наращиваются слои:

| Слой | Статус | Что делает |
|------|--------|------------|
| **0. Ядро** | ✅ готово | SQLite, инбокс, черновики, гейт аппрува, аудит, CLI + веб-консоль |
| **1–2. Проспектинг** | 🔶 каркас | Импорт из `sales-intel`, квалификация Tier S, заглушки тендеров/сигналов |
| **3–4. Аутрич + диалог** | 🔶 черновики | Email-шаблон / Sonnet; WA/TG/звонок — после настройки каналов |
| **5. Стратег** | 🔶 каркас | Кластеры спроса по регионам |
| **6. Разведка** | ⏳ | Регуляторика, сырьё, конкуренты |
| **7. RAG + память** | 🔶 | `kb/` читает `products.json` + `capabilities.yaml` |

## Архитектура

```
                    ┌─────────────────┐
                    │  Orchestrator   │  observe → plan → dispatch → reflect
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   ┌───────────┐      ┌────────────┐      ┌────────────┐
   │ Workers   │      │ Prospecting│      │ Strategist │
   │ triage    │      │ import     │      │ clusters   │
   │ draft     │      │ qualify    │      └────────────┘
   └─────┬─────┘      └────────────┘
         │
         ▼
   ┌───────────┐     необратимое ──► ┌──────────┐
   │   Gate    │ ──────────────────► │ Approvals │ ──► send (dry-run)
   └───────────┘                     └──────────┘
         │
         ▼
   ┌───────────┐
   │  Store    │  sales-agent/data/agent.db
   └───────────┘
```

**Правило:** внутреннее (обогащение, скоринг, черновики) — свободно. Исходящее (email, WA, TG, тендер, задача на звонок) — только через аппрув.

## Telegram: @KDSalesManagerBot

Пароль по умолчанию: `Namaz2015!` (переопределяется `SALES_TG_PASSWORD` в `.env`).

```bash
cd sales-agent
cp .env.example .env   # вписать токен бота и SMTP
python3 -m telegram.bot
```

Меню: статус, **🔥 Горячие** (заинтересованные с контактами), лиды, инбокс, цикл.

### Автономия (по умолчанию включена)

- **Opus** сам одобряет и отправляет рутинный холодный аутрич (без твоего «одобрить»)
- **Тебе приходит только важное:** 🔥 заинтересованные — компания, телефоны, email, директор → звони лично
- Ручной аппрув — только если Opus поставил `hold` (редко): `одобрить 1`

Настройки: `config/autonomy.yaml`

## Почта

Исходящие с `sales@kazandelikates.tatar` (Yandex SMTP) — только после аппрува.
В `.env`: `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST=smtp.yandex.ru`.

## LLM

| Задача | Модель |
|--------|--------|
| Черновики, диалог в боте | Sonnet (`core/llm.call_sonnet`) |
| Стратег, кластеры | Opus (`core/llm.call_opus`) |
| Триаж | Haiku |

Нужен `ANTHROPIC_API_KEY` в `.env` или в окружении VPS (тот же, что у SEO-мозга).

## Быстрый старт

```bash
cd sales-agent

pip install -r requirements.txt   # PyYAML
cp .env.example .env

python3 -m console.cli init

# импорт лидов из sales-intel (read-only)
python3 -m console.cli import-intel --min-score 70 --limit 100

# веб-консоль (только localhost)
python3 -m console.cli serve
# → http://127.0.0.1:8765

# один цикл оркестратора (dry-run отправки)
python3 -m console.cli cycle
```

## Google Sheets CRM (приватная таблица)

Таблица — зеркало работы агента. Источник правды: `data/agent.db`.

```bash
# 1. Service account JSON (тот же проект pepperoni seo, что GSC) → secrets/google-service-account.json
# 2. В Cloud Console включить: Google Sheets API + Google Drive API
# 3. Расшарить таблицу на client_email из JSON (Editor)
./scripts/setup_google_crm.sh

python3 -m console.cli crm-setup   # создать/перестроить вкладки
python3 -m console.cli crm-sync    # pull + push + журнал «Активность»
```

Ключ `AQ.*` из AI Studio — **не** для Sheets. Нужен **service account** (как для GSC).

Подробно: `docs/CRM-SHEETS-SETUP.md`

## CLI

| Команда | Назначение |
|---------|------------|
| `init` | Создать SQLite |
| `stats` | Сводка контура |
| `leads [--tier S]` | Список лидов |
| `inbox` | Входящие |
| `drafts` / `approvals` | Черновики и очередь аппрува |
| `approve <id>` / `reject <id>` | Решение по исходящему |
| `import-intel` | CSV из `../sales-intel/data/` |
| `sync-sheet` | Импорт лидов (API или pub CSV) |
| `crm-setup` | Создать/перестроить CRM в Google Sheets |
| `crm-pull` / `crm-push` / `crm-sync` | Двусторонний sync с таблицей |
| `qualify <lead_id> [--crawl]` | Tier S (опционально краул сайта) |
| `draft <lead_id> [--submit]` | Черновик письма → аппрув |
| `cycle` | Полный цикл оркестратора |
| `serve` | Локальная веб-консоль |
| `audit` | Хвост аудит-лога |

## Конфигурация

- `config/capabilities.yaml` — что **можем** / **не можем** (агент не наобещает курицу в панировке)
- `config/channels.yaml` — каналы и секвенции (email → WA → звонок)
- `config/models.yaml` — роутинг Haiku / Sonnet / Opus / DeepSeek

Каталог SKU подтягивается read-only из `../public/products.json`.

## Связь с sales-intel

`sales-intel/` — офлайн-генератор CSV (ФНС, ОКВЭД, краул «сосиска в тесте»).

`sales-agent/` — runtime: лиды в БД, инбокс, аппрувы, оркестратор. Импорт — мост, без дублирования парсеров.

## Порядок наращивания (рекомендация)

1. **Сейчас:** ядро + импорт + ручной аппрув черновиков в консоли
2. **Далее:** движок проспектинга — тендеры, Telegram-сигналы, WB/Ozon
3. **Потом:** стратег (Opus) — кластеры, win/loss, форсайт по сетям
4. **Параллельно:** send-домен (SPF/DKIM), WhatsApp anti-ban, 152-ФЗ для реестров

## Cron (VPS, не Vercel)

```cron
# Каждые 2 часа — цикл (без live-send)
0 */2 * * * cd /repo/sales-agent && python3 -m orchestrator.run_cycle >> data/cycle.log 2>&1
```

## Безопасность

- `sales-agent/data/` в `.gitignore` — БД и логи не в git
- Отправка по умолчанию **dry-run**
- `--live-send` только когда каналы настроены
- Telegram-уведомления reuse `scripts/telegram_notify.py` (если токен задан)
