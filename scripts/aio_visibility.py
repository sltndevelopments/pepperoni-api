#!/usr/bin/env python3
"""
AIO-VISIBILITY — are we cited by AI assistants? (meta-agent item D, weekly)

A metric almost nobody tracks: when a buyer asks an AI assistant a profile
question ("где купить халяль пепперони оптом"), does it mention US? This agent
asks a fixed panel of buyer-intent questions and detects whether the answer
references our brand / domain / phone, scoring our "AI presence" over time.

Layers:
  1) KNOWLEDGE-BASE PRESENCE (always, via Claude Sonnet) — does the model *know*
     us from its training? Reflects long-term brand/entity presence.
  2) LIVE CITABILITY (optional, via Perplexity online model when PPLX_API_KEY is
     set) — does an assistant WITH live web retrieval cite us right now?
  3) ChatGPT presence (optional, OPENAI_API_KEY) — gpt-4o-mini, knowledge base.
  4) Gemini presence (optional, GEMINI_API_KEY) — gemini-1.5-flash, free tier.

Tracks a git-tracked ledger (data/aio_visibility.json): per-run score = share of
questions where we are mentioned, plus which questions we win/lose. Sends a weekly
Telegram report and feeds the brain so it can prioritise content that earns AI
citations (clear entity facts, FAQ, structured answers).

Env:
  ANTHROPIC_API_KEY             required for layer 1 (Claude)
  PPLX_API_KEY                  optional, enables live citability (Perplexity)
  OPENAI_API_KEY                optional, enables ChatGPT presence check
  GEMINI_API_KEY                optional, enables Gemini presence check
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
from claude_client import call_claude, ANTHROPIC_API_KEY

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
LEDGER = DATA / "aio_visibility.json"

PPLX_KEY = os.environ.get("PPLX_API_KEY", "").strip()
PPLX_URL = "https://api.perplexity.ai/chat/completions"
PPLX_MODEL = os.environ.get("PPLX_MODEL", "sonar")

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = "gpt-4o-mini"

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-1.5-flash"

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
    """Layer 1: Claude Sonnet knowledge-base presence (named 'deepseek' for ledger compat)."""
    system = ("Ты помощник по B2B-закупкам продуктов питания в России. Отвечай "
              "конкретно: называй реальные компании, бренды и сайты, если знаешь.")
    try:
        text, _ = call_claude(q, system=system, max_tokens=600)
        return text or ""
    except Exception as e:
        print(f"· claude failed: {e}", file=sys.stderr)
        return ""


def ask_chatgpt(q: str) -> str:
    """Layer 3: ChatGPT (gpt-4o-mini) knowledge-base presence. Skip if no key."""
    if not OPENAI_KEY:
        return ""
    try:
        import urllib.request as _ur
        payload = json.dumps({
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are a B2B food procurement assistant. Answer concretely: "
                    "name real companies, brands and websites if you know them.")},
                {"role": "user", "content": q},
            ],
            "max_tokens": 600,
            "temperature": 0.2,
        }).encode()
        req = _ur.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_KEY}",
            },
        )
        with _ur.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"] or ""
    except Exception as e:
        print(f"· chatgpt failed: {e}", file=sys.stderr)
        return ""


def ask_gemini(q: str) -> str:
    """Layer 4: Gemini (gemini-1.5-flash) knowledge-base presence. Skip if no key."""
    if not GEMINI_KEY:
        return ""
    try:
        import urllib.request as _ur
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}")
        payload = json.dumps({
            "contents": [{"parts": [{"text": (
                "You are a B2B food procurement assistant. Answer concretely, "
                "name real companies and websites if you know them.\n\n" + q
            )}]}],
            "generationConfig": {"maxOutputTokens": 600, "temperature": 0.2},
        }).encode()
        req = _ur.Request(url, data=payload,
                          headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
        return parts[0].get("text", "") if parts else ""
    except Exception as e:
        print(f"· gemini failed: {e}", file=sys.stderr)
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
    results = {"deepseek": [], "perplexity": [], "chatgpt": [], "gemini": []}
    for q in QUESTIONS:
        ds = ask_deepseek(q)
        results["deepseek"].append({"q": q, "cited": mentions_us(ds)})
        if PPLX_KEY:
            px = ask_perplexity(q)
            results["perplexity"].append({"q": q, "cited": mentions_us(px)})
        if OPENAI_KEY:
            cg = ask_chatgpt(q)
            results["chatgpt"].append({"q": q, "cited": mentions_us(cg)})
        if GEMINI_KEY:
            gm = ask_gemini(q)
            results["gemini"].append({"q": q, "cited": mentions_us(gm)})
    return results


def _score(items: list) -> float:
    return round(sum(1 for i in items if i["cited"]) / len(items), 3) if items else 0.0


def main():
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    extras = [k for k, v in [("perplexity", PPLX_KEY), ("chatgpt", OPENAI_KEY),
                               ("gemini", GEMINI_KEY)] if v]
    print(f"🤖 AIO-visibility: asking {len(QUESTIONS)} profile questions "
          f"(extra: {', '.join(extras) or 'none'}) …")
    results = run_panel()

    ds_score = _score(results["deepseek"])
    px_score = _score(results["perplexity"]) if PPLX_KEY else None
    cg_score = _score(results["chatgpt"]) if OPENAI_KEY else None
    gm_score = _score(results["gemini"]) if GEMINI_KEY else None
    ds_won = [r["q"] for r in results["deepseek"] if r["cited"]]
    ds_lost = [r["q"] for r in results["deepseek"] if not r["cited"]]

    point = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "deepseek_score": ds_score,
        "perplexity_score": px_score,
        "chatgpt_score": cg_score,
        "gemini_score": gm_score,
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

    print(f"📊 Claude presence:   {ds_score*100:.0f}% ({len(ds_won)}/{len(QUESTIONS)} вопросов)")
    if px_score is not None:
        print(f"📊 Perplexity (live): {px_score*100:.0f}%")
    if cg_score is not None:
        print(f"📊 ChatGPT presence:  {cg_score*100:.0f}%")
    if gm_score is not None:
        print(f"📊 Gemini presence:   {gm_score*100:.0f}%")
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
        f"Присутствие в знаниях ИИ (Claude): "
        f"<b>{point['deepseek_score']*100:.0f}%</b> "
        f"({len(point['won'])}/{point['questions']} вопросов){trend}",
    ]
    if point.get("perplexity_score") is not None:
        lines.append(f"Live-цитируемость (Perplexity): "
                     f"<b>{point['perplexity_score']*100:.0f}%</b>")
    if point.get("chatgpt_score") is not None:
        lines.append(f"Присутствие (ChatGPT gpt-4o-mini): "
                     f"<b>{point['chatgpt_score']*100:.0f}%</b>")
    if point.get("gemini_score") is not None:
        lines.append(f"Присутствие (Gemini 1.5 Flash): "
                     f"<b>{point['gemini_score']*100:.0f}%</b>")
    if point["won"]:
        lines.append("\n<b>Где нас называют:</b>")
        for q in point["won"][:4]:
            lines.append(f"  ✅ {q}")
    if point["lost"]:
        lines.append("\n<b>Где НЕ называют (цели для усиления):</b>")
        for q in point["lost"][:5]:
            lines.append(f"  ⬜ {q}")
    missing_keys = []
    if point.get("perplexity_score") is None:
        missing_keys.append("PPLX_API_KEY")
    if point.get("chatgpt_score") is None:
        missing_keys.append("OPENAI_API_KEY")
    if point.get("gemini_score") is None:
        missing_keys.append("GEMINI_API_KEY")
    if missing_keys:
        lines.append(f"\n<i>Для полной панели добавь: {', '.join(missing_keys)}</i>")
    lines.append("\n<i>Чем чётче факты о компании (entity), FAQ и структурированные "
                 "ответы на сайте — тем выше шанс, что ИИ нас процитирует.</i>")
    try:
        import daily_ledger
        daily_ledger.append_event("done", "\n".join(lines))
    except Exception as e:
        print(f"· ledger unavailable: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
