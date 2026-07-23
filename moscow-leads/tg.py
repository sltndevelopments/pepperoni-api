"""Тонкий Telegram Bot API клиент (stdlib only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BOT_TOKEN = (
    os.environ.get("MOSCOW_LEAD_BOT_TOKEN", "").strip()
    or os.environ.get("LEADS_BOT_TOKEN", "").strip()
)
API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def configured() -> bool:
    return bool(BOT_TOKEN)


def api(method: str, params: dict | None = None, *, timeout: int = 60) -> dict:
    if not API:
        return {"ok": False, "description": "bot_token_missing"}
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:400]
        return {"ok": False, "description": f"http_{e.code}:{body}"}
    except Exception as e:
        return {"ok": False, "description": str(e)[:200]}


def send_message(
    chat_id: int | str,
    text: str,
    *,
    reply_markup: dict | None = None,
    parse_mode: str | None = None,
) -> dict:
    params: dict[str, Any] = {"chat_id": chat_id, "text": text[:4000]}
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api("sendMessage", params)


def edit_message(
    chat_id: int | str,
    message_id: int,
    text: str,
    *,
    reply_markup: dict | None = None,
) -> dict:
    params: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text[:4000],
    }
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return api("editMessageText", params)


def answer_callback(callback_id: str, text: str = "") -> dict:
    return api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:180]})


def recipient_ids(env_key: str) -> list[int]:
    raw = os.environ.get(env_key, "").strip()
    ids: list[int] = []
    for part in raw.replace(" ", "").split(","):
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


def group_chat_ids() -> list[int]:
    """Группа лидов — запасной канал, пока Арби не нажал /start у бота."""
    return (
        recipient_ids("MOSCOW_LEAD_GROUP_CHAT_ID")
        or recipient_ids("TELEGRAM_LEADS_CHAT_ID")
    )


def send_to_arbi(
    text: str,
    *,
    reply_markup: dict | None = None,
    owner_on_fallback: bool = True,
) -> int:
    """Личка Арби; при 403/ошибке — в группу лидов + короткий пинг владельцу."""
    primary = recipient_ids("MOSCOW_LEAD_ARBI_CHAT_ID")
    fallback = group_chat_ids()
    sent = 0
    dm_errors: list[str] = []

    for chat_id in primary:
        r = send_message(chat_id, text, reply_markup=reply_markup)
        if r.get("ok"):
            sent += 1
        else:
            dm_errors.append(str(r.get("description") or "send_failed")[:160])

    if sent == 0 and fallback:
        for chat_id in fallback:
            r = send_message(chat_id, text, reply_markup=reply_markup)
            if r.get("ok"):
                sent += 1
        if sent and owner_on_fallback and dm_errors:
            owners = recipient_ids("MOSCOW_LEAD_OWNER_CHAT_ID") or recipient_ids(
                "TELEGRAM_CHAT_ID"
            )
            tip = (
                "⚠️ Карточка ушла в группу лидов: бот не может писать Арби в личку.\n"
                "Арби: открыть @KDPepperoni_Bot → /start\n"
                f"ошибка: {dm_errors[0]}"
            )
            for chat_id in owners:
                send_message(chat_id, tip)

    return sent
