# Headless Architecture: Pepperoni.tatar

## Доменное разделение

| Домен | Роль | Контент | Хостинг |
|-------|------|---------|---------|
| **api.pepperoni.tatar** | Data & AI Layer | JSON, llms.txt, OpenAPI, AI-плагины | VPS nginx |
| **pepperoni.tatar** | Presentation & SEO Layer | HTML, CSS, JS, маркетинг, каталог с фото | Vercel |

## Контракт

- **Frontend** (`pepperoni.tatar`) **не ходит** в Google Sheets. Данные запрашиваются **только** из `https://api.pepperoni.tatar/api/products`.
- **api.pepperoni.tatar** отдаёт данные за <100ms. Без дизайна, картинок, HTML.
- **pepperoni.tatar** — для людей и поисковиков: интерфейс, SEO, база знаний.

## CORS

api.pepperoni.tatar должен отдавать `Access-Control-Allow-Origin: *` (или `https://pepperoni.tatar`) для запросов с pepperoni.tatar.
