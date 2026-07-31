"""Telegram-бот контура Москва: личка Арби + АКБ/контакты/sell-out.

  PYTHONPATH=. python3 bot.py
  MOSCOW_LEAD_BOT_TOKEN=... MOSCOW_LEAD_ARBI_CHAT_ID=... python3 bot.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ingest import ingest_text  # noqa: E402
from keyboards import (  # noqa: E402
    contact_points_keyboard,
    contact_result_keyboard,
    contact_type_keyboard,
    distributor_keyboard,
    format_card,
    lost_keyboard,
    main_keyboard,
    segment_keyboard,
    sellout_distributor_keyboard,
    stuck_keyboard,
)
from model import (  # noqa: E402
    CONTACT_RESULT_LABELS,
    CONTACT_TYPE_LABELS,
    DISTRIBUTORS,
    POINT_SEGMENTS,
    PRIMARY_ACTIONS,
    SELLOUT_DISTRIBUTORS,
    format_actor,
    parse_lead_id,
)
from store import Store  # noqa: E402
from tg import (  # noqa: E402
    ALLOWED_USER_IDS,
    answer_callback,
    api,
    edit_message,
    recipient_ids,
    send_message,
    send_to_arbi,
    send_to_work_chat,
    user_allowed,
    work_chat_ids,
)

POLL_TIMEOUT = 50


def owner_chats() -> list[int]:
    return recipient_ids("MOSCOW_LEAD_OWNER_CHAT_ID") or recipient_ids("TELEGRAM_CHAT_ID")


def notify_lead_card(store: Store, lead: dict) -> int:
    """Карточки — в личку Арби (после /start), не в группу."""
    return send_to_arbi(
        format_card(lead),
        reply_markup=main_keyboard(lead["seq"]),
        store=store,
    )


def _actor_from_cb(cb: dict) -> str:
    return format_actor(cb.get("from"))


def _deny_if_not_allowed(cb: dict) -> bool:
    """True = отказ (уже ответили callback)."""
    from_user = cb.get("from") or {}
    uid = from_user.get("id")
    if user_allowed(uid):
        return False
    answer_callback(cb.get("id") or "", "нет прав")
    return True


def handle_callback(store: Store, cb: dict) -> None:
    if _deny_if_not_allowed(cb):
        return
    data = cb.get("data") or ""
    cq_id = cb.get("id") or ""
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    actor = _actor_from_cb(cb)

    if data.startswith("mc:"):
        handle_contact_callback(store, cb, data, actor, chat_id, message_id, cq_id)
        return
    if data.startswith("so:"):
        handle_sellout_callback(store, cb, data, actor, chat_id, message_id, cq_id)
        return

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
            lead = store.bump_deadline(lead_id, days=3, actor=actor)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, f"дедлайн → {lead['deadline']}")
            return
        if action == "dist" and len(parts) >= 4:
            dist = parts[3]
            if dist not in DISTRIBUTORS:
                answer_callback(cq_id, "неизвестный дистр")
                return
            lead = store.set_status(
                lead_id, "passed_to_distributor", actor=actor, distributor=dist,
                next_step=f"ОС от {dist}",
            )
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, f"передан → {dist}")
            return
        if action == "lost" and len(parts) >= 4:
            lead = store.apply_lost_reason(lead_id, parts[3], actor=actor)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, "закрыт")
            return
        if action == "ask_os":
            lead = store.mark_os_requested(lead_id, actor=actor)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=stuck_keyboard(seq))
            answer_callback(cq_id, "отметили: запросили ОС")
            return
        if action == "take_back":
            lead = store.take_back_from_distributor(lead_id, actor=actor)
            edit_message(chat_id, message_id, format_card(lead), reply_markup=main_keyboard(seq))
            answer_callback(cq_id, "вернул себе")
            return
        if action in PRIMARY_ACTIONS:
            lead = store.set_status(lead_id, PRIMARY_ACTIONS[action], actor=actor)
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


def handle_contact_callback(
    store: Store, cb: dict, data: str, actor: str,
    chat_id, message_id, cq_id: str,
) -> None:
    """mc:… — фиксация контакта в один тап."""
    parts = data.split(":")
    # mc:cancel
    if parts[1] == "cancel":
        edit_message(chat_id, message_id, "Контакт отменён.")
        answer_callback(cq_id, "отмена")
        return
    # mc:new → сегмент → ждём название текстом
    if parts[1] == "new" and len(parts) == 2:
        edit_message(
            chat_id, message_id,
            "Новая точка — выберите сегмент:",
            reply_markup=segment_keyboard(),
        )
        answer_callback(cq_id, "сегмент")
        return
    # mc:seg:<segment>
    if parts[1] == "seg" and len(parts) >= 3:
        seg = parts[2]
        if seg not in POINT_SEGMENTS:
            answer_callback(cq_id, "сегмент?")
            return
        uid = (cb.get("from") or {}).get("id")
        store.set_meta(
            f"contact_draft:{uid}",
            json.dumps({"step": "name", "segment": seg}, ensure_ascii=False),
        )
        edit_message(
            chat_id, message_id,
            f"Сегмент: {seg}\nПришлите название точки одной строкой\n"
            f"(можно: Название | город | ЛПР).",
        )
        answer_callback(cq_id, "ждём название")
        return
    # mc:pt:<seq> → тип контакта
    if parts[1] == "pt" and len(parts) == 3:
        try:
            seq = int(parts[2])
        except ValueError:
            answer_callback(cq_id, "битый id")
            return
        point = store.get_point_by_seq(seq)
        if not point:
            answer_callback(cq_id, "точка не найдена")
            return
        pref = f"pt:{seq}"
        edit_message(
            chat_id, message_id,
            f"Контакт: {point.get('name') or point['id']}\nТип:",
            reply_markup=contact_type_keyboard(pref),
        )
        answer_callback(cq_id, "тип")
        return
    # mc:pt:<seq>:<type> → результат
    if parts[1] == "pt" and len(parts) == 4:
        pref = f"pt:{parts[2]}"
        ctype = parts[3]
        if ctype not in CONTACT_TYPE_LABELS:
            answer_callback(cq_id, "тип?")
            return
        edit_message(
            chat_id, message_id,
            f"Тип: {CONTACT_TYPE_LABELS[ctype]}\nРезультат:",
            reply_markup=contact_result_keyboard(pref, ctype),
        )
        answer_callback(cq_id, "результат")
        return
    # mc:pt:<seq>:<type>:<result> → сохранить
    if parts[1] == "pt" and len(parts) == 5:
        try:
            seq = int(parts[2])
        except ValueError:
            answer_callback(cq_id, "битый id")
            return
        ctype, result = parts[3], parts[4]
        point = store.get_point_by_seq(seq)
        if not point:
            answer_callback(cq_id, "точка не найдена")
            return
        try:
            rec = store.log_contact(
                contact_type=ctype,
                result=result,
                actor=actor,
                point_id=point["id"],
            )
        except ValueError as e:
            answer_callback(cq_id, str(e)[:80])
            return
        point = store.get_point(point["id"])
        edit_message(
            chat_id, message_id,
            f"✅ Контакт записан\n"
            f"{point.get('name')} · {CONTACT_TYPE_LABELS.get(ctype)} → "
            f"{CONTACT_RESULT_LABELS.get(result)}\n"
            f"Статус точки: {point.get('status')} · заказов: {point.get('orders_count')}",
        )
        answer_callback(cq_id, "записано")
        return
    answer_callback(cq_id, "неизвестная кнопка контакта")


def handle_sellout_callback(
    store: Store, cb: dict, data: str, actor: str,
    chat_id, message_id, cq_id: str,
) -> None:
    parts = data.split(":")
    if parts[1] == "cancel":
        uid = (cb.get("from") or {}).get("id")
        store.set_meta(f"sellout_draft:{uid}", "")
        edit_message(chat_id, message_id, "Sell-out отменён.")
        answer_callback(cq_id, "отмена")
        return
    if parts[1] == "dist" and len(parts) >= 3:
        dist = parts[2]
        if dist not in SELLOUT_DISTRIBUTORS:
            answer_callback(cq_id, "дистр?")
            return
        uid = (cb.get("from") or {}).get("id")
        store.set_meta(
            f"sellout_draft:{uid}",
            json.dumps({"step": "month", "distributor": dist}, ensure_ascii=False),
        )
        edit_message(
            chat_id, message_id,
            f"Sell-out · {dist}\nПришлите месяц в формате YYYY-MM (например 2026-06)",
        )
        answer_callback(cq_id, dist)
        return
    answer_callback(cq_id, "sellout?")


def _handle_drafts(store: Store, msg: dict, text: str, chat_id: int, actor: str) -> bool:
    """Обработка текстовых шагов /contact (новая точка) и /sellout. True = съели."""
    from_user = msg.get("from") or {}
    uid = from_user.get("id")
    if uid is None:
        return False

    # --- sellout draft ---
    raw_so = store.get_meta(f"sellout_draft:{uid}") or ""
    if raw_so:
        try:
            draft = json.loads(raw_so)
        except json.JSONDecodeError:
            draft = {}
        step = draft.get("step")
        if step == "month":
            month = text.strip()
            if not re.fullmatch(r"\d{4}-\d{2}", month):
                send_message(chat_id, "Нужен формат YYYY-MM, например 2026-06")
                return True
            draft["month"] = month
            draft["step"] = "kg"
            store.set_meta(f"sellout_draft:{uid}", json.dumps(draft, ensure_ascii=False))
            send_message(chat_id, f"{draft['distributor']} · {month}\nСколько кг sell-out?")
            return True
        if step == "kg":
            try:
                kg = float(text.replace(",", ".").replace(" ", ""))
            except ValueError:
                send_message(chat_id, "Число кг, например 1250")
                return True
            draft["kg"] = kg
            draft["step"] = "points"
            store.set_meta(f"sellout_draft:{uid}", json.dumps(draft, ensure_ascii=False))
            send_message(chat_id, "Сколько уникальных точек в отчёте дистрибьютора?")
            return True
        if step == "points":
            try:
                pts = int(text.strip())
            except ValueError:
                send_message(chat_id, "Целое число точек")
                return True
            rec = store.upsert_sellout(
                distributor=draft["distributor"],
                month=draft["month"],
                kg=float(draft["kg"]),
                points_count=pts,
                actor=actor,
            )
            store.set_meta(f"sellout_draft:{uid}", "")
            send_message(
                chat_id,
                f"✅ Sell-out сохранён\n"
                f"{rec['distributor']} · {rec['month']}: {rec['kg']} кг, "
                f"{rec['points_count']} точек",
            )
            return True

    # --- contact new point draft ---
    raw_c = store.get_meta(f"contact_draft:{uid}") or ""
    if raw_c:
        try:
            draft = json.loads(raw_c)
        except json.JSONDecodeError:
            draft = {}
        if draft.get("step") == "name":
            parts = [p.strip() for p in text.split("|")]
            name = parts[0] if parts else text.strip()
            city = parts[1] if len(parts) > 1 else ""
            lpr = parts[2] if len(parts) > 2 else ""
            if not name:
                send_message(chat_id, "Название не может быть пустым")
                return True
            point = store.create_point(
                name=name,
                segment=draft.get("segment") or "",
                city=city,
                contact_lpr=lpr,
                actor=actor,
            )
            store.set_meta(f"contact_draft:{uid}", "")
            send_message(
                chat_id,
                f"Точка {point['id']} · {point['name']} создана.\nТип контакта:",
                reply_markup=contact_type_keyboard(f"pt:{point['seq']}"),
            )
            return True
    return False


def handle_message(store: Store, msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    chat_id = (msg.get("chat") or {}).get("id")
    chat_type = (msg.get("chat") or {}).get("type") or ""
    from_user = msg.get("from") or {}
    if not text or chat_id is None:
        return

    actor = format_actor(from_user)
    uid = from_user.get("id")

    # Автозаведение из карточки ассистента — в любом чате.
    created = ingest_text(text, store=store, actor=actor)
    if created:
        notify_lead_card(store, created)
        if chat_id not in work_chat_ids():
            send_message(chat_id, f"Создан {created['id']} · статус new")
        return

    if _handle_drafts(store, msg, text, chat_id, actor):
        return

    if text.startswith("/start"):
        # Регистрируем личку Арби для карточек.
        if chat_type == "private" and uid is not None:
            if user_allowed(uid) or not ALLOWED_USER_IDS:
                store.set_meta("arbi_dm_chat_id", str(chat_id))
        send_message(
            chat_id,
            "Контур Москва — территориальный менеджер.\n"
            "Карточки и напоминания приходят сюда (в личку).\n"
            "В группе — только пятничный дайджест.\n\n"
            "Команды:\n"
            "/leads — активные лиды\n"
            "/contact — отметить контакт (точка)\n"
            "/sellout — ввод отчёта дистрибьютора\n"
            "/akb — снимок АКБ\n"
            "/digest — дайджест сейчас",
        )
        return

    if not user_allowed(uid) and ALLOWED_USER_IDS:
        # В группе чужие команды игнорим молча; в личке — отказ.
        if chat_type == "private":
            send_message(chat_id, "Нет прав на команды контура.")
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

    if text.startswith("/akb"):
        snap = store.akb_snapshot()
        lines = [
            f"АКБ: {snap['akb']} active",
            f"Зона риска: {snap['at_risk']}",
            f"Отвал: {snap['churned']}",
            f"Всего точек: {snap['total_points']}",
        ]
        for p in snap["active_points"][:15]:
            lines.append(f"· {p.get('name')} [{p.get('distributor') or '—'}]")
        send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/contact"):
        points = store.list_points(limit=20)
        send_message(
            chat_id,
            "Отметить контакт — выберите точку или создайте новую:",
            reply_markup=contact_points_keyboard(points),
        )
        return

    if text.startswith("/sellout"):
        send_message(
            chat_id,
            "Месячный отчёт дистрибьютора — кого вводим?",
            reply_markup=sellout_distributor_keyboard(),
        )
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
                store.set_status(
                    lead_id, lead["status"], actor=actor,
                    note=note[:500], next_step=lead.get("next_step"),
                )
                send_message(chat_id, f"Заметка к {lead_id} сохранена.")
                return


def poll_forever(store: Store | None = None) -> None:
    store = store or Store()
    store.init()
    from tg import configured
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
