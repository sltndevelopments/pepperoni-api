#!/usr/bin/env python3
"""
Lead Intake Server for pepperoni.tatar
======================================
Receives lead-capture form submissions from site pages (homepage, /x,
commercial landings) and forwards them into the leads Telegram group
"КД ИИ Ассистент" via the KDPepperoni_Bot (which is an admin there and may
post). The MTProto userbot on the leadbot droplet then records the message
into leads.json with page/experiment attribution — closing the SEO→lead loop.

WHY forward to the group instead of writing leads.json directly here:
  The single source of truth for leads is the group (5 channel bots + this
  form). The userbot mirrors the whole group. Posting the form lead there keeps
  ONE ingestion path and gives free attribution (the message carries the source
  URL, which lead_listener._landing_and_experiment maps to an experiment).

152-ФЗ (RU personal data law) compliance is handled on the FORM side:
  explicit non-prechecked consent checkbox + link to /privacy. This endpoint
  additionally refuses submissions without consent=true.

Run:  python3 lead-intake-server.py   (systemd unit, port 5002)
Proxied by nginx at pepperoni.tatar/lead-submit and api.pepperoni.tatar/lead-submit

Environment (from /var/www/pepperoni/seo-agent.env):
  LEADS_BOT_TOKEN   — KDPepperoni_Bot token (admin in the leads group)
  LEADS_GROUP_ID    — the leads group chat id
  LEAD_SEND_ATTEMPTS / LEAD_SEND_TIMEOUT — Bot API retries (default 3 × 5 s)
  LEAD_DEDUP_DB     — sqlite with dedup refs + undelivered-lead spool
  LEAD_EMAIL_TO     — comma-separated addresses that get a copy of every lead
                      (uses ALERT_SMTP_HOST/PORT/USER/PASS; off while unset)
Companion: infra/scripts/lead_intake_flush.py (cron) re-sends the spool and
e-mails ALERT_EMAIL_TO when a lead could not be delivered.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request

LEADS_BOT_TOKEN = os.getenv("LEADS_BOT_TOKEN", "").strip()
LEADS_GROUP_ID = os.getenv("LEADS_GROUP_ID", "").strip()
PORT = int(os.getenv("LEAD_INTAKE_PORT", "5002"))
# Overridable so the delivery path can be exercised against a local mock in tests.
TELEGRAM_API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")

ALLOWED_ORIGINS = {
    "https://pepperoni.tatar",
    "https://www.pepperoni.tatar",
    "https://api.pepperoni.tatar",
}

# Country codes of the export markets the /pepperoni landings advertise in.
# Without them a RU-only validator answers `invalid_phone` to every buyer from
# Uzbekistan, Georgia, Armenia etc. and the lead is lost before it is delivered.
EXPORT_DIAL_CODES = ("375", "374", "992", "994", "995", "996", "998")
MAX_LEN = {"name": 120, "phone": 32, "message": 1000, "page": 300, "experiment_id": 64,
           "client_ref": 64}

# Measurement (2026-09-09): every accepted lead gets an opaque `lead_id` that the
# page uses to count `lead_submit_success` exactly once. `client_ref` is a
# per-form-fill token from the browser; a repeat with the same token within
# DEDUP_TTL (double click, retry after a timeout, reload-and-resubmit) is
# acknowledged with the original lead_id and `duplicate: true` and is NOT sent
# to the sales group again.
DEDUP_TTL = 6 * 3600
# The unit runs gunicorn with 2 workers, so the store must be shared between
# processes — a per-worker dict would let a retry that lands on the other
# worker reach the sales group twice. sqlite (stdlib) with a short busy timeout.
DEDUP_DB = Path(os.getenv("LEAD_DEDUP_DB", "/var/www/pepperoni/data/lead_dedup.sqlite"))


def _dedup_conn():
    import sqlite3
    try:
        DEDUP_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DEDUP_DB, timeout=2)
    except Exception:
        conn = sqlite3.connect(Path(tempfile.gettempdir()) / "lead_dedup.sqlite", timeout=2)
    conn.execute("CREATE TABLE IF NOT EXISTS refs (ref TEXT PRIMARY KEY, ts REAL, lead_id TEXT)")
    return conn


def _dedup_lookup(client_ref: str) -> str | None:
    try:
        with _dedup_conn() as conn:
            conn.execute("DELETE FROM refs WHERE ts < ?", (time.time() - DEDUP_TTL,))
            row = conn.execute("SELECT lead_id FROM refs WHERE ref = ?", (client_ref,)).fetchone()
        return row[0] if row else None
    except Exception as exc:  # dedup is a safety net, never a reason to drop a lead
        log.warning("dedup lookup failed: %s", exc)
        return None


def _dedup_store(client_ref: str, lead_id: str) -> None:
    if not client_ref:
        return
    try:
        with _dedup_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO refs (ref, ts, lead_id) VALUES (?, ?, ?)",
                         (client_ref, time.time(), lead_id))
    except Exception as exc:
        log.warning("dedup store failed: %s", exc)


def phone_ok(raw: str) -> bool:
    """Accept RU/KZ numbers and the CIS export markets we run ads in."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits[0] in "78":  # +7…/8… — Russia, Kazakhstan
        return True
    if len(digits) == 10 and digits[0] == "9":  # RU mobile typed without +7
        return True
    return any(
        digits.startswith(code) and 11 <= len(digits) <= 13
        for code in EXPORT_DIAL_CODES
    )

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lead-intake")

app = Flask(__name__)

# ---- simple in-memory rate limit: max 5 submissions / IP / 10 min ----------
_RECENT: dict[str, deque] = {}
_WINDOW = 600
_MAX_PER_WINDOW = 5


def _rate_ok(ip: str) -> bool:
    now = time.time()
    dq = _RECENT.setdefault(ip, deque())
    while dq and now - dq[0] > _WINDOW:
        dq.popleft()
    if len(dq) >= _MAX_PER_WINDOW:
        return False
    dq.append(now)
    return True


def _clip(value: str, key: str) -> str:
    return (value or "").strip()[: MAX_LEN.get(key, 200)]


# Delivery (2026-09-12 test lead 🆔 84a8dd86… → 502): from the Selectel VPS
# ~25% of Bot API requests time out (15 probes: 4 timeouts dual-stack, 3 forced
# IPv4; TCP+TLS to 149.154.167.220 itself is 70 ms). One attempt with a 15 s
# timeout therefore loses a buyer every fourth submit. Now: up to SEND_ATTEMPTS
# short attempts, and if all fail the lead is written to a durable spool and
# acknowledged as `queued` — lead_intake_flush.py (cron) re-sends it and alerts.
SEND_ATTEMPTS = int(os.getenv("LEAD_SEND_ATTEMPTS", "3"))
SEND_TIMEOUT = float(os.getenv("LEAD_SEND_TIMEOUT", "5"))  # healthy calls take ~0.2 s; failures are hangs


def _send_to_group(text: str, attempts: int = SEND_ATTEMPTS) -> bool:
    if not LEADS_BOT_TOKEN or not LEADS_GROUP_ID:
        log.error("LEADS_BOT_TOKEN / LEADS_GROUP_ID not configured")
        return False
    url = f"{TELEGRAM_API_BASE}/bot{LEADS_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": LEADS_GROUP_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    last = ""
    for i in range(1, max(1, attempts) + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=SEND_TIMEOUT) as r:
                ok = json.loads(r.read()).get("ok", False)
                if ok:
                    if i > 1:
                        log.info("Telegram send succeeded on attempt %d", i)
                    return True
                last = "ok=false"
        except Exception as exc:
            last = str(exc)
        log.warning("Telegram send attempt %d/%d failed: %s", i, attempts, last)
        if i < attempts:
            time.sleep(i)  # 1 s, 2 s — stays inside the browser's patience
    log.error("Telegram send failed after %d attempts: %s", attempts, last)
    return False


# E-mail copy of every accepted lead (owner request 2026-09-12: «Ринат и Арби
# в телеграм группе и на почте»). Independent of the Telegram channel, so it is
# exactly the copy that survives a Bot API outage. Sent from a daemon thread
# after the response is built — SMTP latency or failure never changes what the
# buyer sees. Silently disabled until LEAD_EMAIL_TO and ALERT_SMTP_* are set.
LEAD_EMAIL_TO = [a.strip() for a in os.getenv("LEAD_EMAIL_TO", "").split(",") if a.strip()]
SMTP_HOST = os.getenv("ALERT_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "465") or 465)
SMTP_USER = os.getenv("ALERT_SMTP_USER", "").strip()
SMTP_PASS = os.getenv("ALERT_SMTP_PASS", "").strip()


def email_configured() -> bool:
    return bool(LEAD_EMAIL_TO and SMTP_HOST and SMTP_USER and SMTP_PASS)


def _email_lead_sync(lead_id: str, text: str, page: str) -> None:
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = f"Заявка с pepperoni.tatar {page or ''} · {lead_id}".strip()
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(LEAD_EMAIL_TO)
    msg.set_content(re.sub(r"</?b>", "", text) + "\n\nКопия заявки; оригинал — в группе лидов Telegram.")
    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        log.info("Lead e-mailed: lead_id=%s to=%s", lead_id, ",".join(LEAD_EMAIL_TO))
    except Exception as exc:
        log.error("Lead e-mail failed: lead_id=%s error=%s", lead_id, exc)


def _email_lead(lead_id: str, text: str, page: str) -> None:
    if not email_configured():
        return
    import threading
    threading.Thread(target=_email_lead_sync, args=(lead_id, text, page), daemon=True).start()


def _spool_conn():
    conn = _dedup_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS spool (lead_id TEXT PRIMARY KEY, ts REAL, text TEXT, "
        "attempts INTEGER DEFAULT 0, last_error TEXT, delivered_ts REAL)"
    )
    return conn


def _spool_put(lead_id: str, text: str, error: str) -> bool:
    try:
        with _spool_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO spool (lead_id, ts, text, attempts, last_error, delivered_ts) "
                "VALUES (?, ?, ?, ?, ?, NULL)",
                (lead_id, time.time(), text, SEND_ATTEMPTS, error[:300]),
            )
        return True
    except Exception as exc:
        log.error("spool write failed: %s", exc)
        return False


def spool_pending() -> int:
    try:
        with _spool_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM spool WHERE delivered_ts IS NULL").fetchone()[0]
    except Exception:
        return -1


def _cors_headers(resp):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/lead-submit", methods=["OPTIONS"])
def lead_submit_options():
    return _cors_headers(app.make_response(("", 204)))


@app.route("/lead-submit", methods=["POST"])
def lead_submit():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if not _rate_ok(ip):
        return _cors_headers(jsonify(ok=False, error="rate_limited")), 429

    payload = request.get_json(silent=True) or request.form
    # Honeypot: bots fill hidden "company" field; humans never see it.
    if (payload.get("company") or "").strip():
        log.info("Honeypot triggered from %s — silently accepted", ip)
        return _cors_headers(jsonify(ok=True)), 200  # pretend success, drop it

    # 152-ФЗ: refuse without explicit consent.
    consent = payload.get("consent")
    if consent not in (True, "true", "on", "1", 1):
        return _cors_headers(jsonify(ok=False, error="consent_required")), 400

    name = _clip(payload.get("name", ""), "name")
    phone = _clip(payload.get("phone", ""), "phone")
    message = _clip(payload.get("message", ""), "message")
    page = _clip(payload.get("page", ""), "page")
    experiment_id = _clip(payload.get("experiment_id", ""), "experiment_id")
    client_ref = _clip(payload.get("client_ref", ""), "client_ref")

    if not phone_ok(phone):
        return _cors_headers(jsonify(ok=False, error="invalid_phone")), 400

    if client_ref:
        prior = _dedup_lookup(client_ref)
        if prior:
            log.info("Duplicate submit ignored: ref=%s lead_id=%s", client_ref, prior)
            return _cors_headers(jsonify(ok=True, lead_id=prior, duplicate=True)), 200
    lead_id = uuid.uuid4().hex[:12]

    # Build the group message. Include the source URL so the userbot's
    # _landing_and_experiment() can attribute it to a page/experiment.
    src_url = page
    if page.startswith("/"):
        src_url = f"https://pepperoni.tatar{page}"
    lines = [
        "🌐 <b>Заявка с сайта</b> (форма)",
        f"👤 Имя: {name or '—'}",
        f"📞 Телефон: {phone}",
    ]
    if message:
        lines.append(f"💬 Сообщение: {message}")
    if src_url:
        lines.append(f"🔗 Страница: {src_url}")
    if experiment_id:
        lines.append(f"🧪 Эксперимент: {experiment_id}")
    lines.append(f"🆔 {lead_id}")
    text = "\n".join(lines)

    delivered = _send_to_group(text)
    if not delivered:
        # Durable acceptance: the lead is stored on disk and re-sent by
        # lead_intake_flush.py; the buyer gets the same lead_id and does not
        # have to call. Only if even the spool is unavailable do we say 502.
        if not _spool_put(lead_id, text, "telegram_unreachable"):
            return _cors_headers(jsonify(ok=False, error="delivery_failed")), 502
        log.error("delivery_failed lead_id=%s page=%s — queued in spool (%d pending)",
                  lead_id, page, spool_pending())

    # Московский контур: сразу LEAD со статусом new (без участия человека).
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / "moscow-leads"))
        from bridge import maybe_create_from_text  # type: ignore
        # ingest парсит plain-text поля; HTML-теги в заголовке ему не мешают.
        maybe_create_from_text(text.replace("<b>", "").replace("</b>", ""))
    except Exception as exc:
        log.warning("moscow-leads bridge skipped: %s", exc)

    _dedup_store(client_ref, lead_id)
    _email_lead(lead_id, text, page)
    if delivered:
        log.info("Lead delivered: lead_id=%s page=%s exp=%s", lead_id, page, experiment_id)
        return _cors_headers(jsonify(ok=True, lead_id=lead_id)), 200
    return _cors_headers(jsonify(ok=True, lead_id=lead_id, queued=True)), 200


@app.route("/lead-submit", methods=["GET", "HEAD"])
def lead_submit_get():
    return "Lead intake endpoint is live. POST JSON here.", 200


@app.route("/lead-health", methods=["GET"])
def health():
    return jsonify(
        ok=True,
        configured=bool(LEADS_BOT_TOKEN and LEADS_GROUP_ID),
        email=email_configured(),
        queued=spool_pending(),
    ), 200


if __name__ == "__main__":
    log.info("Starting lead-intake on port %d (configured=%s)",
             PORT, bool(LEADS_BOT_TOKEN and LEADS_GROUP_ID))
    app.run(host="127.0.0.1", port=PORT, debug=False)
