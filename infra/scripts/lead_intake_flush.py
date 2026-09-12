#!/usr/bin/env python3
"""Re-send leads that lead_intake_server.py could not deliver to the Telegram
group, and alert the owner by e-mail about every such lead.

Why: from the Selectel VPS ~25% of Bot API calls time out (measured 2026-09-12),
so the intake keeps undelivered leads in a sqlite spool instead of answering
502 to the buyer. This script runs from cron every 2 minutes:

  */2 * * * * cd /var/www/pepperoni/repo && set -a && . /var/www/pepperoni/seo-agent.env && set +a \
      && python3 infra/scripts/lead_intake_flush.py >> /var/log/pepperoni-lead-flush.log 2>&1

Environment (seo-agent.env): LEADS_BOT_TOKEN, LEADS_GROUP_ID, LEAD_DEDUP_DB
(shared with the server) and, for alerts, ALERT_EMAIL_TO, ALERT_SMTP_HOST,
ALERT_SMTP_PORT (465 = SSL, 587 = STARTTLS), ALERT_SMTP_USER, ALERT_SMTP_PASS.
Without SMTP settings the alert is only logged (grep "ALERT" in the log).

Exit code 0 = nothing pending or all re-sent; 1 = leads still pending.
"""
from __future__ import annotations

import importlib.util
import os
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lead_intake_server", HERE / "lead_intake_server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)  # type: ignore[union-attr]

ALERT_TO = os.getenv("ALERT_EMAIL_TO", "").strip()
SMTP_HOST = os.getenv("ALERT_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "465") or 465)
SMTP_USER = os.getenv("ALERT_SMTP_USER", "").strip()
SMTP_PASS = os.getenv("ALERT_SMTP_PASS", "").strip()
# Alert once per lead as soon as it is seen pending, and again if it is still
# pending after ALERT_STALE_MIN minutes (so a dead channel is not silent).
ALERT_STALE_MIN = int(os.getenv("ALERT_STALE_MIN", "30"))


def _alert(subject: str, body: str) -> None:
    line = f"ALERT {subject} | {body.replace(chr(10), ' / ')}"
    print(line)
    if not (ALERT_TO and SMTP_HOST and SMTP_USER and SMTP_PASS):
        print("ALERT not e-mailed: ALERT_EMAIL_TO / ALERT_SMTP_* not configured")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_TO
    msg.set_content(body)
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
        print(f"ALERT e-mailed to {ALERT_TO}")
    except Exception as exc:
        print(f"ALERT e-mail failed: {exc}")


def main() -> int:
    conn = srv._spool_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS spool_alerts (lead_id TEXT PRIMARY KEY, first_ts REAL, stale_ts REAL)")
    rows = conn.execute(
        "SELECT lead_id, ts, text, attempts FROM spool WHERE delivered_ts IS NULL ORDER BY ts"
    ).fetchall()
    if not rows:
        return 0
    now = time.time()
    still = 0
    for lead_id, ts, text, attempts in rows:
        alerted = conn.execute("SELECT first_ts, stale_ts FROM spool_alerts WHERE lead_id = ?", (lead_id,)).fetchone()
        if not alerted:
            _alert(
                f"[pepperoni.tatar] заявка {lead_id} не доставлена в Telegram — в очереди",
                f"Заявка с сайта не дошла до группы продаж с {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(ts))} "
                f"({attempts} попыток). Повторяем каждые 2 мин.\n\n{text}",
            )
            conn.execute("INSERT OR REPLACE INTO spool_alerts (lead_id, first_ts, stale_ts) VALUES (?, ?, NULL)", (lead_id, now))
            conn.commit()
        if srv._send_to_group(text, attempts=2):
            conn.execute("UPDATE spool SET delivered_ts = ?, attempts = attempts + 1 WHERE lead_id = ?", (now, lead_id))
            conn.commit()
            print(f"delivered {lead_id} after {now - ts:.0f}s in spool")
            _alert(f"[pepperoni.tatar] заявка {lead_id} доставлена в Telegram (из очереди)",
                   f"Доставлена через {now - ts:.0f} с после приёма.\n\n{text}")
            continue
        still += 1
        conn.execute("UPDATE spool SET attempts = attempts + 1, last_error = ? WHERE lead_id = ?",
                     ("flush_retry_failed", lead_id))
        conn.commit()
        if now - ts > ALERT_STALE_MIN * 60 and alerted and not alerted[1]:
            _alert(f"[pepperoni.tatar] заявка {lead_id} всё ещё не доставлена ({ALERT_STALE_MIN}+ мин)",
                   f"Позвоните клиенту по данным ниже; канал Telegram с VPS недоступен.\n\n{text}")
            conn.execute("UPDATE spool_alerts SET stale_ts = ? WHERE lead_id = ?", (now, lead_id))
            conn.commit()
    print(f"pending after flush: {still}")
    return 1 if still else 0


if __name__ == "__main__":
    sys.exit(main())
