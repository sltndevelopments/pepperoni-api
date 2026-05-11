"""
build_sausage_report.py — собирает reports/sausage-in-dough-producers-q1-2026.md
                         из data/bakery-leads-sausage-tested.csv.

Цель: супер-точечный шорт-лист под продукт "сосиска / мини-колбаска для сосиски
      в тесте и хот-догов". Компании, у которых этот SKU уже есть в каталоге,
      не придётся учить делать хот-дог — они только меняют поставщика сосисок.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "bakery-leads-sausage-tested.csv"
OUT = ROOT / "reports" / "sausage-in-dough-producers-q1-2026.md"


def fmt_rev(mln: float) -> str:
    if mln >= 1000:
        return f"{mln/1000:.2f} млрд"
    return f"{mln:.0f} млн"


def first(s: str, n: int = 1) -> str:
    parts = [p.strip() for p in (s or "").split(",") if p.strip()]
    return ", ".join(parts[:n])


def main():
    rows = list(csv.DictReader(SRC.open()))
    for r in rows:
        r["revenue_mln_rub"] = float(r["revenue_mln_rub"]) if r.get("revenue_mln_rub") else 0.0

    strong = [r for r in rows if r["classification"] == "yes_sausage_in_dough"]
    related = [r for r in rows if r["classification"] == "yes_hotdog_or_meat_pirozhki"]
    kolbaska = [r for r in rows if r["classification"] == "yes_kolbaska_pastry"]
    mention = [r for r in rows if r["classification"] == "mention_only"]
    meat = [r for r in rows if r["classification"] == "meat_pastries_only"]
    no_site = [r for r in rows if r["classification"] == "unknown"]
    no_match = [r for r in rows if r["classification"] == "no"]

    for lst in (strong, related, kolbaska, mention, meat, no_site, no_match):
        lst.sort(key=lambda x: -x["revenue_mln_rub"])

    lines: list[str] = []
    w = lines.append

    w("# Сосиска-в-тесте producers — Q1 2026")
    w("")
    w("Точечный шорт-лист из 150 топ-лидов по ОКВЭД 10.71/10.72 + выручка ≥ 100 млн ₽.  ")
    w("Каждый сайт проверен автоматически (`scan_sausage_in_dough.py`): homepage + "
      "до 12 каталожных страниц, grep по `сосис`, `хот-дог`, `колбаск в тесте`, "
      "`булочка с сосиской`, `пирожок с мясом`.")
    w("")
    w("## TL;DR")
    w("")
    w(f"| Класс | N | Доля |")
    w(f"|---|---:|---:|")
    total = len(rows)
    for lbl, lst in (("★ Точно делают сосиску в тесте", strong),
                     ("✓ Делают хот-доги / мясные пирожки", related),
                     ("✓ Делают «колбаску в тесте/слойке»", kolbaska),
                     ("· Слово есть, но не точно в контексте", mention),
                     ("· Только мясные пирожки, без сосисок", meat),
                     ("  ничего не найдено на сайте", no_match),
                     ("? сайт недоступен / не найден", no_site)):
        w(f"| {lbl} | {len(lst)} | {len(lst)/total*100:.0f}% |")
    w("")
    w(f"**Итого точечная выборка для outreach — {len(strong) + len(related) + len(kolbaska)} компаний** "
      f"(сумма выручки ≈ **{sum(r['revenue_mln_rub'] for r in strong+related+kolbaska)/1000:.1f} млрд ₽** в год).")
    w("")

    # === 1. Strong tier ===
    w("## ★ Tier 1 — СОСИСКА В ТЕСТЕ уже в каталоге")
    w("")
    w("Это компании, у которых позиция «сосиска в тесте» / «булочка с сосиской» уже "
      "в продуктовой линейке на сайте. Это означает:")
    w("")
    w("- Линия оборудования настроена (слоёное/дрожжевое тесто + сосиска).")
    w("- Закупка сосисок в промышленном формате уже идёт → у них есть текущий поставщик.")
    w("- Pepperoni предлагает не учить их делать новый SKU, а **заменить текущего поставщика сосисок** на халяль-качество по лучшей цене.")
    w("")
    w("| # | Выручка | Компания | Регион | Сайт | Что уже делают | Контакт |")
    w("|---|---:|---|---|---|---|---|")
    for i, r in enumerate(strong, 1):
        site = r["website_checked"].replace("http://", "").replace("https://", "").rstrip("/")
        snippet = r["evidence_snippet"][:100].replace("|", "/")
        emails = first(r.get("emails", ""), 1) or "—"
        phones = first(r.get("phones", ""), 1) or "—"
        contact = f"`{emails}`<br/>`{phones}`"
        w(f"| {i} | {fmt_rev(r['revenue_mln_rub'])} | **{r['name_short']}** | "
          f"{r['region_name'].title()} | [{site}]({r['website_checked']}) | "
          f"{snippet}… | {contact} |")
    w("")
    w("### Evidence (что именно нашли на сайте)")
    w("")
    for r in strong:
        w(f"**{r['name_short']}** — {r['region_name'].title()}, {fmt_rev(r['revenue_mln_rub'])} ₽, ИНН {r['inn']}")
        w("")
        w(f"- URL: {r['evidence_url']}")
        w(f"- Сниппет: _«…{r['evidence_snippet']}…»_")
        w(f"- Упоминаний «сосиска»: **{r['cnt_sausage_in_dough']} в контексте теста**, "
          f"{r['cnt_sausage_generic']} общих, {r['cnt_hot_dog']} «хот-дог»")
        w(f"- Email: `{r.get('emails','')}`")
        w(f"- Тел.: `{r.get('phones','')}`")
        w("")

    # === 2. Related tier ===
    w("## ✓ Tier 2 — делают хот-доги / мясные пирожки")
    w("")
    w("Компании с горячим направлением «хот-дог», «пирожок с сосиской», «булочка с сосиской» — им нужна та же сосиска-заготовка. "
      "Вероятность, что и в тесто её заворачивают — очень высокая, но автоматически страница с точной позицией не нашлась.")
    w("")
    w("| # | Выручка | Компания | Регион | Сайт | ИНН | Контакт |")
    w("|---|---:|---|---|---|---|---|")
    for i, r in enumerate(related, 1):
        site = r["website_checked"].replace("http://", "").replace("https://", "").rstrip("/")
        emails = first(r.get("emails", ""), 1) or "—"
        w(f"| {i} | {fmt_rev(r['revenue_mln_rub'])} | {r['name_short']} | "
          f"{r['region_name'].title()} | [{site}]({r['website_checked']}) | "
          f"{r['inn']} | `{emails}` |")
    w("")

    # === 3. Mention only ===
    if mention or kolbaska:
        w("## · Tier 3 — слово встречается, но не в основном каталоге")
        w("")
        w("Возможно вариативно (сезонно, в единичном SKU, или это ссылка на пресс-релиз/блог). Требуется ручная проверка.")
        w("")
        for r in kolbaska + mention:
            site = r["website_checked"].replace("http://", "").replace("https://", "").rstrip("/")
            w(f"- **{r['name_short']}** — {fmt_rev(r['revenue_mln_rub'])} ₽, "
              f"{r['region_name'].title()}, [{site}]({r['website_checked']})  \n"
              f"  _«…{r['evidence_snippet'][:150]}…»_")
        w("")

    # === 4. Без сайта — unknown ===
    if no_site:
        w("## ? Tier 4 — нет сайта в открытых источниках")
        w("")
        w("Компании в топ-150 по выручке, но в ГИР БО / zachestnyibiznes сайт не указан. "
          "Требуется ручной поиск в Яндекс/2ГИС + обзвон.")
        w("")
        w("| # | Выручка | Компания | Регион | ИНН |")
        w("|---|---:|---|---|---|")
        for i, r in enumerate(no_site[:25], 1):
            w(f"| {i} | {fmt_rev(r['revenue_mln_rub'])} | {r['name_short']} | "
              f"{r['region_name'].title()} | {r['inn']} |")
        w("")

    # === Limitations ===
    w("## Ограничения методики")
    w("")
    w("1. **Сайты на JS-рендеринге** (React/Next.js без SSR) отдают почти пустой HTML — мы ловим 0 упоминаний. Это ≈ 15–20 компаний из \"no\".")
    w("2. **Каталог в PDF / картинках** — текст не индексируется HTML-парсером. Типично для старых хлебокомбинатов.")
    w("3. **Региональные сетевые пекарни** (Бегемаг, Булкин, Хлебный дом) могут продавать через сеть «наша кухня» без публичного каталога SKU — мы их поймали только по Бегемагу, остальные требуют точечной проверки.")
    w("4. **B2B-производители для HoReCa/ритейла** (ООО «Альтернатива» / BONTIER) часто прячут полный ассортимент за «запросите у менеджера», и тогда на сайте есть только маркетинговое упоминание SKU.")
    w("")
    w("### Что ещё можно сделать")
    w("")
    w("- Поднять порог `--top` до 300 (+150 компаний 300-700 млн ₽).")
    w("- Для Tier 4 (без сайта) — прогнать Яндекс.Поиск `<INN> официальный сайт` или 2ГИС Places API.")
    w("- Для Tier 2 → сделать ручной обзвон «есть ли сосиски в тесте в продуктовой линейке».")
    w("- Для Tier 1 → сразу отправить коммерческое: «у нас халяль-сосиски для сосиски-в-тесте от X ₽/кг, лучше вашего текущего поставщика на Y%».")
    w("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓ {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
