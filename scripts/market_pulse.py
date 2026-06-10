#!/usr/bin/env python3
"""Market pulse — monthly live-web research over the 15 target export markets.

Uses the Perplexity Agent API (web search) to collect, per country: halal-meat
demand trends, import/regulatory changes, and active competitors. Results are
written to data/market_pulse.json which feeds the Brain (Fable) digest, so the
monthly strategy reflects what is actually happening in each market — not just
our own GSC mirror.

Cost: ~15 pro-search agent calls once a month (≈ $0.5). The daily pipeline
calls this script every day, but it exits instantly unless the data is older
than MARKET_PULSE_DAYS (default 28) — no cron change needed.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "market_pulse.json"
MAX_AGE_DAYS = int(os.environ.get("MARKET_PULSE_DAYS", "28"))

COUNTRIES = {
    "kaz": "Казахстан", "blr": "Беларусь", "arm": "Армения",
    "aze": "Азербайджан", "kgz": "Кыргызстан", "tjk": "Таджикистан",
    "geo": "Грузия", "are": "ОАЭ", "sau": "Саудовская Аравия",
    "kwt": "Кувейт", "bhr": "Бахрейн", "omn": "Оман", "yem": "Йемен",
    "qat": "Катар", "egy": "Египет",
}

INSTRUCTIONS = (
    "Ты аналитик рынка халяль мясной продукции. Работаешь на российского "
    "производителя (Казань): пепперони, сосиски, колбасы, казылык, замороженные "
    "полуфабрикаты, OEM/Private Label. Верни ТОЛЬКО JSON без markdown: "
    '{"insights": [str, str, str], "opportunity": str, "risk": str}. '
    "insights — 3 конкретных факта за последние месяцы (спрос, регуляторика, "
    "конкуренты, цены) со страновой спецификой. opportunity — главная "
    "возможность для нас. risk — главный риск/барьер. Кратко, по-русски."
)


def fresh_enough() -> bool:
    try:
        age_days = (datetime.now(timezone.utc).timestamp() - OUT.stat().st_mtime) / 86400
        return age_days < MAX_AGE_DAYS
    except OSError:
        return False


def main() -> int:
    force = "--force" in sys.argv[1:]
    if not force and fresh_enough():
        print(f"market pulse fresh (<{MAX_AGE_DAYS}d) — skip")
        return 0
    try:
        from pplx_client import pplx_agent_json, PPLX_KEY
    except Exception as e:
        print(f"pplx client unavailable: {e}", file=sys.stderr)
        return 0
    if not PPLX_KEY:
        print("PPLX_API_KEY not set — skip")
        return 0

    countries = {}
    for code, name in COUNTRIES.items():
        try:
            # 2000 tokens: Cyrillic JSON is token-dense; 800 truncated mid-string
            # for 6/15 countries on the first live run. json_schema enforces
            # valid structured output server-side.
            data = pplx_agent_json(
                f"Рынок халяль мясной продукции в стране: {name}. "
                f"Что важно знать экспортёру из России прямо сейчас "
                f"(импорт, сертификация, спрос HoReCa/ритейл, конкуренты)?",
                instructions=INSTRUCTIONS, max_steps=3, max_output_tokens=2000,
                json_schema={
                    "type": "object",
                    "properties": {
                        "insights": {"type": "array", "items": {"type": "string"},
                                     "maxItems": 3},
                        "opportunity": {"type": "string"},
                        "risk": {"type": "string"},
                    },
                    "required": ["insights", "opportunity", "risk"],
                })
            countries[code] = {"name": name, **data}
            print(f"  ✓ {name}: {len(data.get('insights', []))} insights")
        except Exception as e:
            print(f"  ✗ {name}: {e}", file=sys.stderr)

    if not countries:
        print("no data collected — keeping previous pulse")
        return 1

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "countries": countries,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ market pulse: {len(countries)}/{len(COUNTRIES)} countries -> {OUT}")

    try:
        from telegram_notify import notify
        top = list(countries.values())[:3]
        lines = ["<b>🌐 Market Pulse (ежемесячная разведка рынков)</b>"]
        for c in top:
            opp = c.get("opportunity", "")[:120]
            lines.append(f"• <b>{c['name']}</b>: {opp}")
        lines.append(f"\n<i>Всего {len(countries)} стран · полные данные ушли Мозгу</i>")
        notify("\n".join(lines))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
