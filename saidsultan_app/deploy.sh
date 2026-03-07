#!/bin/bash
# Деплой на сервер: Nginx + проверка. Запускать из корня saidsultan_app.
# Использование: ./deploy.sh   (часть команд требует sudo)

set -e
cd "$(dirname "$0")"

echo "=== Saidsultan AI Visibility — деплой ==="

PROJECT_ROOT="$(pwd)"

# 0. Venv и зависимости
if [ ! -d venv ]; then
    echo ""
    echo "[0] Создаю venv и устанавливаю зависимости..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt -q
else
    ./venv/bin/pip install -r requirements.txt -q 2>/dev/null || true
fi

# 1. Nginx
echo ""
echo "[1/3] Применяю конфиг Nginx..."
sudo cp deploy/nginx-default.conf /etc/nginx/sites-available/default
sudo nginx -t && sudo systemctl restart nginx
echo "Nginx перезапущен."

# 2. API и бот (systemd)
echo ""
echo "[2/3] Устанавливаю и запускаю systemd-сервисы..."
sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" deploy/saidsultan-api.service | sudo tee /etc/systemd/system/saidsultan-api.service > /dev/null
sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" deploy/saidsultan-bot.service | sudo tee /etc/systemd/system/saidsultan-bot.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable saidsultan-api saidsultan-bot
sudo systemctl restart saidsultan-api saidsultan-bot
echo "Сервисы запущены."

sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ 2>/dev/null | grep -q 200; then
    echo "API работает."
else
    echo "API не отвечает. Запустите вручную: ./run_api.sh"
fi

# 3. Итог
echo ""
echo "[3/3] Готово."
echo ""
echo "Проверьте: https://saidsultan.com/docs"
echo ""
echo "Если API не запущен:"
echo "  ./run_api.sh          # API"
echo "  ./run_bot.sh          # Telegram-бот"
echo ""
echo "Или systemd:"
echo "  sudo systemctl enable --now saidsultan-api saidsultan-bot"
echo ""
