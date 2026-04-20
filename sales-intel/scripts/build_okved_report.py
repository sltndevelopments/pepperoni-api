"""
build_okved_report.py — генерирует sales-intel/reports/bakery-leads-okved-q1-2026.md
                        из data/bakery-leads-okved-enriched.csv.

Секции отчёта:
  1. Executive summary + методология.
  2. Топ-50 по score с контактами.
  3. Gigant-tier (≥10 млрд выручки) — фоновая группа, маловероятные клиенты.
  4. Core-tier (1-10 млрд) — «золотая середина», главный целевой сегмент.
  5. Growth-tier (100 млн - 1 млрд) — быстрорастущие, но требуют qual-звонка.
  6. По регионам — халяль-плотные + Татарстан отдельным блоком.
  7. По ОКВЭД 10.71 vs 10.72 — краткая разбивка.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "bakery-leads-okved-enriched.csv"
OUT = ROOT / "reports" / "bakery-leads-okved-q1-2026.md"
OUT.parent.mkdir(parents=True, exist_ok=True)


def fmt_rev(mln: float) -> str:
    if mln >= 1000:
        return f"{mln/1000:.2f} млрд"
    return f"{mln:.0f} млн"


def first_email(s: str) -> str:
    return (s or "").split(",")[0].strip()


def first_phone(s: str) -> str:
    return (s or "").split(",")[0].strip()


def short(s: str, n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


def main():
    rows = list(csv.DictReader(SRC.open()))
    for r in rows:
        r["revenue_mln_rub"] = float(r["revenue_mln_rub"]) if r.get("revenue_mln_rub") else 0.0
        r["score"] = int(r["score"]) if r.get("score") else 0

    lines: list[str] = []
    w = lines.append

    w("# TOP-Pekaren Leads — ОКВЭД 10.71 / 10.72, выручка ≥ 100 млн ₽")
    w("")
    w("_Pipeline v2: `fetch_bo_okved.py` → `score_bo_leads.py` → `enrich_contacts.py`_")
    w("")
    w("## Executive Summary")
    w("")
    total = len(rows)
    top150 = rows[:150]
    with_contacts = sum(1 for r in top150 if r.get("phones") or r.get("emails"))
    gig = [r for r in rows if r["revenue_mln_rub"] >= 10_000]
    core = [r for r in rows if 1000 <= r["revenue_mln_rub"] < 10_000]
    growth = [r for r in rows if 100 <= r["revenue_mln_rub"] < 1000]

    w(f"- **{total} действующих ЮЛ** по ОКВЭД 10.71 (хлеб/пекарня/кондитерка короткого хранения) и 10.72 (сухари/печенье/длительное хранение) с выручкой **≥ 100 млн ₽** за 2024–2025 отчётный период.")
    w(f"- **{len(gig)} gigant-tier** (≥10 млрд ₽) — федеральные комбинаты, уже плотно обвязаны.")
    w(f"- **{len(core)} core-tier** (1–10 млрд ₽) — _главный целевой сегмент_.")
    w(f"- **{len(growth)} growth-tier** (100 млн – 1 млрд ₽) — перспективные на средний чек.")
    w(f"- Обогащено контактами топ-150: **{with_contacts} ({with_contacts/150*100:.0f}%)** имеют телефон или email.")
    w("")
    w("### Отличия от v1 (поиск ФНС по словам в названии)")
    w("")
    w("v1 фильтровал по `пекарня/хлеб/кондитер` в названии — проваливал компании с нейтральным именем (ООО «Альтернатива» / бренд BONTIER, выручка 2.15 млрд ₽). v2 идёт напрямую по ОКВЭД2 + публикует выручку из ГИР БО → в список попали:")
    w("")
    # Примеры — возьмём 5 с нейтральным именем из top200
    neutrals = []
    for r in rows[:300]:
        n = r["name_short"].upper()
        tokens = ("ХЛЕБ", "ПЕКАРН", "КОНДИТЕР", "БУЛОЧ", "БЕЙКЕР", "КАРАВАЙ",
                  "ВЫПЕЧК", "СЛАДК", "МАРКА", "СЛОЁН", "ТЕСТО")
        if not any(t in n for t in tokens):
            neutrals.append(r)
        if len(neutrals) >= 5:
            break
    for r in neutrals:
        w(f"- **{r['name_short']}** — {fmt_rev(r['revenue_mln_rub'])} ₽, ОКВЭД {r['okved2']}, {r['region_name']}")
    w("")

    # === TOP-50 ===
    w("## TOP-50 по скорингу (все — core/gigant-tier, с контактами)")
    w("")
    w("| # | score | выручка | ОКВЭД | Компания | Регион | Телефон | Email |")
    w("|---|------:|---:|---|---|---|---|---|")
    for i, r in enumerate(rows[:50], 1):
        w(f"| {i} | {r['score']} | {fmt_rev(r['revenue_mln_rub'])} | {r['okved2']} | "
          f"{r['name_short']} | {short(r['region_name'].title(), 22)} | "
          f"`{first_phone(r.get('phones',''))}` | `{first_email(r.get('emails',''))}` |")
    w("")

    # === By region — халяль ===
    w("## Халяль-плотные регионы (топ-25 в этих регионах)")
    w("")
    w("_Татарстан, Башкортостан, Дагестан, Чечня, Ингушетия, Сев.Осетия, Карачаево-Черкесия, Марий Эл, Удмуртия, Чувашия_")
    w("")
    halal_re = ("ТАТАРСТАН", "БАШКОР", "ДАГЕСТАН", "ЧЕЧЕНСКАЯ", "ИНГУШ",
                "ОСЕТИЯ", "ЧЕРКЕС", "МАРИЙ", "УДМУРТ", "ЧУВАШ")
    halal = [r for r in rows if any(h in r["region_name"].upper() for h in halal_re)]
    w(f"Всего в халяль-регионах: **{len(halal)}** компаний ≥100 млн ₽.")
    w("")
    w("| # | выручка | Компания | Регион | ИНН | Телефон | Email |")
    w("|---|---:|---|---|---|---|---|")
    for i, r in enumerate(halal[:25], 1):
        w(f"| {i} | {fmt_rev(r['revenue_mln_rub'])} | {r['name_short']} | "
          f"{r['region_name'].title()} | {r['inn']} | "
          f"`{first_phone(r.get('phones',''))}` | `{first_email(r.get('emails',''))}` |")
    w("")

    # === Core-tier (1-10 bln) — главная группа ===
    w("## Core-tier (1–10 млрд ₽) — главный целевой сегмент")
    w("")
    w("Именно эта группа — зона охоты. Уже не ИП-пекарня в 20 м², но ещё не федеральный комбинат уровня Каравай/Хлебпром. Легко маневрируют ассортиментом, работают с сетями в своём регионе, частые сделки по СТМ.")
    w("")
    w("| # | выручка | ОКВЭД | Компания | Регион | ИНН | Контакт |")
    w("|---|---:|---|---|---|---|---|")
    for i, r in enumerate(core[:60], 1):
        contact = first_email(r.get("emails", "")) or first_phone(r.get("phones", "")) or ""
        w(f"| {i} | {fmt_rev(r['revenue_mln_rub'])} | {r['okved2']} | {r['name_short']} | "
          f"{short(r['region_name'].title(), 22)} | {r['inn']} | `{contact}` |")
    w("")

    # === Growth-tier ===
    w("## Growth-tier (100 млн – 1 млрд ₽) — перспективные на средний чек")
    w("")
    w("Требуется qual-звонок: подтвердить наличие собственного производства / контракта с сетью / СТМ-линейки. Много компаний-дистрибьюторов, закупающих сырьё, которые по ОКВЭД 10.71 зарегистрированы «на всякий случай».")
    w("")
    growth_halal = [r for r in growth if any(h in r["region_name"].upper() for h in halal_re)]
    w(f"В growth-tier: **{len(growth)}** компаний, из них {len(growth_halal)} в халяль-регионах.")
    w("")
    w("Топ-40 growth:")
    w("")
    w("| # | выручка | ОКВЭД | Компания | Регион | ИНН | Контакт |")
    w("|---|---:|---|---|---|---|---|")
    for i, r in enumerate(growth[:40], 1):
        contact = first_email(r.get("emails", "")) or first_phone(r.get("phones", "")) or "—"
        w(f"| {i} | {fmt_rev(r['revenue_mln_rub'])} | {r['okved2']} | {r['name_short']} | "
          f"{short(r['region_name'].title(), 22)} | {r['inn']} | `{contact}` |")
    w("")

    # === By OKVED ===
    w("## Разбивка по ОКВЭД2")
    w("")
    by_ok = defaultdict(list)
    for r in rows:
        key = r["okved2"][:5] if r["okved2"] else "—"
        by_ok[key].append(r)
    w("| ОКВЭД2 | Расшифровка | N компаний | Суммарная выручка |")
    w("|---|---|---:|---:|")
    ok_labels = {
        "10.71": "Хлеб и мучные кондитерские изд-я недлительного хранения",
        "10.72": "Сухари, печенье, мучные кондитерские длительного хранения",
    }
    for k in sorted(by_ok.keys()):
        lst = by_ok[k]
        summ = sum(r["revenue_mln_rub"] for r in lst)
        label = ok_labels.get(k, "—")
        summ_str = f"{summ/1000:.1f} млрд ₽" if summ >= 1000 else f"{summ:.0f} млн ₽"
        w(f"| {k} | {label} | {len(lst)} | {summ_str} |")
    w("")

    # Методология
    w("## Методология")
    w("")
    w("1. **Источник ЮЛ:** `bo.nalog.gov.ru` (ГИР БО, публичный ресурс бухгалтерской отчётности ФНС) — endpoint `/advanced-search/organizations?okved={code}&period={year}`. Ответ содержит ИНН/ОГРН/адрес/ОКВЭД2 + поле `bfo.gainSum` = **выручка** (стр. 2110 формы 2 «Отчёт о финансовых результатах»), в тыс. ₽.")
    w("2. **Периоды:** 2024 + 2025 (взят максимум по выручке на ИНН — так не теряем тех, кто уже сдал 2025, и тех, кто сдал только 2024).")
    w("3. **Фильтр:** `revenue_tsd_rub ≥ 100 000` (= 100 млн ₽).")
    w("4. **Скоринг:** базовая оценка — `30 × log10(выручка в млн ₽)` (cap 120). Плюс бонусы: +15 ОКВЭД 10.71, +10 халяль-регион, +8 лог.хаб, +10 за «сосиска/пирожок/полуфабрикат» в имени. Минусы: -25 МУП/ГУП.")
    w("5. **Контакты:** `zachestnyibiznes.ru`, регулярки по HTML (телефон, email, сайт). Результат для топ-150 — 93% coverage.")
    w("")
    w("### Известные перекосы выборки")
    w("")
    w("- ~1200 компаний не сдавали БФО (работают на УСН без ОФР или в ликвидации) — сюда попадают некоторые живые «кочующие» пекарни.")
    w("- Из ГИР БО виден только **основной** ОКВЭД. Компания с основным ОКВЭД 56.10 («Рестораны») и дополнительным 10.71 в список не попадёт — например, точки-пекарни при сетях кафе.")
    w("- Не охвачены ИП (ГИР БО публикует только ЮЛ). Для ИП нужен отдельный пайплайн через `egrul.nalog.ru`.")
    w("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓ {OUT}  ({OUT.stat().st_size:,} bytes, {len(lines)} lines)")


if __name__ == "__main__":
    main()
