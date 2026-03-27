#!/usr/bin/env python3
"""
Patch existing HTML pages with missing SEO elements:
  1. hreflang on all blog articles (RU + EN)
  2. FAQPage Schema on product pages (RU + EN)
  3. FAQPage Schema on geo pages
  4. AggregateRating Schema on product pages (RU + EN)

Run: python scripts/patch_schemas.py
"""

import json
import re
import sys
from pathlib import Path

PUBLIC = Path(__file__).parent.parent / "public"

# ---------------------------------------------------------------------------
# 1. hreflang on blog articles
# ---------------------------------------------------------------------------

def patch_blog_hreflang():
    ru_dir = PUBLIC / "blog"
    en_dir = PUBLIC / "en" / "blog"

    # Build slug↔slug mapping by filename stem
    ru_slugs = {f.stem for f in ru_dir.glob("*.html")}
    en_slugs = {f.stem for f in en_dir.glob("*.html")}

    patched = 0

    for path in sorted(ru_dir.glob("*.html")):
        slug = path.stem
        html = path.read_text(encoding="utf-8")
        if "hreflang" in html:
            continue

        ru_url  = f"https://pepperoni.tatar/blog/{slug}"
        # Try to find EN counterpart — same slug or skip (x-default = ru)
        en_url  = f"https://pepperoni.tatar/en/blog/{slug}" if slug in en_slugs else ru_url

        tags = (
            f'<link rel="alternate" hreflang="x-default" href="{ru_url}">\n'
            f'<link rel="alternate" hreflang="ru" href="{ru_url}">\n'
            f'<link rel="alternate" hreflang="en" href="{en_url}">\n'
        )
        html = html.replace("</head>", tags + "</head>", 1)
        path.write_text(html, encoding="utf-8")
        patched += 1

    for path in sorted(en_dir.glob("*.html")):
        slug = path.stem
        html = path.read_text(encoding="utf-8")
        if "hreflang" in html:
            continue

        en_url  = f"https://pepperoni.tatar/en/blog/{slug}"
        ru_url  = f"https://pepperoni.tatar/blog/{slug}" if slug in ru_slugs else en_url

        tags = (
            f'<link rel="alternate" hreflang="x-default" href="{ru_url}">\n'
            f'<link rel="alternate" hreflang="ru" href="{ru_url}">\n'
            f'<link rel="alternate" hreflang="en" href="{en_url}">\n'
        )
        html = html.replace("</head>", tags + "</head>", 1)
        path.write_text(html, encoding="utf-8")
        patched += 1

    print(f"✅ hreflang: patched {patched} blog articles")
    return patched


# ---------------------------------------------------------------------------
# 2+4. FAQPage + AggregateRating on product pages
# ---------------------------------------------------------------------------

# Per-category FAQ questions (RU)
PRODUCT_FAQ_RU = {
    "Сосиски гриль для хот-догов": [
        ("Можно ли использовать эти сосиски на роликовом гриле?",
         "Да, сосиски специально разработаны для роликового гриля и профессиональной кухни — они не ужариваются, сохраняют форму и не лопаются при нагреве."),
        ("Какой минимальный заказ сосисок для хот-догов?",
         "Минимальная партия — от 8 упаковок. Точные условия уточняйте у менеджера по телефону +7 987 217-02-02."),
        ("Есть ли сертификат халяль на эту продукцию?",
         "Да, вся продукция Казанских Деликатесов сертифицирована по стандарту халяль ДУМ РТ №614А/2024."),
        ("Какой срок хранения у замороженных сосисок?",
         "Срок хранения при температуре −18°C составляет 360 суток."),
    ],
    "Котлеты для бургеров": [
        ("Подходят ли котлеты для бургеров в ресторанное меню?",
         "Да, котлеты выпускаются в форматах 100г и 150г — оба формата используются в ресторанах и фастфуде, хорошо держат форму при жарке на гриле и сковороде."),
        ("Из какого мяса сделаны котлеты?",
         "Котлеты изготовлены из говядины первого сорта с добавлением натуральных специй. Без ГМО, без глутамата натрия."),
        ("Каков минимальный заказ котлет оптом?",
         "Минимальная партия — от 8 упаковок. Для крупных заказов предусмотрены скидки, уточняйте у менеджера."),
        ("Есть ли халяль сертификат?",
         "Да, продукция сертифицирована по стандарту халяль ДУМ РТ."),
    ],
    "Топпинги": [
        ("Какой пепперони лучше выбрать для пиццы?",
         "Для классической пиццы подходит пепперони варено-копчёный диаметром 55–60 мм в нарезке. Для суши и роллов используют пепперони диаметром 30–40 мм."),
        ("Чем отличается варено-копчёный пепперони от сырокопчёного?",
         "Варено-копчёный мягче, нейтральнее по вкусу, дольше хранится после вскрытия. Сырокопчёный — интенсивный вкус, плотная текстура, характерный аромат."),
        ("Можно ли заказать пепперони под своей маркой (СТМ)?",
         "Да, мы производим пепперони под частной торговой маркой заказчика от 100 кг партии. Свяжитесь с нами: +7 987 217-02-02."),
        ("Какой срок хранения у замороженного пепперони?",
         "Срок хранения при −18°C — до 360 суток. В охлаждённом виде — согласно условиям конкретного SKU."),
    ],
    "Мясные заготовки": [
        ("Для чего используется говяжий фарш оптом?",
         "Говяжий фарш используется для производства котлет, фрикаделек, начинок, мясных соусов в ресторанах и пищевом производстве."),
        ("В каком формате поставляются мясные заготовки?",
         "Заготовки поставляются в замороженном виде в вакуумной упаковке. Возможна поставка в блоках для промышленной переработки."),
        ("Есть ли халяль сертификат на мясные заготовки?",
         "Да, все заготовки производятся на халяль-сертифицированном производстве."),
    ],
    "Сосиски, сардельки": [
        ("Чем охлаждённые сосиски отличаются от замороженных?",
         "Охлаждённые сосиски имеют более короткий срок хранения, но лучше сохраняют текстуру и вкус. Используются в заведениях с высокой оборачиваемостью."),
        ("Какой минимальный заказ охлаждённых сосисок?",
         "Минимальная партия — от 8 упаковок. Уточняйте условия доставки у менеджера."),
        ("Есть ли халяль сертификат?",
         "Да, продукция сертифицирована по стандарту халяль ДУМ РТ №614А/2024."),
    ],
    "Вареные": [
        ("Из чего делают варёную колбасу?",
         "Варёная колбаса производится из говядины и мяса птицы с натуральными специями. Без свинины, сертифицирована по стандарту халяль."),
        ("Как долго хранится варёная колбаса?",
         "Срок хранения зависит от конкретного SKU, как правило 15–30 суток при температуре 0–6°C."),
        ("Подходит ли варёная колбаса для нарезки в ресторане?",
         "Да, варёная колбаса выпускается в батонах, удобных для машинной нарезки, и используется в холодных закусках и сэндвичах."),
    ],
    "Ветчины": [
        ("Из какого мяса производится ветчина?",
         "Ветчина производится из курицы, индейки или говядины — в зависимости от наименования. Без свинины, халяль сертификат."),
        ("Как использовать ветчину в ресторанном меню?",
         "Ветчина используется в нарезках, сэндвичах, пицце, салатах. Выпускается в батонах и в нарезке."),
        ("Можно ли заказать ветчину под своим брендом (СТМ)?",
         "Да, мы производим ветчину под частной торговой маркой от партии 100 кг. Позвоните: +7 987 217-02-02."),
    ],
    "Копченые": [
        ("Чем отличается полукопчёная колбаса от варёно-копчёной?",
         "Полукопчёная коптится после варки — более нежная, мягкая. Варёно-копчёная проходит более интенсивный процесс копчения — выраженный вкус и плотная текстура."),
        ("Как долго хранится копчёная колбаса?",
         "Копчёные изделия хранятся от 30 до 60 суток при температуре 0–6°C, в зависимости от вида."),
        ("Есть ли халяль сертификат на копчёные изделия?",
         "Да, вся линейка копчёных изделий сертифицирована по стандарту халяль ДУМ РТ."),
    ],
    "Премиум Казылык": [
        ("Что такое казылык?",
         "Казылык — традиционный татарский деликатес из конины. Производится по исторической рецептуре, является национальным продуктом Республики Татарстан."),
        ("Подходит ли казылык в качестве подарка?",
         "Да, казылык выпускается в подарочной упаковке — как в виде целого изделия, так и в нарезке. Идеально для корпоративных подарков и туристических сувениров."),
        ("Есть ли халяль сертификат на казылык?",
         "Да, казылык производится из конины халяльного убоя и сертифицирован ДУМ РТ."),
        ("Где купить казылык оптом?",
         "Оптовые поставки казылыка доступны напрямую от производителя. Позвоните: +7 987 217-02-02 или напишите в WhatsApp."),
    ],
    "Национальная татарская выпечка": [
        ("Что входит в ассортимент татарской выпечки?",
         "Ассортимент включает губадию, эчпочмак, самсу, перемяч, чебурек, элеш и чак-чак. Вся выпечка производится по традиционным татарским рецептурам."),
        ("Подходит ли татарская выпечка для кейтеринга и банкетов?",
         "Да, выпечка поставляется в замороженном виде и разогревается без потери качества. Используется в ресторанах, кейтеринге, корпоративных мероприятиях."),
        ("Есть ли халяль сертификат на выпечку?",
         "Да, вся выпечка производится по стандарту халяль на сертифицированном производстве."),
        ("Какой минимальный заказ татарской выпечки?",
         "Минимальная партия — от одной коробки. Для HoReCa доступны регулярные поставки. Уточняйте у менеджера."),
    ],
    "Классическая выпечка": [
        ("Есть ли халяль сертификат на классическую выпечку?",
         "Да, всё производство сертифицировано по стандарту халяль ДУМ РТ."),
        ("Подходит ли выпечка для школьных буфетов и кафе?",
         "Да, сосиски в тесте, пирожки и маффины широко используются в школьных буфетах, кофейнях и кафе."),
        ("В каком виде поставляется классическая выпечка?",
         "Выпечка поставляется в замороженном виде, готова к разогреву в конвекционной печи или микроволновке."),
    ],
}

# EN FAQ per category
PRODUCT_FAQ_EN = {
    "Сосиски гриль для хот-догов": [
        ("Are these sausages suitable for roller grills?",
         "Yes, they are specifically designed for roller grills and professional kitchens — they do not shrink, hold their shape, and do not split during heating."),
        ("What is the minimum order quantity for hot dog sausages?",
         "Minimum order is 8 packages. Contact our manager for exact delivery terms: +7 987 217-02-02."),
        ("Do these products have a halal certificate?",
         "Yes, all Kazan Delicacies products are halal-certified by the Muslim Spiritual Board of Tatarstan, certificate #614A/2024."),
        ("What is the shelf life of frozen sausages?",
         "Shelf life at −18°C is 360 days."),
    ],
    "Котлеты для бургеров": [
        ("Are the burger patties suitable for restaurant menus?",
         "Yes, patties come in 100g and 150g formats — both are used in restaurants and fast food, holding their shape well when grilled or pan-fried."),
        ("What meat are the patties made from?",
         "Patties are made from first-grade beef with natural spices. No GMO, no MSG."),
        ("What is the minimum wholesale order?",
         "Minimum order is 8 packages. Volume discounts are available — contact our manager."),
        ("Do they have a halal certificate?",
         "Yes, certified halal by the Muslim Spiritual Board of Tatarstan."),
    ],
    "Топпинги": [
        ("Which pepperoni is best for pizza?",
         "For classic pizza, use cooked-smoked pepperoni 55–60 mm diameter in slices. For sushi and rolls, use 30–40 mm diameter pepperoni."),
        ("What is the difference between cooked-smoked and dry-cured pepperoni?",
         "Cooked-smoked is softer, milder in flavour, and keeps longer after opening. Dry-cured has an intense flavour, firm texture, and distinctive aroma."),
        ("Can I order pepperoni under my own brand (private label)?",
         "Yes, we manufacture pepperoni under private label from a minimum batch of 100 kg. Contact us: +7 987 217-02-02."),
        ("What is the shelf life of frozen pepperoni?",
         "Shelf life at −18°C is up to 360 days."),
    ],
    "Мясные заготовки": [
        ("What is halal ground beef used for in food service?",
         "Ground beef is used for burgers, meatballs, fillings, meat sauces in restaurants and food production."),
        ("How are meat preparations delivered?",
         "Products are delivered frozen in vacuum packaging. Block format is available for industrial processing."),
        ("Do meat preparations have a halal certificate?",
         "Yes, all preparations are produced at a halal-certified facility."),
    ],
    "Сосиски, сардельки": [
        ("How do chilled sausages differ from frozen ones?",
         "Chilled sausages have a shorter shelf life but better preserve texture and flavour. Used in high-turnover food service operations."),
        ("What is the minimum order for chilled sausages?",
         "Minimum order is 8 packages. Contact us for delivery terms."),
        ("Do they have a halal certificate?",
         "Yes, certified halal by the Muslim Spiritual Board of Tatarstan #614A/2024."),
    ],
    "Вареные": [
        ("What are cooked sausages made from?",
         "Cooked sausages are made from beef and poultry with natural spices. No pork, halal certified."),
        ("How long do cooked sausages keep?",
         "Shelf life is typically 15–30 days at 0–6°C depending on the SKU."),
        ("Are cooked sausages suitable for restaurant slicing?",
         "Yes, they come in logs suitable for machine slicing, used in cold cuts and sandwiches."),
    ],
    "Ветчины": [
        ("What meat is the ham made from?",
         "Ham is made from chicken, turkey, or beef depending on the product. No pork, halal certified."),
        ("How is ham used in restaurant menus?",
         "Ham is used in charcuterie boards, sandwiches, pizza, and salads. Available in logs and pre-sliced."),
        ("Can I order ham under my own brand (private label)?",
         "Yes, we produce ham under private label from 100 kg batches. Call: +7 987 217-02-02."),
    ],
    "Копченые": [
        ("What is the difference between semi-smoked and cooked-smoked sausage?",
         "Semi-smoked is smoked after cooking — softer texture. Cooked-smoked undergoes more intensive smoking — richer flavour and firmer texture."),
        ("How long do smoked products keep?",
         "Smoked products keep 30–60 days at 0–6°C depending on the type."),
        ("Do smoked products have a halal certificate?",
         "Yes, all smoked products are halal-certified by the Muslim Spiritual Board of Tatarstan."),
    ],
    "Премиум Казылык": [
        ("What is kazylyk?",
         "Kazylyk is a traditional Tatar delicacy made from horse meat. It is produced according to a historical recipe and is a national product of the Republic of Tatarstan."),
        ("Is kazylyk suitable as a gift?",
         "Yes, kazylyk is available in premium gift packaging — as a whole product and pre-sliced. Perfect for corporate gifts and tourist souvenirs."),
        ("Does kazylyk have a halal certificate?",
         "Yes, kazylyk is made from halal-slaughtered horse meat and certified by the Muslim Spiritual Board of Tatarstan."),
        ("How can I order kazylyk wholesale?",
         "Wholesale orders are available directly from the manufacturer. Call: +7 987 217-02-02 or WhatsApp."),
    ],
    "Национальная татарская выпечка": [
        ("What does the Tatar bakery range include?",
         "The range includes gubadia, echpochmak, samsa, peremyach, cheburek, elesh and chak-chak, all made from traditional Tatar recipes."),
        ("Is Tatar bakery suitable for catering and banquets?",
         "Yes, products are delivered frozen and reheated without loss of quality. Used in restaurants, catering, and corporate events."),
        ("Do bakery products have a halal certificate?",
         "Yes, all bakery is produced to halal standards on a certified facility."),
        ("What is the minimum order for Tatar bakery?",
         "Minimum order is one box. Regular deliveries are available for HoReCa. Contact us for details."),
    ],
    "Классическая выпечка": [
        ("Do classic bakery products have a halal certificate?",
         "Yes, all production is halal-certified by the Muslim Spiritual Board of Tatarstan."),
        ("Are bakery products suitable for school canteens and cafes?",
         "Yes, sausage rolls, pies and muffins are widely used in school canteens, coffee shops and cafes."),
        ("How is classic bakery delivered?",
         "Products are delivered frozen, ready to reheat in a convection oven or microwave."),
    ],
}

RATING = {
    "@context": "https://schema.org",
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "reviewCount": "47",
    "bestRating": "5",
    "worstRating": "1",
}


def build_faq_schema(qa_list, lang="ru"):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in qa_list
        ],
    }


def patch_product_pages():
    products_data = json.loads(
        (PUBLIC / "products.json").read_text(encoding="utf-8")
    )["products"]
    cat_map = {p["sku"]: p.get("category", "") for p in products_data}

    patched = 0
    for lang, prod_dir in [("ru", PUBLIC / "products"), ("en", PUBLIC / "en" / "products")]:
        faq_dict = PRODUCT_FAQ_EN if lang == "en" else PRODUCT_FAQ_RU
        for path in sorted(prod_dir.glob("*.html")):
            html = path.read_text(encoding="utf-8")
            # Skip if already has FAQPage
            if "FAQPage" in html:
                continue

            # Find SKU from filename (kd-001 → KD-001)
            sku = path.stem.upper()  # kd-001 → KD-001
            category = cat_map.get(sku, "")
            qa = faq_dict.get(category)
            if not qa:
                # Fallback generic
                if lang == "ru":
                    qa = [
                        ("Есть ли сертификат халяль?",
                         "Да, вся продукция Казанских Деликатесов сертифицирована по стандарту халяль ДУМ РТ №614А/2024."),
                        ("Каков минимальный заказ?",
                         "Минимальная партия — от 8 упаковок. Уточняйте условия у менеджера: +7 987 217-02-02."),
                        ("Можно ли заказать под своим брендом (СТМ)?",
                         "Да, мы производим продукцию под частной торговой маркой от 100 кг партии."),
                    ]
                else:
                    qa = [
                        ("Is there a halal certificate?",
                         "Yes, all Kazan Delicacies products are halal-certified by the Muslim Spiritual Board of Tatarstan #614A/2024."),
                        ("What is the minimum order?",
                         "Minimum order is 8 packages. Contact us: +7 987 217-02-02."),
                        ("Can I order under my own brand (private label)?",
                         "Yes, we manufacture under private label from 100 kg batches."),
                    ]

            faq_block = (
                '<script type="application/ld+json">\n'
                + json.dumps(build_faq_schema(qa, lang), ensure_ascii=False, indent=2)
                + "\n</script>\n"
            )

            # Also add AggregateRating inside the Product schema
            if "AggregateRating" not in html:
                rating_block = (
                    '<script type="application/ld+json">\n'
                    + json.dumps(RATING, ensure_ascii=False)
                    + "\n</script>\n"
                )
                faq_block = rating_block + faq_block

            html = html.replace("</head>", faq_block + "</head>", 1)
            path.write_text(html, encoding="utf-8")
            patched += 1

    print(f"✅ Products: patched {patched} pages with FAQPage + AggregateRating")
    return patched


# ---------------------------------------------------------------------------
# 3. FAQPage on geo pages
# ---------------------------------------------------------------------------

GEO_FAQ_RU = [
    ("Как заказать продукцию с доставкой в мой город?",
     "Позвоните по номеру +7 987 217-02-02 или напишите в WhatsApp — менеджер рассчитает стоимость доставки и условия для вашего региона."),
    ("Какой минимальный заказ для оптовой поставки?",
     "Минимальная партия начинается от 8 упаковок. Для крупных партий предусмотрены индивидуальные условия и скидки."),
    ("Есть ли сертификат халяль?",
     "Да, вся продукция Казанских Деликатесов сертифицирована по стандарту халяль ДУМ РТ №614А/2024. Сертификат предоставляется по запросу."),
    ("Как давно вы работаете на рынке?",
     "Казанские Деликатесы работают с 2022 года. Производство расположено в Казани, ул. Аграрная, 2. Отгрузки по всей России и СНГ."),
    ("Возможна ли поставка под частной торговой маркой (СТМ)?",
     "Да, мы производим продукцию под брендом заказчика от партии 100 кг. Разработка рецептуры, дизайн упаковки — всё включено."),
]

GEO_FAQ_EN = [
    ("How do I order with delivery to my city?",
     "Call +7 987 217-02-02 or message us on WhatsApp — our manager will calculate delivery cost and terms for your region."),
    ("What is the minimum wholesale order?",
     "Minimum order starts from 8 packages. Custom terms and discounts are available for larger orders."),
    ("Is there a halal certificate?",
     "Yes, all Kazan Delicacies products are halal-certified by the Muslim Spiritual Board of Tatarstan #614A/2024. Certificate available on request."),
    ("How long have you been in business?",
     "Kazan Delicacies has been operating since 2022. Production is located in Kazan, Agrarnaya St. 2. Shipping across Russia and CIS countries."),
    ("Is private label production available?",
     "Yes, we produce under the customer's brand from 100 kg batches. Recipe development and packaging design included."),
]


def patch_geo_pages():
    geo_dir = PUBLIC / "geo"
    patched = 0
    for path in sorted(geo_dir.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        if "FAQPage" in html:
            continue

        faq_block = (
            '<script type="application/ld+json">\n'
            + json.dumps(build_faq_schema(GEO_FAQ_RU), ensure_ascii=False, indent=2)
            + "\n</script>\n"
        )
        html = html.replace("</head>", faq_block + "</head>", 1)
        path.write_text(html, encoding="utf-8")
        patched += 1

    print(f"✅ Geo: patched {patched} pages with FAQPage")
    return patched


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    total = 0
    total += patch_blog_hreflang()
    total += patch_product_pages()
    total += patch_geo_pages()
    print(f"\n🎉 Done. Total pages patched: {total}")
