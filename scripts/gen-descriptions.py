#!/usr/bin/env python3
"""
One-time / on-demand generator of product descriptions via DeepSeek.

Reads public/products.json, and for every product MISSING
seoDescriptionRU / seoDescriptionEN / ingredientsRU / ingredientsEN,
generates them and stores into data/descriptions-overrides.json keyed by SKU.

These overrides are merged back during sync-sheets (mjs + py) ONLY when the
Google Sheet cell is empty — so the Sheet always stays the source of truth,
but generated text survives every cron sync.

Env: DEEPSEEK_API_KEY  (or pass --api-key)

Usage:
    DEEPSEEK_API_KEY=sk-... python3 scripts/gen-descriptions.py
    python3 scripts/gen-descriptions.py --only KD-005,KD-010   # subset
    python3 scripts/gen-descriptions.py --force                # regen all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from claude_client import call_claude, CONTENT_MODEL

ROOT = Path(__file__).parent.parent
PRODUCTS_JSON = ROOT / "public" / "products.json"
OVERRIDES = ROOT / "data" / "descriptions-overrides.json"

FIELDS = ("seoDescriptionRU", "seoDescriptionEN", "ingredientsRU", "ingredientsEN")

from brand_system import brand_block

SYSTEM = brand_block("ru") + "\n\n" + (
    "Ты — контент-маркетолог и технолог пищевого производства компании "
    "«Казанские Деликатесы» (pepperoni.tatar) — производителя ХАЛЯЛЬНЫХ мясных "
    "изделий и татарской выпечки из Казани. Пишешь точные, аппетитные и при этом "
    "достоверные описания товаров. Не выдумывай сертификаты, ГОСТы или цифры, "
    "которых нет во входных данных. "
    "КРИТИЧЕСКИ ВАЖНО (халяль): продукция НЕ содержит свинины, сала, шпика, "
    "бекона, желатина животного происхождения и алкоголя. Даже если для данного "
    "вида продукта (пепперони, сервелат, салями и т.п.) классический рецепт "
    "обычно свиной — здесь мясная основа ВСЕГДА говядина, мясо птицы или конина, "
    "а жир — говяжий/курдючный. НИКОГДА не указывай свинину/шпик/pork/fatback/"
    "bacon/lard в составе. Не пиши избыточные фразы вроде «без свинины» — халяль "
    "это подразумевает. Состав описывай типичный для халяльного аналога, без "
    "точных процентов."
)


def build_prompt(p: dict) -> str:
    facts = []
    for k in ("name", "category", "section", "weight", "shelfLife", "storage",
              "casing", "diameter", "packageType", "qtyPerBox"):
        v = p.get(k)
        if v:
            facts.append(f"- {k}: {v}")
    cert = p.get("certification") or "Halal"
    facts.append(f"- certification: {cert}")
    qs = p.get("quality_system")
    if qs:
        facts.append(f"- quality_system: {qs}")
    facts_str = "\n".join(facts)

    return f"""Товар:
{facts_str}

Сгенерируй контент для карточки товара. Верни СТРОГО JSON (без markdown, без пояснений):
{{
  "seoDescriptionRU": "<краткий заголовок до 60 символов> | <SEO-подзаголовок до 70 символов> | <полное описание 280-400 символов: вкус, применение (HoReCa, опт, ретейл), польза, происхождение Казань/Татарстан, халяль>",
  "seoDescriptionEN": "<short headline up to 60 chars> | <SEO subheadline up to 70 chars> | <full description 280-400 chars: taste, use-cases, halal, made in Kazan>",
  "ingredientsRU": "Состав: <типичный ХАЛЯЛЬНЫЙ состав: говядина/мясо птицы/конина, говяжий жир — НЕ свинина и НЕ шпик>. Аллергены: <если применимо>.",
  "ingredientsEN": "Ingredients: <typical HALAL composition: beef/poultry/horse meat, beef fat — NO pork, NO fatback/bacon>. Allergens: <if applicable>."
}}
Только валидный JSON в одну структуру."""


def parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    # strip code fences if present
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", ""))
    ap.add_argument("--only", default="", help="comma-separated SKUs")
    ap.add_argument("--force", action="store_true", help="regenerate even if present")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key
    # re-import key into client module
    import claude_client
    claude_client.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    if not claude_client.ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    products = data["products"]

    overrides = {}
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))

    only = {s.strip().upper() for s in args.only.split(",") if s.strip()}

    todo = []
    for p in products:
        sku = p["sku"]
        if only and sku.upper() not in only:
            continue
        # what is missing in the live product (sheet) data?
        missing = [f for f in FIELDS if not (p.get(f) or "").strip()]
        if args.force:
            missing = list(FIELDS)
        # don't re-generate fields we already have in overrides (unless --force)
        if not args.force and sku in overrides:
            missing = [f for f in missing if not (overrides[sku].get(f) or "").strip()]
        if missing:
            todo.append((p, missing))

    print(f"📝 Products needing generation: {len(todo)} / {len(products)}")
    if not todo:
        print("✅ Nothing to generate.")
        return

    ok = 0
    for i, (p, missing) in enumerate(todo, 1):
        sku = p["sku"]
        print(f"  [{i}/{len(todo)}] {sku} — {p['name'][:45]}  (missing: {', '.join(missing)})")
        try:
            raw, _tok = call_claude(build_prompt(p), system=SYSTEM,
                                    max_tokens=1200, effort="medium",
                                    model=CONTENT_MODEL)
        except Exception as ex:
            print(f"     ⚠️  API error: {ex}", file=sys.stderr)
            continue
        gen = parse_json(raw)
        if not gen:
            print(f"     ⚠️  could not parse JSON, skipping", file=sys.stderr)
            continue
        entry = overrides.get(sku, {})
        for f in missing:
            val = (gen.get(f) or "").strip()
            if val:
                entry[f] = val
        if entry:
            overrides[sku] = entry
            ok += 1
        # incremental save so a crash doesn't lose progress
        OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDES.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        time.sleep(args.sleep)

    print(f"\n✅ Generated/updated {ok} products → {OVERRIDES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
