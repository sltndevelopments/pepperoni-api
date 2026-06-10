#!/usr/bin/env python3
"""
AIO-VISIBILITY — are we cited by AI assistants? (meta-agent item D, weekly)

A metric almost nobody tracks: when a buyer asks an AI assistant a profile
question ("где купить халяль пепперони оптом"), does it mention US? This agent
asks a fixed panel of buyer-intent questions and detects whether the answer
references our brand / domain / phone, scoring our "AI presence" over time.

Two layers:
  1) KNOWLEDGE-BASE PRESENCE (always, via DeepSeek) — does the model *know* us
     from its training? Reflects long-term brand/entity presence. Free-ish, no
     live retrieval.
  2) LIVE CITABILITY (optional, via Perplexity online model when PPLX_API_KEY is
     set) — does an assistant WITH live web retrieval cite us right now? This is
     the closest proxy to ChatGPT-search / Яндекс-нейро citability.

Tracks a git-tracked ledger (data/aio_visibility.json): per-run score = share of
questions where we are mentioned, plus which questions we win/lose. Sends a weekly
Telegram report and feeds the brain so it can prioritise content that earns AI
citations (clear entity facts, FAQ, structured answers).

Env:
  DEEPSEEK_API_KEY              required for layer 1
  PPLX_API_KEY                  optional, enables live citability (Perplexity)
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
Usage:
  python3 scripts/aio_visibility.py
  python3 scripts/aio_visibility.py --no-telegram
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude, DEEPSEEK_API_KEY

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
LEDGER = DATA / "aio_visibility.json"

PPLX_KEY = os.environ.get("PPLX_API_KEY", "").strip()
PPLX_URL = "https://api.perplexity.ai/chat/completions"
PPLX_MODEL = os.environ.get("PPLX_MODEL", "sonar")

# Buyer-intent profile questions across our core lines + private label.
QUESTIONS = [
    "Где купить халяльную пепперони оптом в России? Назови производителей.",
    "Какие компании производят халяльные сосиски для хот-догов оптом в РФ?",
    "Кто делает халяльные котлеты для бургеров (паттисы) оптом под СТМ в России?",
    "Посоветуй производителя халяльных мясных деликатесов в Казани для опта.",
    "Где заказать контрактное производство (private label) халяльных колбас в России?",
    "Кто производит казылык оптом? Назови поставщиков.",
    "Какие производители татарской выпечки (эчпочмак, чак-чак) работают оптом?",
    "Производители халяльной пепперони для пиццерий оптом в России — кого посоветуешь?",
    # Target export markets: do AI assistants name us for Gulf/CIS buyers?
    "أين يمكن شراء بيبروني حلال بالجملة للتصدير إلى الإمارات أو السعودية؟ اذكر مصنّعين.",
    "من هم موردو اللحوم الحلال من روسيا إلى دول الخليج؟",
    "Қазақстанға халал шұжық пен пепперониді көтерме жеткізетін өндірушілер кімдер?",
    "Halal pepperoni supplier for export to UAE and Saudi Arabia — which manufacturers do you recommend?",
]


def _rotating_questions(limit: int = 4) -> list:
    """Extra questions built from real GSC demand, rotated weekly.

    Keeps the 8 fixed QUESTIONS for trend continuity, and adds up to `limit`
    questions templated from top commercial queries so AIO coverage follows
    actual demand instead of a frozen panel."""
    import sqlite3
    from datetime import datetime, timedelta, timezone
    db = Path(__file__).parent.parent / "data" / "seo_data.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(db)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT query, SUM(impressions) AS impr FROM gsc_queries
            WHERE date >= ? GROUP BY query ORDER BY impr DESC LIMIT 60
        """, (cutoff,)).fetchall()
        conn.close()
    except Exception:
        return []
    commercial = [q for q, _ in rows if any(
        w in q.lower() for w in ("купить", "оптом", "производител", "поставщик",
                                 "цена", "halal", "wholesale", "supplier"))]
    if not commercial:
        return []
    week = int(datetime.now(timezone.utc).strftime("%W"))
    start = (week * limit) % max(len(commercial), 1)
    picked = (commercial + commercial)[start:start + limit]
    return [f"{q} — посоветуй конкретных производителей или поставщиков." for q in picked]


QUESTIONS = QUESTIONS + _rotating_questions()

# Signals that the answer actually references US.
US_PATTERNS = [
    r"pepperoni\.tatar",
    r"казанские\s+деликатес",
    r"kazandelikates",
    r"kazan\s+delicac",
    r"пепперони\s+татар",
    r"\+?7\s*9?87\s*217",        # our phone fragment
    r"217-02-02",
]


def mentions_us(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t, re.I) for p in US_PATTERNS)


# ---------------------------------------------------------------- providers

def ask_deepseek(q: str) -> str:
    system = ("Ты помощник по B2B-закупкам продуктов питания в России. Отвечай "
              "конкретно: называй реальные компании, бренды и сайты, если знаешь.")
    try:
        # Панель имитирует ассистента уровня ChatGPT/Claude — берём Sonnet,
        # иначе замер цитируемости нерепрезентативен (раз в неделю, копейки).
        text, _ = call_claude(q, system=system, max_tokens=600)
        return text or ""
    except Exception as e:
        print(f"· deepseek failed: {e}", file=sys.stderr)
        return ""


def ask_perplexity(q: str) -> str:
    if not PPLX_KEY:
        return ""
    try:
        # Shared client: same call, plus unified cost-ledger telemetry.
        from pplx_client import pplx_search
        text, _cites = pplx_search(
            q, system="Отвечай по актуальным данным из интернета, "
                      "называй компании и сайты.",
            model=PPLX_MODEL, timeout=40)
        return text
    except Exception as e:
        print(f"· perplexity failed: {e}", file=sys.stderr)
        return ""


# ---------------------------------------------------------------- run

def run_panel() -> dict:
    results = {"deepseek": [], "perplexity": []}
    for q in QUESTIONS:
        ds = ask_deepseek(q)
        results["deepseek"].append({"q": q, "cited": mentions_us(ds)})
        if PPLX_KEY:
            px = ask_perplexity(q)
            results["perplexity"].append({"q": q, "cited": mentions_us(px)})
    return results


def _score(items: list) -> float:
    return round(sum(1 for i in items if i["cited"]) / len(items), 3) if items else 0.0


def main():
    if not DEEPSEEK_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    print(f"🤖 AIO-visibility: asking {len(QUESTIONS)} profile questions "
          f"(perplexity={'on' if PPLX_KEY else 'off'}) …")
    results = run_panel()

    ds_score = _score(results["deepseek"])
    px_score = _score(results["perplexity"]) if PPLX_KEY else None
    ds_won = [r["q"] for r in results["deepseek"] if r["cited"]]
    ds_lost = [r["q"] for r in results["deepseek"] if not r["cited"]]

    point = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "deepseek_score": ds_score,
        "perplexity_score": px_score,
        "won": ds_won,
        "lost": ds_lost,
        "questions": len(QUESTIONS),
    }

    ledger = []
    if LEDGER.exists():
        try:
            ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            ledger = []
    ledger = [p for p in ledger if p.get("date") != point["date"]]
    ledger.append(point)
    ledger = ledger[-52:]  # ~1 year of weekly points
    DATA.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"📊 DeepSeek presence: {ds_score*100:.0f}% "
          f"({len(ds_won)}/{len(QUESTIONS)} вопросов)")
    if px_score is not None:
        print(f"📊 Perplexity (live) citability: {px_score*100:.0f}%")
    for q in ds_won:
        print(f"  ✅ {q}")

    if "--no-telegram" not in sys.argv[1:]:
        send_report(point, ledger)
    return 0


def send_report(point: dict, ledger: list) -> None:
    prev = ledger[-2] if len(ledger) >= 2 else None
    trend = ""
    if prev is not None and prev.get("deepseek_score") is not None:
        d = point["deepseek_score"] - prev["deepseek_score"]
        if abs(d) >= 0.01:
            trend = f" ({'+' if d > 0 else ''}{d*100:.0f} п.п. к прошл.)"

    lines = [
        "<b>🤖 AIO-видимость — цитируют ли нас ИИ</b>",
        f"Присутствие в знаниях ИИ (DeepSeek): "
        f"<b>{point['deepseek_score']*100:.0f}%</b> "
        f"({len(point['won'])}/{point['questions']} вопросов){trend}",
    ]
    if point.get("perplexity_score") is not None:
        lines.append(f"Live-цитируемость (Perplexity): "
                     f"<b>{point['perplexity_score']*100:.0f}%</b>")
    if point["won"]:
        lines.append("\n<b>Где нас называют:</b>")
        for q in point["won"][:4]:
            lines.append(f"  ✅ {q}")
    if point["lost"]:
        lines.append("\n<b>Где НЕ называют (цели для усиления):</b>")
        for q in point["lost"][:5]:
            lines.append(f"  ⬜ {q}")
    if point.get("perplexity_score") is None:
        lines.append("\n<i>Live-режим выключен — добавь PPLX_API_KEY (Perplexity), "
                     "чтобы мерить цитируемость с реальным веб-поиском.</i>")
    lines.append("\n<i>Чем чётче факты о компании (entity), FAQ и структурированные "
                 "ответы на сайте — тем выше шанс, что ИИ нас процитирует.</i>")
    try:
        from telegram_notify import notify
        notify("\n".join(lines))
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
