#!/usr/bin/env python3
"""
KazanDel AI Bot health monitor — watches BOTH customer-facing lead-gen channels:
  1. Chat widget bot (kazandel.service on the VPS, kazandelikates.tatar)
  2. Voice AI operator (kazandel-ai PM2 process, phone calls via MegaFon ATS +
     Twilio SIP trunk + OpenAI Realtime, ai.pepperoni.tatar)

Both are SEPARATE projects (/root/kazandel_ai_bot/, /opt/kazandel-ai-operator/,
not in this repo) but share the same VPS and the same Telegram alert channel
as the SEO brain, so this monitor lives here for a single place to watch
lead-gen health.

Checks (fail-fast, catches the exact failure modes from past incidents):
  1. systemd service is active (kazandel.service) — Telegram @KazanDel_Bot
  2. DeepSeek API key (used by the chat bot for every reply) is valid + has balance
  3. No recent crash-loop signature in the journal (network/connect errors)
  4. PM2 process kazandel-ai is online — voice AI operator (phone calls)
  5. Voice /health: status=ok AND openai.ok (Realtime via SOCKS, not just TCP)
  6. Voice watchdog heartbeat file is fresh (<15 min) — operator itself is probing
  7. Recent calls are not a mute streak (phone up, no speech, no lead)

Primary voice alerts go from the operator into the leads Telegram group.
This script is the SEO-bot backup + watcher-of-watchers.

Sends an alert to Telegram (SEO authorized chats) ONLY when something is wrong.
Cron: every 5 minutes (was hourly; hourly missed a 7-day silent-phone outage).

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
from datetime import datetime, timedelta, timezone
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


VOICE_HEALTH_URL = "https://ai.pepperoni.tatar/health"
VOICE_HEARTBEAT = Path("/opt/kazandel-ai-operator/data/voice-watchdog-heartbeat.json")
VOICE_CALLS_DB = Path("/opt/kazandel-ai-operator/data/calls.db")
HEARTBEAT_MAX_AGE_SEC = 15 * 60
MUTE_STREAK = 3
MUTE_MAX_SEC = 20


def check_voice_pm2() -> dict:
    code, out = _run(["pm2", "jlist"])
    if code != 0:
        return {"ok": False, "error": f"pm2 jlist failed: {out[:200]}"}
    try:
        procs = json.loads(out)
    except Exception as e:
        return {"ok": False, "error": f"pm2 jlist parse error: {e}"}
    for p in procs:
        if p.get("name") == "kazandel-ai":
            status = p.get("pm2_env", {}).get("status", "unknown")
            restarts = p.get("pm2_env", {}).get("restart_time", 0)
            return {"ok": status == "online", "status": status, "restarts": restarts}
    return {"ok": False, "error": "kazandel-ai process not found in pm2 list"}


def check_voice_health() -> dict:
    try:
        with urllib.request.urlopen(VOICE_HEALTH_URL, timeout=12) as r:
            data = json.loads(r.read())
        openai = data.get("openai") or {}
        openai_ok = bool(openai.get("ok"))
        status_ok = data.get("status") == "ok"
        err = openai.get("lastError")
        return {
            "ok": status_ok and openai_ok,
            "status": data.get("status"),
            "openai_ok": openai_ok,
            "http_ok": openai.get("httpOk"),
            "ws_ok": openai.get("wsOk"),
            "error": None if status_ok and openai_ok else (err or f"status={data.get('status')}"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_voice_heartbeat() -> dict:
    if not VOICE_HEARTBEAT.exists():
        return {"ok": False, "error": f"{VOICE_HEARTBEAT} missing — watchdog not running"}
    try:
        data = json.loads(VOICE_HEARTBEAT.read_text())
        ts = data.get("ts")
        age = None
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dt).total_seconds()
        stale = age is None or age > HEARTBEAT_MAX_AGE_SEC
        return {
            "ok": not stale and bool(data.get("openaiOk", True)),
            "age_sec": None if age is None else int(age),
            "openai_ok": data.get("openaiOk"),
            "error": (
                f"heartbeat stale {int(age)}s" if stale and age is not None
                else ("heartbeat ts missing" if stale else data.get("lastError"))
            ),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_voice_mute() -> dict:
    if not VOICE_CALLS_DB.exists():
        return {"ok": True, "note": "calls.db missing, skipped"}
    try:
        import sqlite3
        since = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        con = sqlite3.connect(str(VOICE_CALLS_DB))
        rows = list(con.execute(
            """
            SELECT duration_seconds, language, order_json
            FROM calls
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (since, MUTE_STREAK),
        ))
        con.close()
        if len(rows) < MUTE_STREAK:
            return {"ok": True, "recent": len(rows), "mute": 0}
        mute = 0
        for dur, lang, order in rows:
            if (dur or 0) <= MUTE_MAX_SEC and (not lang or lang == "unknown") and not order:
                mute += 1
        return {
            "ok": mute < MUTE_STREAK,
            "recent": len(rows),
            "mute": mute,
            "error": None if mute < MUTE_STREAK else f"{mute}/{len(rows)} last calls mute (≤{MUTE_MAX_SEC}s, no speech)",
        }
    except Exception as e:
        return {"ok": True, "note": f"mute check skipped: {e}"}


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
        "voice_pm2": check_voice_pm2(),
        "voice_health": check_voice_health(),
        "voice_heartbeat": check_voice_heartbeat(),
        "voice_mute": check_voice_mute(),
    }


def build_report(result: dict) -> str:
    svc, ds, cl = result["service"], result["deepseek"], result["crash_loop"]
    vpm2, vh = result["voice_pm2"], result["voice_health"]
    vhb = result.get("voice_heartbeat") or {"ok": True}
    vmute = result.get("voice_mute") or {"ok": True}
    all_ok = (
        svc["ok"] and ds["ok"] and cl["ok"] and vpm2["ok"]
        and vh["ok"] and vhb["ok"] and vmute["ok"]
    )

    lines = ["<b>🤖 KazanDel AI — здоровье лидогена (чат + звонки)</b>"]

    if svc["ok"]:
        lines.append("✅ Чат-бот активен (kazandel.service)")
    else:
        lines.append(f"🔴 Чат-бот НЕ активен: <b>{svc['state']}</b>")

    if ds["ok"]:
        lines.append(f"✅ DeepSeek ключ рабочий (баланс ${ds.get('balance_usd','?')}, ...{ds.get('key_suffix','')})")
    elif ds.get("low_balance"):
        lines.append(f"🟡 DeepSeek баланс низкий: ${ds.get('balance_usd','?')} — пополни, иначе бот скоро встанет")
    else:
        lines.append(f"🔴 DeepSeek ключ НЕ работает: {ds.get('error','?')} "
                      f"(...{ds.get('key_suffix','?')}) — чат-бот не сможет отвечать клиентам!")

    if cl["ok"]:
        lines.append("✅ Логи чат-бота в норме, шторма ошибок нет")
    else:
        lines.append(f"🔴 Похоже на crash-loop чат-бота: {cl.get('lines_last_hour','?')} строк/час, "
                      f"{cl.get('error_lines_last_hour','?')} с ошибками за последний час")

    if vpm2["ok"]:
        lines.append(f"✅ Голосовой ИИ-оператор (звонки, PM2) online (рестартов: {vpm2.get('restarts','?')})")
    else:
        lines.append(f"🔴 Голосовой ИИ-оператор НЕ работает: {vpm2.get('error', vpm2.get('status','?'))} "
                      f"— входящие звонки с телефона НЕ будут обрабатываться!")

    if vh["ok"]:
        lines.append("✅ Голос: /health + OpenAI Realtime через SOCKS живы")
    else:
        lines.append(
            f"🔴 Голос: путь до OpenAI сломан: {vh.get('error','?')} "
            f"(http={vh.get('http_ok')} ws={vh.get('ws_ok')}) — клиент слышит тишину"
        )

    if vhb["ok"]:
        lines.append(f"✅ Сторож голоса пишет heartbeat (возраст {vhb.get('age_sec','?')}с)")
    else:
        lines.append(f"🔴 Сторож голоса молчит: {vhb.get('error','?')}")

    if vmute["ok"]:
        lines.append("✅ Последние звонки не выглядят как немой автоответ")
    else:
        lines.append(f"🔴 {vmute.get('error','немые звонки')} — трубка берётся, голоса нет")

    if all_ok:
        lines.append("\n<i>Всё в порядке — лиды с сайта и звонки должны доходить нормально.</i>")
    else:
        lines.append("\n<b>⚠️ Требуется вмешательство — лиды или звонки могут теряться!</b>")

    return "\n".join(lines), all_ok


def send_to_telegram(text: str) -> None:
    sent = 0
    try:
        import telegram_notify as tn
        sent = tn.notify(text)
    except Exception as e:
        print(f"⏭ telegram_notify failed: {e}", file=sys.stderr)
    if sent:
        return
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
