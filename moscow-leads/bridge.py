"""Точка входа для lead_userbot / lead-intake: создать LEAD и пингануть Арби.

Безопасно: любая ошибка глотается — SEO-контур не должен падать из-за CRM.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def maybe_create_from_text(text: str, *, notify: bool = True) -> dict | None:
    if os.environ.get("MOSCOW_LEADS_DISABLED", "").strip() in ("1", "true", "yes"):
        return None
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from ingest import ingest_text
        from store import Store

        store = Store()
        store.init()
        lead = ingest_text(text, store=store, actor="bridge")
        if not lead:
            return None
        if notify and (
            os.environ.get("MOSCOW_LEAD_BOT_TOKEN") or os.environ.get("LEADS_BOT_TOKEN")
        ):
            try:
                from bot import notify_lead_card
                notify_lead_card(lead)
            except Exception:
                pass
        return lead
    except Exception as e:
        print(f"[moscow-leads] bridge skip: {e}", file=sys.stderr)
        return None
