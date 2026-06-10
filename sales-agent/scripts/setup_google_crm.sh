#!/usr/bin/env bash
# Настройка Google Sheets CRM для sales-agent (проект pepperoni seo)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$ROOT/secrets/google-service-account.json"

echo "=== KD Sales Agent — Google Sheets CRM ==="
echo ""

# 1. Python deps
pip3 install -q -r "$ROOT/requirements.txt" cryptography 2>/dev/null || pip3 install -r "$ROOT/requirements.txt"

# 2. Service account JSON
if [[ -f "$SECRETS" ]]; then
  echo "✓ Service account: $SECRETS"
elif [[ -n "${GSC_SERVICE_ACCOUNT_KEY:-}" ]]; then
  echo "✓ GSC_SERVICE_ACCOUNT_KEY в окружении"
elif [[ -n "${GSC_SERVICE_ACCOUNT_KEY_B64:-}" ]]; then
  echo "✓ GSC_SERVICE_ACCOUNT_KEY_B64 в окружении"
else
  echo "⚠ Нет service account JSON."
  echo ""
  echo "Сделайте в Google Cloud (проект pepperoni seo):"
  echo "  1. APIs & Services → Enable → Google Sheets API + Google Drive API"
  echo "  2. IAM → Service Accounts → (существующий GSC SA или новый sales-agent)"
  echo "  3. Keys → Add key → JSON → сохранить как:"
  echo "     $SECRETS"
  echo "  4. Если используете СУЩЕСТВУЮЩУЮ таблицу — Share → Editor → email из JSON client_email"
  echo ""
  echo "Ключ AQ.* из AI Studio — НЕ для Sheets. Нужен service account."
  exit 1
fi

# 3. ADC (опционально, для локальной разработки с gcloud)
if command -v gcloud >/dev/null 2>&1; then
  echo "→ gcloud найден. ADC: gcloud auth application-default login"
else
  echo "→ gcloud не установлен — используем только service account JSON (нормально для VPS/cron)."
fi

cd "$ROOT"
python3 -m console.cli init

if [[ -n "${CRM_SHEET_ID:-}" ]]; then
  echo "→ CRM_SHEET_ID задан — перестраиваем вкладки..."
  python3 -m console.cli crm-setup
else
  echo "→ Создаём новую таблицу CRM..."
  python3 -m console.cli crm-setup
fi

echo ""
echo "Готово. Откройте URL из вывода crm-setup."
echo "Дальше: python3 -m console.cli crm-sync"
