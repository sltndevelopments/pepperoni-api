"""Telegram-бот контура Москва: напоминания + inline-статусы для Арби.

  PYTHONPATH=. python3 bot.py
  MOSCOW_LEAD_BOT_TOKEN=... MOSCOW_LEAD_ARBI_CHAT_ID=... python3 bot.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ingest import ingest_text  # noqa: E402
from keyboards import (  # noqa: E402
    distributor_keyboard,
    format_card,
    lost_keyboard,
    main_keyboard,
    stuck_keyboard,
)
from model import DISTRIBUTORS, PRIMARY_ACTIONS, parse_lead_id  # noqa: E402
from store import Store  # noqa: E402
from tg import (  # noqa: E402
    answer_callback,
    api,
    configured,
    edit_message,
    group_chat_ids,
    recipient_ids,
    send_message,
    send_to_arbi,
)

POLL_TIMEOUT = 50


def arbi_chats() -> list[int]:
    return recipient_ids("MOSCOW_LEAD_ARBI_CHAT_ID") + group_chat_ids()


def owner_chats() -> list[int]:
    return recipient_ids("MOSCOW_LEAD_OWNER_CHAT_ID") or recipient_ids("TELEGRAM_CHAT_ID")


def notify_arbi(text: str, *, reply_markup: dict | None = None) -> int:
    return send_to_arbi(text, reply_markup=reply_markup)


def notify_lead_card(lead: dict) -> int:
    return notify_arbi(format_card(lead), reply_markup=main_keyboard(lead["seq"]))


def handle_callback(store: Store, cb: dict) -> None:
    data = cb.get("data") or ""
    cq_id = cb.get("id") or ""
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "ml":
        answer_callback(cq_id, "неизвестная кнопка")
        return
    try:
        seq = int(parts[1])
    except ValueError:
        answer_callback(cq_id, "битый id")
        return
    lead = store.get_by_seq(seq)
    if not lead:
        answer_callback(cq_id, "лид не найден")
        return
    lead_id = lead["id"]
    action = parts[2]

    try:
        if action == "dist_menu":
            edit_message(chat_id, message_id, format_card(lead) + "\n\nКому передать?",
                         reply_markup=distributor_keyboard(seq))
            answer_callback(cq_id, "выберите дистрибьютора")
            return
        if action == "lost_menu":
            edit_message(chat_id, message_id, format_card(lead) + "\n\nПочему не наш?",
                         reply_markup=lost_keyboard(seq))
            answer_callback(cq_id, "выберите причину")
            return
        if action == "back":
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id)
            return
        if action == "plus3":
            lead = store.bump_deadline(lead_id, days=3)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, f"дедлайн → {lead['deadline']}")
            return
        if action == "dist" and len(parts) >= 4:
            dist = parts[3]
            if dist not in DISTRIBUTORS:
                answer_callback(cq_id, "неизвестный дистр")
                return
            lead = store.set_status(
                lead_id, "passed_to_distributor", distributor=dist,
                next_step=f"ОС от {dist}",
            )
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, f"передан → {dist}")
            return
        if action == "lost" and len(parts) >= 4:
            lead = store.apply_lost_reason(lead_id, parts[3])
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, "закрыт")
            return
        if action == "ask_os":
            lead = store.mark_os_requested(lead_id)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=stuck_keyboard(seq))
            answer_callback(cq_id, "отметили: запросили ОС")
            return
        if action == "take_back":
            lead = store.take_back_from_distributor(lead_id)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, "вернул себе")
            return
        if action in PRIMARY_ACTIONS:
            lead = store.set_status(lead_id, PRIMARY_ACTIONS[action])
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, STATUS_OK.get(action, "ок"))
            return
        answer_callback(cq_id, "действие не поддержано")
    except Exception as e:
        answer_callback(cq_id, f"ошибка: {str(e)[:80]}")


STATUS_OK = {
    "contacted": "связался",
    "samples_sent": "образцы",
    "meeting_done": "встреча",
    "first_shipment": "первая отгрузка",
    "repeat_shipment": "повтор",
    "won": "выигран",
}


def handle_message(store: Store, msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    chat_id = (msg.get("chat") or {}).get("id")
    if not text or chat_id is None:
        return

    # Автозаведение, если в чат/группу пришла карточка ассистента/сайта.
    created = ingest_text(text, store=store, actor="telegram")
    if created:
        notify_lead_card(created)
        if chat_id not in arbi_chats():
            send_message(chat_id, f"Создан {created['id']} · статус new")
        return

    if text.startswith("/start"):
        send_message(
            chat_id,
            "Контур Москва. Статусы только кнопками в карточке лида.\n"
            "Команды: /leads — активные, /digest — дайджест сейчас.",
        )
        return
    if text.startswith("/leads"):
        active = store.list_leads(active_only=True, limit=20)
        if not active:
            send_message(chat_id, "Активных лидов нет.")
            return
        for lead in active[:15]:
            send_message(chat_id, format_card(lead), reply_markup=main_keyboard(lead["seq"]))
        return
    if text.startswith("/digest"):
        from digest import build_weekly_digest
        send_message(chat_id, build_weekly_digest(store))
        return
    # Опциональная заметка: LEAD-00042 заметка текст
    if text.upper().startswith("LEAD-") and " " in text:
        lead_id = text.split()[0].upper()
        if parse_lead_id(lead_id):
            note = text.split(None, 1)[1]
            if note.lower().startswith("заметка"):
                note = note.split(None, 1)[1] if " " in note else ""
            lead = store.get(lead_id)
            if lead and note:
                store.set_status(lead_id, lead["status"], note=note[:500], next_step=lead.get("next_step"))
                send_message(chat_id, f"Заметка к {lead_id} сохранена.")
                return


def poll_forever(store: Store | None = None) -> None:
    store = store or Store()
    store.init()
    if not configured():
        raise SystemExit("MOSCOW_LEAD_BOT_TOKEN (или LEADS_BOT_TOKEN) не задан")
    offset = 0
    print("[moscow-leads] bot polling…", flush=True)
    while True:
        updates = api(
            "getUpdates",
            {"timeout": POLL_TIMEOUT, "offset": offset, "allowed_updates": '["message","callback_query"]'},
            timeout=POLL_TIMEOUT + 15,
        )
        if not updates.get("ok"):
            time.sleep(3)
            continue
        for upd in updates.get("result") or []:
            offset = max(offset, int(upd["update_id"]) + 1)
            if "callback_query" in upd:
                handle_callback(store, upd["callback_query"])
            elif "message" in upd:
                handle_message(store, upd["message"])


if __name__ == "__main__":
    poll_forever()
