#!/usr/bin/env bash
# Запуск FastAPI (ядро стартапа)
# Использование: ./run_api.sh   или   bash run_api.sh
cd "$(dirname "$0")"
PYTHON="python3"
[ -f venv/bin/python3 ] && PYTHON="venv/bin/python3"
exec $PYTHON -m uvicorn main:app --host 127.0.0.1 --port 8000
