#!/usr/bin/env python3
"""Generate /kak-zakazat and /en/kak-zakazat from site_facts + evidence already
on the site. Unknown payment methods, transit days and sample prices are omitted.
"""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commercial_page import page as wrap_page  # noqa: E402
from site_facts import FACTS, phone_tel, phone_wa, sku_count  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
_CO = FACTS["company"]
_TERMS = FACTS["terms"]
N = sku_count()
TEL = phone_tel()
WA = phone_wa()


def _faq_ld(pairs: list[tuple[str, str]]) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs
        ],
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def _howto_ld(name: str, steps: list[str]) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": name,
        "step": [
            {"@type": "HowToStep", "position": i, "text": t}
            for i, t in enumerate(steps, 1)
        ],
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def _crumbs(lang: str) -> str:
    if lang == "ru":
        payload = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Главная",
                 "item": "https://pepperoni.tatar/"},
                {"@type": "ListItem", "position": 2, "name": "Как заказать",
                 "item": "https://pepperoni.tatar/kak-zakazat"},
            ],
        }
    else:
        payload = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home",
                 "item": "https://pepperoni.tatar/en/"},
                {"@type": "ListItem", "position": 2, "name": "How to order",
                 "item": "https://pepperoni.tatar/en/kak-zakazat"},
            ],
        }
    return (
        '<script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def ru() -> str:
    inn, ogrn = _CO["inn"], _CO["ogrn"]
    phone, email = _CO["phone"], _CO["email"]
    addr = _CO["address_ru"]
    legal = _CO["legal_name_ru"]
    steps = [
        f"Выберите позиции в каталоге ({N} SKU) или в прайс-листе. Цены на прайсе совпадают с карточками.",
        "Отправьте заявку: телефон, e-mail, WhatsApp или форма на странице категории. Укажите город, сегмент и ориентировочный объём.",
        "Отдел продаж подтвердит наличие, состав паллеты и цену из действующего каталога. Цена заказа фиксируется в счёте.",
        f"Базис поставки — {_TERMS['basis']}. Доставку оплачивает покупатель; срок отгрузки согласовывается по заявке.",
        "С отгрузкой идут сертификат халяль, декларация соответствия, ВСД (ФГИС «Меркурий»), маркировка «Честный знак» и электронная транспортная накладная (ЭТрН).",
    ]
    faq = [
        ("Какой минимальный заказ?",
         f"Минимальный заказ — {_TERMS['moq']}. Объём считаем кратно паллете."),
        ("Кто оплачивает доставку и какой базис?",
         f"Базис — {_TERMS['basis']}. Доставку оплачивает покупатель; маршрут и срок — индивидуально."),
        ("Как фиксируется оплата?",
         "Условия оплаты фиксируются в счёте по каждому заказу."),
        ("Какие документы идут с отгрузкой?",
         "Сертификат халяль, декларация соответствия, ВСД (ФГИС «Меркурий»), маркировка «Честный знак», электронная транспортная накладная (ЭТрН)."),
        ("Какой минимум для контрактного производства (СТМ)?",
         f"От {_TERMS['private_label_min']}. Подробности — на странице контрактного производства."),
        ("Как получить образцы или пробную партию?",
         "Образцы согласуем индивидуально. Пробная отгрузка — в том же паллетном минимуме: одна паллета, сборная из нескольких SKU возможна. Цену образца отдельно не публикуем."),
    ]
    faq_html = "".join(
        f"<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>"
        for q, a in faq
    )
    body = f"""
<nav class="crumb"><a href="/">Главная</a> → Как заказать</nav>
<h1>Как заказать халяль продукцию оптом</h1>
<p>{escape(legal)} поставляет {N} SKU халяльной мясной продукции и выпечки с производства в Казани. Ниже — порядок работы, который уже описан на сайте и в реестре фактов. Сроки в днях и процент предоплаты не публикуем: их нет в подтверждённых данных.</p>

<h2>Шаги</h2>
<ol>
<li>Выберите ассортимент в <a href="/">каталоге</a> или в <a href="/price">прайс-листе</a>. Цены на прайсе — те же, что на карточках. Файлы: <a href="/prices.xlsx">Excel</a>, <a href="/prices.pdf">PDF</a>.</li>
<li>Отправьте заявку по телефону <a href="{TEL}">{escape(phone)}</a>, почте <a href="mailto:{escape(email)}">{escape(email)}</a>, <a href="{WA}">WhatsApp</a> или через форму на странице категории. Укажите город, тип точки и ориентировочный объём.</li>
<li>Отдел продаж подтвердит наличие, состав паллеты и цену из действующего каталога. Цена заказа фиксируется в счёте.</li>
<li>Базис поставки — {escape(_TERMS['basis'])}. Доставку оплачивает покупатель; срок отгрузки согласовывается по конкретной заявке.</li>
<li>С отгрузкой идут сертификат халяль, декларация соответствия, ВСД (ФГИС «Меркурий»), маркировка «Честный знак» и электронная транспортная накладная (ЭТрН).</li>
</ol>

<h2>Минимальный заказ</h2>
<div class="card">
<p><strong>Опт:</strong> {escape(_TERMS['moq'])}. Объём считаем кратно паллете.</p>
<p><strong>Контрактное производство (СТМ):</strong> от {escape(_TERMS['private_label_min'])}. Условия — на странице <a href="/kontraktnoe-proizvodstvo">контрактного производства</a>.</p>
</div>

<h2>Доставка и оплата</h2>
<div class="card">
<p>Базис — {escape(_TERMS['basis'])}. Покупатель забирает товар со склада в Казани либо организует перевозку за свой счёт. Срок отгрузки называем по заказу.</p>
<p>Условия оплаты фиксируются в счёте. В каталоге — справочные экспортные цены в USD, KZT, UZS, KGS, BYN, AZN.</p>
<p>Подробнее о базисе и экспортных валютах — на странице <a href="/delivery">доставки</a>.</p>
</div>

<h2>Документы</h2>
<ul>
<li>Сертификат халяль ДУМ РТ</li>
<li>Декларация соответствия</li>
<li>ВСД в ФГИС «Меркурий»</li>
<li>Маркировка «Честный знак»</li>
<li>Электронная транспортная накладная (ЭТрН)</li>
</ul>
<p>Реестр сертификатов — <a href="/halal">/halal</a>.</p>

<h2 id="samples">Образцы и пробная партия</h2>
<div class="card">
<p>Перед контрактом можно запросить образцы — состав, объём и доставку образца согласуем индивидуально. Отдельной цены «за образец» в каталоге нет.</p>
<p>Пробная партия идёт как обычный оптовый заказ: {escape(_TERMS['moq'])}. Сборная паллета из нескольких SKU возможна. Это тот же базис {escape(_TERMS['basis'])}, те же документы к отгрузке.</p>
<p>В заявке укажите город, тип точки и SKU с <a href="/price">прайса</a>. Для сетей — <a href="/dlya-setey">/dlya-setey</a>, для дистрибьюторов — <a href="/dlya-distributorov">/dlya-distributorov</a>, для HoReCa — <a href="/dlya-horeca">/dlya-horeca</a>.</p>
</div>

<h2>Контакты</h2>
<div class="card">
<p>{escape(legal)} · ИНН {escape(inn)} · ОГРН {escape(ogrn)}</p>
<p>{escape(addr)}</p>
<p><a href="{TEL}">{escape(phone)}</a> · <a href="mailto:{escape(email)}">{escape(email)}</a> · <a href="{WA}">WhatsApp</a></p>
</div>

<section class="faq" id="faq">
<h2>Частые вопросы</h2>
{faq_html}
</section>
"""
    extra = _crumbs("ru") + _howto_ld("Как заказать халяль продукцию оптом", steps) + _faq_ld(faq)
    nav = (
        '<div class="topnav">'
        '<a href="/">Каталог</a><a href="/price">Прайс</a>'
        '<a href="/delivery">Доставка</a><a href="/about">О компании</a>'
        '<span class="here">Как заказать</span>'
        '<a href="/en/kak-zakazat" style="margin-left:auto;color:#888">English</a></div>'
    )
    return wrap_page(
        lang="ru",
        title="Как заказать халяль продукцию оптом — Казанские Деликатесы",
        description=(
            f"Как заказать оптом у {legal}: каталог и прайс, заявка, "
            f"минимальный заказ { _TERMS['moq'] }, базис {_TERMS['basis']}, документы к отгрузке."
        ),
        canonical="https://pepperoni.tatar/kak-zakazat",
        hreflang_ru="https://pepperoni.tatar/kak-zakazat",
        hreflang_en="https://pepperoni.tatar/en/kak-zakazat",
        nav_html=nav,
        body=body,
        extra_head=extra,
    )


def en() -> str:
    inn, ogrn = _CO["inn"], _CO["ogrn"]
    phone, email = _CO["phone"], _CO["email"]
    addr = _CO["address_en"]
    legal = _CO["legal_name_en"]
    steps = [
        f"Pick SKUs from the catalog ({N} items) or the price list. Prices on the list match the product cards.",
        "Send an enquiry by phone, e-mail, WhatsApp or the category-page form. State city, channel and approximate volume.",
        "Sales confirms availability, pallet mix and the catalog price. The order price is fixed in the invoice.",
        "Basis is EXW Kazan. The buyer pays freight; lead time is agreed per order.",
        "Shipping documents: halal certificate, declaration of conformity, veterinary certificate (Mercury), Chestny ZNAK marking, electronic waybill (ETrN).",
    ]
    faq = [
        ("What is the minimum order?",
         "Minimum order is one pallet; a mixed pallet of several SKUs is possible. Volumes are quoted in pallet multiples."),
        ("Who pays for delivery?",
         "Basis is EXW Kazan. The buyer pays freight; route and lead time are quoted individually."),
        ("How is payment agreed?",
         "Payment terms are fixed in the invoice for each order."),
        ("Which documents ship with the goods?",
         "Halal certificate, declaration of conformity, veterinary certificate (Mercury), Chestny ZNAK marking, electronic waybill (ETrN)."),
        ("What is the private-label minimum?",
         f"From {_TERMS['private_label_min']}. Details are on the private-label page."),
        ("How do we get samples or a pilot shipment?",
         "Samples are agreed individually. A pilot shipment uses the same wholesale minimum: one pallet, mixed SKUs possible. We do not publish a separate sample price."),
    ]
    faq_html = "".join(
        f"<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>"
        for q, a in faq
    )
    body = f"""
<nav class="crumb"><a href="/en/">Home</a> → How to order</nav>
<h1>How to order halal products wholesale</h1>
<p>{escape(legal)} supplies {N} SKUs of halal meat products and bakery from the Kazan plant. The steps below repeat terms already published on the site and in the facts registry. Transit times in days and prepayment percentages are omitted: they are not in the verified data.</p>

<h2>Steps</h2>
<ol>
<li>Choose items in the <a href="/en/">catalog</a> or the <a href="/en/price">price list</a>. Prices match the product cards. Files: <a href="/prices.xlsx">Excel</a>, <a href="/prices.pdf">PDF</a>.</li>
<li>Send an enquiry by phone <a href="{TEL}">{escape(phone)}</a>, e-mail <a href="mailto:{escape(email)}">{escape(email)}</a>, <a href="{WA}">WhatsApp</a> or the form on a category page. State city, channel and approximate volume.</li>
<li>Sales confirms availability, pallet mix and the live catalog price. The order price is fixed in the invoice.</li>
<li>Basis is EXW Kazan. The buyer pays freight; lead time is agreed for the specific order.</li>
<li>Shipping set: halal certificate, declaration of conformity, veterinary certificate (Mercury), Chestny ZNAK marking, electronic waybill (ETrN).</li>
</ol>

<h2>Minimum order</h2>
<div class="card">
<p><strong>Wholesale:</strong> one pallet; a mixed pallet is possible. Volumes are quoted in pallet multiples.</p>
<p><strong>Private label:</strong> from {escape(_TERMS['private_label_min'])}. See the <a href="/en/private-label">private-label page</a>.</p>
</div>

<h2>Delivery and payment</h2>
<div class="card">
<p>Basis is EXW Kazan. The buyer collects from the Kazan warehouse or arranges freight at their own cost. Lead time is named per order.</p>
<p>Payment terms are fixed in the invoice. The catalog lists reference export prices in USD, KZT, UZS, KGS, BYN, AZN.</p>
<p>More on the basis and export currencies: <a href="/en/delivery">delivery</a>.</p>
</div>

<h2>Documents</h2>
<ul>
<li>DUM RT halal certificate</li>
<li>Declaration of conformity</li>
<li>Veterinary certificate in Mercury (VSD)</li>
<li>Chestny ZNAK marking</li>
<li>Electronic waybill (ETrN)</li>
</ul>
<p>Certificate list: <a href="/en/halal">/en/halal</a>.</p>

<h2 id="samples">Samples and pilot shipment</h2>
<div class="card">
<p>Samples before a contract are agreed individually — assortment, volume and how the sample is sent. The catalog has no separate “sample price”.</p>
<p>A pilot shipment is a normal wholesale order: one pallet; a mixed pallet of several SKUs is possible. Same EXW Kazan basis, same shipping documents.</p>
<p>State city, channel and SKUs from the <a href="/en/price">price list</a>. Retail chains: <a href="/en/dlya-setey">/en/dlya-setey</a>. Distributors: <a href="/en/dlya-distributorov">/en/dlya-distributorov</a>. HoReCa: <a href="/en/dlya-horeca">/en/dlya-horeca</a>.</p>
</div>

<h2>Contacts</h2>
<div class="card">
<p>{escape(legal)} · INN {escape(inn)} · OGRN {escape(ogrn)}</p>
<p>{escape(addr)}</p>
<p><a href="{TEL}">{escape(phone)}</a> · <a href="mailto:{escape(email)}">{escape(email)}</a> · <a href="{WA}">WhatsApp</a></p>
</div>

<section class="faq" id="faq">
<h2>FAQ</h2>
{faq_html}
</section>
"""
    extra = _crumbs("en") + _howto_ld("How to order halal products wholesale", steps) + _faq_ld(faq)
    nav = (
        '<div class="topnav">'
        '<a href="/en/">Catalog</a><a href="/en/price">Price list</a>'
        '<a href="/en/delivery">Delivery</a><a href="/en/about">About</a>'
        '<span class="here">How to order</span>'
        '<a href="/kak-zakazat" style="margin-left:auto;color:#888">Русский</a></div>'
    )
    return wrap_page(
        lang="en",
        robots="noindex, follow",
        title="How to order halal products wholesale — Kazan Delicacies",
        description=(
            f"How to order wholesale from {legal}: catalog and price list, enquiry, "
            "pallet minimum, EXW Kazan, shipping documents."
        ),
        canonical="https://pepperoni.tatar/en/kak-zakazat",
        hreflang_ru="https://pepperoni.tatar/kak-zakazat",
        hreflang_en="https://pepperoni.tatar/en/kak-zakazat",
        nav_html=nav,
        body=body,
        extra_head=extra,
    )


def main() -> int:
    (PUBLIC / "kak-zakazat.html").write_text(ru(), encoding="utf-8")
    (PUBLIC / "en").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "en" / "kak-zakazat.html").write_text(en(), encoding="utf-8")
    print("how-to-order: /kak-zakazat + /en/kak-zakazat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
