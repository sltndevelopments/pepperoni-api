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

# Кто может менять статусы / жать кнопки. Пусто = все (dev), в проде задать явно.
ALLOWED_USER_IDS: frozenset[int] = frozenset(
    int(x)
    for x in os.environ.get("MOSCOW_LEAD_ALLOWED_USER_IDS", "").replace(" ", "").split(",")
    if x.lstrip("-").isdigit()
)


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


def work_chat_ids() -> list[int]:
    """Рабочая группа — только дайджест (не карточки/кнопки)."""
    return (
        recipient_ids("MOSCOW_LEAD_GROUP_CHAT_ID")
        or recipient_ids("TELEGRAM_LEADS_CHAT_ID")
    )


# backward-compatible alias
group_chat_ids = work_chat_ids


def arbi_chat_ids_from_env() -> list[int]:
    return recipient_ids("MOSCOW_LEAD_ARBI_CHAT_ID")


def user_allowed(user_id: int | None) -> bool:
    """Если белый список пуст — разрешаем всем (локальная отладка)."""
    if not ALLOWED_USER_IDS:
        return True
    if user_id is None:
        return False
    return int(user_id) in ALLOWED_USER_IDS


def send_to_work_chat(
    text: str,
    *,
    reply_markup: dict | None = None,
) -> int:
    """Дайджест / общие уведомления в группу."""
    sent = 0
    for chat_id in work_chat_ids():
        if send_message(chat_id, text, reply_markup=reply_markup).get("ok"):
            sent += 1
    return sent


def send_to_arbi(
    text: str,
    *,
    reply_markup: dict | None = None,
    store=None,
) -> int:
    """Карточки и напоминания — в личку Арби (после /start или env)."""
    ids: list[int] = []
    if store is not None:
        raw = store.get_meta("arbi_dm_chat_id")
        if raw and raw.lstrip("-").isdigit():
            ids.append(int(raw))
    ids.extend(arbi_chat_ids_from_env())
    # уникальные, сохраняя порядок
    seen: set[int] = set()
    uniq: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    sent = 0
    for chat_id in uniq:
        if send_message(chat_id, text, reply_markup=reply_markup).get("ok"):
            sent += 1
    # fallback: если личка не настроена — в группу (чтобы не потерять карточку)
    if sent == 0:
        sent = send_to_work_chat(text, reply_markup=reply_markup)
    return sent
