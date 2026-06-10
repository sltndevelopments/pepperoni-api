"""
Пересылка важного с sales@ → kam@ (владельцу).

Срабатывает при: горячий лид, входящий с интересом, ответ клиента.
Не дублирует рутинный исходящий холодняк.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import env as _env  # noqa: F401

OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "kam@kazandelikates.tatar")


def forward_to_owner(
    subject: str,
    body: str,
    *,
    category: str = "important",
    meta: dict | None = None,
) -> dict:
    """Отправить копию на kam@ (через SMTP sales@)."""
    if not OWNER_EMAIL:
        return {"ok": False, "error": "no_owner_email"}

    from channels.email import send_email

    prefix = {
        "hot_lead": "🔥 [Sales] Горячий лид",
        "inbound": "📥 [Sales] Входящее",
        "reply": "↩️ [Sales] Ответ клиента",
        "lpr_found": "👤 [Sales] ЛПР найден",
    }.get(category, "📌 [Sales] Важное")

    full_subject = f"{prefix}: {subject}"[:200]
    footer = ""
    if meta:
        footer = "\n\n---\n" + "\n".join(f"{k}: {v}" for k, v in meta.items() if v)

    result = send_email(
        OWNER_EMAIL,
        full_subject,
        body + footer,
        dry_run=False,
    )
    return result
