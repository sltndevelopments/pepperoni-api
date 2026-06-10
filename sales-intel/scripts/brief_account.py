#!/usr/bin/env python3
"""Pre-call account brief — досье на B2B-лида перед первым звонком.

Вход:  ИНН или название компании (позиционный аргумент), либо --top N для
       первых N лидов из bakery-leads-top200.csv.
Шаги:  1) ищем лида в локальных CSV (скоринг, контакты, выручка — уже есть);
       2) Perplexity (live web): свежие новости, ассортимент, сети сбыта,
          признаки халяль-направления, тендеры;
       3) Haiku собирает одностраничное досье: кто такие, зачем им халяль,
          угол захода, риски, 3 вопроса для звонка.
Выход: sales-intel/data/briefs/<inn>.md + текст в stdout.

Стоимость: ~$0.01–0.02 на лида (1 pplx pro-search + 1 Haiku).
Запуск:  python3 sales-intel/scripts/brief_account.py 7723801936
         python3 sales-intel/scripts/brief_account.py "БонтьеР"
         python3 sales-intel/scripts/brief_account.py --top 5
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "sales-intel" / "data"
BRIEFS = DATA / "briefs"
LEAD_FILES = ["bakery-leads-top200.csv", "bakery-leads-enriched.csv",
              "bakery-leads-okved-enriched.csv"]


def find_lead(query: str) -> dict | None:
    q = query.strip().lower()
    for fname in LEAD_FILES:
        p = DATA / fname
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if q == row.get("inn", "").strip() or q in row.get("name_short", "").lower():
                    return row
    return None


def top_leads(n: int) -> list[dict]:
    p = DATA / "bakery-leads-top200.csv"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))[:n]


def research(lead: dict) -> str:
    """Live-web интел через Perplexity (pro-search)."""
    from pplx_client import pplx_agent
    name = lead.get("name_full") or lead.get("name_short", "")
    region = lead.get("region_name", "")
    site = lead.get("sites", "")
    return pplx_agent(
        f"Компания: {name} (ИНН {lead.get('inn', '?')}, {region}, сайт: {site or 'неизвестен'}). "
        "Это производитель выпечки/полуфабрикатов в России. Найди: 1) актуальный "
        "ассортимент и бренды; 2) каналы сбыта (сети, HoReCa, тендеры); 3) новости "
        "за последний год (расширение, новые линии, проблемы); 4) признаки "
        "халяль-ассортимента или мусульманской аудитории в регионе; 5) ЛПР/закупки "
        "если упоминаются публично. Кратко, фактами, по-русски.",
        instructions="Ты B2B-аналитик. Только проверяемые факты с указанием источников.",
        max_steps=4, max_output_tokens=1500)


def compose_brief(lead: dict, intel: str) -> str:
    """Haiku: 1 страница «зачем им мы и как заходить»."""
    from claude_client import call_claude_cheap
    facts = "\n".join(f"{k}: {v}" for k, v in lead.items()
                      if v and k in ("name_short", "inn", "region_name", "director",
                                     "score", "score_reasons", "phones", "emails",
                                     "sites", "registered"))
    text, _ = call_claude_cheap(
        f"ДАННЫЕ ИЗ CRM:\n{facts}\n\nWEB-РАЗВЕДКА:\n{intel}\n\n"
        "Собери досье перед первым звонком, строго по схеме:\n"
        "## Кто это\n(2-3 предложения)\n"
        "## Зачем им халяль от «Казанских Деликатесов»\n(3 пункта: продукт-фит, "
        "география, аудитория)\n"
        "## Угол захода\n(1 конкретное предложение первого оффера: какой SKU/услуга, "
        "почему именно им)\n"
        "## Риски/возражения\n(2 пункта)\n"
        "## 3 вопроса для звонка\n(каждый раскрывает потребность)",
        system=("Ты — помощник отдела продаж халяль-производителя «Казанские "
                "Деликатесы» (Казань): пепперони, сосиски для хот-догов и сосисок "
                "в тесте, котлеты, казылык, татарская выпечка, Private Label/OEM. "
                "Пиши кратко, по-русски, без воды. Не выдумывай факты — только из "
                "входных данных."),
        max_tokens=900)
    return text


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    if args[0] == "--top":
        leads = top_leads(int(args[1]) if len(args) > 1 else 3)
    else:
        lead = find_lead(" ".join(args))
        if not lead:
            print(f"❌ Лид не найден в {', '.join(LEAD_FILES)}")
            return 1
        leads = [lead]

    BRIEFS.mkdir(parents=True, exist_ok=True)
    for lead in leads:
        name = lead.get("name_short", "?")
        print(f"\n{'=' * 60}\n🔍 {name} (ИНН {lead.get('inn', '?')})")
        try:
            intel = research(lead)
        except Exception as e:
            print(f"  ⚠️ Perplexity недоступен ({e}) — досье только по CRM-данным")
            intel = "(web-разведка недоступна)"
        try:
            brief = compose_brief(lead, intel)
        except Exception as e:
            print(f"  ❌ LLM: {e}")
            continue
        out = BRIEFS / f"{lead.get('inn', 'unknown')}.md"
        out.write_text(f"# {name}\n\n{brief}\n\n---\n\n## Сырая web-разведка\n\n{intel}\n",
                       encoding="utf-8")
        print(brief)
        print(f"\n💾 {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
