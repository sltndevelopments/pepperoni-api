#!/usr/bin/env python3
"""Lead Listener — Fable's window into REAL incoming leads from all channels.

The owner runs a Telegram group ("КД ИИ Ассистент") where 5 bots from different
channels (website, phone, Avito, messengers, …) post every incoming lead. This
listener reads that group, parses each lead into a structured record, and stores
it in data/leads.json — which the brain digest reads. That gives Fable real
demand/conversion feedback ("what people actually request"), not just clicks.

Design:
  • Uses a SEPARATE bot token (LEADS_BOT_TOKEN) so it can poll the leads group
    independently of the control bot's getUpdates offset (two bots can't share
    one getUpdates cursor). If LEADS_BOT_TOKEN is unset it stays idle.
  • Telegram nuance: a bot only sees group messages it is allowed to. The owner
    must (a) add the bot to the group and (b) either disable the bot's privacy
    mode in @BotFather (so it sees all messages) OR the lead-bots must post in a
    way the bot can read. We auto-discover the group chat_id from updates.
  • Read-only: never replies in the group, only records leads.

Lead parsing is heuristic and channel-aware: it pulls a channel tag, any phone
number, and a short text, and classifies commercial intent (wholesale/OEM/price)
so Fable can tie leads back to the product clusters it is pushing.

Output: data/leads.json
  {"leads": [{"at","channel","phone","text","intent","msg_id","chat_id"}],
   "by_channel": {...}, "by_intent": {...}, "updated_at": "...",
   "group_chat_id": <int>, "offset": <int>}

Usage:
  python3 scripts/lead_listener.py           # one polling pass (for cron)
  python3 scripts/lead_listener.py --loop     # keep polling (for a service)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
OUT = DATA / "leads.json"

TOKEN = os.environ.get("LEADS_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
# Optional explicit group id; otherwise auto-discovered from updates.
GROUP_ID = os.environ.get("LEADS_GROUP_ID", "").strip()
MAX_LEADS = 2000

PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
COMMERCIAL = ("опт", "оптом", "цена", "прайс", "поставщ", "производит", "заказ",
              "b2b", "oem", "стм", "private label", "пиццери", "horeca", "хорека",
              "общепит", "купить", "сколько стоит", "коммерч", "дистрибь")
CHANNEL_HINTS = {
    "avito": "avito", "авито": "avito", "whatsapp": "whatsapp", "ватсап": "whatsapp",
    "wa.me": "whatsapp", "telegram": "telegram", "телеграм": "telegram",
    "сайт": "site", "site": "site", "форма": "site", "звон": "phone",
    "телефон": "phone", "phone": "phone", "instagram": "instagram",
    "vk": "vk", "вконтакте": "vk",
}


def _api(method: str, params: dict) -> dict:
    url = f"{API}/{method}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"⚠️  telegram {method}: {e}", file=sys.stderr)
        return {}


def _load() -> dict:
    try:
        d = json.loads(OUT.read_text())
    except Exception:
        d = {}
    d.setdefault("leads", [])
    d.setdefault("offset", 0)
    d.setdefault("group_chat_id", int(GROUP_ID) if GROUP_ID.lstrip("-").isdigit() else None)
    return d


def _save(d: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    # Recompute rollups so the brain digest is cheap to read.
    by_channel: dict = {}
    by_intent: dict = {}
    for lead in d["leads"]:
        by_channel[lead.get("channel", "?")] = by_channel.get(lead.get("channel", "?"), 0) + 1
        by_intent[lead.get("intent", "?")] = by_intent.get(lead.get("intent", "?"), 0) + 1
    d["by_channel"] = by_channel
    d["by_intent"] = by_intent
    d["updated_at"] = datetime.now(timezone.utc).isoformat()
    d["leads"] = d["leads"][-MAX_LEADS:]
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def _classify(text: str) -> str:
    low = text.lower()
    if any(k in low for k in COMMERCIAL):
        return "commercial"
    return "other"


def _channel(text: str, sender: str) -> str:
    low = (text + " " + sender).lower()
    for hint, chan in CHANNEL_HINTS.items():
        if hint in low:
            return chan
    return "unknown"


def _parse_lead(msg: dict) -> dict | None:
    text = msg.get("text") or msg.get("caption") or ""
    if not text.strip():
        return None
    frm = msg.get("from", {}) or {}
    sender = (frm.get("username") or frm.get("first_name") or "")
    phones = PHONE_RE.findall(text)
    return {
        "at": datetime.fromtimestamp(msg.get("date", 0), timezone.utc).isoformat(),
        "channel": _channel(text, sender),
        "phone": phones[0] if phones else "",
        "text": text.strip()[:500],
        "intent": _classify(text),
        "msg_id": msg.get("message_id"),
        "chat_id": (msg.get("chat") or {}).get("id"),
        "from_bot": bool(frm.get("is_bot")),
    }


def poll_once(d: dict) -> int:
    """One getUpdates pass. Records new leads from the group. Returns #new."""
    if not TOKEN:
        print("ℹ️  LEADS_BOT_TOKEN not set — listener idle.")
        return 0
    res = _api("getUpdates", {"timeout": 25, "offset": d["offset"],
                              "allowed_updates": json.dumps(["message", "channel_post"])})
    if not res.get("ok"):
        return 0
    updates = res.get("result", [])
    new = 0
    seen = {(l.get("chat_id"), l.get("msg_id")) for l in d["leads"]}
    for upd in updates:
        d["offset"] = upd["update_id"] + 1
        msg = upd.get("message") or upd.get("channel_post")
        if not msg:
            continue
        chat = msg.get("chat") or {}
        # Auto-discover the group on first sight (a group/supergroup the bot is in).
        if d["group_chat_id"] is None and chat.get("type") in ("group", "supergroup"):
            d["group_chat_id"] = chat.get("id")
            print(f"📌 discovered leads group: {chat.get('title')} ({chat.get('id')})")
        # Only record messages from the configured/discovered leads group.
        if d["group_chat_id"] is not None and chat.get("id") != d["group_chat_id"]:
            continue
        lead = _parse_lead(msg)
        if not lead:
            continue
        if (lead["chat_id"], lead["msg_id"]) in seen:
            continue
        d["leads"].append(lead)
        seen.add((lead["chat_id"], lead["msg_id"]))
        new += 1
    return new


def digest() -> dict:
    """Compact leads view for the brain digest / chat (last 30d focus)."""
    try:
        d = json.loads(OUT.read_text())
    except Exception:
        return {"status": "unavailable"}
    if not TOKEN and not d.get("leads"):
        return {"status": "unavailable", "why": "LEADS_BOT_TOKEN not set"}
    leads = d.get("leads", [])
    recent = leads[-50:]
    return {
        "total_tracked": len(leads),
        "by_channel": d.get("by_channel", {}),
        "by_intent": d.get("by_intent", {}),
        "recent_examples": [
            {"at": l["at"][:10], "channel": l["channel"],
             "intent": l["intent"], "text": l["text"][:120]}
            for l in recent if l.get("intent") == "commercial"
        ][-8:],
        "group_connected": d.get("group_chat_id") is not None,
    }


def main() -> int:
    d = _load()
    loop = "--loop" in sys.argv[1:]
    if loop:
        print("🔄 lead listener loop…")
        while True:
            n = poll_once(d)
            if n:
                _save(d)
                print(f"➕ {n} new lead(s)")
            time.sleep(2)
    else:
        n = poll_once(d)
        _save(d)
        print(f"✅ lead listener: +{n} new, {len(d['leads'])} total, "
              f"group={'connected' if d.get('group_chat_id') else 'not yet'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
