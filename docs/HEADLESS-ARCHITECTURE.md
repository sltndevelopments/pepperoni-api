# Headless Architecture: Pepperoni.tatar

> **Обновлено 2026-07-01.** Актуальная схема: **всё на Селектел (VPS `37.9.4.101`)**,
> напрямую, без Cloudflare proxy и без Vercel в проде. Причина смены схемы —
> Cloudflare throttled РКН у розничных РФ-провайдеров (Мегафон LTE, Ростелеком)
> с 16 КБ payload cap, из-за чего сайт не открывался с мобильных сетей в России.
> Vercel остаётся только как staging/preview (без привязанных доменов).

## Доменное разделение

| Домен | Роль | Контент | Хостинг |
|-------|------|---------|---------|
| **api.pepperoni.tatar** | Data & AI Layer | JSON, llms.txt, OpenAPI, AI-плагины | VPS nginx (`37.9.4.101`) |
| **pepperoni.tatar** | Presentation & SEO Layer | HTML, CSS, JS, маркетинг, каталог с фото | VPS nginx (`37.9.4.101`), статика из `/var/www/pepperoni/repo/public` |

DNS: `pepperoni.tatar` и `www.pepperoni.tatar` — **A-запись на `37.9.4.101`, DNS only (серое облако)**, не через Cloudflare proxy. Смена DNS — вручную, в дашборде Cloudflare (см. `docs/CLOUDFLARE-DNS-RU.md`).

## Почему не Cloudflare / не Vercel в проде

- **Cloudflare proxy** (оранжевое облако) — под RKN-throttling с розничных РФ-операторов: пропускает только первые ~16 КБ ответа, страница физически не догружается. Дата-центровые проверки (check-host.net и т.п.) это не видят — блок применяется на уровне мобильных/домашних провайдеров, не в магистральных сетях.
- **Vercel** — тот же класс риска (иностранная инфраструктура США), может попасть под аналогичные ограничения в будущем.
- **Селектел** — российский хостинг (AS49505), не в реестре блокировок; для RU-аудитории это единственный путь без риска DPI-блокировки. Для зарубежной аудитории (EN-версия) задержка чуть выше (сервер физически в РФ), но для B2B-каталога с прайсом это не критично.

## Деплой

Код: `git push` в `origin/main` → GitHub Actions (`deploy-vps.yml`) по SSH заходит на VPS и делает `git fetch && git reset --hard origin/main` + `npm install` + рестарт сервисов. Это уже настроено и работает — не нужно создавать заново.

**VPS — ephemeral runtime, не среда для ручных правок.** Если что-то поменяли на сервере вручную (хотфикс), закоммитьте и запушьте в `origin/main` как можно быстрее — иначе следующий `git reset --hard` из деплой-пайплайна затрёт правку без предупреждения. См. `docs/vps-drift.md`.

nginx на VPS отдаёт `public/` как статику напрямую (`try_files`), с fallback на `pepperoni-api.vercel.app` (staging deployment, не кастомный домен) если локального файла нет — резерв на случай рассинхрона.

## Контракт

- **Frontend** (`pepperoni.tatar`) **не ходит** в Google Sheets напрямую. Каталог обновляется через `scripts/sync-sheets.mjs` (cron на VPS, `sync-vps.sh`), результат — `public/products.json`.
- **api.pepperoni.tatar** отдаёт данные за <100ms. Без дизайна, картинок, HTML.
- **pepperoni.tatar** — для людей и поисковиков: интерфейс, SEO, база знаний.

## CORS

api.pepperoni.tatar должен отдавать `Access-Control-Allow-Origin: *` (или `https://pepperoni.tatar`) для запросов с pepperoni.tatar.
