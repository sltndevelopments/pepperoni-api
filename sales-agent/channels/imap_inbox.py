"""
IMAP-ловля входящих на sales@kazandelikates.tatar (Yandex).

Каждый запуск: непрочитанные письма → inbox в agent.db → triage/interest
в общем цикле. Привязка к лиду — по email отправителя.
"""
from __future__ import annotations

import email
import email.header
import imaplib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import env as _env  # noqa: F401
from core.store import Store

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.yandex.ru")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "") or os.environ.get("SMTP_USER", "")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "") or os.environ.get("SMTP_PASSWORD", "")

# Доп. ящик info@ — ТОЛЬКО приём входящих заявок (с него не шлём).
INFO_USER = os.environ.get("INFO_IMAP_USER", "")
INFO_PASSWORD = os.environ.get("INFO_IMAP_PASSWORD", "")

SEEN_FILE = ROOT / "data" / "imap_seen.json"


def _accounts() -> list[dict]:
    """Список почтовых ящиков для приёма. sales@ — основной, info@ — приёмный."""
    accts = []
    if IMAP_USER and IMAP_PASSWORD:
        accts.append({"user": IMAP_USER, "password": IMAP_PASSWORD, "box": "sales"})
    if INFO_USER and INFO_PASSWORD:
        accts.append({"user": INFO_USER, "password": INFO_PASSWORD, "box": "info"})
    return accts

# Авторассылки и сервисные письма — не лиды
SKIP_FROM = re.compile(
    r"mailer-daemon|postmaster|no-?reply|noreply|notification|newsletter|digest",
    re.I,
)

# Форм-заявки с сайта (Tilda шлёт с noreply@tilda.ws) — это ГОРЯЧИЙ лид,
# имеет приоритет над SKIP_FROM. Отправитель ИЛИ тема выдают форму.
FORM_FROM = re.compile(r"tilda\.ws|tildacdn|@.*\.tilda|forms?@", re.I)
FORM_SUBJECT = re.compile(
    r"заявк|форм[аы]|с сайта|новое сообщение|new lead|new order|обратн\w* связь|"
    r"заказ звонк|оставил\w* заявк", re.I,
)
# Служебные письма самой Тильды (коды активации, подключение) — не лиды
TILDA_SERVICE = re.compile(r"код активации|activation code|подключени\w* приёмщик|подтверд", re.I)


def _is_form_lead(sender: str, from_raw: str, subject: str) -> bool:
    if TILDA_SERVICE.search(subject):
        return False
    if FORM_FROM.search(sender) or FORM_FROM.search(from_raw):
        return True
    if FORM_SUBJECT.search(subject):
        return True
    return False

# Bounce-детект (mailer-daemon): обрабатываем ДО skip — это сигнал доставляемости
BOUNCE_FROM = re.compile(r"mailer-daemon|postmaster|mail delivery", re.I)
BOUNCE_SUBJECT = re.compile(
    r"undeliver|delivery (?:status|failed|fail)|failure notice|returned mail|"
    r"не доставлено|недоставлен|возврат", re.I,
)
# Final-Recipient / X-Failed-Recipients / просто email в DSN-теле
FAILED_RCPT = re.compile(
    r"(?:Final-Recipient:\s*rfc822;\s*|X-Failed-Recipients:\s*|<)([\w.+-]+@[\w-]+\.[\w.-]+)",
    re.I,
)
HARD_BOUNCE = re.compile(
    r"\b5\.\d\.\d\b|550|551|553|554|user unknown|no such user|mailbox (?:unavailable|not found|disabled)|"
    r"recipient .*rejected|does not exist|invalid recipient", re.I,
)


def _handle_bounce(store: Store, msg: email.message.Message, body: str) -> dict | None:
    """DSN от mailer-daemon: hard → блэклист + статус лида bounced; soft → аудит."""
    sender = _sender_email(msg)
    subject = _decode(msg.get("Subject", ""))
    if not (BOUNCE_FROM.search(sender) or BOUNCE_FROM.search(_decode(msg.get("From", "")))
            or BOUNCE_SUBJECT.search(subject)):
        return None

    failed = ""
    m = FAILED_RCPT.search(body)
    if m and m.group(1).lower() != IMAP_USER.lower():
        failed = m.group(1).lower()
    if not failed:
        # любой email в теле, кроме нашего
        for em in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", body):
            e = em.group(0).lower()
            if e != IMAP_USER.lower() and "daemon" not in e and "postmaster" not in e:
                failed = e
                break

    hard = bool(HARD_BOUNCE.search(body) or HARD_BOUNCE.search(subject))
    detail = {"failed_recipient": failed, "hard": hard, "subject": subject[:120]}

    if failed:
        lead = _find_lead_by_email(store, failed)
        if hard:
            from channels.deliverability import add_blacklist
            add_blacklist(failed, f"hard bounce: {subject[:80]}", domain_too=False)
            detail["blacklisted"] = True
        if lead:
            detail["lead"] = lead["name"][:60]
            profile = dict(lead.get("profile") or {})
            profile["bounce"] = {"email": failed, "hard": hard, "subject": subject[:120]}
            new_status = "bounced" if hard else lead.get("status")
            store.upsert_lead(
                lead["name"], lead_id=lead["id"], inn=lead.get("inn"),
                region=lead.get("region"), tier=lead.get("tier"),
                fit_score=lead.get("fit_score") or 0,
                status=new_status, source=lead.get("source"), profile=profile,
            )

    store.audit("imap", "bounce_hard" if hard else "bounce_soft", detail=detail)
    return detail


def imap_configured() -> bool:
    return bool(_accounts())


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for data, enc in parts:
        if isinstance(data, bytes):
            out.append(data.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(data)
    return "".join(out)


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    return re.sub(r"<[^>]+>", " ", html)
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def _sender_email(msg: email.message.Message) -> str:
    raw = _decode(msg.get("From", ""))
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw)
    return m.group(0).lower() if m else ""


def _load_seen() -> set[str]:
    try:
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_seen(seen: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen)[-2000:]), encoding="utf-8")


def _find_lead_by_email(store: Store, sender: str) -> dict | None:
    if not sender:
        return None
    sender = sender.strip().lower()
    domain = sender.split("@", 1)[1] if "@" in sender else ""
    from core import agent_profile as ap

    for lead in store.list_leads(limit=5000):
        p = lead.get("profile") or {}
        emails = " ".join(
            str(value or "")
            for value in (ap.get(p, "email_best"), p.get("emails"), p.get("email"))
        ).lower()
        # точное вхождение адреса (в т.ч. в списке через запятую/с пробелами)
        if sender and sender in emails:
            return lead
        # домен компании (не free-mail)
        if domain and domain not in (
            "mail.ru", "yandex.ru", "gmail.com", "bk.ru", "inbox.ru", "list.ru", "rambler.ru",
        ) and f"@{domain}" in emails:
            return lead
    return None


def _fetch_one(acct: dict, *, store: Store, seen: set[str], limit: int) -> dict:
    """Обработать один ящик. box: 'sales' (приём+bounce) или 'info' (приём заявок)."""
    box = acct["box"]
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    fetched = skipped = matched = bounces = 0
    try:
        imap.login(acct["user"], acct["password"])
        imap.select("INBOX")
        # Оба ящика могут читать люди раньше Стива. Берём последние три дня,
        # а Message-ID в imap_seen.json обеспечивает идемпотентность.
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%d-%b-%Y")
        status, data = imap.search(None, f'(SINCE {since})')
        if status != "OK":
            return {"ok": False, "box": box, "error": f"search_failed:{status}"}

        # самые свежие — первыми; ограничиваем объём
        nums = data[0].split()
        nums = list(reversed(nums))[:limit]
        for num in nums:
            # BODY.PEEK не меняет флаг \Seen — не «крадём» прочтение у людей
            status, msg_data = imap.fetch(num, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            msg_id = msg.get("Message-ID", "").strip() or f"imap-{box}-{num.decode()}"
            if msg_id in seen:
                continue
            seen.add(msg_id)

            # bounce-логика актуальна только для sales@ (с info@ мы не шлём)
            if box == "sales":
                bounce = _handle_bounce(store, msg, _body_text(msg)[:6000])
                if bounce is not None:
                    bounces += 1
                    continue

            sender = _sender_email(msg)
            from_raw = _decode(msg.get("From", ""))
            subject = _decode(msg.get("Subject", ""))
            is_form = _is_form_lead(sender, from_raw, subject)

            # форм-заявка с сайта имеет приоритет над SKIP_FROM (noreply@tilda)
            if not is_form and (SKIP_FROM.search(sender) or SKIP_FROM.search(from_raw)):
                skipped += 1
                continue

            body = _body_text(msg)[:4000]
            lead = _find_lead_by_email(store, sender)
            lead_id = lead["id"] if lead else None
            if lead:
                matched += 1
                profile = dict(lead.get("profile") or {})
                profile["reply_snippet"] = body[:800]
                profile["reply_from"] = sender
                profile["reply_at"] = datetime.now(timezone.utc).isoformat()
                profile["reply_box"] = box
                store.upsert_lead(
                    lead["name"], lead_id=lead_id, inn=lead.get("inn"),
                    region=lead.get("region"), tier=lead.get("tier"),
                    fit_score=lead.get("fit_score") or 0,
                    status="replied" if lead.get("status") == "contacted" else lead.get("status"),
                    source=lead.get("source"), profile=profile,
                )

            # форм-заявка с сайта — горячий вход; info@ — приёмный; sales@ — переписка
            if is_form:
                channel = "email_form"
            elif box == "info":
                channel = "email_info"
            else:
                channel = "email"
            store.add_inbound(
                channel, body, subject=subject, lead_id=lead_id, external_id=msg_id,
                meta={"from": sender, "matched_lead": bool(lead), "box": box, "form": is_form},
            )
            fetched += 1

        store.audit("imap", "fetched", detail={
            "box": box, "fetched": fetched, "matched": matched,
            "skipped": skipped, "bounces": bounces,
        })
        return {"ok": True, "box": box, "fetched": fetched, "matched_leads": matched,
                "skipped": skipped, "bounces": bounces}
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def fetch_inbox(*, store: Store | None = None, limit: int = 50) -> dict:
    """Забрать свежие письма со всех ящиков (sales@ + info@) → agent.db inbox."""
    accts = _accounts()
    if not accts:
        return {"ok": False, "error": "imap_not_configured"}

    store = store or Store()
    store.init()
    seen = _load_seen()

    per_box = []
    agg = {"fetched": 0, "matched_leads": 0, "skipped": 0, "bounces": 0}
    for acct in accts:
        try:
            r = _fetch_one(acct, store=store, seen=seen, limit=limit)
        except Exception as e:
            r = {"ok": False, "box": acct["box"], "error": str(e)[:160]}
        per_box.append(r)
        for k in agg:
            agg[k] += r.get(k, 0) or 0

    _save_seen(seen)
    return {"ok": True, **agg, "boxes": per_box}


if __name__ == "__main__":
    print(json.dumps(fetch_inbox(), ensure_ascii=False, indent=2))
