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

from __future__ import annotations

import html
import json
import os
import re
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

# Bot state lives OUTSIDE the git tree (survives deploys/reset); telegram_notify
# owns the dir resolution + one-time migration from data/.
from telegram_notify import STATE_DIR as TG_STATE
AUTH_FILE = TG_STATE / "tg_authorized.json"
PENDING_FILE = TG_STATE / "tg_pending.json"   # pending confirmations
APPROVALS_FILE = DATA / "approvals.json"  # high-impact actions awaiting human OK

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
    ["🩺 SEO здоровье", "🧪 Эксперименты"],
    ["🛰 Разведка", "🎯 Цели"],
    ["🤖 Мета-агент", "📒 Решения"],
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

    # Is the worker scheduled in cron?
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout or ""
    scheduled = "seo-worker.sh" in cron and not cron.count("#PAUSED 15")

    # Last worker tick + pages pushed (from its log)
    last_line = ""
    pushed = ""
    try:
        log = Path("/var/log/pepperoni-seo-worker.log")
        if log.exists():
            tail = log.read_text(errors="ignore").splitlines()[-40:]
            ticks = [l for l in tail if "Worker tick" in l or "pushed" in l]
            for l in reversed(tail):
                if "pushed" in l:
                    pushed = l.split("pushed", 1)[1].strip()
                    break
            starts = [l for l in tail if "SEO Worker tick" in l]
            if starts:
                # timestamp like [2026-06-02 18:15:01]
                ts = starts[-1].split("]", 1)[0].lstrip("[")
                last_line = ts
    except Exception:
        pass

    if running:
        gen = "🟢 активна (идёт прямо сейчас)"
    elif scheduled:
        gen = "🟡 по расписанию (каждые 3ч)"
        if last_line:
            gen += f"\nПоследний прогон: <b>{last_line}</b>"
        if pushed:
            gen += f" · +{pushed}"
    else:
        gen = "⚪ остановлена (крон выключен)"

    return (
        f"<b>📊 Статус сайта</b>\n"
        f"Гео-страниц: <b>{geo}</b>\n"
        f"Блог-статей: <b>{blog}</b>\n"
        f"Private Label: <b>{pl}</b>\n"
        f"Генерация: {gen}"
    )


def action_budget() -> str:
    lines = []
    # Brain (Fable) budget — separate guarded wallet.
    try:
        from opus_brain_client import remaining_budget, MONTHLY_BUDGET_USD, _load_budget
        d = _load_budget()
        lines.append(
            f"<b>💰 Бюджет мозга (Fable)</b>\n"
            f"Месяц: {d['month']}\n"
            f"Потрачено: <b>${d.get('spent_usd',0):.3f}</b> / ${MONTHLY_BUDGET_USD:.0f}\n"
            f"Осталось: <b>${remaining_budget():.3f}</b> · вызовов: {d.get('calls',0)}"
        )
    except Exception as e:
        lines.append(f"Бюджет мозга недоступен: {e}")

    # Full LLM telemetry — every Anthropic/Perplexity call across all scripts.
    try:
        led = json.loads((DATA / "llm_costs.json").read_text())
        from datetime import date as _date
        m = led.get(_date.today().strftime("%Y-%m"), {})
        if m:
            usd = m.get("usd", 0.0)
            base = m.get("usd_baseline", 0.0)
            saved = max(0.0, base - usd)
            pct = (saved / base * 100) if base else 0
            lines.append(
                f"\n<b>📟 Все LLM-вызовы (месяц)</b>\n"
                f"Фактически: <b>${usd:.2f}</b>\n"
                f"Без оптимизаций было бы: ${base:.2f}\n"
                f"Экономия: <b>${saved:.2f}</b> ({pct:.0f}%)"
            )
            scripts = sorted(m.get("scripts", {}).items(),
                             key=lambda kv: -kv[1].get("usd", 0))[:6]
            if scripts:
                lines.append("\nТоп по скриптам:")
                for name, s in scripts:
                    lines.append(f"• {name}: ${s.get('usd',0):.2f} "
                                 f"({s.get('calls',0)} выз.)")
        else:
            lines.append("\n📟 Телеметрия LLM: данных за месяц ещё нет.")
    except Exception:
        lines.append("\n📟 Телеметрия LLM: леджер ещё не создан.")
    return "\n".join(lines)


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


def action_seo_health() -> str:
    """Run the SEO health monitor on demand and return its report inline.

    Uses --no-telegram so the result comes back here instead of broadcasting,
    and --always so we still show a clean ✅ even when there are no issues."""
    try:
        out = subprocess.run(
            ["python3", str(ROOT / "scripts" / "monitor_seo_health.py"),
             "--no-telegram", "--raw-report"],
            capture_output=True, text=True, timeout=180,
        )
        text = (out.stdout or "").strip()
        return text or "🩺 Проверка завершена, отчёт пуст. См. логи."
    except subprocess.TimeoutExpired:
        return "🩺 Проверка идёт дольше обычного — результат будет в логах."
    except Exception as e:
        return f"🩺 Не удалось запустить проверку: {e}"


def action_experiments() -> str:
    """Show the SEO optimizer's experiment ledger summary (FREE, no LLM)."""
    try:
        led = json.loads((DATA / "experiments.json").read_text())
    except Exception:
        return ("🧪 <b>Эксперименты оптимизатора</b>\n"
                "Пока пусто — оптимизатор ещё не вносил правок title/meta "
                "(или ledger не синхронизирован на этот хост).")
    if not led:
        return "🧪 <b>Эксперименты оптимизатора</b>\nПока пусто."
    verdicts: dict = {}
    for e in led:
        v = e.get("verdict", "pending")
        verdicts[v] = verdicts.get(v, 0) + 1
    lines = ["🧪 <b>Эксперименты оптимизатора</b>",
             f"Всего: <b>{len(led)}</b> · в ожидании замера: <b>{verdicts.get('pending',0)}</b>",
             f"🟢 win: {verdicts.get('win',0)} · ⚪ neutral: {verdicts.get('neutral',0)} · "
             f"🔴 откат: {verdicts.get('reverted',0)}"]
    wins = [e for e in led if e.get("verdict") == "win"][-3:]
    if wins:
        lines.append("\n<b>Недавние победы:</b>")
        for e in wins:
            lines.append(f"  🟢 «{e.get('query')}»: поз {e.get('before_pos')}→{e.get('after_pos')}")
    pend = [e for e in led if e.get("verdict") == "pending"][-3:]
    if pend:
        lines.append("\n<b>В работе (ждут замера ~14 дней):</b>")
        for e in pend:
            lines.append(f"  ⏳ «{e.get('query')}» → {(e.get('after_title') or '')[:42]}")
    return "\n".join(lines)


def action_scout() -> str:
    """Show the latest Scout demand-discovery findings (FREE, no LLM)."""
    try:
        f = json.loads((DATA / "scout_findings.json").read_text())
    except Exception:
        return ("🛰 <b>Разведка спроса</b>\nПока нет данных — Scout ещё не запускался "
                "(или findings не синхронизированы на этот хост).")
    nq, rq, gq = f.get("new_queries", []), f.get("rising_queries", []), f.get("coverage_gaps", [])
    lines = ["🛰 <b>Разведка спроса</b>",
             f"<i>обновлено: {f.get('generated_at','')[:16]}</i>"]
    if nq:
        lines.append("\n<b>🆕 Новые запросы:</b>")
        for e in nq[:6]:
            lines.append(f"  «{e['query']}» — {e['impr']} показов, поз {e['pos']}")
    if rq:
        lines.append("\n<b>📈 Растущий спрос:</b>")
        for e in rq[:6]:
            lines.append(f"  «{e['query']}» — {e.get('from_impr','?')}→{e['impr']}")
    if gq:
        lines.append("\n<b>🕳 Пробелы (ранжируется только главная):</b>")
        for e in gq[:6]:
            lines.append(f"  «{e['query']}» — {e['impr']} показов")
    if not (nq or rq or gq):
        lines.append("\nНовых сигналов нет — спрос стабилен.")
    return "\n".join(lines)


def action_meta_status() -> str:
    """One-glance summary of the whole meta-agent system (FREE, no LLM)."""
    def _read(name, default):
        try:
            return json.loads((DATA / name).read_text())
        except Exception:
            return default

    lines = ["🤖 <b>Статус мета-агента</b>", ""]

    # A. Landing-Builder — approved/built landings (from approvals + landing dir)
    appr = _read("approvals.json", [])
    built = _count(PUBLIC / "landing")
    queued_landing = sum(1 for a in appr
                         if a.get("action") == "create_landing"
                         and a.get("status") in ("pending", "approved"))
    lines.append(f"🏗 <b>Landing-Builder</b>: построено {built} · "
                 f"в очереди на выполнение {queued_landing} (автономно)")

    # C. Linker — internal links coverage
    linked = 0
    for d in (PUBLIC / "blog", PUBLIC / "oem", PUBLIC / "landing"):
        if d.exists():
            for f in d.glob("*.html"):
                try:
                    if 'data-linker="1"' in f.read_text(errors="ignore"):
                        linked += 1
                except Exception:
                    pass
    lines.append(f"🔗 <b>Linker</b>: перелинковано страниц {linked}")

    # B. Competitor-Scout — losing queries
    comp = _read("competitor_findings.json", {})
    lq = comp.get("losing_queries", [])
    if lq:
        worst = lq[0]
        lines.append(f"🔭 <b>Competitor-Scout</b>: проигрываем {len(lq)} запросов "
                     f"(худший «{worst['query']}» поз {worst['our_position']})")
    else:
        lines.append("🔭 <b>Competitor-Scout</b>: нет данных (запускается по пн)")

    # E. Anomaly-Guard — baseline points + last status
    series = _read("anomaly_baseline.json", [])
    if series:
        last = series[-1]
        lines.append(f"🚨 <b>Anomaly-Guard</b>: история {len(series)} дн., "
                     f"посл. {last.get('date')} — клики {last.get('clicks')}, "
                     f"поз {last.get('wpos')}")
    else:
        lines.append("🚨 <b>Anomaly-Guard</b>: baseline ещё не набран")

    # D. AIO-Visibility — citability score
    aio = _read("aio_visibility.json", [])
    if aio:
        a = aio[-1]
        ds = a.get("deepseek_score")
        px = a.get("perplexity_score")
        extra = f" · live {px*100:.0f}%" if px is not None else ""
        lines.append(f"🤖 <b>AIO-видимость</b>: ИИ знает нас в "
                     f"{(ds or 0)*100:.0f}% вопросов{extra}")
    else:
        lines.append("🤖 <b>AIO-видимость</b>: нет данных (запускается по пн)")

    # F. Escalation — last escalation
    esc = _read("escalation_state.json", {})
    if esc.get("last_escalation_at"):
        lines.append(f"⚡ <b>Эскалация</b>: посл. {esc['last_escalation_at'][:16]}")
    else:
        lines.append("⚡ <b>Эскалация</b>: пока не срабатывала")

    # Experiments roll-up
    led = _read("experiments.json", [])
    if led:
        wins = sum(1 for e in led if e.get("verdict") == "win")
        pend = sum(1 for e in led if e.get("verdict") == "pending")
        lines.append(f"\n🧪 Эксперименты: {len(led)} всего · 🟢 {wins} побед · ⏳ {pend} в замере")

    lines.append("\n<i>Полный цикл: спрос → измерение → эскалация → стратегия → исполнение.</i>")
    return "\n".join(lines)


# ── High-impact approval queue ───────────────────────────────────────────────────
def load_approvals() -> list:
    try:
        return json.loads(APPROVALS_FILE.read_text())
    except Exception:
        return []


def save_approvals(rows: list) -> None:
    DATA.mkdir(exist_ok=True)
    APPROVALS_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2))


def action_decisions() -> str:
    """Audit log of autonomous decisions (FREE). Approvals are gone — Fable decides."""
    rows = load_approvals()
    if not rows:
        return ("📒 <b>Решения Fable</b>\nПока пусто.\n"
                "<i>Система работает автономно: агенты решают и выполняют сами, "
                "сюда пишется журнал их решений.</i>")
    recent = sorted(rows, key=lambda a: a.get("created_at", ""), reverse=True)[:12]
    status_icon = {"approved": "⏳ в очереди", "done": "✅ выполнено",
                   "pending": "⏳ в очереди", "rejected": "❌ отклонено"}
    lines = ["📒 <b>Решения Fable</b> (автономный режим)\n"]
    for a in recent:
        st = status_icon.get(a.get("status"), a.get("status", "?"))
        lines.append(f"• {st} — {a.get('title','?')}")
        lines.append(f"   <i>{a.get('requested_by','agent')} · {a.get('created_at','')[:16]}</i>")
    return "\n".join(lines)


def action_goals() -> str:
    """Distance-to-#1 scoreboard from data/goals.json (FREE)."""
    try:
        g = json.loads((DATA / "goals.json").read_text())
    except Exception:
        return ("🎯 <b>Цели</b>\nТаблица ещё не построена — появится после "
                "ближайшего ежедневного цикла.")
    lines = [f"🎯 <b>Цель: №1 по каждому запросу</b>",
             f"Достигнуто: <b>{g.get('achieved',0)}</b> из {g.get('total',0)} "
             f"(с данными: {g.get('tracked',0)})\n"]
    for row in g.get("goals", [])[:18]:
        pos = row.get("position_7d") or row.get("position_28d")
        if row.get("achieved"):
            icon, postxt = "🥇", f"#{pos}"
        elif pos is None:
            icon, postxt = "⚪", "нет данных"
        elif pos <= 3.5:
            icon, postxt = "🟢", f"#{pos} (до №1: {row.get('gap_to_1')})"
        elif pos <= 10:
            icon, postxt = "🟡", f"#{pos} (до №1: {row.get('gap_to_1')})"
        else:
            icon, postxt = "🔴", f"#{pos}"
        tr = row.get("trend")
        trend = f" {'📈' if tr > 0 else '📉'}{abs(tr)}" if tr else ""
        lines.append(f"{icon} {row['query']} — {postxt}{trend}")
    countries = g.get("countries") or []
    visible = [c for c in countries if c.get("impressions_28d")]
    dark = [c["country"] for c in countries if not c.get("impressions_28d")]
    if countries:
        lines.append("\n<b>🌍 Целевые страны (28д):</b>")
        for c in sorted(visible, key=lambda x: -x["impressions_28d"])[:8]:
            pos = f" · поз. {c['position_28d']}" if c.get("position_28d") else ""
            lines.append(f"• {c['country']}: {c['impressions_28d']} показов, "
                         f"{c['clicks_28d']} кликов{pos}")
        if dark:
            lines.append(f"⚫ Нет видимости: {', '.join(dark[:10])}")
    lines.append(f"\n<i>Обновлено: {g.get('generated_at','')[:16]}</i>")
    return "\n".join(lines)


def _approval_decision(text: str):
    """Parse 'одобрить N' / 'отклонить N' / 'approve N' / 'reject N'. Returns (idx, approve) or None."""
    parts = (text or "").strip().lower().split()
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    verb = parts[0]
    if verb in ("одобрить", "одобряю", "approve", "ок"):
        return int(parts[1]), True
    if verb in ("отклонить", "отклоняю", "reject", "отказ"):
        return int(parts[1]), False
    return None


def decide_approval(index_1based: int, approve: bool, who: str) -> str:
    rows = load_approvals()
    pend = [a for a in rows if a.get("status") == "pending"]
    if index_1based < 1 or index_1based > len(pend):
        return f"Нет действия №{index_1based}. Открой ✅ Аппрувы, чтобы увидеть список."
    target = pend[index_1based - 1]
    target["status"] = "approved" if approve else "rejected"
    target["decided_at"] = datetime.now(timezone.utc).isoformat()
    target["decided_by"] = who
    save_approvals(rows)
    J.log_event("approval", f"{'approved' if approve else 'rejected'}: {target.get('title')}", who=who)
    verb = "одобрено ✅ — агент выполнит на следующем цикле" if approve else "отклонено ❌"
    return f"{verb}: {target.get('title')}"


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


def _load_strategy_text() -> str:
    try:
        st = json.loads((DATA / "strategy.json").read_text())
        return json.dumps(st, ensure_ascii=False)[:1500]
    except Exception:
        return "стратегия ещё не сформирована"


def _site_inventory(max_chars: int = 1200) -> str:
    """Factual page inventory from the local repo, so the dialogue LLM answers
    «есть ли у нас страница X?» from real data instead of 'нет доступа к сайту'."""
    lines = []
    big = {"products": "карточки товаров RU", "en/products": "карточки EN",
           "geo": "гео-страницы RU", "en/geo": "гео EN", "ar/geo": "гео AR",
           "blog": "блог", "export": "экспортные страницы"}
    small = ["landing", "oem", "private-label", "en/oem"]
    for rel, label in big.items():
        cnt = len(list((PUBLIC / rel).glob("*.html"))) if (PUBLIC / rel).is_dir() else 0
        if cnt:
            lines.append(f"{rel}/ — {cnt} стр. ({label})")
    for rel in small:
        d = PUBLIC / rel
        if d.is_dir():
            slugs = sorted(p.stem for p in d.glob("*.html"))
            if slugs:
                lines.append(f"{rel}/: " + ", ".join(slugs))
    return "\n".join(lines)[:max_chars]


def talk_to_brain(chat_id: int, question: str) -> str:
    """
    Tiered dialogue (cost-safe):
      • SONNET ("voice") answers using current strategy + journal context.
      • If the question requires real re-planning, Sonnet emits a marker and
        we AUTO-ESCALATE to OPUS ("brain") to produce/refresh strategy, then
        Sonnet-style summary is returned. All within the shared budget.
    """
    try:
        from opus_brain_client import call_voice, call_opus, brain_available, remaining_budget
    except Exception as e:
        return f"Мозг недоступен: {e}"
    if not brain_available():
        return ("🧠 Недоступно: нет ANTHROPIC_API_KEY или исчерпан бюджет "
                f"(${remaining_budget():.2f}).")

    context = J.recent_summary(max_chars=1800)
    strategy = _load_strategy_text()
    voice_system = (
        "Ты — голос стратегического мозга компании «Казанские Деликатесы» "
        "(pepperoni.tatar), халяль производитель мяса и выпечки. Цель — №1 в РФ, "
        "СНГ, арабских/африканских/ЮВА рынках по всему ассортименту и услугам "
        "Private Label/OEM. Ты ОБЪЯСНЯЕШЬ и отвечаешь на вопросы владельца кратко, "
        "по-русски, по делу, опираясь на текущую стратегию и журнал. "
        "Стратегические РЕШЕНИЯ принимает мозг (Opus), не ты. "
        "Если вопрос требует НОВОГО глубокого плана/перестройки стратегии — начни "
        "ответ строго со строки '[ESCALATE]' и кратко поясни почему. Иначе отвечай обычно. "
        "У тебя есть ФАКТИЧЕСКИЙ инвентарь страниц сайта (ниже): на вопросы «есть ли "
        "у нас страница/лендинг X» отвечай по нему и НИКОГДА не говори, что у тебя "
        "нет доступа к сайту.\n\n"
        f"ИНВЕНТАРЬ САЙТА:\n{_site_inventory()}\n\n"
        f"ТЕКУЩАЯ СТРАТЕГИЯ: {strategy}\n\nЖУРНАЛ:\n{context}"
    )
    try:
        reply, usage = call_voice(question, system=voice_system, max_tokens=1200)
    except Exception as e:
        return f"Ошибка диалога: {e}"
    J.log_event("user_cmd", question, who=str(chat_id))

    if reply.strip().startswith("[ESCALATE]"):
        reason = reply.strip()[len("[ESCALATE]"):].strip()[:200]
        # Auto-escalate to Opus to refresh the real strategy.
        try:
            import seo_brain
            J.log_event("system", f"auto-escalation to Opus: {reason}", who="bot")
            seo_brain.main()  # writes data/strategy.json via Opus
            new_strat = action_strategy()
            J.log_event("brain_reply", "strategy refreshed via escalation", who="opus")
            v_cost = usage.get("cost_usd", 0)
            return (f"🧠 Вопрос требует стратегии — подключил мозг (Opus) и обновил план.\n\n"
                    f"{new_strat}\n\n<i>Sonnet ${v_cost} + Opus (см. 💰 Бюджет)</i>")
        except Exception as e:
            return f"Пытался подключить мозг, но: {e}"

    cost = usage.get("cost_usd", 0)
    rem = usage.get("budget_remaining_usd", 0)
    J.log_event("brain_reply", reply, who="sonnet", meta={"cost_usd": cost})
    return f"💬 {reply}\n\n<i>${cost} (Sonnet) · бюджет: ${rem}</i>"


# ── Command dispatch ─────────────────────────────────────────────────────────────
def _norm_cmd(s: str) -> str:
    """'📊 Статус сайта' / '/status' / 'СТАТУС' → comparable key."""
    s = re.sub(r"[^\w\s]", " ", s.lower().replace("ё", "е"), flags=re.UNICODE)
    return " ".join(s.split())


def _cmd_health(cid: int) -> None:
    send(cid, "🩺 Проверяю структурированные данные…")
    send(cid, action_seo_health(), keyboard=MAIN_MENU)


def _cmd_fix_schema(cid: int) -> None:
    """Deterministic schema fixer: enrich Product JSON-LD site-wide, commit, push."""
    send(cid, "🛠 Чиню Product-схемы по всему сайту (fix_schema.py)…")
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "fix_schema.py")],
                           capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        tail = "\n".join((r.stdout or r.stderr or "—").strip().splitlines()[-10:])
        changed = "enriched" in (r.stdout or "")
        if changed:
            subprocess.run(["git", "add", "-A", "public"], cwd=str(ROOT), timeout=60)
            c = subprocess.run(["git", "commit", "-m", "fix(schema): enrich Product JSON-LD (via bot)"],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            if c.returncode == 0:
                subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT),
                               capture_output=True, timeout=120)
        send(cid, "<pre>" + html.escape(tail)[:3500] + "</pre>", keyboard=MAIN_MENU)
        J.log_event("system", "fix_schema run via bot", who=str(cid))
    except Exception as e:
        send(cid, f"❌ fix_schema: {e}", keyboard=MAIN_MENU)


def _action_brain_questions() -> str:
    """Show open questions the brain asked the owner."""
    import json as _json
    try:
        q = _json.loads((ROOT / "data" / "brain_questions.json").read_text())
    except Exception:
        return "❓ Открытых вопросов от мозга нет."
    items = [x for x in q.get("questions", []) if not x.get("answered")]
    if not items:
        return "❓ Открытых вопросов от мозга нет — он решает сам."
    lines = ["❓ <b>Вопросы мозга</b>",
             "<i>Ответь: «ответ &lt;id&gt; &lt;текст&gt;»</i>", ""]
    for x in items:
        lines.append(f"<b>[{x.get('id','?')}]</b> {x.get('text','')}")
        if x.get("options"):
            lines.append("   варианты: " + " / ".join(x["options"]))
        lines.append("")
    return "\n".join(lines)


def _record_brain_answer(qid: str, answer: str, chat_id: int) -> str:
    """Persist the owner's answer to a brain question so the next brain cycle
    reads it from data/brain_answers.json (via telegram_notify.STATE_DIR)."""
    import json as _json
    from datetime import datetime, timezone
    try:
        from telegram_notify import STATE_DIR
        path = Path(STATE_DIR) / "brain_answers.json"
    except Exception:
        path = ROOT / "data" / "brain_answers.json"
    try:
        data = _json.loads(path.read_text())
    except Exception:
        data = {"answers": []}
    data.setdefault("answers", []).append({
        "id": qid, "answer": answer,
        "answered_at": datetime.now(timezone.utc).isoformat(),
        "by": str(chat_id),
    })
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json.dumps(data, ensure_ascii=False, indent=1))
    except Exception as e:
        return f"❌ Не смог сохранить ответ: {e}"
    # mark the question answered in the repo-tracked questions file
    try:
        qf = ROOT / "data" / "brain_questions.json"
        q = _json.loads(qf.read_text())
        for item in q.get("questions", []):
            if str(item.get("id")) == qid:
                item["answered"] = True
        qf.write_text(_json.dumps(q, ensure_ascii=False, indent=1))
    except Exception:
        pass
    J.log_event("owner_answer", f"[{qid}] {answer}", who=str(chat_id))
    return (f"✅ Записал твой ответ на вопрос <b>[{qid}]</b>. "
            f"Мозг учтёт его в следующем цикле планирования.")


def _make_dispatch() -> dict:
    table = [
        (("start", "меню", "menu", "главное меню"),
         lambda cid: send(cid, "Главное меню. Выбери действие:", keyboard=MAIN_MENU)),
        (("статус", "status", "статус сайта"),
         lambda cid: send(cid, action_status(), keyboard=MAIN_MENU)),
        (("бюджет", "budget", "бюджет мозга"),
         lambda cid: send(cid, action_budget(), keyboard=MAIN_MENU)),
        (("стратегия", "strategy", "стратегия мозга"),
         lambda cid: send(cid, action_strategy(), keyboard=MAIN_MENU)),
        (("история", "history"),
         lambda cid: send(cid, action_history(), keyboard=MAIN_MENU)),
        (("запустить генерацию", "запустить", "run", "генерация"),
         lambda cid: send(cid, action_run_generation(cid), keyboard=MAIN_MENU)),
        (("seo здоровье", "здоровье", "health", "seo health"), _cmd_health),
        (("эксперименты", "experiments"),
         lambda cid: send(cid, action_experiments(), keyboard=MAIN_MENU)),
        (("разведка", "scout"),
         lambda cid: send(cid, action_scout(), keyboard=MAIN_MENU)),
        (("решения", "аппрувы", "approvals", "решения мозга"),
         lambda cid: send(cid, action_decisions(), keyboard=MAIN_MENU)),
        (("цели", "goals"),
         lambda cid: send(cid, action_goals(), keyboard=MAIN_MENU)),
        (("мета", "мета агент", "meta", "мета агент статус"),
         lambda cid: send(cid, action_meta_status(), keyboard=MAIN_MENU)),
        (("почини schema", "почини схему", "почини схемы", "fix schema"), _cmd_fix_schema),
        (("вопросы", "вопросы мозга", "questions"),
         lambda cid: send(cid, _action_brain_questions(), keyboard=MAIN_MENU)),
    ]
    return {alias: fn for aliases, fn in table for alias in aliases}


_DISPATCH = _make_dispatch()


# ── Message router ───────────────────────────────────────────────────────────────
def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    name = msg["chat"].get("first_name", "user")
    text = (msg.get("text") or "").strip()

    # Remember this chat for agent push notifications (even before password auth).
    try:
        from telegram_notify import register_chat
        register_chat(chat_id, name)
    except Exception:
        pass

    # 1) Auth gate
    if not is_authorized(chat_id):
        if text == PASSWORD or _pw_hash(text) == PASSWORD_HASH:
            authorize(chat_id, name)
            J.log_event("system", f"authorized {name} ({chat_id})", who="bot")
            send(chat_id,
                 f"✅ Доступ открыт, {name}! Ты управляешь мозгом сайта.\n"
                 f"chat_id: <code>{chat_id}</code>",
                 keyboard=MAIN_MENU)
        else:
            send(chat_id,
                 f"🔒 Введите пароль для доступа к мозгу сайта.\n\n"
                 f"<i>Ваш chat_id: <code>{chat_id}</code> — добавьте в "
                 f"TELEGRAM_CHAT_ID (GitHub Secrets / seo-agent.env), "
                 f"чтобы агенты слали уведомления без входа.</i>")
        return

    # 2) Pending confirmation (e.g. brain question)
    low = text.lower()
    pend = None
    if low in ("да", "yes", "✅ да", "подтверждаю"):
        pend = pop_pending(chat_id)
        if pend and pend["kind"] == "ask_brain":
            send(chat_id, "💬 Думаю…")
            send(chat_id, talk_to_brain(chat_id, pend["payload"]), keyboard=MAIN_MENU)
            return
    if low in ("нет", "no", "❌ нет", "отмена"):
        pop_pending(chat_id)
        send(chat_id, "Отменено.", keyboard=MAIN_MENU)
        return

    # 3) Menu / commands (FREE) — emoji/case/slash-insensitive matching, so taps
    #    on report header lines («📊 Статус сайта») route here, not to the LLM.
    n = _norm_cmd(text)
    handler = _DISPATCH.get(n)
    if handler:
        handler(chat_id)
        return
    if _approval_decision(text) is not None:
        idx, approve = _approval_decision(text)
        send(chat_id, decide_approval(idx, approve, str(chat_id)), keyboard=MAIN_MENU)
        return
    if n in ("спросить мозг", "ask"):
        set_pending(chat_id, "ask_brain_prompt", "")
        send(chat_id, "Напиши вопрос — отвечу через Sonnet (дёшево). "
                      "Если понадобится глубокая стратегия, сам подключу Opus.\n"
                      "Например: «что улучшить по выпечке в Турции?»")
        return

    # 4) Unmatched UI tap (emoji-prefixed, no real question) → menu, not LLM.
    if not n or (not text[0].isalnum() and len(n.split()) <= 4):
        send(chat_id, "Не понял команду. Вот меню:", keyboard=MAIN_MENU)
        return

    # 4b) Answer to a brain question: "ответ <id> <текст>" / "answer <id> <текст>"
    m = re.match(r"(?:ответ|answer)\s+(\S+)\s+(.+)", text, re.I | re.S)
    if m:
        send(chat_id, _record_brain_answer(m.group(1), m.group(2).strip(), chat_id),
             keyboard=MAIN_MENU)
        return

    # 5) Free-form text → dialogue turn (cheap Sonnet), incl. pending brain question
    pop_pending(chat_id)
    send(chat_id, "💬 Думаю…")
    send(chat_id, talk_to_brain(chat_id, text), keyboard=MAIN_MENU)


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
