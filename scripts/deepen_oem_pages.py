#!/usr/bin/env python3
"""One-shot deepener for thin OEM category pages (RU+EN).

Burger-patties and hotdog-sausages were deepened by hand. This script brings the
remaining 5 categories (meat, raw-meat, toppings, bakery, pastry) up to the same
depth (~900 words) by inserting two query-targeted sections before the
<h2>Сертификаты</h2> / <h2>Certificates</h2> anchor:

  • "Как выбрать поставщика … оптом" / "How to choose a wholesale … supplier"
  • "Оптовые условия и логистика" / "Wholesale terms and logistics"

Copy emphasises the *wholesale* ("оптом") phrasing buyers actually search, since
GSC shows demand is on "X оптом", not "private label". Idempotent: skips a page
that already contains the marker comment.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OEM = ROOT / "public" / "oem"
OEM_EN = ROOT / "public" / "en" / "oem"

MARKER = "<!-- deep-oem -->"

# (ru_intro, ru_logi) per slug
RU = {
    "meat": (
        "Когда вы ищете, где <strong>купить мясные и колбасные изделия оптом</strong> под свою марку, "
        "ключевое — стабильность рецептуры и сырья от партии к партии. Варёные, копчёные и "
        "сырокопчёные колбасы, сосиски, ветчины и деликатесы под СТМ должны иметь одинаковый вкус, "
        "цвет среза и выход на всех поставках, иначе сеть теряет узнаваемость продукта. Поэтому "
        "фиксируйте рецептуру и спецификацию в договоре и запрашивайте контроль партий.",
        "Поставку колбасных изделий оптом строим под объём: пилот от 500 кг/мес, серия 2–5 т/мес с "
        "фиксированной ценой и графиком. Отгрузка EXW Казань и из Казани по всей России "
        "и на экспорт в СНГ и ОАЭ. Под собственной маркой адаптируем рецептуру, фасовку (батон, "
        "нарезка, газовая среда) и оформление под канал — ретейл, HoReCa, дистрибуция."),
    "raw-meat": (
        "Если вы ищете, где <strong>купить фарш и мясные полуфабрикаты оптом</strong>, главное — "
        "стабильный состав, жирность и фракция помола. Фарш, формованные котлеты, тефтели, люля и "
        "заготовки под СТМ должны давать предсказуемый выход и одинаковую прожарку на потоке. "
        "Калибровка и шоковая заморозка сохраняют свежесть и убирают потери на размораживании.",
        "Сырое мясное оптом поставляем под объём: пилот от 500 кг/мес, серия 2–5 т/мес. Шоковая "
        "заморозка, фиксированная фракция и жирность под вашу рецептуру. Отгрузка EXW Казань и со "
        "Казани по РФ и на экспорт. Под СТМ адаптируем фасовку и оформление — для "
        "ретейла, HoReCa и дистрибуции."),
    "toppings": (
        "Когда вы выбираете, где <strong>купить топпинги для пиццы оптом</strong> (пепперони-топпинг, "
        "колбасные нарезки), важна термостабильность: топпинг не должен расплываться и пускать жир "
        "при запекании, а должен держать рисунок и форму на пицце. Калиброванная нарезка ускоряет "
        "сборку и даёт одинаковый вид пиццы на всех точках сети.",
        "Топпинги оптом поставляем нарезкой в фиксированной фасовке, пилот от 500 кг/мес, серия "
        "2–5 т/мес. Под СТМ подбираем толщину нарезки, диаметр и упаковку под вашу линию сборки. "
        "Отгрузка EXW Казань и со Казани по РФ и на экспорт — для пиццерий, "
        "производителей замороженной пиццы и HoReCa."),
    "bakery": (
        "Если вы ищете, где <strong>купить замороженную выпечку оптом</strong> под свою марку "
        "(татарская и классическая), главное — стабильная доготовка из заморозки без "
        "размораживания и одинаковый результат на любой печи. Эчпочмаки, перемячи, самса, "
        "слоёные и дрожжевые изделия под СТМ должны иметь предсказуемый вес и время доготовки.",
        "Замороженную выпечку оптом поставляем коробками с фиксированной фасовкой, пилот от "
        "500 кг/мес, серия 2–5 т/мес. Под собственной маркой адаптируем рецептуру, вес изделия и "
        "упаковку. Отгрузка EXW Казань и со Казани по РФ и на экспорт — для пекарен, "
        "кафе татарской кухни, столовых и стрит-фуда."),
    "pastry": (
        "Когда вы ищете, где <strong>купить кондитерские изделия оптом</strong> под свою марку "
        "(торты, пирожные, десерты), важны стабильная рецептура, внешний вид и срок годности. "
        "Кондитерка под СТМ должна выдерживать логистику и витрину без потери вида, поэтому "
        "фиксируйте спецификацию и условия хранения заранее.",
        "Кондитерские изделия оптом поставляем под объём: пилот от 500 кг/мес, серия 2–5 т/мес. "
        "Под собственной маркой подбираем рецептуру, порцию и упаковку. Отгрузка EXW Казань и со "
        "Казани по РФ и на экспорт — для кофеен, кафе, ретейла и HoReCa."),
}

EN = {
    "meat": (
        "When you look for where to <strong>buy meat and sausage products wholesale</strong> under "
        "your own brand, the key is recipe and raw-material consistency batch to batch. Cooked, "
        "smoked and dry-cured sausages, hams and delicacies under private label must have the same "
        "taste, slice colour and yield across every delivery, or the chain loses product "
        "recognition. Lock the recipe and specification into the contract and ask for batch control.",
        "We build wholesale sausage supply around volume: a pilot from 500 kg/month, a series of "
        "2–5 t/month with a fixed price and schedule. Shipping EXW Kazan "
        "warehouse across Russia and for export to the CIS and the UAE. Under your own brand we "
        "adapt recipe, format (baton, sliced, modified-atmosphere) and design to the channel — "
        "retail, HoReCa, distribution."),
    "raw-meat": (
        "If you are looking for where to <strong>buy minced meat and semi-finished products "
        "wholesale</strong>, the key is consistent composition, fat content and grind. Mince, "
        "formed patties, meatballs, lula and prepared items under private label must give a "
        "predictable yield and even cooking on the line. Calibration and blast freezing keep "
        "freshness and remove thawing losses.",
        "We supply raw-meat wholesale by volume: a pilot from 500 kg/month, a series of 2–5 "
        "t/month. Blast freezing, fixed grind and fat content to your recipe. Shipping EXW Kazan "
        "and from Kazan across Russia and for export. Under private label we adapt format and "
        "design — for retail, HoReCa and distribution."),
    "toppings": (
        "When you choose where to <strong>buy pizza toppings wholesale</strong> (pepperoni "
        "topping, sausage slices), heat stability matters: the topping must not spread or release "
        "fat when baked and must hold its pattern and shape on the pizza. Calibrated slicing "
        "speeds assembly and gives identical pizzas across all points of the chain.",
        "We supply toppings wholesale sliced in fixed packs, a pilot from 500 kg/month, a series "
        "of 2–5 t/month. Under private label we tune slice thickness, diameter and packaging to "
        "your assembly line. Shipping EXW Kazan and from Kazan across Russia and for export — "
        "for pizzerias, frozen-pizza producers and HoReCa."),
    "bakery": (
        "If you look for where to <strong>buy frozen pastry wholesale</strong> under your own "
        "brand (Tatar and classic), the key is consistent finishing from frozen with no thawing "
        "and the same result in any oven. Echpochmak, peremech, samsa, puff and yeast products "
        "under private label must have a predictable weight and finishing time.",
        "We supply frozen pastry wholesale in fixed-pack cases, a pilot from 500 kg/month, a "
        "series of 2–5 t/month. Under your own brand we adapt recipe, item weight and packaging. "
        "Shipping EXW Kazan and from Kazan across Russia and for export — for bakeries, Tatar "
        "cuisine cafes, canteens and street food."),
    "pastry": (
        "When you look for where to <strong>buy confectionery wholesale</strong> under your own "
        "brand (cakes, pastries, desserts), consistent recipe, appearance and shelf life matter. "
        "Private-label confectionery must withstand logistics and the display case without losing "
        "appearance, so fix the specification and storage conditions in advance.",
        "We supply confectionery wholesale by volume: a pilot from 500 kg/month, a series of 2–5 "
        "t/month. Under your own brand we tune recipe, portion and packaging. Shipping EXW Kazan "
        "and from Kazan across Russia and for export — for coffee shops, cafes, retail and "
        "HoReCa."),
}


RU_QUALITY = (
    "Для опта, ретейла и маркетплейсов важен полный пакет документов: декларация "
    "ЕАЭС, ХАССП, ISO 22000:2018 и действующий сертификат «Халяль». Вся продукция "
    "«Казанских Деликатесов» — халяль, произведена из говядины и/или птицы (конины) "
    "по стандартам халяль, с ВСД «Меркурий». Это снимает риски при входе в сети и "
    "даёт вам аргумент для конечного покупателя. Образец под вашу спецификацию "
    "делаем за 2–3 недели, от брифа до первой серийной отгрузки — 4–8 недель.")

EN_QUALITY = (
    "For wholesale, retail and marketplaces a full document package matters: an EAEU "
    "declaration, HACCP, ISO 22000:2018 and a valid Halal certificate. All Kazan "
    "Delicacies products are halal, made from beef and/or poultry to halal standards, "
    "with Mercury/Vetis veterinary records. This removes risk when entering chains and "
    "gives you an argument for the end customer. A sample to your specification takes "
    "2–3 weeks; from brief to first series shipment is 4–8 weeks.")


def block_ru(intro: str, logi: str) -> str:
    return (
        f"{MARKER}\n"
        "    <h2>Как выбрать поставщика оптом</h2>\n"
        f"    <div class=\"card\"><p style=\"margin-top:0\">{intro}</p></div>\n"
        "    <h2>Оптовые условия и логистика</h2>\n"
        f"    <div class=\"card\"><p style=\"margin-top:0\">{logi}</p></div>\n"
        "    <h2>Документы, халяль и сроки</h2>\n"
        f"    <div class=\"card\"><p style=\"margin-top:0\">{RU_QUALITY}</p></div>\n\n    ")


def block_en(intro: str, logi: str) -> str:
    return (
        f"{MARKER}\n"
        "    <h2>How to choose a wholesale supplier</h2>\n"
        f"    <div class=\"card\"><p style=\"margin-top:0\">{intro}</p></div>\n"
        "    <h2>Wholesale terms and logistics</h2>\n"
        f"    <div class=\"card\"><p style=\"margin-top:0\">{logi}</p></div>\n"
        "    <h2>Documents, halal and lead times</h2>\n"
        f"    <div class=\"card\"><p style=\"margin-top:0\">{EN_QUALITY}</p></div>\n\n    ")


def patch(path: Path, anchor: str, block: str) -> str:
    html = path.read_text(encoding="utf-8")
    if MARKER in html:
        return "skip (already deep)"
    if anchor not in html:
        return f"ANCHOR NOT FOUND ({anchor!r})"
    html = html.replace(anchor, block + anchor, 1)
    path.write_text(html, encoding="utf-8")
    return "patched"


def main() -> int:
    for slug, (intro, logi) in RU.items():
        p = OEM / f"{slug}.html"
        print(f"RU {slug:10} -> {patch(p, '<h2>Сертификаты</h2>', block_ru(intro, logi))}")
    for slug, (intro, logi) in EN.items():
        p = OEM_EN / f"{slug}.html"
        print(f"EN {slug:10} -> {patch(p, '<h2>Certificates</h2>', block_en(intro, logi))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
