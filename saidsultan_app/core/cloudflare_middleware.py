"""
Middleware: принимаем только запросы, прошедшие через Cloudflare.
Прямой доступ по IP (без заголовков CF) отклоняется.
В dev-режиме (SKIP_CF_CHECK=1) проверка отключена для локального тестирования.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import get_settings

CF_HEADERS = ("cf-connecting-ip", "true-client-ip")


class CloudflareGuardMiddleware(BaseHTTPMiddleware):
    """Отклоняет запросы без заголовков Cloudflare (прямой доступ по IP)."""

    async def dispatch(self, request: Request, call_next):
        if get_settings().skip_cf_check:
            return await call_next(request)
        has_cf = any(request.headers.get(h) for h in CF_HEADERS)
        if not has_cf:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Direct access not allowed. Use the application via Cloudflare (saidsultan.com)."
                },
            )
        return await call_next(request)
