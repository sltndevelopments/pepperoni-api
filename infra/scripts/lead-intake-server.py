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
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from collections import deque

from flask import Flask, jsonify, request

LEADS_BOT_TOKEN = os.getenv("LEADS_BOT_TOKEN", "").strip()
LEADS_GROUP_ID = os.getenv("LEADS_GROUP_ID", "").strip()
PORT = int(os.getenv("LEAD_INTAKE_PORT", "5002"))

ALLOWED_ORIGINS = {
    "https://pepperoni.tatar",
    "https://www.pepperoni.tatar",
    "https://api.pepperoni.tatar",
}

# Minimal RU phone validator: +7/8 followed by 10 digits with optional separators.
PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
MAX_LEN = {"name": 120, "phone": 32, "message": 1000, "page": 300, "experiment_id": 64}

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


def _send_to_group(text: str) -> bool:
    if not LEADS_BOT_TOKEN or not LEADS_GROUP_ID:
        log.error("LEADS_BOT_TOKEN / LEADS_GROUP_ID not configured")
        return False
    url = f"https://api.telegram.org/bot{LEADS_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": LEADS_GROUP_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            ok = json.loads(r.read()).get("ok", False)
            if not ok:
                log.error("Telegram sendMessage returned ok=false")
            return ok
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)
        return False


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

    if not phone or not PHONE_RE.search(phone):
        return _cors_headers(jsonify(ok=False, error="invalid_phone")), 400

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
    text = "\n".join(lines)

    if not _send_to_group(text):
        return _cors_headers(jsonify(ok=False, error="delivery_failed")), 502

    log.info("Lead delivered: phone=%s page=%s exp=%s", phone, page, experiment_id)
    return _cors_headers(jsonify(ok=True)), 200


@app.route("/lead-submit", methods=["GET", "HEAD"])
def lead_submit_get():
    return "Lead intake endpoint is live. POST JSON here.", 200


@app.route("/lead-health", methods=["GET"])
def health():
    return jsonify(
        ok=True,
        configured=bool(LEADS_BOT_TOKEN and LEADS_GROUP_ID),
    ), 200


if __name__ == "__main__":
    log.info("Starting lead-intake on port %d (configured=%s)",
             PORT, bool(LEADS_BOT_TOKEN and LEADS_GROUP_ID))
    app.run(host="127.0.0.1", port=PORT, debug=False)
