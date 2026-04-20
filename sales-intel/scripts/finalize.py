"""
finalize.py — post-process bakery-leads-enriched.csv:
  1. Filter out obvious false positives (oil&gas "Бейкер Хьюз", language schools, hotels, etc.)
  2. Filter out companies in liquidation (директор=ЛИКВИДАТОР)
  3. Enrich with target_segment label (A/B/C tier)
  4. Produce two outputs:
       - data/bakery-leads-top200.csv  — cleaned, ready-for-sales
       - data/bakery-leads-TOP.md       — markdown top-30 with commentary
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "bakery-leads-enriched.csv"
OUT_CSV = ROOT / "data" / "bakery-leads-top200.csv"
OUT_MD = ROOT / "data" / "bakery-leads-TOP.md"

# Words/phrases that indicate the company is NOT a bakery producer,
# despite name matching our query.
NOISE_PATTERNS = [
    r"\bхьюз\b",                     # Baker Hughes (oil&gas)
    r"нефтян|нефтегаз|буров",        # oil
    r"иностранных языков|школа|образова|учебн",   # language schools
    r"логистик|транспорт|перевоз|такси",          # logistics
    r"хост|хостинг|интернет|IT|ай[\-\s]?ти|digital",  # IT
    r"тревел|тур|туризм|hotel|отел",  # travel
    r"фитнес|фит[\-\s]?клуб",          # fitness
    r"автомоб|шины|колес",            # auto
    r"стомат|медиц|аптек|клиник",     # medical
    r"пицц[ае]|pizza",                # pizza (too different)
    r"кофе|кафе|ресторан|bar\b|бар\b|паб\b|столов",  # HoReCa (not producers)
    r"магазин\b|маркет\b|shop\b",     # retail
    r"строй|строительн|застройщик",    # construction
    r"охота|рыболов|кфх|фермер",       # agri / hunting
    r"хостел|общежит",                 # hostels
    r"аграрн|сельхоз|агроном|агрокомплекс|племсовхоз",  # agro
    r"апп\b|app\b|мобильн",            # mobile apps
    r"реклам|маркетинг",               # advertising
    r"энерд?ж?и|энерго",               # energy
    r"бух\b|консалт|юрид|правов",      # services
    r"студи[яи]|производство видео",   # studios
]


def is_noise(name: str) -> bool:
    n = name.lower()
    for p in NOISE_PATTERNS:
        if re.search(p, n):
            return True
    return False


def in_liquidation(director: str) -> bool:
    d = (director or "").lower()
    return "ликвидатор" in d or "конкурсный управляющий" in d


def tier(score: int) -> str:
    if score >= 90: return "A"
    if score >= 70: return "B"
    if score >= 50: return "C"
    return "D"


def main():
    rows = list(csv.DictReader(IN.open()))
    print(f"Input: {len(rows)} leads")

    # Clean
    cleaned = []
    drop_reasons = {"noise": 0, "liquidation": 0}
    for r in rows:
        if is_noise(r["name_short"] + " " + r.get("name_full", "")):
            drop_reasons["noise"] += 1
            continue
        if in_liquidation(r.get("director", "")):
            drop_reasons["liquidation"] += 1
            continue
        r["tier"] = tier(int(r["score"]))
        cleaned.append(r)

    print(f"After filter: {len(cleaned)} (dropped {sum(drop_reasons.values())})")
    for k, v in drop_reasons.items():
        print(f"  – {k}: {v}")

    # Sort by score desc, then by whether contacts present
    cleaned.sort(key=lambda x: (-int(x["score"]), 0 if x.get("phones") else 1))

    # Take top-200
    top200 = cleaned[:200]

    # Write CSV
    fieldnames = ["tier", "score", "name_short", "inn", "region_name",
                  "director", "registered", "phones", "emails", "sites",
                  "found_by_query", "score_reasons", "name_full", "ogrn", "kpp", "kind"]
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in top200:
            w.writerow(r)
    print(f"\n✓ CSV: {OUT_CSV}  ({len(top200)} leads)")

    # Markdown report — top 30 with commentary
    def fmt_director(d):
        if not d: return "—"
        return d.replace("Генеральный директор:", "").replace("ГЕНЕРАЛЬНЫЙ ДИРЕКТОР:", "") \
                .replace("Директор:", "").replace("ДИРЕКТОР:", "").strip().title()[:40]

    def fmt_site(s):
        if not s: return ""
        sites = s.split(",")
        clean = [x.strip().rstrip("/") for x in sites if x.strip()]
        # prefer ones that look like real sites
        priority = [x for x in clean if not any(bad in x for bad in (".jpg", ".png", ".svg", ".xml", ".css"))]
        return priority[0] if priority else clean[0]

    lines = []
    lines.append("# Pepperoni Sales Intel — Топ региональных пекарен и мясопереработчиков")
    lines.append("")
    lines.append(f"**Источник:** ФНС ЕГРЮЛ + обогащение контактами через zachestnyibiznes.ru  ")
    lines.append(f"**Активных ЮЛ в базе:** 1240  ")
    lines.append(f"**Отфильтровано шум/ликвидация:** {sum(drop_reasons.values())}  ")
    lines.append(f"**Обогащено контактами:** 100  ")
    lines.append(f"**CSV:** `data/bakery-leads-top200.csv`")
    lines.append("")
    lines.append("## Цель")
    lines.append("Найти **региональных B2B-производителей хлебобулочных и мясных полуфабрикатов**, которые потенциально могут стать повторением кейса «Русь-Бейкери» — заказывать у Pepperoni сосиски/колбасы для своих готовых изделий (сосиски-в-тесте, пирожки, хот-доги), которые они поставляют в федеральные сети (X5, Магнит, ВкусВилл, Лента).")
    lines.append("")
    lines.append("## Tier'ы")
    lines.append("")
    lines.append("- **A (90+ баллов)**: название прямо указывает на профиль + юр.форма ООО/АО + приоритетный регион.")
    lines.append("- **B (70-89)**: либо ближе к профилю, либо хуже регион/форма.")
    lines.append("- **C (50-69)**: косвенно релевантные, на ревизию.")
    lines.append("- **D (<50)**: шум, оставлены для полноты.")
    lines.append("")
    lines.append("## TOP-30 кандидатов (tier A + B)")
    lines.append("")

    for i, r in enumerate(top200[:30], 1):
        name = r["name_short"].strip().replace('"', '')
        inn = r["inn"]
        region = r["region_name"]
        phones = r.get("phones", "").strip() or "—"
        emails = r.get("emails", "").strip() or "—"
        site = fmt_site(r.get("sites", ""))
        director = fmt_director(r.get("director", ""))

        lines.append(f"### {i}. [{r['tier']}/{r['score']}] {name}")
        lines.append(f"- ИНН: `{inn}`  |  Регион: {region}")
        lines.append(f"- Руководитель: {director}")
        if r.get("registered"):
            lines.append(f"- Зарегистрирована: {r['registered']}")
        if phones != "—":
            lines.append(f"- 📞 {phones}")
        if emails != "—":
            lines.append(f"- ✉ {emails}")
        if site:
            lines.append(f"- 🌐 {site}")
        lines.append(f"- Триггер: «{r['found_by_query']}»")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**Полный список** — 200 кандидатов в `data/bakery-leads-top200.csv` (tier A: "
                 f"{sum(1 for r in top200 if r['tier']=='A')}, "
                 f"B: {sum(1 for r in top200 if r['tier']=='B')}, "
                 f"C: {sum(1 for r in top200 if r['tier']=='C')}, "
                 f"D: {sum(1 for r in top200 if r['tier']=='D')}).")
    lines.append("")
    lines.append("## Что делать дальше")
    lines.append("")
    lines.append("1. Передать CSV в отдел продаж для квалификации по топ-100 (первые 2 недели — обзвон / email).")
    lines.append("2. Для каждого tier-A составить персональный питч на основе кейса Русь-Бейкери: «мы уже стабильно поставляем сосиски для их СТМ в X5».")
    lines.append("3. Повторный прогон раз в квартал — для новых регистраций и освежения контактов.")
    lines.append("4. Доп. обогащение платными источниками (Контур.Фокус / СПАРК) — для tier-A добавить **выручку и штат** (разделит «настоящих производителей» от «кафе с красивым названием»).")

    OUT_MD.write_text("\n".join(lines))
    print(f"✓ Markdown: {OUT_MD}")


if __name__ == "__main__":
    main()
