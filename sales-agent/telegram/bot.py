#!/usr/bin/env python3
"""
@KDSalesManagerBot — консоль менеджера продаж Pepperoni.

Пароль: SALES_TG_PASSWORD (default Namaz2015!)
Sonnet — диалог и черновики; Opus — стратегия по запросу.

  python3 -m telegram.bot
  python3 sales-agent/telegram/bot.py
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import env as _env  # noqa: F401 — load .env
from core.gate import Gate
from core.llm import brain_available, call_opus, call_sonnet, remaining_budget
from core.store import Store
from kb.loader import KnowledgeBase
from orchestrator.run_cycle import run_cycle
from workers.escalate import format_contacts

DATA = ROOT / "data"
AUTH_FILE = DATA / "sales_tg_authorized.json"
PENDING_FILE = DATA / "sales_tg_pending.json"

BOT_TOKEN = os.environ.get("SALES_TELEGRAM_BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
PASSWORD = os.environ.get("SALES_TG_PASSWORD", "Namaz2015!")
SALT = os.environ.get("SALES_TG_SALT", "kdsales-manager-salt-v1")
POLL_TIMEOUT = 50

MAIN_MENU = [
    ["📊 Статус", "🔥 Горячие"],
    ["📋 Лиды", "📥 Инбокс"],
    ["🔄 Цикл", "🧠 Стратег"],
    ["💬 Спросить", "💰 Бюджет"],
]


def _pw_hash(pw: str) -> str:
    return hmac.new(SALT.encode(), pw.encode(), hashlib.sha256).hexdigest()


PASSWORD_HASH = _pw_hash(PASSWORD)


def load_authorized() -> dict:
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_authorized(d: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def is_authorized(chat_id: int) -> bool:
    return str(chat_id) in load_authorized()


def authorize(chat_id: int, name: str) -> None:
    d = load_authorized()
    d[str(chat_id)] = {"name": name, "since": datetime.now(timezone.utc).isoformat()}
    save_authorized(d)


def _api(method: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[sales-tg] api error {method}: {e}", file=sys.stderr)
        return {}


def send(chat_id: int, text: str, keyboard: list | None = None) -> None:
    params = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"}
    if keyboard is not None:
        params["reply_markup"] = json.dumps({"keyboard": keyboard, "resize_keyboard": True})
    _api("sendMessage", params)


def set_pending(chat_id: int, kind: str, payload: str = "") -> None:
    d = {}
    try:
        d = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    d[str(chat_id)] = {"kind": kind, "payload": payload}
    PENDING_FILE.write_text(json.dumps(d), encoding="utf-8")


def pop_pending(chat_id: int) -> dict | None:
    try:
        d = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    item = d.pop(str(chat_id), None)
    PENDING_FILE.write_text(json.dumps(d), encoding="utf-8")
    return item


def _approval_decision(text: str):
    parts = (text or "").strip().lower().split()
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    if parts[0] in ("одобрить", "одобряю", "approve", "ок"):
        return int(parts[1]), True
    if parts[0] in ("отклонить", "отклоняю", "reject", "отказ"):
        return int(parts[1]), False
    return None


def action_status() -> str:
    store = Store()
    store.init()
    s = store.stats()
    kb = KnowledgeBase()
    email_ok = "🟢" if os.environ.get("SMTP_PASSWORD") else "🔴"
    brain = "🟢" if brain_available() else "🔴"
    return (
        f"<b>📊 Sales Agent</b>\n"
        f"Лиды: <b>{s['leads']}</b> · <b>🔥 {s.get('hot_leads', 0)}</b> горячих\n"
        f"Ручных аппрувов: {s['pending_approvals']} (редко)\n"
        f"Черновики: {s['open_drafts']} · инбокс: {s['inbox_messages']}\n"
        f"Сигналы: {s['unprocessed_signals']}\n"
        f"SKU: {kb.product_count()} · почта {email_ok} · LLM {brain}\n"
        f"Бюджет Opus/Sonnet: <b>${remaining_budget():.2f}</b> осталось"
    )


def action_leads() -> str:
    store = Store()
    rows = store.list_leads(limit=12)
    if not rows:
        return "📋 Лидов нет. Запусти import-intel на VPS."
    lines = ["<b>📋 Топ лидов</b>"]
    for r in rows:
        lines.append(
            f"• <b>{r['tier']}</b> {r['fit_score']} — {r['name'][:42]} "
            f"({r.get('region') or '—'})"
        )
    return "\n".join(lines)


def action_hot_leads() -> str:
    store = Store()
    rows = store.list_hot_leads(10)
    if not rows:
        return (
            "🔥 Горячих лидов пока нет.\n\n"
            "<i>Агент сам шлёт холодняк (Opus). Сюда попадают заинтересованные — "
            "с контактами для личного звонка.</i>"
        )
    lines = ["<b>🔥 Заинтересованные — звони лично</b>"]
    for r in rows:
        p = r.get("profile") or {}
        reason = p.get("escalation_reason", "интерес")
        lines.append(f"\n{format_contacts(r)}\n<i>{reason[:200]}</i>")
    return "\n".join(lines)


def action_approvals() -> str:
    """Ручной hold — только если Opus сомневался."""
    store = Store()
    rows = store.list_approvals("pending", 10)
    if not rows:
        return "Ручных аппрувов нет — Opus решает сам."
    lines = ["<b>⚠️ Ручной hold</b> (<code>одобрить N</code> / <code>отклонить N</code>)"]
    for i, a in enumerate(rows, 1):
        lines.append(f"\n<b>{i}.</b> {a.get('lead_name','?')} — {a.get('title','')}")
    return "\n".join(lines)


def action_inbox() -> str:
    store = Store()
    msgs = store.inbox(8)
    if not msgs:
        return "📥 Инбокс пуст."
    lines = ["<b>📥 Инбокс</b>"]
    for m in msgs:
        lines.append(f"• {m.get('channel','?')}: {(m.get('body') or '')[:90]}")
    return "\n".join(lines)


def decide_approval(index_1: int, approve: bool, who: str) -> str:
    store = Store()
    gate = Gate(store)
    rows = store.list_approvals("pending")
    if index_1 < 1 or index_1 > len(rows):
        return f"Нет аппрува №{index_1}."
    aid = rows[index_1 - 1]["id"]
    if approve:
        gate.approve(aid, decided_by=who)
        return f"✅ Одобрено: {rows[index_1 - 1].get('lead_name','?')} — отправится на следующем цикле"
    gate.reject(aid, decided_by=who)
    return f"❌ Отклонено: {rows[index_1 - 1].get('lead_name','?')}"


def action_cycle() -> str:
    r = run_cycle(dry_run_send=False, max_drafts=3)
    done = r.get("tasks_done", 0)
    return (
        f"🔄 Цикл завершён: {done} задач.\n"
        f"<i>Холодняк — Opus одобрил и отправил с sales@. "
        f"Горячие — в 🔥 Горячие и пушем.</i>"
    )


def action_budget() -> str:
    """Расход LLM из единого леджера llm_costs.json — отдельно sales:* и всего."""
    try:
        import claude_client  # type: ignore
        summary = claude_client.month_summary()
    except Exception as e:
        return f"💰 Леджер недоступен: {e}"
    if not summary:
        return "💰 В этом месяце расходов ещё нет."

    total = summary.get("usd", 0.0)
    baseline = summary.get("usd_baseline", 0.0)
    scripts = summary.get("scripts", {})

    sales_usd = 0.0
    sales_lines = []
    for name, node in sorted(scripts.items(), key=lambda kv: -(kv[1].get("usd") or 0)):
        usd = node.get("usd", 0.0)
        if name.startswith("sales:"):
            sales_usd += usd
            sales_lines.append(f"  • {name[6:]}: ${usd:.3f} ({node.get('calls', 0)} вызовов)")

    saved_pct = (1 - total / baseline) * 100 if baseline > 0 else 0
    lines = [
        "<b>💰 Бюджет LLM (месяц)</b>",
        f"Всего по проекту: <b>${total:.2f}</b> (без оптимизаций было бы ${baseline:.2f}, −{saved_pct:.0f}%)",
        f"Sales-agent: <b>${sales_usd:.3f}</b>",
    ]
    if sales_lines:
        lines += sales_lines
    lines.append(f"\nОстаток общего бюджета: ${remaining_budget():.2f}")
    return "\n".join(lines)


def talk_sonnet(chat_id: int, question: str) -> str:
    if not brain_available():
        return "💬 LLM недоступен: нет ключа или бюджет исчерпан."
    kb = KnowledgeBase()
    store = Store()
    stats = store.stats()
    system = (
        "Ты B2B-ассистент менеджера продаж Казанских Деликатесы. "
        "Не публикуй kam@ и личный телефон в чате — только в email-черновиках. "
        "Цены из каталога можно, с оговоркой «согласовать с Ринатом».\n\n"
        f"{kb.sales_context(8)}\n\nСтатистика: {stats}"
    )
    try:
        reply, usage = call_sonnet(question, system=system, max_tokens=1200)
    except Exception as e:
        return f"Ошибка Sonnet: {e}"
    cost = usage.get("cost_usd", 0)
    store.audit(str(chat_id), "sonnet_chat", detail={"q": question[:200], "cost": cost})
    return f"💬 {reply}\n\n<i>Sonnet ${cost:.4f} · бюджет ${usage.get('budget_remaining_usd', 0):.2f}</i>"


def talk_strategy(chat_id: int) -> str:
    if not brain_available():
        return "🧠 Opus недоступен."
    store = Store()
    kb = KnowledgeBase()
    leads = store.list_leads(limit=30)
    tier_s = [l for l in leads if l.get("tier") == "S"]
    by_region: dict[str, int] = {}
    for l in tier_s:
        r = l.get("region") or "?"
        by_region[r] = by_region.get(r, 0) + 1

    prompt = (
        f"Данные контура продаж:\n"
        f"Всего лидов: {len(leads)}, Tier S: {len(tier_s)}\n"
        f"Кластеры Tier S по регионам: {by_region}\n"
        f"Аппрувы в очереди: {store.stats()['pending_approvals']}\n\n"
        "Дай стратегию на 2 недели: куда бить, что пилотировать, "
        "как загрузить фикс-базу Астрахани. 5-8 пунктов, конкретно."
    )
    system = (
        "Ты стратегический мозг B2B продаж halal-производителя мяса и выпечки. "
        "Opus-уровень: глубоко, но без воды.\n\n" + kb.context_for_prompt(12)
    )
    try:
        reply, usage = call_opus(prompt, system=system, max_tokens=2500, effort="medium")
    except Exception as e:
        return f"Ошибка Opus: {e}"
    store.add_signal("strategist", "opus_plan", {"text": reply[:2000], "by": str(chat_id)})
    cost = usage.get("cost_usd", 0)
    return f"🧠 <b>Стратегия (Opus)</b>\n\n{reply}\n\n<i>Opus ${cost:.4f}</i>"


def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    name = msg["chat"].get("first_name", "user")
    text = (msg.get("text") or "").strip()

    if not is_authorized(chat_id):
        if text == PASSWORD or _pw_hash(text) == PASSWORD_HASH:
            authorize(chat_id, name)
            send(
                chat_id,
                f"✅ Доступ открыт, {name}!\n"
                f"Менеджер продаж @KDSalesManagerBot\n"
                f"chat_id: <code>{chat_id}</code>",
                keyboard=MAIN_MENU,
            )
        else:
            send(
                chat_id,
                "🔒 Введите пароль для доступа к Sales Agent.\n\n"
                f"<i>chat_id: <code>{chat_id}</code></i>",
            )
        return

    dec = _approval_decision(text)
    if dec:
        idx, ok = dec
        send(chat_id, decide_approval(idx, ok, str(chat_id)), keyboard=MAIN_MENU)
        return

    if text in ("/start", "📋 Меню", "меню"):
        send(chat_id, "Меню Sales Agent:", keyboard=MAIN_MENU)
    elif text in ("📊 Статус", "/status"):
        send(chat_id, action_status(), keyboard=MAIN_MENU)
    elif text in ("📋 Лиды", "/leads"):
        send(chat_id, action_leads(), keyboard=MAIN_MENU)
    elif text in ("🔥 Горячие", "/hot", "горячие"):
        send(chat_id, action_hot_leads(), keyboard=MAIN_MENU)
    elif text in ("✅ Аппрувы", "/approvals"):
        send(chat_id, action_approvals(), keyboard=MAIN_MENU)
    elif text in ("📥 Инбокс", "/inbox"):
        send(chat_id, action_inbox(), keyboard=MAIN_MENU)
    elif text in ("🔄 Цикл", "/cycle"):
        send(chat_id, "🔄 Запускаю цикл…")
        send(chat_id, action_cycle(), keyboard=MAIN_MENU)
    elif text in ("🧠 Стратег", "/strategy"):
        send(chat_id, "🧠 Opus думает…")
        send(chat_id, talk_strategy(chat_id), keyboard=MAIN_MENU)
    elif text in ("💰 Бюджет", "/budget"):
        send(chat_id, action_budget(), keyboard=MAIN_MENU)
    elif text in ("💬 Спросить", "/ask"):
        set_pending(chat_id, "ask_sonnet")
        send(chat_id, "Напиши вопрос — отвечу через Sonnet.")
    else:
        try:
            d = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        if d.get(str(chat_id), {}).get("kind") == "ask_sonnet":
            pop_pending(chat_id)
            send(chat_id, "💬 Думаю…")
            send(chat_id, talk_sonnet(chat_id, text), keyboard=MAIN_MENU)
        else:
            send(chat_id, "💬 Думаю…")
            send(chat_id, talk_sonnet(chat_id, text), keyboard=MAIN_MENU)


def main() -> int:
    if not BOT_TOKEN:
        print("❌ SALES_TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return 1
    Store().init()
    print("🤖 KDSalesManagerBot started (long-poll).")
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
                    print(f"[sales-tg] handler error: {e}", file=sys.stderr)
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
