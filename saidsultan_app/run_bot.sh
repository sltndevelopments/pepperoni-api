#!/usr/bin/env bash
# Запуск Telegram-бота
# Использование: ./run_bot.sh   или   bash run_bot.sh
cd "$(dirname "$0")"
PYTHON="python3"
[ -f venv/bin/python3 ] && PYTHON="venv/bin/python3"
exec $PYTHON bot/tg_bot.py
