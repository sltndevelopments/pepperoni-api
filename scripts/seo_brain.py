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


def build_digest() -> dict:
    return {
        "date": TODAY,
        "inventory": inventory(),
        "coverage": coverage_gaps(),
        "opportunities": opportunities(),
    }


# ── Playbook (static, cacheable system prompt) ─────────────────────────────────
PLAYBOOK = """Ты — стратегический директор по поисковому и AI-присутствию компании
«Казанские Деликатесы» (pepperoni.tatar), производителя ХАЛЯЛЬ мясных изделий и
выпечки из Казани. Миссия: стать №1 в России и СНГ по ВСЕМУ ассортименту, а также
№1 по услугам контрактного производства — Private Label / White Label / OEM (СТМ) —
причём не только по колбасам/мясу, но и по ВСЕЙ выпечке (татарская + классическая +
европейская).

Архитектура: ты — «мозг» (думаешь редко, дорого, качественно). DeepSeek Flash —
«руки» (генерят страницы 24/7 дёшево). Твоя задача — на основе дайджеста состояния
сайта выдать КОМПАКТНУЮ стратегию-директиву, которую руки исполнят.

ПРИНЦИПЫ:
- Приоритизируй по ROI: запросы с трафиком и позицией 5-15 (близко к топу) важнее
  пустых ниш. Города-миллионники и регионы с высоким % мусульман — выше.
- Private Label / OEM / White Label — стратегический приоритет: это высокомаржинальная
  B2B-услуга. Нужны кластеры RU + экспорт (EN/AR для GCC, СНГ).
- Избегай thin/duplicate. Каждая директива должна давать уникальную ценность.
- Не раздувай вывод. Списки — короткие и конкретные.

ВЕРНИ СТРОГО валидный JSON (без markdown, без комментариев) по схеме:
{
  "focus_products": ["product_id", ...],        // 3-6 продуктов в порядке приоритета
  "focus_langs": ["ru","en","ar","kk",...],     // языки на период
  "geo_daily_target": 60,                        // сколько гео-страниц/день генерить
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
    print(f"🧠 Brain ({OPUS_MODEL}) thinking… budget left ${remaining_budget():.2f}")

    try:
        text, usage = call_opus(
            prompt=build_user_prompt(digest),
            system=PLAYBOOK,
            max_tokens=4000,
            temperature=0.3,
            cache_system=True,
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
