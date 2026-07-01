#!/usr/bin/env python3
"""
KazanDel AI Bot health monitor — watches the customer-facing lead-gen bot
(kazandel.service on the VPS, powers the chat widget on kazandelikates.tatar
and forwards hot leads / manager requests to Telegram).

This bot is a SEPARATE project (/root/kazandel_ai_bot/, not in this repo) but
shares the same VPS and the same Telegram alert channel as the SEO brain, so
this monitor lives here for a single place to watch site health.

Checks (fail-fast, catches the exact failure mode from 2026-07-01 incident):
  1. systemd service is active (kazandel.service)
  2. DeepSeek API key (used by the bot for every reply) is valid + has balance
  3. No recent crash-loop signature in the journal (network/connect errors)

Sends an alert to Telegram (same authorized chats as the SEO bot) ONLY when
something is wrong, so it stays quiet in the good case. Run via cron every
hour — the 2026-07-01 incident went undetected for ~12 days because nothing
was watching this bot at all.

Usage:
    python3 scripts/monitor_kazandel_bot.py             # check + alert on Telegram
    python3 scripts/monitor_kazandel_bot.py --no-telegram
    python3 scripts/monitor_kazandel_bot.py --always     # always send, even if OK
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
SNAPSHOT = DATA / "kazandel_health.json"

BOT_DIR = Path("/root/kazandel_ai_bot")
CONFIG_PY = BOT_DIR / "config.py"
SERVICE_NAME = "kazandel.service"

DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
CRASH_LOOP_WINDOW = "1 hour ago"
# Normal polling (getUpdates every ~10s) produces ~360 lines/hour. The 2026-06-26
# crash-loop produced ~10,680 lines/hour (30x). Set the bar well above normal
# noise but well below a real storm.
CRASH_LOOP_THRESHOLD = 2000


def _run(cmd: list) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def check_service() -> dict:
    code, out = _run(["systemctl", "is-active", SERVICE_NAME])
    active = out.strip() == "active"
    return {"ok": active, "state": out.strip() or "unknown"}


def check_deepseek_key() -> dict:
    if not CONFIG_PY.exists():
        return {"ok": False, "error": f"{CONFIG_PY} not found (bot moved/reinstalled?)"}
    try:
        text = CONFIG_PY.read_text()
        m = re.search(r'DEEPSEEK_API_KEY\s*=\s*"([^"]+)"', text)
        if not m:
            return {"ok": False, "error": "DEEPSEEK_API_KEY not found in config.py"}
        key = m.group(1)
    except Exception as e:
        return {"ok": False, "error": f"cannot read config.py: {e}"}

    req = urllib.request.Request(
        DEEPSEEK_BALANCE_URL, headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        available = bool(data.get("is_available"))
        balance = ""
        for b in data.get("balance_infos", []):
            if b.get("currency") == "USD":
                balance = b.get("total_balance", "")
                break
        low_balance = False
        try:
            low_balance = balance != "" and float(balance) < 2.0
        except Exception:
            pass
        return {
            "ok": available and not low_balance,
            "available": available,
            "balance_usd": balance,
            "low_balance": low_balance,
            "key_suffix": key[-4:],
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        return {"ok": False, "error": f"HTTP {e.code}: {body}", "key_suffix": key[-4:]}
    except Exception as e:
        return {"ok": False, "error": str(e), "key_suffix": key[-4:]}


def check_crash_loop() -> dict:
    code, out = _run([
        "journalctl", "-u", SERVICE_NAME, "--since", CRASH_LOOP_WINDOW,
        "--no-pager", "-o", "cat",
    ])
    if code != 0:
        return {"ok": True, "note": "journalctl unavailable, skipped"}
    lines = out.splitlines()
    errors = [l for l in lines if re.search(r"error|traceback|exception|connecterror", l, re.I)]
    return {
        "ok": len(lines) < CRASH_LOOP_THRESHOLD and len(errors) < 20,
        "lines_last_hour": len(lines),
        "error_lines_last_hour": len(errors),
    }


def run_checks() -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": check_service(),
        "deepseek": check_deepseek_key(),
        "crash_loop": check_crash_loop(),
    }


def build_report(result: dict) -> str:
    svc, ds, cl = result["service"], result["deepseek"], result["crash_loop"]
    all_ok = svc["ok"] and ds["ok"] and cl["ok"]

    lines = ["<b>🤖 KazanDel AI Bot — здоровье лидогена</b>"]

    if svc["ok"]:
        lines.append("✅ Сервис активен (kazandel.service)")
    else:
        lines.append(f"🔴 Сервис НЕ активен: <b>{svc['state']}</b>")

    if ds["ok"]:
        lines.append(f"✅ DeepSeek ключ рабочий (баланс ${ds.get('balance_usd','?')}, ...{ds.get('key_suffix','')})")
    elif ds.get("low_balance"):
        lines.append(f"🟡 DeepSeek баланс низкий: ${ds.get('balance_usd','?')} — пополни, иначе бот скоро встанет")
    else:
        lines.append(f"🔴 DeepSeek ключ НЕ работает: {ds.get('error','?')} "
                      f"(...{ds.get('key_suffix','?')}) — бот не сможет отвечать клиентам!")

    if cl["ok"]:
        lines.append("✅ Логи в норме, шторма ошибок нет")
    else:
        lines.append(f"🔴 Похоже на crash-loop: {cl.get('lines_last_hour','?')} строк/час, "
                      f"{cl.get('error_lines_last_hour','?')} с ошибками за последний час")

    if all_ok:
        lines.append("\n<i>Всё в порядке — лиды с сайта должны доходить нормально.</i>")
    else:
        lines.append("\n<b>⚠️ Требуется вмешательство — лиды с сайта могут теряться!</b>")

    return "\n".join(lines), all_ok


def send_to_telegram(text: str) -> None:
    try:
        import telegram_bot as tg
    except Exception as e:
        print(f"⏭ telegram unavailable: {e}", file=sys.stderr)
        return
    auth = tg.load_authorized()
    if not auth:
        print("⏭ no authorized telegram chats")
        return
    for cid in auth:
        tg.send(int(cid), text)
    print(f"📤 sent to {len(auth)} chat(s)")


def main():
    args = set(sys.argv[1:])
    result = run_checks()

    try:
        DATA.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    except Exception as e:
        print(f"⚠️ snapshot write failed: {e}", file=sys.stderr)

    report, all_ok = build_report(result)
    if "--raw-report" in args:
        print(report)
    else:
        print(report.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))

    if "--no-telegram" not in args:
        if not all_ok or "--always" in args:
            send_to_telegram(report)
        else:
            print("✅ all checks passed — telegram alert skipped (use --always to force)")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
