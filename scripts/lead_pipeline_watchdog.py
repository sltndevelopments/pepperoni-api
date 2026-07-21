#!/usr/bin/env python3
"""Lead pipeline watchdog.

Checks the two moving parts of the site→lead loop and alerts the owner via
Telegram (emergency severity, deduped) when either is down:

  1. lead-intake server (this VPS): HTTP /lead-health must return ok.
  2. leadbot userbot (DigitalOcean droplet): systemd leadbot.service must be
     active AND leads.json must be advancing (updated recently).

Run from cron every ~10 min:
  */10 * * * * cd /var/www/pepperoni/repo && python3 scripts/lead_pipeline_watchdog.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).resolve().parent.parent
LEADS_FILE = ROOT / "data" / "leads.json"
DROPLET = os.environ.get("LEADBOT_DROPLET", "root@178.62.250.104")
INTAKE_HEALTH = os.environ.get("LEAD_INTAKE_HEALTH", "http://127.0.0.1:5002/lead-health")


def _alert(text: str, key: str) -> None:
    try:
        from notification_router import emit
        emit("emergency", "lead_pipeline", text, dedupe_key=key)
    except Exception as exc:  # never let the watchdog itself crash silently
        print(f"ALERT (emit failed: {exc}): {text}", file=sys.stderr)


def check_intake() -> list[str]:
    problems = []
    try:
        with urllib.request.urlopen(INTAKE_HEALTH, timeout=10) as r:
            data = json.loads(r.read())
        if not data.get("ok"):
            problems.append("lead-intake: health ok=false")
        elif not data.get("configured"):
            problems.append("lead-intake: not configured (token/group missing)")
    except Exception as exc:
        problems.append(f"lead-intake unreachable: {type(exc).__name__}")
    return problems


def check_droplet() -> list[str]:
    problems = []
    try:
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new",
             DROPLET, "systemctl is-active leadbot.service"],
            capture_output=True, text=True, timeout=30,
        )
        state = (out.stdout or "").strip()
        if state != "active":
            problems.append(f"droplet leadbot.service: {state or 'unreachable'}")
    except Exception as exc:
        problems.append(f"droplet SSH failed: {type(exc).__name__}")
    return problems


def check_leads_file() -> list[str]:
    """Validate the mirrored leads.json is present and parseable.

    NOTE: we deliberately do NOT alarm on a stale updated_at — no new leads for a
    while is a normal business state, not a pipeline failure. Userbot liveness is
    covered by check_droplet (systemd active); the sync cron keeps the mirror
    fresh. Here we only catch a corrupt/missing mirror.
    """
    problems = []
    try:
        d = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        if not isinstance(d.get("leads"), list):
            problems.append("leads.json malformed (no leads list)")
    except FileNotFoundError:
        problems.append("leads.json missing on VPS")
    except Exception as exc:
        problems.append(f"leads.json unreadable: {type(exc).__name__}")
    return problems


def main() -> int:
    problems = check_intake() + check_droplet() + check_leads_file()
    if problems:
        text = ("Пайплайн заявок с сайта деградировал:\n• "
                + "\n• ".join(problems)
                + "\n\nЗаявки с форм могут не доходить. Проверить сервисы "
                  "lead-intake (VPS) и leadbot (дроплет).")
        _alert(text, key="lead_pipeline_down")
        print("PROBLEMS:", "; ".join(problems))
        return 1
    print("lead pipeline healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
