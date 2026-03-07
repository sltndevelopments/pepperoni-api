"""
Модуль отправки промптов в LLM и сбора ответов.
Проверяет, упоминается ли бренд в ответах ИИ.
"""
import asyncio
from typing import List, Optional

from openai import AsyncOpenAI

from config import get_settings


class AIScanner:
    """Асинхронный сканер видимости бренда в ответах LLM (DeepSeek)."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=api_key or settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self._model = "deepseek-chat"

    async def _scan_one(self, brand_name: str, prompt: str) -> dict:
        """Один промпт — один ответ. Для параллельного запуска."""
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = (resp.choices[0].message.content or "").strip()
            mentioned = brand_name.lower() in answer.lower()
            return {"prompt": prompt, "answer": answer, "mentioned": mentioned}
        except Exception as e:
            return {"prompt": prompt, "answer": str(e), "mentioned": False}

    async def scan(self, brand_name: str, prompts: List[str]) -> List[dict]:
        """
        Задаёт каждый промпт модели и возвращает список:
        [{"prompt": str, "answer": str, "mentioned": bool}, ...]
        Промпты выполняются параллельно для ускорения (укладываемся в таймаут Cloudflare).
        """
        tasks = [self._scan_one(brand_name, p) for p in prompts]
        results = await asyncio.gather(*tasks)
        return list(results)
