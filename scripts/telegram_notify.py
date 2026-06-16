#!/usr/bin/env python3
"""
Lightweight Telegram notifications for SEO agents (no long-poll, no brain_journal).

Recipients (union, deduped):
  1. TELEGRAM_CHAT_ID / TELEGRAM_LEADS_CHAT_ID env — comma-separated chat IDs
     (works in GitHub Actions where tg_authorized.json does not exist).
  2. data/tg_authorized.json — chats that logged into @KDSEOSiteBot on the VPS.

Env: TELEGRAM_BOT_TOKEN (required to send)
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"


def tg_state_dir() -> Path:
    """Persistent state dir OUTSIDE the git working tree, so deploys/clean/reset
    can never wipe bot auth. Falls back to data/ for local dev."""
    for cand in (os.environ.get("TG_STATE_DIR"), "/var/www/pepperoni/tg-state"):
        if not cand:
            continue
        p = Path(cand)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".w"
            probe.write_text("")
            probe.unlink()
            return p
        except OSError:
            continue
    return DATA


STATE_DIR = tg_state_dir()
AUTH_FILE = STATE_DIR / "tg_authorized.json"
NOTIFY_FILE = STATE_DIR / "tg_notify.json"  # anyone who ever opened the bot

# One-time migration from the old in-repo location.
if STATE_DIR != DATA:
    for _name in ("tg_authorized.json", "tg_notify.json"):
        _old, _new = DATA / _name, STATE_DIR / _name
        if _old.exists() and not _new.exists():
            try:
                _new.write_text(_old.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def get_recipients() -> list[int]:
    ids: list[int] = []
    for env_key in ("TELEGRAM_CHAT_ID", "TELEGRAM_LEADS_CHAT_ID"):
        raw = os.environ.get(env_key, "").strip()
        if not raw:
            continue
        for part in raw.replace(" ", "").split(","):
            if part.lstrip("-").isdigit():
                ids.append(int(part))
    for path in (AUTH_FILE, NOTIFY_FILE):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cids = raw.keys()
            elif isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        cid = item.get("id")
                    else:
                        cid = item
                    if cid is not None and str(cid).lstrip("-").isdigit():
                        ids.append(int(cid))
                continue
            else:
                continue
            for cid in cids:
                if str(cid).lstrip("-").isdigit():
                    ids.append(int(cid))
        except Exception:
            pass
    # preserve order, dedupe
    seen: set[int] = set()
    out: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def send(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    if not API:
        return False
    params = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true",
    }
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            return bool(body.get("ok"))
    except Exception:
        return False


def notify(text: str) -> int:
    """Send to all known recipients. Returns count sent."""
    recipients = get_recipients()
    if not recipients:
        print("⏭ telegram notify: no recipients "
              "(set TELEGRAM_CHAT_ID or log into @KDSEOSiteBot on VPS)")
        return 0
    sent = sum(1 for cid in recipients if send(cid, text))
    print(f"📤 telegram notify: sent to {sent}/{len(recipients)} chat(s)")
    return sent


def notify_emergency(text: str) -> int:
    """Send an EMERGENCY alert immediately, bypassing the daily ledger buffer.

    Use ONLY for the narrow ЧП whitelist:
      - deploy failure (site not updated after push)
      - page_reviewer unavailable (gate broken)
      - brand / halal violation caught
      - security issue in brain toolsmith

    Everything else goes through daily_ledger.append_event().
    """
    prefixed = f"🚨 <b>ЧП</b>\n\n{text}"
    return notify(prefixed)


def register_chat(chat_id: int, name: str = "") -> None:
    """Remember a chat that contacted the bot (for push alerts before full auth)."""
    try:
        rows = json.loads(NOTIFY_FILE.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            rows = []
    except Exception:
        rows = []
    entry = {"id": chat_id, "name": name}
    if not any(r.get("id") == chat_id for r in rows):
        rows.append(entry)
        DATA.mkdir(parents=True, exist_ok=True)
        NOTIFY_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "🧪 test notification from pepperoni SEO agents"
    notify(msg)
