"""
score_bo_leads.py — фильтрует и скорит лиды, собранные fetch_bo_okved.py.

Логика v2 (по-другому, чем в score_and_export.py):
    - Баллы от выручки — главный фактор (ранее его не было).
    - Скоринг имени — второстепенный (это и был фейл: ООО Альтернатива получает
      0 за нейтральное имя, но её выручка 2.2 млрд перебивает всё).
    - ОКВЭД 10.71 (короткое хранение — выпечка/пекарня) > 10.72 (сухари/печенье).
    - Регион — халяль-плотный / лог.хаб — мелкий бонус.

Выход: data/bakery-leads-okved.csv — отсортировано по score desc, с колонкой
       revenue_mln_rub — чтобы в топе не оказывались мелочи.

Порог: --min-revenue-mln 100 (по умолчанию).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "raw" / "bo_okved_raw.jsonl"
OUT = ROOT / "data" / "bakery-leads-okved.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Region codes -> short labels
REGION_ALIASES = {
    "МОСКВА": "Москва", "МОСКОВСКАЯ": "Московская обл",
    "САНКТ-ПЕТЕРБУРГ": "СПб", "ЛЕНИНГРАДСКАЯ": "Ленинградская обл",
    "ТАТАРСТАН": "Татарстан", "БАШКОРТОСТАН": "Башкортостан",
    "ДАГЕСТАН": "Дагестан", "ЧЕЧЕНСКАЯ": "Чечня", "ИНГУШЕТИЯ": "Ингушетия",
}

HALAL_DENSE = re.compile(r"татарстан|башкор|дагестан|чечен|ингуш|осетия|черкес|марий|удмурт|чуваш", re.I)
LOGISTICS = re.compile(
    r"москва|московская|петербург|ленинградская|свердловск|самарск|нижегородск|"
    r"ростовск|краснодар|воронежск|челябинск|новосибирск|пермск|тюменск", re.I)


def score(r: dict) -> tuple[int, list[str]]:
    pts = 0
    reasons: list[str] = []

    rev = r.get("revenue_tsd_rub") or 0
    rev_mln = rev / 1000.0

    # === Выручка — главный сигнал ===
    # 100 млн → 60, 300 → 75, 1 млрд → 90, 3 млрд → 105, 10 млрд → 120 (cap).
    if rev_mln > 0:
        rev_pts = int(min(120, 30 * math.log10(max(rev_mln, 1))))
        pts += rev_pts
        if rev_mln >= 10000:
            reasons.append(f"+{rev_pts} выручка {rev_mln/1000:.1f} млрд ₽")
        elif rev_mln >= 1000:
            reasons.append(f"+{rev_pts} выручка {rev_mln/1000:.2f} млрд ₽")
        else:
            reasons.append(f"+{rev_pts} выручка {rev_mln:.0f} млн ₽")

    # === ОКВЭД ===
    okved = (r.get("okved2") or "").strip()
    if okved.startswith("10.71"):
        pts += 15
        reasons.append("+15 ОКВЭД 10.71 (короткое хранение, основная цель)")
    elif okved.startswith("10.72"):
        pts += 5
        reasons.append("+5 ОКВЭД 10.72 (длительное хранение, второстепенно)")

    # === Регион ===
    reg = (r.get("region_name") or "")
    if HALAL_DENSE.search(reg):
        pts += 10
        reasons.append("+10 халяль-плотный регион")
    elif LOGISTICS.search(reg):
        pts += 8
        reasons.append("+8 лог.хаб / крупный регион")

    # === Форма собственности — МУП/ГУП/МП сильный минус ===
    name = (r.get("name_short") or "")
    if re.search(r"\bМУП\b|\bГУП\b|\bМП\b|МУНИЦ", name):
        pts -= 25
        reasons.append("-25 МУП/ГУП (соц.обязательства)")
    elif re.search(r"^АО |\"АО |^ПАО |^ЗАО |^ОАО ", name) or re.search(r"\bАО\b|\bПАО\b", name):
        pts += 5
        reasons.append("+5 АО/ПАО (зрелая компания)")

    # === Имя — лёгкие сигналы, не доминируют ===
    low = name.lower()
    if re.search(r"хлебозавод|хлебокомбинат|хлебпром", low):
        pts += 8
        reasons.append("+8 индустр. масштаб в названии")
    elif re.search(r"пекарн|бейкер|бейкери|кондитер|булочн|выпечк|каравай", low):
        pts += 5
        reasons.append("+5 профильное имя")
    if re.search(r"сосиск|пирожк|хот.дог|чебуреч|полуфабрикат", low):
        pts += 10
        reasons.append("+10 продуктовый таргет в имени")

    # === Свежесть отчётности ===
    if r.get("bfo_period") == "2025":
        pts += 3
        reasons.append("+3 сдал БФО 2025")

    return pts, reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-revenue-mln", type=float, default=100.0,
                    help="Минимальная выручка, млн ₽ (по умолчанию 100)")
    ap.add_argument("--include-no-revenue", action="store_true",
                    help="Включать компании без выручки (не сдавшие БФО)")
    args = ap.parse_args()

    if not IN.exists():
        print(f"! {IN} missing — сначала запусти fetch_bo_okved.py")
        return

    rows = [json.loads(l) for l in IN.read_text().splitlines() if l.strip()]
    print(f"Загружено {len(rows)} организаций из {IN.name}")

    threshold_tsd = args.min_revenue_mln * 1000
    filtered = []
    dropped_low = 0
    dropped_nodata = 0
    for r in rows:
        rev = r.get("revenue_tsd_rub")
        if rev is None or rev == 0:
            if args.include_no_revenue:
                filtered.append(r)
            else:
                dropped_nodata += 1
            continue
        if rev < threshold_tsd:
            dropped_low += 1
            continue
        filtered.append(r)

    print(f"Отфильтровано: {dropped_nodata} без данных, {dropped_low} ниже порога "
          f"{args.min_revenue_mln:.0f} млн ₽")
    print(f"Осталось кандидатов: {len(filtered)}")

    scored = []
    for r in filtered:
        pts, reasons = score(r)
        rev = r.get("revenue_tsd_rub") or 0
        scored.append({
            **r,
            "score": pts,
            "score_reasons": "; ".join(reasons),
            "revenue_mln_rub": round(rev / 1000, 1),
        })
    scored.sort(key=lambda x: (-x["score"], -(x["revenue_tsd_rub"] or 0)))

    fields = [
        "score", "revenue_mln_rub", "bfo_period",
        "name_short", "inn", "ogrn",
        "okved2", "region_name", "city", "address",
        "status_code", "status_date", "score_reasons",
    ]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in scored:
            w.writerow({k: row.get(k, "") for k in fields})

    # Summary
    print(f"\n✓ Экспорт {len(scored)} лидов → {OUT}")
    print()
    print("Распределение по выручке:")
    buckets = [(0.1, "100-300 млн"), (0.3, "300 млн-1 млрд"),
               (1, "1-3 млрд"), (3, "3-10 млрд"), (10, "10+ млрд")]
    for i, (thr_bln, lbl) in enumerate(buckets):
        lo = thr_bln * 1_000_000  # tsd rub
        hi = buckets[i + 1][0] * 1_000_000 if i + 1 < len(buckets) else float("inf")
        n = sum(1 for r in scored if lo <= (r.get("revenue_tsd_rub") or 0) < hi)
        print(f"  {lbl:>18}: {n}")

    print()
    print("=== ТОП-30 по score ===")
    print(f"{'#':>3} {'score':>5} {'выручка':>12}  {'ОКВЭД':<8} {'название':<52}  регион")
    for i, s in enumerate(scored[:30], 1):
        rev = s["revenue_mln_rub"]
        rev_str = f"{rev/1000:.2f} млрд" if rev >= 1000 else f"{rev:.0f} млн"
        print(f"{i:>3} {s['score']:>5} {rev_str:>12}  {s['okved2'][:8]:<8} "
              f"{s['name_short'][:52]:<52}  {s['region_name'][:22]}")


if __name__ == "__main__":
    main()
