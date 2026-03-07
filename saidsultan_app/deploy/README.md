# Деплой Saidsultan AI Visibility

## Один скрипт — всё настроено

На сервере, из папки с проектом:

```bash
cd /root/saidsultan_app   # или ваш путь
pip install -r requirements.txt   # если ещё не ставили
chmod +x deploy.sh
./deploy.sh
```

Скрипт: применяет Nginx, ставит systemd-сервисы, запускает API и бота. После этого проверьте https://saidsultan.com/docs

---

## Быстрый старт (вручную)

### 1. Зависимости

```bash
cd /root/saidsultan_app   # или ваш путь к проекту
pip install -r requirements.txt
```

### 2. Nginx (обратный прокси)

```bash
sudo cp deploy/nginx-default.conf /etc/nginx/sites-available/default
sudo nginx -t && sudo systemctl restart nginx
```

### 3. Запуск API и бота

**Вариант A — вручную (два терминала)**

```bash
# Терминал 1 — API
./run_api.sh
# или: uvicorn main:app --host 127.0.0.1 --port 8000

# Терминал 2 — Telegram-бот
./run_bot.sh
# или: python bot/tg_bot.py
```

**Вариант B — systemd (рекомендуется для продакшена)**

```bash
# Скопировать юниты (путь WorkingDirectory поправьте при необходимости)
sudo cp deploy/saidsultan-api.service /etc/systemd/system/
sudo cp deploy/saidsultan-bot.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable saidsultan-api saidsultan-bot
sudo systemctl start saidsultan-api saidsultan-bot
sudo systemctl status saidsultan-api saidsultan-bot
```

### 4. Проверка

- **Сайт:** https://saidsultan.com/docs — Swagger UI
- **API:** https://saidsultan.com/api/cf-check — проверка Cloudflare
- **Бот:** Telegram → @RSultanBot → `/start` → `/analyze Казанские Деликатесы`

---

## Локальная разработка (без Cloudflare)

Если тестируете на localhost и получаете 403, добавьте в `.env`:

```env
SKIP_CF_CHECK=1
```

Тогда проверка заголовков Cloudflare отключится, и API будет доступен по `http://127.0.0.1:8000`.

---

## Переменные окружения (.env)

| Переменная | Описание |
|------------|----------|
| `DEEPSEEK_API_KEY` | Ключ DeepSeek (Scanner + Advisor) |
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `CLOUDFLARE_API_TOKEN` | Токен Cloudflare (для /api/cf-check) |
| `CLOUDFLARE_ACCOUNT_ID` | ID аккаунта Cloudflare |
| `SKIP_CF_CHECK` | `1` — отключить проверку CF (только для локальной разработки) |

---

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| 403 при открытии сайта | Nginx должен передавать заголовки Cloudflare. Проверьте `proxy_set_header CF-Connecting-IP`. Либо временно добавьте `SKIP_CF_CHECK=1` в `.env` для теста. |
| 404 на saidsultan.com | Nginx не проксирует на FastAPI. Убедитесь, что `proxy_pass http://127.0.0.1:8000` и API запущен (`./run_api.sh` или systemd). |
| `ModuleNotFoundError: aiogram` | Выполните `pip install -r requirements.txt` в папке проекта. |
| Бот не отвечает | Проверьте `TELEGRAM_BOT_TOKEN` в `.env`. Запустите `python bot/tg_bot.py` и смотрите вывод в консоль. |
| systemd: юнит не стартует | Проверьте путь `WorkingDirectory` в `.service` — он должен указывать на папку с проектом. Выполните `journalctl -u saidsultan-api -n 50` для логов. |
