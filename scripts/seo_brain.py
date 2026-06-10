#!/usr/bin/env python3
"""
SEO BRAIN — the strategic layer of the autonomous engine.

Claude Opus reads a compact digest of the current site state (inventory,
coverage gaps, fresh GSC/Yandex opportunities) and emits a COMPACT JSON
strategy that the cheap DeepSeek "hands" execute 24/7.

Designed to run as a step inside seo-agent-vps.sh AFTER fetch+analyze, so
the opportunities table (volatile) is fresh. Falls back to filesystem-only
digest if the DB is empty. If no ANTHROPIC_API_KEY / budget, it leaves the
previous strategy.json untouched and exits 0 (non-fatal).

Output: data/strategy.json
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from opus_brain_client import call_opus, brain_available, remaining_budget, OPUS_MODEL

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
DB_PATH = DATA / "seo_data.db"
STRATEGY_FILE = DATA / "strategy.json"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Digest builders ───────────────────────────────────────────────────────────
def _count(glob_dir: Path, pattern: str = "*.html") -> int:
    try:
        return len(list(glob_dir.glob(pattern)))
    except Exception:
        return 0


def inventory() -> dict:
    return {
        "geo_ru": _count(PUBLIC / "geo"),
        "geo_en": _count(PUBLIC / "en/geo"),
        "blog_ru": _count(PUBLIC / "blog"),
        "blog_en": _count(PUBLIC / "en/blog"),
        "products": _count(PUBLIC / "products"),
    }


def coverage_gaps() -> dict:
    """How much of the product×city×lang matrix is done, per product."""
    try:
        pg = json.loads((DATA / "products_geo.json").read_text())
        products = pg["products"]
        ru = json.loads((DATA / "cities_russia.json").read_text())["cities"]
        world = json.loads((DATA / "cities_world.json").read_text())["countries"]
    except Exception as e:
        return {"error": str(e)}

    n_ru = len(ru)
    n_world_cities = sum(len(c["cities"]) for c in world)
    existing = set()
    for d in (PUBLIC / "geo", PUBLIC / "en/geo"):
        try:
            existing |= {p.name for p in d.glob("*.html")}
        except Exception:
            pass

    per_product = []
    for p in products:
        slug_ru = p.get("slug_ru", p["id"])
        # rough done-count: files starting with this product slug
        done = sum(1 for fn in existing if fn.startswith(slug_ru + "-") or fn == slug_ru + ".html")
        per_product.append({
            "id": p["id"],
            "name": p.get("name_ru", ""),
            "done_pages": done,
        })
    return {
        "cities_ru": n_ru,
        "cities_world": n_world_cities,
        "products": len(products),
        "per_product": sorted(per_product, key=lambda x: x["done_pages"]),
    }


def opportunities(limit: int = 40) -> dict:
    """Fresh GSC/Yandex opportunities, best-effort (DB may be empty)."""
    out = {"low_ctr": [], "quick_growth": [], "commercial": []}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        for typ in out:
            rows = conn.execute(
                """SELECT query, page, position, impressions, ctr
                   FROM opportunities WHERE type=? AND status='new'
                   ORDER BY impressions DESC LIMIT ?""",
                (typ, limit),
            ).fetchall()
            out[typ] = [dict(r) for r in rows]
        conn.close()
    except Exception:
        pass
    return out


def experiments_digest() -> dict:
    """Compact summary of optimizer experiments so the brain learns what works.

    Reads the durable JSON ledger (data/experiments.json). Surfaces verdict
    tallies and concrete examples of winning vs reverted title rewrites so the
    strategy can double down on patterns that lift CTR and avoid those that hurt.
    """
    try:
        led = json.loads((DATA / "experiments.json").read_text())
    except Exception:
        return {}
    verdicts: dict = {}
    for e in led:
        v = e.get("verdict", "pending")
        verdicts[v] = verdicts.get(v, 0) + 1
    def _ex(e):
        return {"query": e.get("query"), "before": (e.get("before_title") or "")[:60],
                "after": (e.get("after_title") or "")[:60],
                "pos": [e.get("before_pos"), e.get("after_pos")]}
    wins = [_ex(e) for e in led if e.get("verdict") == "win"][-8:]
    reverts = [_ex(e) for e in led if e.get("verdict") == "reverted"][-8:]
    return {
        "verdicts": verdicts,
        "pending": verdicts.get("pending", 0),
        "winning_rewrites": wins,
        "reverted_rewrites": reverts,
    }


def scout_digest() -> dict:
    """New/rising/gap demand signals discovered by the Scout agent."""
    try:
        f = json.loads((DATA / "scout_findings.json").read_text())
    except Exception:
        return {}
    def _trim(lst):
        return [{"query": e.get("query"), "impr": e.get("impr"),
                 "pos": e.get("pos"), "page": e.get("page")} for e in (lst or [])[:12]]
    return {
        "new_queries": _trim(f.get("new_queries")),
        "rising_queries": _trim(f.get("rising_queries")),
        "coverage_gaps": _trim(f.get("coverage_gaps")),
    }


def competitor_digest() -> dict:
    """Queries where competitors outrank us (Competitor-Scout), with why-they-win."""
    try:
        f = json.loads((DATA / "competitor_findings.json").read_text())
    except Exception:
        return {}
    losing = []
    for e in (f.get("losing_queries") or [])[:12]:
        losing.append({"query": e.get("query"), "impr": e.get("impressions"),
                       "our_pos": e.get("our_position"),
                       "why": e.get("why_they_win") or []})
    return {"enriched": f.get("enriched"), "losing_queries": losing}


def aio_digest() -> dict:
    """AI-assistant citability over time (AIO-Visibility agent)."""
    try:
        led = json.loads((DATA / "aio_visibility.json").read_text())
    except Exception:
        return {}
    if not led:
        return {}
    last = led[-1]
    return {"deepseek_score": last.get("deepseek_score"),
            "perplexity_score": last.get("perplexity_score"),
            "not_cited_for": (last.get("lost") or [])[:6]}


def goals_digest() -> dict:
    """Distance-to-#1 scoreboard (goals_scoreboard.py) — the mission, quantified."""
    try:
        g = json.loads((DATA / "goals.json").read_text())
    except Exception:
        return {}
    rows = g.get("goals", [])
    return {
        "achieved": g.get("achieved", 0),
        "total": g.get("total", 0),
        "worst_gaps": [
            {"q": r["query"], "pos": r.get("position_7d") or r.get("position_28d"),
             "gap": r.get("gap_to_1"), "impr": r.get("impressions_28d")}
            for r in rows
            if r.get("gap_to_1") and r["gap_to_1"] > 0.3
        ][:12],
        "no_data": [r["query"] for r in rows if r.get("position_28d") is None][:8],
        "countries": [
            {"c": r["country"], "impr": r["impressions_28d"],
             "clicks": r["clicks_28d"], "pos": r["position_28d"]}
            for r in g.get("countries", [])
        ],
    }


def ai_bots_digest() -> dict:
    """AI crawler visits from nginx logs (parse-ai-bots digest, if present on VPS)."""
    import os
    for p in (Path(os.environ.get("AI_BOTS_DIGEST_DIR", "/var/log/nginx"))
              / "ai-bots-digest-latest.md",):
        try:
            txt = p.read_text(encoding="utf-8")
            return {"latest": txt[:1500]}
        except Exception:
            pass
    return {}


def market_pulse_digest() -> dict:
    """Monthly live-web market intel (market_pulse.py / Perplexity)."""
    try:
        mp = json.loads((DATA / "market_pulse.json").read_text())
        out = {}
        for code, c in (mp.get("countries") or {}).items():
            out[c.get("name", code)] = {
                "insights": (c.get("insights") or [])[:3],
                "opportunity": c.get("opportunity", ""),
                "risk": c.get("risk", ""),
            }
        return {"generated_at": mp.get("generated_at", ""), "markets": out}
    except Exception:
        return {}


def costs_digest() -> dict:
    """LLM spend telemetry so the brain can weigh content volume vs budget."""
    try:
        led = json.loads((DATA / "llm_costs.json").read_text())
        from datetime import date as _date
        m = led.get(_date.today().strftime("%Y-%m"), {})
        if not m:
            return {}
        days = m.get("days", {})
        top = sorted(m.get("scripts", {}).items(),
                     key=lambda kv: -kv[1].get("usd", 0))[:5]
        geo = m.get("scripts", {}).get("generate_geo_bulk", {})
        geo_pages = max(geo.get("calls", 0), 1)
        return {
            "month_usd": round(m.get("usd", 0.0), 2),
            "month_usd_without_optimizations": round(m.get("usd_baseline", 0.0), 2),
            "days_tracked": len(days),
            "avg_daily_usd": round(m.get("usd", 0.0) / max(len(days), 1), 2),
            "monthly_budget_usd": float(os.environ.get("LLM_MONTHLY_BUDGET", "200")),
            "top_spenders": {k: round(v.get("usd", 0.0), 2) for k, v in top},
            "geo_page_unit_cost_usd": round(geo.get("usd", 0.0) / geo_pages, 3),
        }
    except Exception:
        return {}


def build_digest() -> dict:
    return {
        "date": TODAY,
        "goals": goals_digest(),
        "inventory": inventory(),
        "coverage": coverage_gaps(),
        "opportunities": opportunities(),
        "experiments": experiments_digest(),
        "scout": scout_digest(),
        "competitors": competitor_digest(),
        "aio_visibility": aio_digest(),
        "ai_bots": ai_bots_digest(),
        "market_pulse": market_pulse_digest(),
        "costs": costs_digest(),
    }


# ── Playbook (static, cacheable system prompt) ─────────────────────────────────
PLAYBOOK = """Ты — стратегический директор по поисковому и AI-присутствию компании
«Казанские Деликатесы» (pepperoni.tatar), производителя ХАЛЯЛЬ мясных изделий и
выпечки из Казани. Миссия: стать №1 в России и СНГ по ВСЕМУ ассортименту, а также
№1 по услугам контрактного производства — Private Label / White Label / OEM (СТМ) —
причём не только по колбасам/мясу, но и по ВСЕЙ выпечке (татарская + классическая +
европейская).

Архитектура: ты — «мозг» (думаешь редко, дорого, качественно). Claude Sonnet —
«руки» (генерят страницы 24/7 дёшево). Твоя задача — на основе дайджеста состояния
сайта выдать КОМПАКТНУЮ стратегию-директиву, которую руки исполнят.

ПОЛНАЯ АВТОНОМИЯ: владелец полностью доверяет твоим решениям — аппрувов нет.
Твоя директива исполняется автоматически в тот же цикл. Решай смело, но помни:
ошибки никто не перепроверит — следи за халяль-целостностью и качеством сам.

ПРИНЦИПЫ:
- ЦЕЛИ: блок "goals" — таблица «дистанция до №1» по целевым запросам. Это
  ГЛАВНЫЙ KPI. worst_gaps — запросы с наибольшим отставанием при реальном
  спросе: их подтягивание (rewrite_pages, new_blog_topics, перелинковка) —
  приоритет №1. no_data — целевые запросы, по которым нас вообще не видно:
  для них нужны новые страницы.
- ЦЕЛЕВЫЕ СТРАНЫ: goals.countries — видимость по 16 целевым рынкам (РФ, СНГ:
  Казахстан/Беларусь/Армения/Азербайджан/Кыргызстан/Таджикистан/Грузия;
  Залив+Египет: ОАЭ/Саудовская Аравия/Кувейт/Бахрейн/Оман/Йемен/Катар/Египет).
  Есть /export/{страна} лендинги (ru/en/ar) и арабский хаб /ar/. Страны с
  нулевыми показами — направляй туда гео-страницы, blog-темы и rewrite
  существующих export-страниц. Для Залива приоритет ar+en контент.
- РАВНОМЕРНОЕ покрытие ВСЕГО ассортимента — не зацикливайся на одной категории.
  Все категории (пепперони, колбасы, сосиски, ветчины, котлеты, фарши, пельмени,
  копчёные, казылык, топпинги, ВСЯ выпечка — татарская/классическая/прочая,
  Private Label) должны расти параллельно. В focus_products чередуй категории так,
  чтобы со временем покрытие было сбалансированным; в первую очередь подтягивай те,
  где done_pages меньше всего (видно в coverage.per_product).
- Private Label / OEM / White Label — ВАЖНОЕ, но НЕ единственное направление: держи
  по нему 1-2 страницы за период (RU + экспорт EN/AR), не больше, чтобы не перекосить.
- ГЕОГРАФИЯ масштабная: Россия + СНГ (приоритет) + арабские страны (GCC, Левант,
  Египет, Судан) + Африка (Нигерия, Марокко, Алжир, Тунис, Сенегал, Кения, ЮАР) +
  Юго-Восточная Азия (Малайзия, Индонезия, Бруней — крупнейшие халяль-рынки) +
  Южная Азия (Пакистан, Бангладеш) + Турция. Цель — чтобы нас находили ВЕЗДЕ.
  Языки подбирай под рынок: ms (Малайзия), id (Индонезия), tr (Турция),
  fr (Сев./Зап. Африка), ar (арабские), en (международный), ru (РФ/СНГ) и т.д.
- Приоритизируй по ROI: запросы с трафиком и позицией 5-15 важнее пустых ниш;
  города-миллионники и рынки с высоким % мусульман — выше.
- КОНКУРЕНТЫ: в дайджесте competitors.losing_queries — запросы со спросом, где нас
  обходят (наша позиция хуже 10). Если есть why (длиннее контент / больше schema /
  отзывы / FAQ) — закладывай конкретные улучшения: усилить/удлинить контент целевой
  страницы, добавить FAQ/Review-разметку, перелинковку. Это приоритетные цели «рук».
- AIO-ВИДИМОСТЬ: aio_visibility.not_cited_for — вопросы покупателей, где ИИ-ассистенты
  нас НЕ называют. Чтобы нас цитировали: усиливай entity-факты (кто мы, что делаем,
  сертификаты, контакты), чёткие FAQ и структурированные ответы под эти вопросы.
  Блок "costs" — твоя экономика: сколько система тратит на LLM в этом месяце,
  средний расход в день, бюджет месяца (monthly_budget_usd), цена одной
  гео-страницы. ТЫ управляешь расходами: geo_daily_target и количество тем —
  это твой бюджетный рычаг. Трать там, где goals показывают отдачу (рост
  позиций/показов), и сокращай объём по направлениям без движения. Если
  avg_daily_usd * 30 превышает бюджет — снижай объёмы осознанно, начиная с
  наименее результативных направлений. Качество всегда важнее количества.
  Блок "market_pulse" — ежемесячная живая разведка 15 экспортных рынков через
  веб-поиск (спрос, регуляторика, конкуренты, возможности и риски по каждой
  стране). Используй её при выборе стран для гео-страниц, blog-тем и экспортного
  контента: возможности → контент-приоритет, риски → не трать туда бюджет.
  Блок "ai_bots" — реальные визиты ИИ-краулеров (GPTBot, ClaudeBot, PerplexityBot)
  по логам: какие страницы они читают. Усиливай именно читаемые ими страницы.
- Избегай thin/duplicate. Каждая директива — уникальная ценность.
- УЧИСЬ НА ЭКСПЕРИМЕНТАХ: в дайджесте есть блок "experiments" — результаты
  автоматических правок title/meta (win = CTR/позиция выросли, reverted =
  ухудшение, откатили). Смотри winning_rewrites/reverted_rewrites: усиливай
  паттерны формулировок, которые ДАЮТ win (например «запрос — что это», intent
  в начале title), и избегай тех, что приводили к откату. Отрази это в
  prompt_tweaks (как руки должны писать title/meta).
- ГЛАВНАЯ МЕТРИКА — клики/трафик, а НЕ количество страниц. Если опт-эксперименты
  дают win — это важнее, чем выпуск новых гео-страниц.
- РАЗВЕДКА СПРОСА: блок "scout" — это сигналы от агента-разведчика:
  new_queries (новые запросы без нормальной страницы), rising_queries (растущий
  спрос), coverage_gaps (есть спрос, но ранжируется только главная — нужен
  отдельный лендинг). Это ВЫСШИЙ приоритет для new_blog_topics / pl_oem_topics /
  rewrite_pages: делай страницы под РЕАЛЬНЫЙ обнаруженный спрос, а не догадки.
- Не раздувай вывод. Списки короткие и конкретные.

ВЕРНИ СТРОГО валидный JSON (без markdown, без комментариев) по схеме:
{
  "focus_products": ["product_id", ...],        // 3-6 продуктов в порядке приоритета
  "focus_langs": ["ru","en","ar","ms","id","tr","fr","kk",...], // языки под целевые рынки
  "geo_daily_target": 80,                        // гео-страниц/день (равномерно по категориям и странам)
  "new_blog_topics": [                           // 3-8 новых статей
    {"slug":"...", "title_ru":"...", "intent":"информационный|коммерческий"}
  ],
  "pl_oem_topics": [                             // 3-8 страниц по Private Label/OEM
    {"slug":"...", "title":"...", "lang":"ru|en|ar", "angle":"кратко суть"}
  ],
  "rewrite_pages": [                             // страницы на доработку (позиция 5-15)
    {"path":"/geo/...","reason":"..."}
  ],
  "prompt_tweaks": {"geo":"...", "blog":"...", "pl":"..."}, // доп.инструкции рукам
  "notes": "1-3 предложения: логика решений на этот период"
}"""


def build_user_prompt(digest: dict) -> str:
    return (
        "Дайджест состояния сайта на сегодня (JSON):\n\n"
        + json.dumps(digest, ensure_ascii=False, indent=1)
        + "\n\nПроанализируй и верни стратегию-директиву строго по схеме из системного "
          "промпта. Учитывай: где меньше всего готовых страниц — там пробелы; "
          "opportunities (если есть) — это реальные запросы из GSC/Yandex, по ним "
          "максимальный ROI. Private Label/OEM и полную выпечку держи в фокусе."
    )


# Structured-output schema mirroring the playbook's contract: the API
# guarantees the reply parses, so a malformed strategy can no longer waste a
# Fable call (~$0.5 each).
STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "focus_products": {"type": "array", "items": {"type": "string"}},
        "focus_langs": {"type": "array", "items": {"type": "string"}},
        "geo_daily_target": {"type": "integer"},
        "new_blog_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title_ru": {"type": "string"},
                    "intent": {"type": "string"},
                },
                "required": ["slug", "title_ru"],
            },
        },
        "pl_oem_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "lang": {"type": "string"},
                    "angle": {"type": "string"},
                },
                "required": ["slug", "title"],
            },
        },
        "rewrite_pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["path"],
            },
        },
        "prompt_tweaks": {
            "type": "object",
            "properties": {
                "geo": {"type": "string"},
                "blog": {"type": "string"},
                "pl": {"type": "string"},
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["focus_products", "focus_langs", "geo_daily_target",
                 "new_blog_topics", "pl_oem_topics", "notes"],
}


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text else text
        text = text.lstrip("json").strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in Opus reply")
    return json.loads(text[start:end + 1])


def main():
    if not brain_available():
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ℹ️  Brain disabled: ANTHROPIC_API_KEY not set. Keeping existing strategy.")
        else:
            print(f"⚠️  Opus monthly budget exhausted (${remaining_budget():.2f} left). "
                  "Keeping existing strategy.")
        return 0

    digest = build_digest()
    user_prompt = build_user_prompt(digest)

    # Free pre-flight: catch silent digest bloat (the brain is the priciest
    # call in the system — $10/MTok in, $50/MTok out).
    try:
        from claude_client import count_tokens
        n = count_tokens(user_prompt, system=PLAYBOOK, model=OPUS_MODEL)
        if n > 0:
            print(f"📏 digest size: {n:,} input tokens")
        if n > 30_000:
            warn = (f"⚠️ Дайджест Мозга распух: {n:,} токенов (>30K). "
                    f"Проверь блоки digest — это бьёт по бюджету Fable.")
            print(warn)
            try:
                from telegram_notify import notify
                notify(warn)
            except Exception:
                pass
    except Exception:
        pass

    # Daily ticks run at medium effort; escalations/monthly planning set
    # BRAIN_EFFORT=high. Effort trims Fable's adaptive-thinking spend.
    effort = os.environ.get("BRAIN_EFFORT", "medium")
    print(f"🧠 Brain ({OPUS_MODEL}, effort={effort}) thinking… "
          f"budget left ${remaining_budget():.2f}")

    try:
        text, usage = call_opus(
            prompt=user_prompt,
            system=PLAYBOOK,
            max_tokens=4000,
            temperature=0.3,
            cache_system=True,
            effort=effort,
            json_schema=STRATEGY_SCHEMA,
        )
    except Exception as e:
        print(f"⚠️  Opus call failed ({e}). Keeping existing strategy.")
        return 0

    try:
        strategy = _extract_json(text)
    except Exception as e:
        print(f"⚠️  Could not parse strategy JSON ({e}). Keeping existing strategy.")
        return 0

    strategy["generated_at"] = datetime.now(timezone.utc).isoformat()
    strategy["model"] = OPUS_MODEL
    strategy["digest_summary"] = {
        "inventory": digest["inventory"],
        "opportunities_counts": {k: len(v) for k, v in digest["opportunities"].items()},
        "experiments": digest.get("experiments", {}).get("verdicts", {}),
    }
    STRATEGY_FILE.write_text(json.dumps(strategy, ensure_ascii=False, indent=1))

    print(f"✅ Strategy written → {STRATEGY_FILE}")
    print(f"   focus_products: {strategy.get('focus_products')}")
    print(f"   geo_daily_target: {strategy.get('geo_daily_target')}")
    print(f"   blog topics: {len(strategy.get('new_blog_topics', []))} | "
          f"PL/OEM: {len(strategy.get('pl_oem_topics', []))} | "
          f"rewrites: {len(strategy.get('rewrite_pages', []))}")
    print(f"   cost: ${usage.get('cost_usd')} | budget left: ${usage.get('budget_remaining_usd')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
