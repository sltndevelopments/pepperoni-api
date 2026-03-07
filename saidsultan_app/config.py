"""Настройки из .env. Все ключи — только здесь."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    telegram_bot_token: str = ""
    # Локальная разработка: SKIP_CF_CHECK=1 отключает проверку заголовков Cloudflare
    skip_cf_check: bool = False
    # SMTP для отправки отчётов
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # Email для заявок (если не задан — используется smtp_user)
    admin_email: str = ""


def get_settings() -> Settings:
    return Settings()
