"""
RAG-система на основе досье компании.
Анализирует ответы ИИ и даёт рекомендации по видимости бренда.
"""
from pathlib import Path
from typing import List, Optional

from openai import AsyncOpenAI

from config import get_settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COMPANY_INFO_FILE = DATA_DIR / "company_info.txt"


class AIAdvisor:
    """Советник: контекст из company_info.txt + ответы сканера → 3 стратегических шага (GEO). DeepSeek."""

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=api_key or settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self._model = "deepseek-chat"
        self._knowledge = self._load_knowledge()

    def _load_knowledge(self) -> str:
        if COMPANY_INFO_FILE.exists():
            return COMPANY_INFO_FILE.read_text(encoding="utf-8").strip()
        return "Досье компании не заполнено."

    async def generate_advice(
        self,
        scan_results: List[dict],
        brand_name: str = "",
        company_info: Optional[str] = None,
    ) -> List[str]:
        """
        Отправляет в OpenAI результаты сканера + контекст из базы знаний,
        просит вернуть 3 стратегических шага (GEO) для улучшения видимости бренда в ответах нейросетей.
        company_info: если задан, используется вместо файла company_info.txt
        """
        context = (company_info or "").strip() or self._knowledge
        scan_text = "\n\n".join(
            f"Промпт: {r.get('prompt', '')}\nОтвет ИИ: {r.get('answer', '')}\nУпоминание бренда: {r.get('mentioned', False)}"
            for r in scan_results
        )
        system = (
            "Ты эксперт по видимости брендов в ИИ-поисковиках (ChatGPT, Perplexity и т.д.). "
            "На основе досье компании и результатов сканирования ответов ИИ ты даёшь конкретные стратегические рекомендации. "
            "Отвечай строго списком из 3 шагов (GEO), нумерованных 1, 2, 3. Каждый шаг — одна короткая фраза."
        )
        user = (
            f"Досье компании:\n{context}\n\n"
            f"Результаты сканирования ответов ИИ:\n{scan_text}\n\n"
            f"Бренд: {brand_name or 'клиент'}. Дай 3 стратегических шага для улучшения видимости этого бренда в ответах нейросетей."
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            # Парсим нумерованные шаги
            steps = []
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line[0].isdigit() and (". " in line or ") " in line or " " in line):
                    steps.append(line.lstrip("0123456789.) ").strip() or line)
                else:
                    steps.append(line)
            return steps[:3] if len(steps) >= 3 else (steps + ["—", "—", "—"])[:3]
        except Exception as e:
            return [f"Ошибка советника: {e}", "—", "—"]

    async def generate_personalized_report(
        self,
        scan_results: List[dict],
        brand_name: str = "",
        site_content: str = "",
        clients: str = "",
        regions: str = "",
        goal: str = "",
    ) -> dict:
        """
        Генерирует персональный отчёт: почему не упоминают + 5 конкретных действий.
        Учитывает клиентов, регионы, цель.
        """
        scan_text = "\n\n".join(
            f"Промпт: {r.get('prompt', '')}\nОтвет ИИ: {r.get('answer', '')}\nУпоминание: {r.get('mentioned', False)}"
            for r in scan_results
        )
        system = (
            "Ты эксперт по видимости брендов в ИИ-поисковиках. "
            "Отвечай СТРОГО в формате:\n\n"
            "ПОЧЕМУ НЕ УПОМИНАЮТ:\n<короткий анализ 2-4 предложения>\n\n"
            "ЧТО ДЕЛАТЬ:\n1. <действие>\n2. <действие>\n3. <действие>\n4. <действие>\n5. <действие>\n\n"
            "Действия должны быть КОНКРЕТНЫМИ: темы статей под нишу и регион, площадки под тип клиентов, справочники для регистрации."
        )
        user = (
            f"Сайт компании:\n{site_content[:2500]}\n\n"
            f"Результаты сканирования ИИ:\n{scan_text}\n\n"
            f"Бренд: {brand_name}\n"
            f"Клиенты: {clients}\n"
            f"Регионы: {regions}\n"
            f"Цель: {goal}\n\n"
            "Дай анализ и 5 конкретных действий под этот бизнес."
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            why = ""
            actions = []
            if "ПОЧЕМУ НЕ УПОМИНАЮТ:" in text:
                parts = text.split("ПОЧЕМУ НЕ УПОМИНАЮТ:", 1)
                if "ЧТО ДЕЛАТЬ:" in parts[1]:
                    why_part, rest = parts[1].split("ЧТО ДЕЛАТЬ:", 1)
                    why = why_part.strip()
                    for line in rest.strip().split("\n"):
                        line = line.strip()
                        if line and line[0].isdigit():
                            actions.append(line.lstrip("0123456789.) ").strip() or line)
                else:
                    why = parts[1].strip()
            else:
                why = text[:500]
            return {
                "why_not_mentioned": why or "Анализ недоступен.",
                "actions": (actions + ["—"] * 5)[:5],
            }
        except Exception as e:
            return {
                "why_not_mentioned": f"Ошибка: {e}",
                "actions": ["—", "—", "—", "—", "—"],
            }
