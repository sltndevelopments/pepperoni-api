"""
Модуль для работы с API Cloudflare:
верификация токена, логи, 301 редиректы для сетки доменов.
"""
from typing import Optional

import httpx

from config import get_settings

CF_VERIFY_URL = "https://api.cloudflare.com/client/v4/user/tokens/verify"


class CloudflareClient:
    """Асинхронный клиент Cloudflare API."""

    def __init__(self, api_token: Optional[str] = None):
        settings = get_settings()
        self._token = api_token or settings.cloudflare_api_token
        self._headers = {"Authorization": f"Bearer {self._token}"}

    async def verify_token(self) -> dict:
        """
        GET на /user/tokens/verify. Возвращает статус токена или ошибку.
        Успех: {"status": "active", ...}
        """
        async with httpx.AsyncClient() as client:
            r = await client.get(CF_VERIFY_URL, headers=self._headers, timeout=10.0)
            data = r.json()
            if r.is_success and data.get("success"):
                return {"status": "active", **data}
            return {"status": "error", "success": False, "errors": data.get("errors", [])}
