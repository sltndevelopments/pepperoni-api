"""Push-уведомления через @KDSalesManagerBot."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from core import env as _env  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUTH_FILE = DATA / "sales_tg_authorized.json"

BOT_TOKEN = os.environ.get("SALES_TELEGRAM_BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def get_recipients() -> list[int]:
    ids: list[int] = []
    raw = os.environ.get("SALES_TELEGRAM_CHAT_ID", "") or os.environ.get("TELEGRAM_CHAT_ID", "")
    for part in raw.replace(" ", "").split(","):
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    try:
        auth = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        for cid in auth:
            if str(cid).lstrip("-").isdigit():
                ids.append(int(cid))
    except Exception:
        pass
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def notify(text: str) -> int:
    if not API:
        return 0
    sent = 0
    for chat_id in get_recipients():
        try:
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": text[:4000],
                "parse_mode": "HTML",
            }).encode()
            req = urllib.request.Request(f"{API}/sendMessage", data=data)
            with urllib.request.urlopen(req, timeout=15) as r:
                if json.loads(r.read()).get("ok"):
                    sent += 1
        except Exception:
            pass
    return sent


def notify_with_handoff(text: str) -> int:
    """Отправить сообщение с инлайн-кнопкой «✅ Передал менеджеру».

    Нажатие кнопки вызывает callback_data='handoff_bounced', который
    telegram/bot.py обрабатывает: помечает все tier S/A bounced_need_research
    лиды как handed_off.
    """
    if not API:
        return 0
    sent = 0
    keyboard = json.dumps({
        "inline_keyboard": [[
            {"text": "✅ Передал менеджеру", "callback_data": "handoff_bounced"}
        ]]
    })
    for chat_id in get_recipients():
        try:
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": text[:4000],
                "parse_mode": "HTML",
                "reply_markup": keyboard,
            }).encode()
            req = urllib.request.Request(f"{API}/sendMessage", data=data)
            with urllib.request.urlopen(req, timeout=15) as r:
                if json.loads(r.read()).get("ok"):
                    sent += 1
        except Exception:
            pass
    return sent
