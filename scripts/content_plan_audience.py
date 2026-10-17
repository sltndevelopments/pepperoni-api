#!/usr/bin/env python3
"""Content-plan 2026-10-16 items 5, 6, 12, 14.

Catalog-backed audience pages. No invented SLA, oven tests, client volumes
or exclusivity. KD-012 stays out. Item 7 (samples / pilot) lives on
/kak-zakazat via gen_how_to_order.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import content_plan_pages as cp
from site_facts import FACTS, cert_line_en, cert_line_ru, sku_count

PUBLIC = Path(__file__).resolve().parent.parent / "public"
TRANSLATIONS = Path(__file__).resolve().parent / "translations.json"
SETEY_SKUS = tuple(f"KD-{i:03d}" for i in list(range(25, 35)) + list(range(36, 46)))
HOTDOG_CHILL = tuple(f"KD-{i:03d}" for i in range(19, 25))
COFFEE_SKUS = ("KD-055", "KD-057", "KD-058", "KD-059", "KD-060",
               "KD-062", "KD-063", "KD-064", "KD-067", "KD-068")
TR = json.loads(TRANSLATIONS.read_text(encoding="utf-8")) if TRANSLATIONS.exists() else {}
N = sku_count()
PHONE = FACTS["company"]["phone"]
MOQ = FACTS["terms"]["moq"]
BASIS = FACTS["terms"]["basis"]
PL_MIN = FACTS["terms"]["private_label_min"]


def _en_name(p: dict) -> str:
    clean = " ".join(str(p.get("name") or "").split())
    return TR.get("products", {}).get(clean.lower()) or clean


def _named(p: dict, lang: str) -> dict:
    if lang == "en":
        q = dict(p)
        q["name"] = _en_name(p)
        return q
    return p


def _barcode_table(products: list[dict], lang: str) -> str:
    head = ("SKU", "Название", "EAN", "Масса", "Срок", "Хранение", "Цена EXW") if lang == "ru" else (
        "SKU", "Name", "EAN", "Weight", "Shelf life", "Storage", "EXW price")
    rows = []
    for p in products:
        q = _named(p, lang)
        ean = str(p.get("barcode") or "—")
        rows.append(
            "<tr>"
            f'<td><a href="{cp.product_url(p["sku"], lang)}">{p["sku"]}</a></td>'
            f"<td>{q['name']}</td><td>{ean}</td>"
            f"<td>{cp.weight_label(p)}</td>"
            f"<td>{p.get('shelfLife') or '—'}</td>"
            f"<td>{p.get('storage') or '—'}</td>"
            f"<td>{cp.price_label(p, lang)}</td></tr>"
        )
    note = (
        "EAN — поле barcode из каталога. Цена EXW Казань с НДС, как на карточке."
        if lang == "ru" else
        "EAN is the catalog barcode field. EXW Kazan price incl. VAT, same as the card."
    )
    return (
        "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head)
        + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table><p>" + note + "</p>"
    )


def _links(lang: str) -> str:
    if lang == "ru":
        return (
            '<p>Смежные страницы: '
            '<a href="/kak-zakazat">как заказать</a> · '
            '<a href="/kak-zakazat#samples">образцы и пробная партия</a> · '
            '<a href="/price">прайс</a> · '
            '<a href="/dlya-setey">сети</a> · '
            '<a href="/dlya-distributorov">дистрибьюторы</a> · '
            '<a href="/dlya-horeca">HoReCa</a> · '
            '<a href="/sosiski-dlya-hotdog">сосиски для хот-догов</a> · '
            '<a href="/dlya-azs">АЗС</a> · '
            '<a href="/vyipechka-halyal">выпечка</a> · '
            '<a href="/zamorozhennaya-vypechka-dlya-kofeen">выпечка для кофеен</a> · '
            '<a href="/chak-chak-optom">чак-чак оптом</a> · '
            '<a href="/halyal-vypechka-optom-dlya-pekaren">выпечка для пекарен</a> · '
            '<a href="/cases">кейсы</a>.</p>'
        )
    return (
        '<p>Related: '
        '<a href="/en/kak-zakazat">how to order</a> · '
        '<a href="/en/kak-zakazat#samples">samples and pilot</a> · '
        '<a href="/en/price">price list</a> · '
        '<a href="/en/dlya-setey">retail chains</a> · '
        '<a href="/en/dlya-distributorov">distributors</a> · '
        '<a href="/en/dlya-horeca">HoReCa</a> · '
        '<a href="/en/sosiski-dlya-hotdog">hot-dog sausages</a> · '
        '<a href="/en/dlya-azs">fuel stations</a> · '
        '<a href="/en/vyipechka-halyal">bakery</a> · '
        '<a href="/en/zamorozhennaya-vypechka-dlya-kofeen">bakery for coffee shops</a> · '
        '<a href="/en/chak-chak-optom">chak-chak wholesale</a> · '
        '<a href="/en/halyal-vypechka-optom-dlya-pekaren">bakery for bakeries</a> · '
        '<a href="/en/cases">cases</a>.</p>'
    )


def write_setey() -> None:
    data = cp.catalog()
    products = cp.by_sku(data, *SETEY_SKUS)
    cert_ru, cert_en = cert_line_ru(), cert_line_en()
    for lang in ("ru", "en"):
        shown = [_named(p, lang) for p in products]
        table = _barcode_table(products, lang)
        if lang == "ru":
            title = "Халяль продукция для розничных сетей — поставщик | Казанские Деликатесы"
            desc = (
                f"Поставщик халяль продукции для розничных сетей: {len(products)} SKU из каталога "
                f"(KD-025–034, 036–045), EAN с карточек, {MOQ}, {BASIS}. "
                f"{cert_ru}."
            )
            h1 = "Халяль-продукция для розничных сетей"
            body = (
                f"<p class=\"lead\">Страница для закупщика сети: матрица из действующего "
                f"каталога, штрихкод, срок и хранение с карточки, пакет документов к отгрузке. "
                f"Имена сетей и объёмы — только на <a href=\"/cases\">/cases</a>, если там уже "
                f"опубликованы. Проценты сервиса и отсрочку на этой странице не публикуем.</p>"
                f"<p>{cert_ru}</p>"
                f"<h2>Матрица из каталога ({len(products)} SKU)</h2>{table}"
                f"<h2>Документы для РЦ</h2><ul>"
                f"<li>Сертификат халяль ДУМ РТ (проверка — <a href=\"/halal\">/halal</a>)</li>"
                f"<li>Декларация соответствия, ВСД (ФГИС «Меркурий»), «Честный знак», ЭТрН</li>"
                f"<li>EAN — в таблице, как в products.json</li></ul>"
                f"<p>Протоколы испытаний, QR по смене и SLA в процентах на этой странице нет: "
                f"их нет в реестре доказательств.</p>"
                f"<h2>Условия</h2><div class=\"card\"><ul>"
                f"<li>Базис {BASIS}, минимум {MOQ}</li>"
                f"<li>Образцы и пробная паллета — <a href=\"/kak-zakazat#samples\">как заказать</a></li>"
                f"<li>СТМ от {PL_MIN} — <a href=\"/kontraktnoe-proizvodstvo\">контрактное производство</a></li>"
                f"<li>Ритм отгрузок — по договору, без выдуманного «еженедельно»</li></ul></div>"
                + _links("ru")
            )
            faq = [
                ("Какие SKU для полки?",
                 f"На этой странице — {len(products)} позиций варёных, ветчин, копчёных и казылыка "
                 "из текущего каталога. Пепперони, сосиски и выпечка — смежные страницы, не дубль матрицы."),
                ("Какой сертификат для мяса?",
                 "Основной халяль ДУМ РТ №0008; №614A/2024 тоже действует. Проверка — /halal."),
                ("Есть ли кейс с названием сети?",
                 "Названия покупателей только на /cases. Здесь их не повторяем и не добавляем новых."),
            ]
        else:
            title = "Halal products for retail chains — supplier | Kazan Delicacies"
            desc = (
                f"Halal supplier for retail chains: {len(products)} catalog SKUs "
                f"(KD-025–034, 036–045), card EAN, {MOQ}, EXW Kazan. {cert_en}."
            )
            h1 = "Halal products for retail chains"
            body = (
                f"<p class=\"lead\">Buyer page: live-catalog matrix, barcode, shelf life and "
                f"storage from the card, shipping documents. Chain names and volumes only on "
                f"<a href=\"/en/cases\">/en/cases</a> where already published. "
                f"Service percentages are not published here.</p>"
                f"<p>{cert_en}</p>"
                f"<h2>Catalog matrix ({len(products)} SKUs)</h2>{table}"
                f"<h2>DC documents</h2><ul>"
                f"<li>DUM RT halal certificate (<a href=\"/en/halal\">/en/halal</a>)</li>"
                f"<li>Declaration of conformity, Mercury VSD, Chestny ZNAK, e-waybill</li>"
                f"<li>EAN as in the table / products.json</li></ul>"
                f"<p>This page does not publish lab-protocol schedules, per-shift QR or SLA percentages: "
                f"they are not in the evidence registry.</p>"
                f"<h2>Terms</h2><div class=\"card\"><ul>"
                f"<li>Basis EXW Kazan, minimum {MOQ}</li>"
                f"<li>Samples and a pilot pallet — <a href=\"/en/kak-zakazat#samples\">how to order</a></li>"
                f"<li>Private label from {PL_MIN} — <a href=\"/en/private-label\">private label</a></li>"
                f"<li>Shipment cadence is per contract; we do not publish a weekly promise</li></ul></div>"
                + _links("en")
            )
            faq = [
                ("Which SKUs for the shelf?",
                 f"This page lists {len(products)} cooked, ham, smoked and kazylyk SKUs from the live catalog. "
                 "Pepperoni, sausages and bakery are linked, not copied."),
                ("Which certificate covers meat?",
                 "Primary halal DUM RT No. 0008; 614A/2024 is also valid. Verify on /en/halal."),
                ("Are chain names listed here?",
                 "Buyer names only on /en/cases. This page does not add new names."),
            ]
        html = cp.ensure_metrika_html(
            cp.shell(lang, "dlya-setey", title, desc, h1, body, faq)
        )
        path = PUBLIC / ("en/dlya-setey.html" if lang == "en" else "dlya-setey.html")
        path.write_text(html, encoding="utf-8")
        print(f"  dlya-setey [{lang}] sku={len(shown)}")


def write_distributorov() -> None:
    data = cp.catalog()
    n = sku_count()
    sections: dict[str, int] = {}
    for p in data["products"]:
        sec = p.get("section") or "—"
        sections[sec] = sections.get(sec, 0) + 1
    sec_ru = "".join(f"<li>{k}: {v} SKU</li>" for k, v in sections.items())
    sec_en = "".join(
        f"<li>{ {'Заморозка':'Frozen','Охлаждённая продукция':'Chilled','Выпечка':'Bakery'}.get(k,k) }: {v} SKU</li>"
        for k, v in sections.items()
    )
    for lang in ("ru", "en"):
        if lang == "ru":
            title = "Дистрибьютор халяль мясной продукции — ищем поставщика | Казанские Деликатесы"
            desc = (
                f"Ищем поставщика? Дистрибьютор халяль мясной продукции из Казани: каталог {n} SKU, "
                f"{BASIS}, {MOQ}, образцы индивидуально, эксклюзивность обсуждается индивидуально."
            )
            h1 = "Халяль для дистрибьюторов"
            body = (
                f"<p class=\"lead\">Страница для оптовика: рублёвый прайс EXW, паллетный минимум, "
                f"пилот как обычная паллета, рекламации и эксклюзивность — только как в реестре фактов. "
                f"Клиентов и «региональную эксклюзивность» публично не обещаем.</p>"
                f"<p>{cert_line_ru()}</p>"
                f"<h2>Матрица {n} SKU</h2><ul>{sec_ru}</ul>"
                f"<p>Полный список — <a href=\"/price\">прайс</a> и <a href=\"/\">каталог</a>.</p>"
                f"<h2>Условия</h2><div class=\"card\"><ul>"
                f"<li>Прайс в рублях, {BASIS}; экспортные валюты в каталоге — справочные, не оферта</li>"
                f"<li>MOQ: {MOQ}</li>"
                f"<li>Пилот / образцы: <a href=\"/kak-zakazat#samples\">индивидуально, в том же паллетном базисе</a></li>"
                f"<li>Регулярность отгрузок — по договору, без выдуманного графика</li>"
                f"<li>Рекламации — по факту партии и документов к отгрузке</li>"
                f"<li>Эксклюзивность территории — обсуждается индивидуально, на сайте не обещаем</li></ul></div>"
                + _links("ru")
            )
            faq = [
                ("Какой ассортимент отдаёте дистрибьютору?",
                 f"Весь текущий каталог: {n} SKU. Срез по разделам — в списке выше."),
                ("Можно ли эксклюзив на регион?",
                 "Публично не обещаем. Формулировка на сайте: обсуждается индивидуально."),
                ("Как выглядит пилот?",
                 "Как оптовый заказ: одна паллета. Отдельного «дистрибьюторского кг» нет."),
            ]
        else:
            title = "Halal meat distributor supply from Kazan | Kazan Delicacies"
            desc = (
                f"Distributor terms for Kazan halal: {n} SKU catalog, EXW Kazan, {MOQ}, "
                "samples individually, exclusivity discussed individually."
            )
            h1 = "Halal for distributors"
            body = (
                f"<p class=\"lead\">Wholesaler page: RUB price list EXW, pallet minimum, "
                f"pilot as a normal pallet. Regional exclusivity is not a public promise.</p>"
                f"<p>{cert_line_en()}</p>"
                f"<h2>{n} SKU matrix</h2><ul>{sec_en}</ul>"
                f"<p>Full list: <a href=\"/en/price\">price list</a> and <a href=\"/en/\">catalog</a>.</p>"
                f"<h2>Terms</h2><div class=\"card\"><ul>"
                f"<li>RUB price list, EXW Kazan; catalog export currencies are reference, not an offer</li>"
                f"<li>Minimum order: 1 pallet</li>"
                f"<li>Pilot / samples: <a href=\"/en/kak-zakazat#samples\">individually, same pallet basis</a></li>"
                f"<li>Shipment cadence per contract — no invented timetable</li>"
                f"<li>Claims against the consignment and shipping documents</li>"
                f"<li>Territory exclusivity is discussed individually and not promised here</li></ul></div>"
                + _links("en")
            )
            faq = [
                ("What assortment do distributors get?",
                 f"The live catalog: {n} SKUs. Section counts are listed above."),
                ("Is regional exclusivity available?",
                 "Not as a public promise. The site wording is: discussed individually."),
                ("What is a pilot?",
                 "A wholesale order: Minimum order: 1 pallet. There is no separate distributor kilogram."),
            ]
        html = cp.ensure_metrika_html(
            cp.shell(lang, "dlya-distributorov", title, desc, h1, body, faq)
        )
        path = PUBLIC / ("en/dlya-distributorov.html" if lang == "en" else "dlya-distributorov.html")
        path.write_text(html, encoding="utf-8")
        print(f"  dlya-distributorov [{lang}] sku={n}")


def write_horeca() -> None:
    data = cp.catalog()
    grill = [p for p in cp.by_sku(data, *[f"KD-{i:03d}" for i in range(1, 9)]) if not p.get("specHold")]
    chill = cp.by_sku(data, *HOTDOG_CHILL)
    pepp = cp.by_sku(data, "KD-013", "KD-014")
    for lang in ("ru", "en"):
        gtable = cp.sku_table([_named(p, lang) for p in grill], lang)
        ctable = cp.sku_table([_named(p, lang) for p in chill], lang)
        ptable = cp.sku_table([_named(p, lang) for p in pepp], lang)
        if lang == "ru":
            title = "Поставки мяса в рестораны — HoReCa халяль оптом из Казани | Казанские Деликатесы"
            desc = (
                "Поставки мяса в рестораны и HoReCa: халяль сосиски, пепперони, котлеты и ветчина "
                "от производителя в Казани. Гриль KD-001–008 (кроме hold), охлаждённые KD-019–024, "
                "пепперони KD-013/014. Тест гриля с температурой не публикуем."
            )
            h1 = "Поставки мяса в рестораны — халяль для HoReCa"
            body = (
                "<p class=\"lead\">Поставки мяса в рестораны: канал HoReCa и кухня точки — "
                "сосиски с каталога, пепперони для пиццы, котлеты и ветчина соседними URL. "
                "Производитель в Казани, ул. Аграрная, 2, оф. 7; отгрузки по России. "
                "Температуру роликового гриля и «350 °C» не публикуем — в реестре нет такого теста.</p>"
                f"<p>{cert_line_ru()}</p>"
                "<h2>Гриль-сосиски (заморозка)</h2>"
                "<p>Полная карточка и форма запроса — "
                "<a href=\"/sosiski-dlya-hotdog\">/sosiski-dlya-hotdog</a>. "
                "KD-006 и KD-007 с коммерческой витрины сняты, пока уточняется состав.</p>"
                f"{gtable}"
                "<h2>Охлаждённые сосиски KD-019–024</h2>"
                f"{ctable}"
                "<h2>Пепперони для кухни</h2>"
                "<p>Применение в пиццерии — "
                "<a href=\"/pepperoni-dlya-pizzerii\">/pepperoni-dlya-pizzerii</a>.</p>"
                f"{ptable}"
                "<h2>Ветчина и котлеты — отдельные URL</h2><ul>"
                "<li><a href=\"/vetchina-optom\">Ветчина оптом</a></li>"
                "<li><a href=\"/kotlety-dlya-burgerov\">Котлеты для бургеров</a></li>"
                "<li><a href=\"/dlya-azs\">АЗС / прикассовая зона</a></li></ul>"
                + _links("ru")
            )
            faq = [
                ("Поставки мяса в рестораны — что входит?",
                 "Поставки мяса в рестораны с этой страницы: гриль- и охлаждённые сосиски, "
                 "пепперони KD-013/014; ветчина и котлеты — соседние URL. "
                 "Производитель в Казани. Минимальный заказ — 1 паллета."),
                ("Можно ли жарить сосиски на роликовом гриле?",
                 "В каталоге у гриль-сосисок указан способ приготовления, включая роликовый гриль. "
                 "Условий теста (время, температура, фото) на сайте нет."),
                ("Где ветчина и котлеты?",
                 "Отдельные страницы /vetchina-optom и /kotlety-dlya-burgerov — чтобы не дублировать ассортимент."),
                ("Какой минимум для кафе?",
                 f"{MOQ}. Образцы — /kak-zakazat#samples."),
            ]
        else:
            title = "Halal sausages for HoReCa — wholesale from Kazan | Kazan Delicacies"
            desc = (
                "Halal sausages for HoReCa and fuel stations: grill KD-001–008 (holds excluded), "
                "chilled KD-019–024, pepperoni KD-013/014. Ham and patties are links. "
                "No published grill-test temperatures."
            )
            h1 = "Halal products for HoReCa"
            body = (
                "<p class=\"lead\">Foodservice channel: catalog sausages, pepperoni for pizza, "
                "ham and patties on their own URLs. We do not publish roller-grill temperature "
                "or “350 °C” — there is no such test in the evidence registry.</p>"
                f"<p>{cert_line_en()}</p>"
                "<h2>Grill sausages (frozen)</h2>"
                "<p>Cards and enquiry form: "
                "<a href=\"/en/sosiski-dlya-hotdog\">/en/sosiski-dlya-hotdog</a>. "
                "KD-006 and KD-007 are off the commercial showcase while ingredients are reviewed.</p>"
                f"{gtable}"
                "<h2>Chilled sausages KD-019–024</h2>"
                f"{ctable}"
                "<h2>Pepperoni for the kitchen</h2>"
                "<p>Pizzeria use: "
                "<a href=\"/en/pepperoni-dlya-pizzerii\">/en/pepperoni-dlya-pizzerii</a>.</p>"
                f"{ptable}"
                "<h2>Ham and patties — separate URLs</h2><ul>"
                "<li><a href=\"/en/vetchina-optom\">Halal ham</a></li>"
                "<li><a href=\"/en/kotlety-dlya-burgerov\">Burger patties</a></li>"
                "<li><a href=\"/en/dlya-azs\">Fuel stations</a></li></ul>"
                + _links("en")
            )
            faq = [
                ("Can the sausages go on a roller grill?",
                 "The catalog lists cooking methods for the grill sausages, including a roller grill. "
                 "This site has no test with time, temperature or a photo."),
                ("Where are ham and patties?",
                 "Their own pages /en/vetchina-optom and /en/kotlety-dlya-burgerov, so this URL does not copy the assortment."),
                ("What is the café minimum?",
                 "Minimum order: 1 pallet. Samples: /en/kak-zakazat#samples."),
            ]
        html = cp.ensure_metrika_html(
            cp.shell(lang, "dlya-horeca", title, desc, h1, body, faq)
        )
        path = PUBLIC / ("en/dlya-horeca.html" if lang == "en" else "dlya-horeca.html")
        path.write_text(html, encoding="utf-8")
        print(f"  dlya-horeca [{lang}] grill={len(grill)} chill={len(chill)}")


def write_coffee() -> None:
    data = cp.catalog()
    products = cp.by_sku(data, *COFFEE_SKUS)
    for lang in ("ru", "en"):
        head = ("SKU", "Название", "Масса", "Короб, шт", "Хранение", "Срок", "Цена за шт") if lang == "ru" else (
            "SKU", "Name", "Weight", "Box, pcs", "Storage", "Shelf life", "Price / pc")
        rows = []
        for p in products:
            q = _named(p, lang)
            qty = p.get("qtyPerBox") or "—"
            rows.append(
                "<tr>"
                f'<td><a href="{cp.product_url(p["sku"], lang)}">{p["sku"]}</a></td>'
                f"<td>{q['name']}</td><td>{cp.weight_label(p)}</td><td>{qty}</td>"
                f"<td>{p.get('storage') or '—'}</td>"
                f"<td>{p.get('shelfLife') or '—'}</td>"
                f"<td>{cp.price_label(p, lang)}</td></tr>"
            )
        table = (
            "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )
        if lang == "ru":
            title = "Замороженная выпечка халяль для кофеен и АЗС | Казанские Деликатесы"
            desc = (
                "Сценарий для кофейни: замороженная выпечка KD-055, 057–060, 062–064, 067, 068 "
                "из каталога. Время и температуру печи не публикуем — подтверждённого теста нет."
            )
            h1 = "Замороженная выпечка для кофеен"
            body = (
                "<p class=\"lead\">Не копия хаба выпечки: здесь сценарий «из морозилки на витрину». "
                "Татарская линейка остаётся на <a href=\"/vyipechka-halyal\">/vyipechka-halyal</a>. "
                "Пекарни с сосиской в тесте — <a href=\"/sosiska-v-teste\">/sosiska-v-teste</a>. "
                "Статья для пекарен и кофеен — "
                "<a href=\"/halyal-vypechka-optom-dlya-pekaren\">/halyal-vypechka-optom-dlya-pekaren</a>.</p>"
                f"<p>{cert_line_ru()}</p>"
                "<h2>Из заморозки в печь</h2>"
                "<div class=\"note\">Масса, срок, хранение и количество в коробе — из карточек каталога "
                "(колонки таблицы). Температуру и минуты выпечки на странице нет: в реестре "
                "доказательств нет воспроизводимого теста. Режим подтверждает отдел продаж под вашу печь.</div>"
                f"{table}"
                f"<p>Минимум {MOQ}. Образец — <a href=\"/kak-zakazat#samples\">как заказать</a>. "
                f"АЗС: <a href=\"/dlya-azs\">/dlya-azs</a>.</p>"
                + _links("ru")
            )
            faq = [
                ("Чем страница отличается от /vyipechka-halyal?",
                 "Хаб — татарская линейка. Здесь классическая заморозка для кофейни и АЗС, без дубля эчпочмака."),
                ("Какая температура печи?",
                 "Не публикуем. В products.json нет поля с режимом выпечки, отдельного теста с условиями нет."),
                ("KD-061 сосиска в тесте здесь?",
                 "Нет. Она на /sosiska-v-teste для пекарен."),
            ]
        else:
            title = "Frozen halal bakery for coffee shops and fuel stations | Kazan Delicacies"
            desc = (
                "Coffee-shop scenario: frozen bakery KD-055, 057–060, 062–064, 067, 068 from the catalog. "
                "Oven time and temperature are not published — there is no confirmed test."
            )
            h1 = "Frozen bakery for coffee shops"
            body = (
                "<p class=\"lead\">Not a copy of the bakery hub: this page is the freezer-to-counter scenario. "
                "Tatar line stays on <a href=\"/en/vyipechka-halyal\">/en/vyipechka-halyal</a>. "
                "Sausage in dough for bakeries: <a href=\"/en/sosiska-v-teste\">/en/sosiska-v-teste</a>. "
                "Bakeries and coffee shops article: "
                "<a href=\"/en/halyal-vypechka-optom-dlya-pekaren\">/en/halyal-vypechka-optom-dlya-pekaren</a>.</p>"
                f"<p>{cert_line_en()}</p>"
                "<h2>From freezer to oven</h2>"
                "<div class=\"note\">Weight, shelf life, storage and pieces per box come from the catalog cards "
                "(table columns). This page does not list oven temperature or minutes: the evidence registry has no "
                "reproducible test. Sales confirms a setting for your oven.</div>"
                f"{table}"
                f"<p>Minimum one pallet. Sample: <a href=\"/en/kak-zakazat#samples\">how to order</a>. "
                f"Fuel stations: <a href=\"/en/dlya-azs\">/en/dlya-azs</a>.</p>"
                + _links("en")
            )
            faq = [
                ("How is this different from /en/vyipechka-halyal?",
                 "The hub is the Tatar line. This page is classic frozen pastry for coffee shops and fuel stations."),
                ("What oven temperature?",
                 "Not published. products.json has no bake-mode field and there is no test with conditions."),
                ("Is KD-061 sausage in dough here?",
                 "No. That SKU is on /en/sosiska-v-teste for bakeries."),
            ]
        html = cp.ensure_metrika_html(
            cp.shell(lang, "zamorozhennaya-vypechka-dlya-kofeen", title, desc, h1, body, faq)
        )
        path = PUBLIC / (
            "en/zamorozhennaya-vypechka-dlya-kofeen.html" if lang == "en"
            else "zamorozhennaya-vypechka-dlya-kofeen.html"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        print(f"  coffee [{lang}] sku={len(products)}")


HOTDOG_MARK = "<!-- content-plan-hotdog:start -->"
HOTDOG_MARK_END = "<!-- content-plan-hotdog:end -->"


def patch_hotdog() -> None:
    data = cp.catalog()
    chill = cp.by_sku(data, *HOTDOG_CHILL)
    for lang, rel in (("ru", "sosiski-dlya-hotdog.html"), ("en", "en/sosiski-dlya-hotdog.html")):
        path = PUBLIC / rel
        html = path.read_text(encoding="utf-8")
        table = cp.sku_table([_named(p, lang) for p in chill], lang)
        if lang == "ru":
            block = (
                f"{HOTDOG_MARK}<h2>Охлаждённые сосиски KD-019–024</h2>"
                "<p>Для кухни HoReCa, не дубль гриль-линейки. Ветчина и котлеты — "
                "<a href=\"/vetchina-optom\">/vetchina-optom</a> и "
                "<a href=\"/kotlety-dlya-burgerov\">/kotlety-dlya-burgerov</a>. "
                "Канал: <a href=\"/dlya-horeca\">/dlya-horeca</a>, АЗС: <a href=\"/dlya-azs\">/dlya-azs</a>.</p>"
                f"{table}{HOTDOG_MARK_END}"
            )
        else:
            block = (
                f"{HOTDOG_MARK}<h2>Chilled sausages KD-019–024</h2>"
                "<p>For the HoReCa kitchen, not a copy of the grill line. Ham and patties: "
                "<a href=\"/en/vetchina-optom\">/en/vetchina-optom</a> and "
                "<a href=\"/en/kotlety-dlya-burgerov\">/en/kotlety-dlya-burgerov</a>. "
                "Channel: <a href=\"/en/dlya-horeca\">/en/dlya-horeca</a>, "
                "fuel stations: <a href=\"/en/dlya-azs\">/en/dlya-azs</a>.</p>"
                f"{table}{HOTDOG_MARK_END}"
            )
        html = re.sub(
            re.escape(HOTDOG_MARK) + r".*?" + re.escape(HOTDOG_MARK_END),
            block, html, count=1, flags=re.S,
        )
        if HOTDOG_MARK not in html:
            html = html.replace(
                '<section class="faq-section">',
                block + '\n  <section class="faq-section">',
                1,
            )
        path.write_text(html, encoding="utf-8")
        print(f"  sosiski-dlya-hotdog patch [{lang}] chill={len(chill)}")


DELIVERY_MARK = "<!-- content-plan-samples:start -->"
DELIVERY_MARK_END = "<!-- content-plan-samples:end -->"


def patch_delivery() -> None:
    for lang, rel in (("ru", "delivery.html"), ("en", "en/delivery.html")):
        path = PUBLIC / rel
        html = path.read_text(encoding="utf-8")
        if lang == "ru":
            block = (
                f"{DELIVERY_MARK}<p>📦 <a href=\"/kak-zakazat#samples\" style=\"color:#0066cc\">"
                "Образцы и пробная партия</a> — состав и доставку образца согласуем индивидуально; "
                "пилот идёт как обычный оптовый заказ (паллета), базис EXW Казань.</p>"
                f"{DELIVERY_MARK_END}"
            )
            needle = '<p>🛒 <a href="/kak-zakazat"'
        else:
            block = (
                f"{DELIVERY_MARK}<p>📦 <a href=\"/en/kak-zakazat#samples\" style=\"color:#0066cc\">"
                "Samples and a pilot shipment</a> — assortment and how the sample is sent are agreed "
                "individually; a pilot is a normal wholesale order (Minimum order: 1 pallet), EXW Kazan.</p>"
                f"{DELIVERY_MARK_END}"
            )
            needle = '<p>🛒 <a href="/en/kak-zakazat"'
        html = re.sub(
            re.escape(DELIVERY_MARK) + r".*?" + re.escape(DELIVERY_MARK_END),
            block, html, count=1, flags=re.S,
        )
        if DELIVERY_MARK not in html:
            html = html.replace(needle, block + "\n      " + needle, 1)
        path.write_text(html, encoding="utf-8")
        print(f"  delivery samples link [{lang}]")


def write_batch4() -> None:
    write_setey()
    write_distributorov()
    write_horeca()
    write_coffee()
    patch_hotdog()
    patch_delivery()
    print("content_plan_audience: done")
