# -*- coding: utf-8 -*-
"""
Telegram-бот для проверки ИИ-видимости брендов (Saidsultan AI Visibility).

Запуск (из корня проекта saidsultan_app):
  python bot/tg_bot.py
  # или:
  python -m bot.tg_bot

Запуск параллельно с FastAPI:
  • Два терминала: в одном — uvicorn main:app --host 127.0.0.1 --port 8000,
    в другом — python bot/tg_bot.py
  • Или tmux/screen: создать два окна и запустить в каждом по процессу.
  • Или systemd: два юнита (saidsultan-api.service и saidsultan-bot.service),
    в каждом свой ExecStart.

Перед запуском: в .env задать TELEGRAM_BOT_TOKEN (токен от @BotFather).
"""
import asyncio
import sys
from pathlib import Path

# Корень проекта в path, чтобы работали импорты core/config при запуске python bot/tg_bot.py
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove

router = Router()

from config import get_settings
from core.advisor import AIAdvisor
from core.scanner import AIScanner

DEFAULT_PROMPTS = [
    "Где купить лучший казылык в Казани?",
    "Назови топ производителей халяльных мясных деликатесов",
]


def get_bot_token() -> str:
    return get_settings().telegram_bot_token.strip()


def _escape_html(text: str) -> str:
    """Экранирует спецсимволы для Telegram HTML."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_report(brand: str, scan_results: list, advice_steps: list) -> str:
    """Формирует отчёт в HTML (безопасно для любых символов в бренде/ответах)."""
    b = _escape_html(brand)
    lines = [
        f"<b>Отчёт по видимости: {b}</b>",
        "",
        "<b>Результаты сканирования ИИ:</b>",
    ]
    for i, r in enumerate(scan_results, 1):
        mentioned = "✅ Упоминание есть" if r.get("mentioned") else "❌ Нет упоминания"
        lines.append(f"{i}. {mentioned}")
        prompt_preview = _escape_html((r.get("prompt", "") or "")[:80])
        lines.append(f"   <i>Промпт:</i> {prompt_preview}...")
        ans = (r.get("answer") or "")[:200]
        if len((r.get("answer") or "")) > 200:
            ans += "..."
        lines.append(f"   <i>Ответ ИИ:</i> {_escape_html(ans)}")
        lines.append("")
    lines.append("<b>Рекомендации (3 шага GEO):</b>")
    for i, step in enumerate(advice_steps or [], 1):
        lines.append(f"{i}. {_escape_html(str(step))}")
    return "\n".join(lines)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я ИИ-ассистент платформы Saidsultan.\n\n"
        "Отправь команду /analyze [Название бренда], и я проверю его видимость в нейросетях (DeepSeek).",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("analyze"))
async def cmd_analyze(message: Message) -> None:
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    brand = (parts[1].strip() if len(parts) > 1 else "").strip()

    if not brand:
        await message.answer(
            "Напиши название бренда после команды, например:\n"
            "/analyze Казанские Деликатесы",
        )
        return

    await message.answer(f"🔍 Сканирую ИИ-пространство для бренда <b>{_escape_html(brand)}</b>...", parse_mode=ParseMode.HTML)

    try:
        scanner = AIScanner()
        scan_results = await scanner.scan(brand_name=brand, prompts=DEFAULT_PROMPTS)
        advisor = AIAdvisor()
        advice_steps = await advisor.generate_advice(scan_results=scan_results, brand_name=brand)
        report = build_report(brand, scan_results, advice_steps)
        await message.answer(report, parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.answer(f"Ошибка при анализе: {e!s}")


async def main() -> None:
    token = get_bot_token()
    if not token:
        print("TELEGRAM_BOT_TOKEN не задан в .env. Получите токен у @BotFather.")
        sys.exit(1)

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
