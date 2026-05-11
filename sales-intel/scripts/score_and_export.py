"""
score_and_export.py — apply heuristic scoring to candidates in fns_raw.jsonl
                      and export top-N as data/bakery-leads.csv.

Scoring (all rule-based, no ML):
    positive signals on name:
        +60  contains "сосиск" / "сосиска"      (primary target — sausage-in-dough producers)
        +55  contains "пирож" / "чебуреч" / "хот-дог"/"хотдог"
        +50  contains "пекарн" / "бейкер" / "бейкери"
        +45  contains "хлебозавод" / "хлебокомбинат"
        +40  contains "полуфабрикат" / "заморож"
        +35  contains "кондитер" / "булочн" / "слоён" / "выпечк"
        +25  contains "хлеб" (less specific, catches many)
        +25  contains "мясокомбинат" / "мясопереработ"
        +20  contains "колбасн"

    positive org-type signals:
        +15  ЗАО/ОАО/АО/ПАО  (usually larger / older firms)
        +10  ООО
         0  ПО (потребобщество — rural coop, often small)
        -30 ИП / частное лицо (not the profile we want)

    positive region signals:
        +10  target high-priority region (Москва, МО, СПб, ТР, Башкирия, СПб obl, Самара, НН, Краснодар,
              Дагестан, Чечня — halal density or logistics-good)

    negative signals:
        -20  название содержит "деревня"/"село"/"хутор"/"райпо"/"сельпо"
        -40  в статусе ликвидации (уже отфильтровано при загрузке)
        -15  registered before 1995 without modern name (slow Soviet leftover)

Output: data/bakery-leads.csv  sorted by score desc
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "raw" / "fns_raw.jsonl"
OUT = ROOT / "data" / "bakery-leads.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

HALAL_DENSE_REGIONS = {"16", "02", "05", "07", "20", "15", "09", "06", "12", "18"}
LOGISTICS_HUBS = {"77", "50", "78", "47", "63", "52", "23", "61", "66", "74"}


def score(entry: dict) -> tuple[int, list[str]]:
    pts = 0
    reasons: list[str] = []

    name = (entry.get("name_short") or entry.get("name_full") or "").lower()

    # Primary product signals
    patterns = [
        (r"сосиск", 60, "сосиски"),
        (r"пирож|чебуреч|хот[-\s]?дог", 55, "пирожки/хот-доги"),
        (r"пекарн|бейкер|бейкери", 50, "пекарня"),
        (r"хлебозавод|хлебокомбинат|хлебопекар", 45, "хлебозавод"),
        (r"полуфабрикат|заморож", 40, "полуфабрикаты"),
        (r"кондитер|булочн|слоён|выпечк|выпечки", 35, "кондитерка"),
        (r"мясокомбинат|мясопереработ", 25, "мясокомбинат"),
        (r"колбасн", 20, "колбасные"),
        (r"хлеб", 25, "хлеб"),
    ]
    matched = set()
    for pat, pt, lbl in patterns:
        if re.search(pat, name) and lbl not in matched:
            pts += pt
            reasons.append(f"+{pt} name:{lbl}")
            matched.add(lbl)
    # Cap at 120 so multiple name matches don't runaway.
    if pts > 120:
        reasons.append(f"(cap @120, was {pts})")
        pts = 120

    # Org-type / kind
    if entry.get("kind") != "ul":
        pts -= 30
        reasons.append("-30 ИП/физ")
    else:
        if re.search(r"\b(ЗАО|ОАО|АО|ПАО)\b", entry.get("name_short") or ""):
            pts += 15
            reasons.append("+15 АО/ЗАО/ПАО")
        elif "ООО" in (entry.get("name_short") or ""):
            pts += 10
            reasons.append("+10 ООО")
        elif re.search(r'\bПО\b|\bПОТРЕБ', entry.get("name_short") or "", re.IGNORECASE):
            pts -= 5
            reasons.append("-5 потребкооп")

    # Region
    reg = entry.get("region_code", "")
    if reg in HALAL_DENSE_REGIONS:
        pts += 10
        reasons.append("+10 халяль-регион")
    elif reg in LOGISTICS_HUBS:
        pts += 10
        reasons.append("+10 лог.хаб")

    # Name noise
    if re.search(r"райпо|сельпо|деревн|село|хутор|колхоз", name):
        pts -= 20
        reasons.append("-20 сельск.")

    # Very old registration (< 1995) often defunct-ish Soviet leftover
    reg_date = entry.get("registered") or ""
    if reg_date:
        year_match = re.search(r"(\d{4})", reg_date[-5:])
        if year_match:
            year = int(year_match.group(1))
            if year < 1995 and not re.search(r"бейкер|бейкери|хот.дог|сосиска|пиццер", name):
                pts -= 15
                reasons.append("-15 до-1995")
            elif 2010 <= year <= 2020:
                pts += 5
                reasons.append("+5 modern")

    return pts, reasons


def main():
    if not IN.exists():
        print(f"! Input {IN} missing — run fetch_fns.py first.")
        return
    rows = [json.loads(l) for l in IN.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} entities from {IN.name}")

    scored = []
    for r in rows:
        pts, reasons = score(r)
        scored.append({**r, "score": pts, "score_reasons": "; ".join(reasons)})
    scored.sort(key=lambda x: -x["score"])

    # Export top-N + full file
    export_fields = [
        "score", "name_short", "inn", "ogrn", "region_name",
        "director", "registered", "found_by_query", "score_reasons",
        "name_full", "kpp", "kind",
    ]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=export_fields)
        w.writeheader()
        for row in scored:
            w.writerow({k: row.get(k, "") for k in export_fields})

    # Summary
    print(f"\n✓ Exported {len(scored)} leads → {OUT}")
    print()
    print("Score distribution:")
    buckets = {"≥100": 0, "80-99": 0, "60-79": 0, "40-59": 0, "20-39": 0, "<20": 0}
    for s in scored:
        sc = s["score"]
        if sc >= 100: buckets["≥100"] += 1
        elif sc >= 80: buckets["80-99"] += 1
        elif sc >= 60: buckets["60-79"] += 1
        elif sc >= 40: buckets["40-59"] += 1
        elif sc >= 20: buckets["20-39"] += 1
        else: buckets["<20"] += 1
    for k, v in buckets.items():
        print(f"  {k:>7}: {v}")

    print()
    print("=== TOP-30 ===")
    for i, s in enumerate(scored[:30], 1):
        print(f"{i:>3} {s['score']:>4}  {s['name_short'][:55]:<55}  {s['region_name'][:20]:<20}"
              f"  {s['found_by_query']}")


if __name__ == "__main__":
    main()
