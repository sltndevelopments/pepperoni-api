# AGENTS.md — pepperoni-api

Контекст для AI-агентов (Cursor, Claude Code и т.п.), работающих в этом репозитории.
Этот файл — **правда о проекте**. Если код ему противоречит — чинить код или обновлять
этот файл, но не игнорировать одно ради другого.

## Что это

Репозиторий продукта «Казанские Деликатесы» (pepperoni.tatar), два слоя одного домена:

- **pepperoni.tatar** — презентационный слой. Статические HTML-страницы, маркетинг,
  каталог. Деплой: Vercel (`vercel.json`, `cleanUrls`, строгий CSP).
- **api.pepperoni.tatar** — слой данных и AI. JSON-каталог, `llms.txt`, OpenAPI, MCP.
  Деплой: VPS + nginx, обновление по cron.

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

- Vercel: push в `main` → деплой `public/`.
- VPS: GitHub Actions `deploy-vps.yml` (rsync, исключая `data/`) + cron-синхронизация
  (`sync-prices.yml` / `update_catalog.yml`).

## Бренд, контакты, халяль

Не дублировать факты сюда. Источник — `public/brand.txt` (через
`scripts/brand_system.py::brand_block(lang)`) и `.cursor/rules/pepperoni-brand.mdc`.

## Architect → Worker (Cursor)

Handoff между планированием и кодом — файл `instruction_next.md` в корне.
Architect (Chat) пишет **Current step**; Worker (Agent) выполняет и дописывает **Log**.
Подробнее: `docs/CURSOR-WORKFLOW.md`, правила `.cursor/rules/architect-handoff.mdc` и
`worker-execute.mdc`.
