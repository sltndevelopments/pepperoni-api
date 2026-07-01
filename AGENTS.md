# AGENTS.md — pepperoni-api

Контекст для AI-агентов (Cursor, Claude Code и т.п.), работающих в этом репозитории.
Этот файл — **правда о проекте**. Если код ему противоречит — чинить код или обновлять
этот файл, но не игнорировать одно ради другого.

## Что это

Репозиторий продукта «Казанские Деликатесы» (pepperoni.tatar), два слоя одного домена:

- **pepperoni.tatar** — презентационный слой. Статические HTML-страницы, маркетинг,
  каталог. Деплой: **VPS Селектел (`37.9.4.101`) + nginx, напрямую, DNS only** (не через
  Cloudflare proxy — RKN throttling с розничных РФ-провайдеров режет Cloudflare до 16 КБ,
  сайт физически не открывался с мобильных сетей). Vercel — только staging/preview,
  без привязанных доменов. Подробности: `docs/HEADLESS-ARCHITECTURE.md`.
- **api.pepperoni.tatar** — слой данных и AI. JSON-каталог, `llms.txt`, OpenAPI, MCP.
  Деплой: тот же VPS + nginx, обновление по cron.

> ⚠️ В репозитории также лежат **отдельные продукты**: `sales-agent/`, `sales-intel/`
> и SEO-автоматизация в `scripts/` (`seo_brain.py`, `fable_*`, `opus_brain_client.py`).
> Это НЕ часть сайта. См. «Границы репозитория» в `.cursor/rules/pepperoni-infra.mdc`.

## Стек и зависимости (это НЕ «чистая статика»)

- Node ESM (`"type": "module"`). Зависимости в `package.json`: `exceljs`, `zod`,
  `@modelcontextprotocol/sdk`.
- Python 3 скрипты в `scripts/` (генерация страниц, синхронизация, SEO).
- Тест-фреймворка нет. QA — детерминированный: `scripts/fix_pages.py` (ремонт) +
  `scripts/qa_pages.py` (проверка). Pre-commit: `.githooks/pre-commit`.

## Команды

| Команда | Что делает |
|---|---|
| `npm run dev` | Локальный статик-сервер `public/` на :3000 |
| `npm run sync` | `scripts/sync-sheets.mjs`: Google Sheets → `public/products.json` + страницы |
| `npm run gen-cards` | Перегенерация RU+EN карточек товаров |
| `npm run mcp` | MCP-сервер (stdio) |
| `bash scripts/sync-vps.sh` | Полный прод-цикл на VPS: sync → gen-ru/en → gen-llms → атомарная подмена `products.json` |

## Поток данных (канонический)

```
Google Sheets (опубликованный CSV, 3 листа: Заморозка / Охлаждённая / Выпечка)
        → scripts/sync-sheets.mjs
        → public/products.json   (поле lastSynced)
        → VPS отдаёт как https://api.pepperoni.tatar/api/products
```

**Единственный источник правды по каталогу — Google Sheets.
Единственный канонический эндпоинт — `api.pepperoni.tatar`.
Фронтенд фетчит каталог только оттуда, никогда напрямую из Sheets.**

## Деплой

- **Прод (pepperoni.tatar + api.pepperoni.tatar) — VPS Селектел.** `git push` в `main` →
  GitHub Actions `deploy-vps.yml` по SSH делает `git fetch && git reset --hard origin/main`
  на VPS (не rsync — см. `docs/vps-drift.md` почему) + `npm install` + рестарт сервисов.
  Плюс cron-синхронизация цен (`sync-vps.sh`, каждые 10 мин) и SEO-агент (`seo-agent-vps.sh`,
  ежедневно).
- **VPS — ephemeral runtime, не среда разработки.** Любая ручная правка на сервере должна
  быть закоммичена и запушена в `origin/main` как можно быстрее — иначе следующий деплой
  (`git reset --hard`) её сотрёт без предупреждения.
- Vercel: деплоится автоматически при push, но домены `pepperoni.tatar`/`api.pepperoni.tatar`
  к нему не привязаны — используется только для preview/staging.

## Бренд, контакты, халяль

Не дублировать факты сюда. Источник — `public/brand.txt` (через
`scripts/brand_system.py::brand_block(lang)`) и `.cursor/rules/pepperoni-brand.mdc`.

## Architect → Worker (Cursor)

| Файл | Роль |
|------|------|
| `CLAUDE.md` | Рельсы исполнителя: гейт, grep, лимит итераций |
| `instructions/next-task.md` | Handoff: Architect → Worker (Current step) |
| `.cursor/rules/agent-executor-gates.mdc` | То же для Cursor Agent (alwaysApply) |

Автономия = задача + исполнение + **механический гейт** + эскалация. Не «две модели без присмотра».
Подробнее: `docs/CURSOR-WORKFLOW.md`.
