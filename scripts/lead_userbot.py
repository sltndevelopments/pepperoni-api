#!/usr/bin/env python3
"""Lead Userbot — MTProto reader for the leads group.

WHY THIS EXISTS
    Telegram *bots* can never receive messages sent by *other bots* — not via
    getUpdates, not even as group admins. The leads group "КД ИИ Ассистент" is
    fed by 5 channel bots (site form, phone, Avito, messengers), so the Bot-API
    listener (scripts/lead_listener.py) sees 0 of them. A *user* account (MTProto
    via Telethon) reads the full group history, bot messages included.

    This reader parses each message with the SAME logic as lead_listener
    (_parse_lead) and writes to the SAME data/leads.json in the SAME shape, so
    the brain digest keeps working unchanged. It is additive: it only records
    messages the bot listener could not see.

AUTH (one-time, done by the owner)
    Needs API_ID + API_HASH from https://my.telegram.org (owner's own app) and a
    one-time login (phone + code Telegram sends). The session is stored in
    LEADS_USERBOT_SESSION (default: tg-state/lead_userbot.session) and reused
    forever after — no code prompts on cron runs.

ENV
    TG_API_ID, TG_API_HASH        — from my.telegram.org
    LEADS_GROUP_ID                — same supergroup id the bot listener uses
    LEADS_USERBOT_SESSION         — session file path (optional)

USAGE
    python3 scripts/lead_userbot.py --login   # interactive, one time
    python3 scripts/lead_userbot.py           # one polling pass (cron)
    python3 scripts/lead_userbot.py --loop     # live listener (service)
"""
from __future__ import annotations

import os
import sys
from datetime import timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import lead_listener as ll  # reuse parsing + storage — single source of truth

ROOT = Path(__file__).parent.parent
API_ID = os.environ.get("TG_API_ID", "").strip()
API_HASH = os.environ.get("TG_API_HASH", "").strip()
GROUP_ID = os.environ.get("LEADS_GROUP_ID", "").strip()
SESSION = os.environ.get(
    "LEADS_USERBOT_SESSION",
    str(Path(getattr(ll, "DATA", ROOT / "data")).parent / "tg-state" / "lead_userbot"),
)
# Backfill window: how many recent messages to scan on a normal pass.
SCAN_LIMIT = int(os.environ.get("LEADS_USERBOT_SCAN", "200"))


def _require(cond: bool, msg: str) -> None:
    if not cond:
        print(f"❌ {msg}", file=sys.stderr)
        raise SystemExit(2)


def _to_botapi_msg(m) -> dict:
    """Adapt a Telethon Message into the Bot-API-shaped dict _parse_lead expects.

    _parse_lead reads: text/caption, from{username,first_name,is_bot},
    date (unix), message_id, chat{id}.
    """
    sender = getattr(m, "sender", None)
    username = getattr(sender, "username", None) if sender else None
    first = getattr(sender, "first_name", None) if sender else None
    title = getattr(sender, "title", None) if sender else None  # channel/bot as sender
    is_bot = bool(getattr(sender, "bot", False)) if sender else False
    date = m.date
    unix = int(date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp())
    chat_id = getattr(m, "chat_id", None)
    return {
        "text": m.message or "",
        "caption": "",
        "from": {"username": username, "first_name": first or title, "is_bot": is_bot},
        "date": unix,
        "message_id": m.id,
        "chat": {"id": chat_id, "type": "supergroup"},
    }


def _record(d: dict, messages) -> int:
    seen = {(l.get("chat_id"), l.get("msg_id")) for l in d["leads"]}
    new = 0
    for m in messages:
        if not (m.message or "").strip():
            continue
        lead = ll._parse_lead(_to_botapi_msg(m))
        if not lead:
            continue
        if (lead["chat_id"], lead["msg_id"]) in seen:
            continue
        d["leads"].append(lead)
        seen.add((lead["chat_id"], lead["msg_id"]))
        new += 1
    return new


def _client():
    try:
        from telethon.sync import TelegramClient
    except Exception:
        print("❌ telethon not installed. Run: pip install telethon", file=sys.stderr)
        raise SystemExit(2)
    _require(API_ID.isdigit(), "TG_API_ID missing/invalid (get it at my.telegram.org)")
    _require(bool(API_HASH), "TG_API_HASH missing (get it at my.telegram.org)")
    Path(SESSION).parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(SESSION, int(API_ID), API_HASH)


def _group_entity(client):
    _require(GROUP_ID.lstrip("-").isdigit(), "LEADS_GROUP_ID missing/invalid")
    return int(GROUP_ID)


def do_login() -> int:
    client = _client()
    client.start()  # interactive: prompts phone + code the first time
    me = client.get_me()
    print(f"✅ logged in as {getattr(me, 'username', None) or me.first_name}")
    print(f"   session saved to {SESSION}.session — cron will reuse it")
    client.disconnect()
    return 0


def poll_once() -> int:
    d = ll._load()
    if d.get("group_chat_id") is None and GROUP_ID.lstrip("-").isdigit():
        d["group_chat_id"] = int(GROUP_ID)
    client = _client()
    if not client.start():
        print("❌ not authorized — run: python3 scripts/lead_userbot.py --login",
              file=sys.stderr)
        return 2
    entity = _group_entity(client)
    messages = list(client.iter_messages(entity, limit=SCAN_LIMIT))
    n = _record(d, messages)
    ll._save(d)
    client.disconnect()
    print(f"✅ lead userbot: +{n} new, {len(d['leads'])} total")
    return 0


def run_loop() -> int:
    from telethon import events
    d = ll._load()
    if d.get("group_chat_id") is None and GROUP_ID.lstrip("-").isdigit():
        d["group_chat_id"] = int(GROUP_ID)
    client = _client()
    client.start()
    entity = _group_entity(client)
    # Catch up on anything missed while offline.
    n0 = _record(d, list(client.iter_messages(entity, limit=SCAN_LIMIT)))
    if n0:
        ll._save(d)
    print(f"🔄 lead userbot loop (caught up +{n0})…")

    @client.on(events.NewMessage(chats=entity))
    async def _handler(event):
        added = _record(d, [event.message])
        if added:
            ll._save(d)
            print(f"➕ {added} new lead(s)")

    client.run_until_disconnected()
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--login" in args:
        return do_login()
    if "--loop" in args:
        return run_loop()
    return poll_once()


if __name__ == "__main__":
    raise SystemExit(main())
