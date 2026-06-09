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
        "ответ строго со строки '[ESCALATE]' и кратко поясни почему. Иначе отвечай обычно.\n\n"
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
    elif text in ("🩺 SEO здоровье", "/health", "здоровье"):
        send(chat_id, "🩺 Проверяю структурированные данные…")
        send(chat_id, action_seo_health(), keyboard=MAIN_MENU)
    elif text in ("🧪 Эксперименты", "/experiments", "эксперименты"):
        send(chat_id, action_experiments(), keyboard=MAIN_MENU)
    elif text in ("🛰 Разведка", "/scout", "разведка"):
        send(chat_id, action_scout(), keyboard=MAIN_MENU)
    elif text in ("📒 Решения", "✅ Аппрувы", "/approvals", "аппрувы", "решения"):
        send(chat_id, action_decisions(), keyboard=MAIN_MENU)
    elif text in ("🎯 Цели", "/goals", "цели"):
        send(chat_id, action_goals(), keyboard=MAIN_MENU)
    elif text in ("🤖 Мета-агент", "/meta", "мета", "мета-агент"):
        send(chat_id, action_meta_status(), keyboard=MAIN_MENU)
    elif _approval_decision(text) is not None:
        idx, approve = _approval_decision(text)
        send(chat_id, decide_approval(idx, approve, str(chat_id)), keyboard=MAIN_MENU)
    elif text in ("🧠 Спросить мозг", "/ask"):
        set_pending(chat_id, "ask_brain_prompt", "")
        send(chat_id, "Напиши вопрос — отвечу через Sonnet (дёшево). "
                      "Если понадобится глубокая стратегия, сам подключу Opus.\n"
                      "Например: «что улучшить по выпечке в Турции?»")
    else:
        # If we're waiting for a brain question, treat this text as the question
        try:
            d = json.loads(PENDING_FILE.read_text())
        except Exception:
            d = {}
        if d.get(str(chat_id), {}).get("kind") == "ask_brain_prompt":
            pop_pending(chat_id)
            send(chat_id, "💬 Думаю…")
            send(chat_id, talk_to_brain(chat_id, text), keyboard=MAIN_MENU)
        else:
            # Free-form text from an authorized user → treat as a dialogue turn (cheap Sonnet)
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
