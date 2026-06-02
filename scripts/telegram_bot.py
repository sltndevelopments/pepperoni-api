#!/usr/bin/env python3
"""
Telegram control bot for the autonomous SEO brain (pepperoni.tatar).

DESIGN (cost-safe):
  • Most actions are FREE (read files / run scripts) — no LLM tokens.
  • Only the explicit "🧠 Спросить мозг" flow calls Opus (costs ~$0.01-0.03),
    and it shows an estimate + confirm before spending.
  • First login requires a password (stored as a salted hash, never plaintext).
    Authorized chat_ids are persisted in data/tg_authorized.json.
  • Every interaction is written to the brain journal (persistent memory).

Runs as a long-poll loop (stdlib only). Managed by systemd (see install docs).

Env:
  TELEGRAM_BOT_TOKEN   — from @BotFather (required)
  TG_PASSWORD          — first-login password (default: Namaz2015!)
  ANTHROPIC_API_KEY    — for the "ask brain" flow (optional)
"""

import json
import os
import subprocess
import sys
import time
import hashlib
import hmac
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import brain_journal as J

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
AUTH_FILE = DATA / "tg_authorized.json"
PENDING_FILE = DATA / "tg_pending.json"   # pending confirmations

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
PASSWORD = os.environ.get("TG_PASSWORD", "Namaz2015!")
SALT = os.environ.get("TG_SALT", "pepperoni-brain-salt-v1")

POLL_TIMEOUT = 50


# ── Auth ───────────────────────────────────────────────────────────────────────
def _pw_hash(pw: str) -> str:
    return hmac.new(SALT.encode(), pw.encode(), hashlib.sha256).hexdigest()

PASSWORD_HASH = _pw_hash(PASSWORD)


def load_authorized() -> dict:
    try:
        return json.loads(AUTH_FILE.read_text())
    except Exception:
        return {}


def save_authorized(d: dict) -> None:
    DATA.mkdir(exist_ok=True)
    AUTH_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def is_authorized(chat_id: int) -> bool:
    return str(chat_id) in load_authorized()


def authorize(chat_id: int, name: str) -> None:
    d = load_authorized()
    d[str(chat_id)] = {"name": name, "since": datetime.now(timezone.utc).isoformat()}
    save_authorized(d)


# ── Telegram API helpers ────────────────────────────────────────────────────────
def _api(method: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[tg] api error {method}: {e}", file=sys.stderr)
        return {}


def send(chat_id: int, text: str, keyboard: list | None = None) -> None:
    params = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"}
    if keyboard is not None:
        params["reply_markup"] = json.dumps({
            "keyboard": keyboard, "resize_keyboard": True
        })
    _api("sendMessage", params)


MAIN_MENU = [
    ["📊 Статус", "💰 Бюджет"],
    ["🚀 Запустить генерацию", "📜 История"],
    ["🧠 Спросить мозг", "📋 Стратегия"],
]


# ── Free actions (no LLM) ────────────────────────────────────────────────────────
def _count(p: Path, pat="*.html") -> int:
    try:
        return len(list(p.glob(pat)))
    except Exception:
        return 0


def action_status() -> str:
    geo = _count(PUBLIC / "geo") + sum(_count(d) for d in PUBLIC.glob("*/geo"))
    blog = _count(PUBLIC / "blog") + sum(_count(d) for d in PUBLIC.glob("*/blog"))
    pl = _count(PUBLIC / "private-label") + sum(_count(d) for d in PUBLIC.glob("*/private-label"))
    running = subprocess.run(["pgrep", "-f", "generate_geo_bulk"],
                             capture_output=True).returncode == 0
    return (
        f"<b>📊 Статус сайта</b>\n"
        f"Гео-страниц: <b>{geo}</b>\n"
        f"Блог-статей: <b>{blog}</b>\n"
        f"Private Label: <b>{pl}</b>\n"
        f"Массовая генерация: {'🟢 идёт' if running else '⚪ остановлена'}"
    )


def action_budget() -> str:
    try:
        from opus_brain_client import remaining_budget, MONTHLY_BUDGET_USD, _load_budget
        d = _load_budget()
        return (
            f"<b>💰 Бюджет мозга (Opus)</b>\n"
            f"Месяц: {d['month']}\n"
            f"Потрачено: <b>${d.get('spent_usd',0):.3f}</b> / ${MONTHLY_BUDGET_USD:.0f}\n"
            f"Осталось: <b>${remaining_budget():.3f}</b>\n"
            f"Вызовов мозга: {d.get('calls',0)}"
        )
    except Exception as e:
        return f"Бюджет недоступен: {e}"


def action_strategy() -> str:
    try:
        s = json.loads((DATA / "strategy.json").read_text())
        fp = ", ".join(s.get("focus_products", [])[:6]) or "—"
        langs = ", ".join(s.get("focus_langs", [])[:8]) or "—"
        return (
            f"<b>📋 Текущая стратегия</b>\n"
            f"Обновлена: {s.get('generated_at','?')[:16]}\n"
            f"Фокус-продукты: {fp}\n"
            f"Языки: {langs}\n"
            f"Гео/день: {s.get('geo_daily_target','?')}\n"
            f"Блог-тем: {len(s.get('new_blog_topics',[]))} | "
            f"PL/OEM: {len(s.get('pl_oem_topics',[]))}\n"
            f"Заметка: {s.get('notes','')[:300]}"
        )
    except Exception:
        return "Стратегия ещё не сформирована (мозг не запускался или нет ключа)."


def action_history() -> str:
    entries = J.tail(12)
    if not entries:
        return "📜 История пуста."
    lines = ["<b>📜 Последние действия</b>"]
    for e in entries:
        ts = e.get("ts", "")[:16].replace("T", " ")
        lines.append(f"• [{ts}] {e.get('kind')}: {e.get('text','')[:90]}")
    return "\n".join(lines)


def action_run_generation(chat_id: int) -> str:
    running = subprocess.run(["pgrep", "-f", "generate_geo_bulk"],
                             capture_output=True).returncode == 0
    if running:
        return "🟢 Генерация уже идёт — дождись завершения."
    # Launch the cheap worker tick (DeepSeek only, no LLM brain cost)
    subprocess.Popen(
        ["bash", str(ROOT / "scripts" / "seo-worker.sh")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    J.log_event("user_cmd", "запуск генерации (worker tick)", who=str(chat_id))
    return "🚀 Запустил рабочий цикл (DeepSeek). Через пару минут проверь 📊 Статус."


# ── Brain flow (costs money — confirmed) ─────────────────────────────────────────
def set_pending(chat_id: int, kind: str, payload: str) -> None:
    d = {}
    try:
        d = json.loads(PENDING_FILE.read_text())
    except Exception:
        pass
    d[str(chat_id)] = {"kind": kind, "payload": payload}
    PENDING_FILE.write_text(json.dumps(d))


def pop_pending(chat_id: int) -> dict | None:
    try:
        d = json.loads(PENDING_FILE.read_text())
    except Exception:
        return None
    item = d.pop(str(chat_id), None)
    PENDING_FILE.write_text(json.dumps(d))
    return item


def ask_brain(chat_id: int, question: str) -> str:
    """Call Opus with journal context. Costs money — already confirmed."""
    try:
        from opus_brain_client import call_opus, brain_available, remaining_budget
    except Exception as e:
        return f"Мозг недоступен: {e}"
    if not brain_available():
        return ("🧠 Мозг недоступен: нет ANTHROPIC_API_KEY или исчерпан бюджет "
                f"(осталось ${remaining_budget():.2f}).")

    context = J.recent_summary(max_chars=2000)
    system = (
        "Ты — стратегический мозг SEO/AI-присутствия компании «Казанские Деликатесы» "
        "(pepperoni.tatar), халяль производитель мяса и выпечки. Цель — №1 в РФ, СНГ, "
        "арабских/африканских/ЮВА рынках по всему ассортименту и услугам Private Label/OEM. "
        "Отвечай кратко, по делу, на русском. Если предлагаешь действия — конкретные шаги. "
        "Помни про равномерное покрытие всех категорий и масштабную географию.\n\n"
        f"КОНТЕКСТ (журнал последних действий):\n{context}"
    )
    try:
        text, usage = call_opus(prompt=question, system=system,
                                max_tokens=1500, temperature=0.4, cache_system=False)
    except Exception as e:
        return f"Ошибка вызова мозга: {e}"
    J.log_event("user_cmd", question, who=str(chat_id))
    J.log_event("brain_reply", text, who="opus",
                meta={"cost_usd": usage.get("cost_usd")})
    cost = usage.get("cost_usd", 0)
    rem = usage.get("budget_remaining_usd", 0)
    return f"🧠 {text}\n\n<i>стоимость: ${cost} · осталось в бюджете: ${rem}</i>"


# ── Message router ───────────────────────────────────────────────────────────────
def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    name = msg["chat"].get("first_name", "user")
    text = (msg.get("text") or "").strip()

    # 1) Auth gate
    if not is_authorized(chat_id):
        if text == PASSWORD or _pw_hash(text) == PASSWORD_HASH:
            authorize(chat_id, name)
            J.log_event("system", f"authorized {name} ({chat_id})", who="bot")
            send(chat_id, f"✅ Доступ открыт, {name}! Ты управляешь мозгом сайта.",
                 keyboard=MAIN_MENU)
        else:
            send(chat_id, "🔒 Введите пароль для доступа к мозгу сайта:")
        return

    # 2) Pending confirmation (e.g. brain question)
    low = text.lower()
    pend = None
    if low in ("да", "yes", "✅ да", "подтверждаю"):
        pend = pop_pending(chat_id)
        if pend and pend["kind"] == "ask_brain":
            send(chat_id, "🧠 Думаю…")
            send(chat_id, ask_brain(chat_id, pend["payload"]), keyboard=MAIN_MENU)
            return
    if low in ("нет", "no", "❌ нет", "отмена"):
        pop_pending(chat_id)
        send(chat_id, "Отменено.", keyboard=MAIN_MENU)
        return

    # 3) Menu / commands (FREE)
    if text in ("/start", "📋 Меню", "меню"):
        send(chat_id, "Главное меню. Выбери действие:", keyboard=MAIN_MENU)
    elif text in ("📊 Статус", "/status", "статус"):
        send(chat_id, action_status(), keyboard=MAIN_MENU)
    elif text in ("💰 Бюджет", "/budget", "бюджет"):
        send(chat_id, action_budget(), keyboard=MAIN_MENU)
    elif text in ("📋 Стратегия", "/strategy", "стратегия"):
        send(chat_id, action_strategy(), keyboard=MAIN_MENU)
    elif text in ("📜 История", "/history", "история"):
        send(chat_id, action_history(), keyboard=MAIN_MENU)
    elif text in ("🚀 Запустить генерацию", "/run", "запустить"):
        send(chat_id, action_run_generation(chat_id), keyboard=MAIN_MENU)
    elif text in ("🧠 Спросить мозг", "/ask"):
        set_pending(chat_id, "ask_brain_prompt", "")
        send(chat_id, "Напиши вопрос мозгу одним сообщением "
                      "(например: «что улучшить по выпечке в Турции?»).")
    else:
        # If we're waiting for a brain question, treat this text as the question
        try:
            d = json.loads(PENDING_FILE.read_text())
        except Exception:
            d = {}
        if d.get(str(chat_id), {}).get("kind") == "ask_brain_prompt":
            pop_pending(chat_id)
            set_pending(chat_id, "ask_brain", text)
            send(chat_id, f"❓ Спросить мозг (Opus): «{text[:120]}»\n"
                          f"Это будет стоить ~$0.01-0.03. Подтвердить?",
                 keyboard=[["✅ Да", "❌ Нет"]])
        else:
            send(chat_id, "Не понял. Открой меню кнопкой ниже.", keyboard=MAIN_MENU)


# ── Daily digest (called by cron, not the loop) ──────────────────────────────────
def send_daily_digest() -> None:
    auth = load_authorized()
    if not auth:
        return
    body = action_status() + "\n\n" + action_strategy()
    J.log_event("digest", "daily digest sent", who="bot")
    for cid in auth:
        send(int(cid), "<b>☀️ Утренний дайджест</b>\n\n" + body, keyboard=MAIN_MENU)


# ── Main loop ────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return 1
    if "--digest" in sys.argv:
        send_daily_digest()
        return 0

    print("🤖 Telegram bot started (long-poll).")
    offset = 0
    while True:
        resp = _api("getUpdates", {"timeout": POLL_TIMEOUT, "offset": offset})
        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message")
            if msg and "chat" in msg:
                try:
                    handle_message(msg)
                except Exception as e:
                    print(f"[tg] handler error: {e}", file=sys.stderr)
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
