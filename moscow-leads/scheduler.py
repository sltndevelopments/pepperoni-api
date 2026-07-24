"""Напоминания, правило 72ч, пятничный дайджест.

Запуск (cron):
  # каждый час — дедлайны + 72ч
  5 * * * * cd /var/www/pepperoni/repo/moscow-leads && PYTHONPATH=. python3 scheduler.py tick
  # пятница 17:00 МСК = 14:00 UTC
  0 14 * * 5 cd /var/www/pepperoni/repo/moscow-leads && PYTHONPATH=. python3 scheduler.py digest
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from digest import build_weekly_digest  # noqa: E402
from keyboards import format_card, main_keyboard, stuck_keyboard  # noqa: E402
from store import Store, datetime_from_iso  # noqa: E402
from tg import recipient_ids, send_message, send_to_arbi, send_to_work_chat  # noqa: E402


def _owner() -> list[int]:
    return recipient_ids("MOSCOW_LEAD_OWNER_CHAT_ID") or recipient_ids("TELEGRAM_CHAT_ID")


def _broadcast(chat_ids: list[int], text: str, *, reply_markup: dict | None = None) -> int:
    n = 0
    for cid in chat_ids:
        if send_message(cid, text, reply_markup=reply_markup).get("ok"):
            n += 1
    return n


def send_due_reminders(store: Store) -> dict:
    """Арби (личка): карточка с кнопками по просроченным дедлайнам (не чаще раза в 20ч на лид)."""
    sent = 0
    skipped = 0
    for lead in store.due_reminders():
        key = f"remind:{lead['id']}"
        last = store.get_meta(key)
        if last:
            try:
                if datetime.now(timezone.utc) - datetime_from_iso(last) < timedelta(hours=20):
                    skipped += 1
                    continue
            except Exception:
                pass
        text = f"⏰ Напоминание\n{format_card(lead)}"
        n = send_to_arbi(text, reply_markup=main_keyboard(lead["seq"]), store=store)
        if n:
            store.set_meta(key, datetime.now(timezone.utc).isoformat())
            sent += n
    return {"reminders_sent": sent, "skipped": skipped}


def check_72h_distributor(store: Store) -> dict:
    """
    1) 72ч без движения у дистра → Арби кнопки [Запросить ОС] [Вернуть себе]
    2) ещё +24ч без реакции (нет ask_os / смены статуса) → владельцу
    """
    to_arbi = 0
    to_owner = 0
    now = datetime.now(timezone.utc)
    for lead in store.stuck_at_distributor(hours=72):
        lead_id = lead["id"]
        changed = datetime_from_iso(lead["status_changed_at"])
        age_h = (now - changed).total_seconds() / 3600
        arbi_key = f"stuck72:{lead_id}"
        owner_key = f"stuck96:{lead_id}"
        arbi_at = store.get_meta(arbi_key)

        if not arbi_at:
            text = (
                f"⚠️ {lead_id} у {lead.get('distributor') or '?'} "
                f"{int(age_h)}ч без движения\n{format_card(lead)}"
            )
            n = send_to_arbi(text, reply_markup=stuck_keyboard(lead["seq"]), store=store)
            if n:
                store.set_meta(arbi_key, now.isoformat())
                to_arbi += n
            continue

        try:
            ping_age_h = (now - datetime_from_iso(arbi_at)).total_seconds() / 3600
        except Exception:
            ping_age_h = 0
        if ping_age_h < 24 or store.get_meta(owner_key):
            continue
        if lead.get("status") != "passed_to_distributor":
            continue

        events = store.events(lead_id, limit=30)
        reacted = any(
            e.get("action") in ("ask_os", "status") and (e.get("at") or "") >= arbi_at
            for e in events
        )
        if reacted:
            continue

        text = (
            f"📣 Лид застрял у дистрибьютора >96ч\n"
            f"{lead_id} · {lead.get('company') or '—'}\n"
            f"Дистрибьютор: {lead.get('distributor') or '?'}\n"
            f"Арби не ответил на напоминание (нет ОС / возврата)."
        )
        n = _broadcast(_owner(), text)
        if n:
            store.set_meta(owner_key, now.isoformat())
            to_owner += n
    return {"arbi_alerts": to_arbi, "owner_alerts": to_owner}


def send_friday_digest(store: Store) -> dict:
    text = build_weekly_digest(store)
    # Дайджест: группа + владелец + личка Арби.
    sent = send_to_work_chat(text)
    sent += _broadcast(_owner(), text)
    sent += send_to_arbi(text, store=store)
    store.set_meta("last_friday_digest", datetime.now(timezone.utc).isoformat())
    return {"digest_sent": sent, "chars": len(text)}


def tick() -> dict:
    store = Store()
    store.init()
    result = {}
    result["reminders"] = send_due_reminders(store)
    result["stuck72"] = check_72h_distributor(store)
    return result


def main(argv: list[str]) -> None:
    cmd = (argv[1] if len(argv) > 1 else "tick").strip()
    if cmd == "tick":
        print(json.dumps(tick(), ensure_ascii=False, indent=2))
    elif cmd == "digest":
        print(json.dumps(send_friday_digest(Store()), ensure_ascii=False, indent=2))
    elif cmd == "print-digest":
        print(build_weekly_digest(Store()))
    else:
        raise SystemExit(f"unknown command: {cmd} (tick|digest|print-digest)")


if __name__ == "__main__":
    main(sys.argv)
