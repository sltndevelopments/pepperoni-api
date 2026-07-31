"""
Исходящая почта sales@kazandelikates.tatar (SMTP).

Только после аппрува в gate — напрямую не вызывать.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from core import env as _env  # noqa: F401

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "sales@kazandelikates.tatar")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Казанские Деликатесы — Sales")
SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes")
REPLY_TO = os.environ.get("OWNER_EMAIL", "kam@kazandelikates.tatar")
TRACK_BASE_URL = os.environ.get("SALES_TRACK_BASE_URL", "https://api.pepperoni.tatar/sales-track")


def email_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def _open_tracking_html(body: str, token: str | None) -> str:
    """Plain-текст в <pre> + невидимый 1x1 пиксель — для open-rate без смены тона письма."""
    import html
    escaped = html.escape(body)
    pixel = ""
    if token:
        pixel = (
            f'<img src="{TRACK_BASE_URL}/o/{token}.gif" width="1" height="1" '
            f'style="display:none" alt="" />'
        )
    return f"<pre style=\"font-family:inherit;white-space:pre-wrap\">{escaped}</pre>{pixel}"


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    reply_to: str | None = None,
    dry_run: bool = False,
    track_token: str | None = None,
) -> dict:
    if not to or "@" not in to:
        return {"ok": False, "error": "invalid_recipient"}
    if dry_run:
        return {"ok": True, "dry_run": True, "to": to, "subject": subject}

    if not email_configured():
        return {"ok": False, "error": "smtp_not_configured"}

    from channels.deliverability import can_send, record_send

    ok, reason = can_send(to)
    if not ok:
        return {"ok": False, "error": reason, "to": to}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_USER))
    msg["To"] = to
    msg["Reply-To"] = reply_to or REPLY_TO
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(_open_tracking_html(body, track_token), "html", "utf-8"))

    try:
        if SMTP_USE_SSL:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=30) as smtp:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.sendmail(SMTP_USER, [to], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.sendmail(SMTP_USER, [to], msg.as_string())
        record_send(to, subject)
        return {"ok": True, "to": to, "subject": subject, "reply_to": reply_to or REPLY_TO}
    except Exception as e:
        err = str(e)[:300]
        if "550" in err or "554" in err or "blocked" in err.lower():
            from channels.deliverability import add_blacklist
            add_blacklist(to, err)
        return {"ok": False, "error": err}


def pick_recipient(profile: dict) -> str | None:
    """Выбрать получателя.

    Приоритет:
    1. _agent.email_best (исследованный, отранжированный email)
    2. Первый корпоративный (не freemail) из profile.emails
    3. Первый любой из profile.emails
    """
    try:
        from core import agent_profile as ap
        best = ap.get(profile, "email_best")
        if best and "@" in best:
            return best.strip().lower()
    except Exception:
        pass

    raw = profile.get("emails") or profile.get("email") or ""
    emails = [p.strip().lower() for p in str(raw).replace(";", ",").split(",") if "@" in p]
    free = ("@mail.ru", "@yandex.ru", "@gmail.com", "@bk.ru", "@inbox.ru")
    for e in emails:
        if not any(e.endswith(d) for d in free):
            return e
    return emails[0] if emails else None
