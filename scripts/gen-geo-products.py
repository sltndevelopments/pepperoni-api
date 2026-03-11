#!/usr/bin/env python3
"""
Generate geo-targeted landing pages for:
1. Котлеты для бургеров (halal burger patties)
2. Сосиски для хот-догов и франч-догов (halal hot dog sausages)
18 locations each = 36 pages total.
"""

from pathlib import Path
import re

PUBLIC = Path(__file__).parent.parent / "public"
GEO_DIR = PUBLIC / "geo"
GEO_DIR.mkdir(exist_ok=True)

GTM = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->"""

GTM_NS = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

CSS = """
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
    .container{max-width:800px;margin:0 auto;padding:40px 24px}
    h1{font-size:2rem;font-weight:700;margin-bottom:8px}
    h2{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}
    p{margin-bottom:14px}
    .badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0;letter-spacing:.5px}
    .badge-outline{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}
    .hero-subtitle{color:#666;font-size:1.05rem;margin-bottom:4px}
    .card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}
    .grid-2{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:16px 0}
    .feat-card{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px}
    .feat-card .icon{font-size:1.6rem;margin-bottom:6px}
    .feat-card .title{font-weight:600;font-size:.9rem}
    .feat-card .desc{font-size:.82rem;color:#666;margin-top:4px}
    .prices-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:16px 0}
    .price-card{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px;text-align:center}
    .price-card .name{font-size:.85rem;font-weight:600;margin-bottom:4px}
    .price-card .weight{font-size:.75rem;color:#888}
    .price-card .price{font-size:1.4rem;font-weight:700;color:#1b7a3d;margin-top:8px}
    table{width:100%;border-collapse:collapse;margin:12px 0}
    th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}
    th{background:#f5f5f5;font-weight:600}
    ul{margin:8px 0 14px 24px}
    li{margin-bottom:4px}
    .spec-value{font-weight:600;color:#1b7a3d}
    .cta{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0;font-size:.95rem}
    .cta:hover{background:#15652f}
    .cta-outline{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}
    .cta-outline:hover{background:#1b7a3d;color:#fff}
    footer{text-align:center;color:#aaa;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}
    footer a{color:#888;text-decoration:none}
    @media(max-width:600px){.grid-2,.prices-grid{grid-template-columns:1fr}}
"""

LOCATIONS = [
    {"slug_suffix": "moskva",   "city": "Москва",            "city_gen": "Москвы",            "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Москва — крупнейший рынок бургерных и dark kitchen в России. Тысячи заведений ежедневно нуждаются в стабильных поставках халяль-котлет.",
     "hotdog_angle": "Москва — лидер по количеству хот-дог стендов, фудтраков и сетей франч-догов. Спрос на халяль-сосиски растёт вместе с мусульманской аудиторией города.",
     "logistics": "Еженедельные рейсы Казань — Москва. Доставка через ТК или самовывоз на нашем складе.", "currency": "RUB", "export": False},
    {"slug_suffix": "spb",      "city": "Санкт-Петербург",   "city_gen": "Санкт-Петербурга",  "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Петербург — второй ресторанный рынок России с высокими стандартами качества. Бургерные сети и HoReCa-операторы требуют полный пакет документов.",
     "hotdog_angle": "Петербург активно развивает стритфуд-культуру: хот-доги, франч-доги, сосиски-гриль на каждом шагу. Наш продукт идеально подходит для этого рынка.",
     "logistics": "Регулярная логистика через ТК. Доставка до вашего склада.", "currency": "RUB", "export": False},
    {"slug_suffix": "kazan",    "city": "Казань",             "city_gen": "Казани",            "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Казань — наш родной город. Самовывоз прямо с производства, минимальные цены, поставки в тот же день.",
     "hotdog_angle": "Производство в Казани — значит самовывоз в день заказа. Для казанских точек стритфуда, АЗС и HoReCa это лучший вариант.",
     "logistics": "Самовывоз: г. Казань, ул. Аграрная, 2. Отгрузка день в день.", "currency": "RUB", "export": False},
    {"slug_suffix": "ufa",      "city": "Уфа",                "city_gen": "Уфы",               "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Уфа и Башкортостан — мусульманский регион с высоким спросом на халяль. Котлеты для халяль-бургеров востребованы в каждом заведении.",
     "hotdog_angle": "В Уфе сосиски-халяль — стандарт для большинства точек общепита. Наши сосиски для хот-догов и франч-догов уже поставляются в регион.",
     "logistics": "Короткое плечо Казань — Уфа. Регулярные поставки через ТК.", "currency": "RUB", "export": False},
    {"slug_suffix": "ekaterinburg", "city": "Екатеринбург",   "city_gen": "Екатеринбурга",     "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Екатеринбург — третий город России, логистический хаб Урала. Через Екатеринбург удобно дистрибутировать по всему уральскому региону.",
     "hotdog_angle": "Уральский рынок стритфуда активно растёт. Сосиски для франч-догов и хот-догов в заморозке идеальны для длинного плеча доставки.",
     "logistics": "Доставка через ТК до Екатеринбурга. Заморозка — 360 суток хранения.", "currency": "RUB", "export": False},
    {"slug_suffix": "yanao",    "city": "ЯНАО",               "city_gen": "ЯНАО",              "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Северный завоз требует продукции с длительным сроком хранения. Наши котлеты хранятся 360 суток при −18°C — идеально для арктических поставок.",
     "hotdog_angle": "Для Севера критичен срок хранения. Наши замороженные сосиски (360 суток при −18°C) — оптимальный выбор для северного завоза на АЗС, столовые, магазины.",
     "logistics": "Плановый северный завоз. Заморозка 360 суток. Крупные партии под завоз.", "currency": "RUB", "export": False},
    {"slug_suffix": "dagestan", "city": "Дагестан",           "city_gen": "Дагестана",         "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "В Дагестане халяль — единственный приемлемый стандарт. Котлеты для бургеров из говядины с сертификатом Halal ДУМ РТ — именно то, что нужно рынку.",
     "hotdog_angle": "Дагестанский рынок требует 100% халяль. Наши сосиски из говядины и курицы с сертификатом ДУМ РТ — стандарт для каждой точки стритфуда в регионе.",
     "logistics": "Поставки через дистрибьюторов по Дагестану. Полный пакет ветеринарных документов.", "currency": "RUB", "export": False},
    {"slug_suffix": "mahachkala", "city": "Махачкала",        "city_gen": "Махачкалы",         "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Махачкала — столица Дагестана с быстро растущим рынком бургерных и фастфуда. Халяль — обязательное условие для всего рынка.",
     "hotdog_angle": "Рынок хот-догов и стритфуда в Махачкале активно развивается. Поставляем халяль-сосиски с официальной сертификацией для дагестанского рынка.",
     "logistics": "Работаем с дистрибьюторами в Махачкале. Поставки по всему Дагестану.", "currency": "RUB", "export": False},
    {"slug_suffix": "grozny",   "city": "Грозный",            "city_gen": "Грозного",          "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Грозный активно развивает ресторанный сегмент. Халяль-котлеты из говядины — основа для любой бургерной в Чеченской Республике.",
     "hotdog_angle": "В Чечне халяль — норма жизни. Наши сосиски из говядины и курицы с сертификатом Halal поставляются в регион для точек фастфуда и стритфуда.",
     "logistics": "Поставки в Грозный через дистрибьюторов Северного Кавказа.", "currency": "RUB", "export": False},
    {"slug_suffix": "sochi",    "city": "Сочи",               "city_gen": "Сочи",              "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Сочи — курортный город с круглогодичным потоком туристов. Халяль-бургеры востребованы среди гостей из мусульманских регионов и стран.",
     "hotdog_angle": "Сочинские набережные, парки, фудтраки — огромный спрос на сосиски-гриль и хот-доги. Халяль-статус привлекает туристов из мусульманских стран.",
     "logistics": "Поставки по Краснодарскому краю. Регулярная логистика в сезон.", "currency": "RUB", "export": False},
    {"slug_suffix": "krasnodar", "city": "Краснодарский край", "city_gen": "Краснодарского края", "country": "Россия",   "flag": "🇷🇺",
     "burger_angle": "Краснодарский край — топ-5 по обороту общепита в России. Бургерные, сети фастфуда, HoReCa — всем нужны стабильные поставки халяль-котлет.",
     "hotdog_angle": "Кубань, Сочи, Анапа, Новороссийск — огромный рынок стритфуда. Работаем с дистрибьюторами по всему краю.",
     "logistics": "Дистрибуция по всему Краснодарскому краю через региональных партнёров.", "currency": "RUB", "export": False},
    {"slug_suffix": "astrahan", "city": "Астрахань",          "city_gen": "Астрахани",         "country": "Россия",      "flag": "🇷🇺",
     "burger_angle": "Астрахань — мусульманский регион и транзитная точка для экспорта в Казахстан. Халяль-котлеты для местного рынка и экспортных поставок.",
     "hotdog_angle": "Астрахань — ворота в Казахстан. Работаем с местным рынком и транзитными дистрибьюторами для дальнейших поставок в Казахстан.",
     "logistics": "Поставки в Астрахань. Документы ЕАЭС для транзита в Казахстан.", "currency": "RUB", "export": False},
    {"slug_suffix": "kazakhstan", "city": "Казахстан",        "city_gen": "Казахстана",        "country": "Казахстан",   "flag": "🇰🇿",
     "burger_angle": "Казахстан — крупнейший экспортный рынок в СНГ. Котлеты для халяль-бургеров в рамках ЕАЭС: без таможенных барьеров, цены в KZT.",
     "hotdog_angle": "Рынок хот-догов и стритфуда в Казахстане активно растёт. Поставляем халяль-сосиски в Алматы, Астану, Шымкент. Цены в KZT, документы ЕАЭС.",
     "logistics": "EXW Казань. ЕАЭС — без таможенных пошлин. Цены в KZT.", "currency": "KZT", "export": True},
    {"slug_suffix": "uzbekistan", "city": "Узбекистан",       "city_gen": "Узбекистана",       "country": "Узбекистан",  "flag": "🇺🇿",
     "burger_angle": "Узбекистан переживает бум бургерных. Ташкент, Самарканд, Бухара — рынок растёт на 20–30% ежегодно. Поставляем халяль-котлеты с документами для узбекской таможни.",
     "hotdog_angle": "Стритфуд в Узбекистане растёт. Хот-доги, франч-доги — новый тренд в Ташкенте. Поставляем халяль-сосиски. Цены в USD и UZS.",
     "logistics": "EXW Казань. Документы для узбекской таможни. Цены в USD/UZS.", "currency": "UZS", "export": True},
    {"slug_suffix": "belarus",  "city": "Беларусь",           "city_gen": "Беларуси",          "country": "Беларусь",    "flag": "🇧🇾",
     "burger_angle": "Беларусь — член ЕАЭС. Котлеты для бургеров из Казани поставляются в Минск без таможенных барьеров. Цены в BYN.",
     "hotdog_angle": "Белорусский рынок фастфуда активно растёт. Поставляем халяль-сосиски в Беларусь в рамках ЕАЭС. Цены в BYN, без пошлин.",
     "logistics": "ЕАЭС — без пошлин. Цены в BYN. EXW Казань или доставка до Минска.", "currency": "BYN", "export": True},
    {"slug_suffix": "armenia",  "city": "Армения",            "city_gen": "Армении",           "country": "Армения",     "flag": "🇦🇲",
     "burger_angle": "Ереван переживает гастрономический бум. Бургерные рестораны растут стремительно. Поставляем халяль-котлеты в Армению в рамках ЕАЭС. Цены в USD.",
     "hotdog_angle": "Армения — ЕАЭС. Рынок стритфуда и хот-догов в Ереване активно развивается. Поставляем халяль-сосиски. Цены в USD.",
     "logistics": "ЕАЭС. EXW Казань. Цены в USD.", "currency": "USD", "export": True},
    {"slug_suffix": "azerbaijan", "city": "Азербайджан",      "city_gen": "Азербайджана",      "country": "Азербайджан", "flag": "🇦🇿",
     "burger_angle": "Баку — один из самых динамичных ресторанных рынков СНГ. Халяль — стандарт рынка. Поставляем котлеты для бургеров с сертификатом Halal. Цены в AZN.",
     "hotdog_angle": "Азербайджан — мусульманская страна. Стритфуд и фастфуд-рынок Баку требует халяль. Поставляем сосиски с сертификатом ДУМ РТ. Цены в AZN.",
     "logistics": "EXW Казань. Экспортная документация. Цены в AZN.", "currency": "AZN", "export": True},
    {"slug_suffix": "kyrgyzstan", "city": "Кыргызстан",       "city_gen": "Кыргызстана",       "country": "Кыргызстан",  "flag": "🇰🇬",
     "burger_angle": "Кыргызстан — ЕАЭС. Бишкек активно развивает рынок бургерных и фастфуда. Поставляем халяль-котлеты. Цены в KGS, без таможенных барьеров.",
     "hotdog_angle": "Рынок стритфуда в Бишкеке растёт. ЕАЭС упрощает поставки из России. Халяль-сосиски с сертификатом ДУМ РТ для кыргызского рынка. Цены в KGS.",
     "logistics": "ЕАЭС — без пошлин. EXW Казань. Цены в KGS.", "currency": "KGS", "export": True},
]


def build_burger_page(loc):
    city = loc["city"]
    city_gen = loc["city_gen"]
    flag = loc["flag"]
    slug = f"kotlety-dlya-burgerov-{loc['slug_suffix']}"
    url = f"https://pepperoni.tatar/geo/{slug}"
    exp = " Экспорт в рамках ЕАЭС." if loc["export"] else ""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="/favicon.ico" type="image/x-icon">
  <title>Халяль котлеты для бургеров оптом — {city} | Казанские Деликатесы</title>
  <meta name="description" content="Котлеты для бургеров халяль оптом в {city_gen}. Говяжьи и куриные. Заморозка, 360 суток. ХАССП. Halal № 614A/2024. Поставки от производителя.{exp}">
  <meta name="keywords" content="котлеты для бургеров {city.lower()}, халяль котлеты для бургеров {city.lower()}, котлеты для бургеров оптом {city.lower()}, burger patties halal {city.lower()}, котлеты говяжьи для бургеров {city.lower()}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Котлеты для бургеров халяль — {city}",
    "description": "Котлеты для бургеров халяль оптом в {city_gen}. Говяжьи и куриные, в заморозке.",
    "brand": {{"@type": "Brand", "name": "Казанские Деликатесы"}},
    "additionalProperty": [
      {{"@type": "PropertyValue", "name": "Сертификация", "value": "Halal № 614A/2024 (ДУМ РТ)"}},
      {{"@type": "PropertyValue", "name": "Контроль качества", "value": "HACCP"}},
      {{"@type": "PropertyValue", "name": "Рынок", "value": "{city}"}}
    ],
    "offers": {{"@type": "Offer", "priceCurrency": "RUB", "price": "276.00", "availability": "https://schema.org/InStock"}}
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "Каталог", "item": "https://pepperoni.tatar/"}},
      {{"@type": "ListItem", "position": 2, "name": "Котлеты для бургеров", "item": "https://pepperoni.tatar/kotlety-dlya-burgerov"}},
      {{"@type": "ListItem", "position": 3, "name": "{city}", "item": "{url}"}}
    ]
  }}
  </script>
  <style>{CSS}</style>
</head>
<body>
{GTM_NS}
<div class="container">
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
    <a href="/" style="color:#0066cc;text-decoration:none;font-weight:600">Каталог</a>
    <a href="/pepperoni" style="color:#0066cc;text-decoration:none">Пепперони</a>
    <a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
    <a href="/delivery" style="color:#0066cc;text-decoration:none">Доставка</a>
    <a href="/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
  </div>
  <nav aria-label="Breadcrumb" style="font-size:.85rem;color:#888;margin-bottom:24px">
    <a href="/">Каталог</a> &rsaquo; <a href="/kotlety-dlya-burgerov">Котлеты для бургеров</a> &rsaquo; <span>{city}</span>
  </nav>

  <h1>Халяль котлеты для бургеров оптом — {flag} {city}</h1>
  <p class="hero-subtitle">Говяжьи и куриные. Заморозка 360 суток. {loc["logistics"]}</p>
  <span class="badge">HALAL № 614A/2024</span>
  <span class="badge badge-outline">ХАССП</span>
  <span class="badge badge-outline">Заморозка</span>
  <span class="badge badge-outline">{flag} {city}</span>

  <p>{loc["burger_angle"]} Поставляем <strong>халяль котлеты для бургеров</strong> из говядины — прямо с производства «Казанские Деликатесы» в Казани.</p>

  <h2>Ассортимент котлет</h2>
  <div class="prices-grid">
    <div class="price-card"><div class="name">Котлета говяжья прожаренная</div><div class="weight">100 г × 3 шт (0,3 кг)</div><div class="price">276 ₽</div></div>
    <div class="price-card"><div class="name">Котлета говяжья прожаренная</div><div class="weight">150 г × 2 шт (0,3 кг)</div><div class="price">276 ₽</div></div>
  </div>
  <p style="font-size:.85rem;color:#888">Цены без НДС. Оптовые условия и экспортные цены в {loc["currency"]} — по запросу.</p>

  <h2>Характеристики</h2>
  <div class="card">
    <table>
      <tbody>
        <tr><td>Состав</td><td class="spec-value">Говядина халяльного убоя, специи</td></tr>
        <tr><td>Формат</td><td class="spec-value">100 г × 3 шт / 150 г × 2 шт</td></tr>
        <tr><td>Упаковка</td><td class="spec-value">Вакуум / лоток</td></tr>
        <tr><td>Хранение</td><td class="spec-value">360 суток при −18°C</td></tr>
        <tr><td>Сертификация</td><td class="spec-value">Halal № 614A/2024 (ДУМ РТ), ХАССП</td></tr>
        <tr><td>Декларация ЕАЭС</td><td class="spec-value">Есть</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Для {city_gen}: почему выбирают нас</h2>
  <div class="grid-2">
    <div class="feat-card"><div class="icon">☪️</div><div class="title">100% халяль</div><div class="desc">Сертификат № 614A/2024 ДУМ РТ. Говядина халяльного убоя.</div></div>
    <div class="feat-card"><div class="icon">❄️</div><div class="title">360 суток</div><div class="desc">Замороженный формат — удобно для длинных поставок и запасов.</div></div>
    <div class="feat-card"><div class="icon">📋</div><div class="title">Полные документы</div><div class="desc">Декларация ЕАЭС, ветсвидетельства, ФГИС ВЕТИС — всё готово.</div></div>
    <div class="feat-card"><div class="icon">🏷️</div><div class="title">Private Label</div><div class="desc">Производство под вашим брендом для сетей и дистрибьюторов {city_gen}.</div></div>
  </div>

  <h2>Логистика в {city_gen}</h2>
  <div class="card"><p>{loc["logistics"]}</p></div>

  <h2>Также поставляем в {city_gen}</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin:16px 0">
    <a href="/geo/pepperoni-{loc['slug_suffix']}" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;text-decoration:none;color:#1a1a1a;font-size:.88rem">🍕 <strong>Пепперони халяль</strong></a>
    <a href="/geo/sosiki-dlya-hotdog-{loc['slug_suffix']}" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;text-decoration:none;color:#1a1a1a;font-size:.88rem">🌭 <strong>Сосиски для хот-догов</strong></a>
  </div>

  <h2>Связаться</h2>
  <p>Обсудим объёмы, цены и условия поставки в {city_gen}. Ответим в течение нескольких часов.</p>
  <a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
  <a href="mailto:info@kazandelikates.tatar" class="cta cta-outline">📧 info@kazandelikates.tatar</a>

  <footer>
    <p><a href="/">← Каталог</a> &middot; <a href="/pepperoni">Пепперони</a> &middot; <a href="/about">О компании</a> &middot; <a href="/delivery">Доставка</a></p>
    <p>&copy; <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> &middot; <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
  </footer>
</div>
</body>
</html>"""


def build_hotdog_page(loc):
    city = loc["city"]
    city_gen = loc["city_gen"]
    flag = loc["flag"]
    slug = f"sosiki-dlya-hotdog-{loc['slug_suffix']}"
    url = f"https://pepperoni.tatar/geo/{slug}"
    exp = " Экспорт в рамках ЕАЭС." if loc["export"] else ""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="/favicon.ico" type="image/x-icon">
  <title>Халяль сосиски для хот-догов и франч-догов оптом — {city}</title>
  <meta name="description" content="Сосиски для хот-догов и франч-догов халяль оптом в {city_gen}. Говядина, курица. Заморозка 360 суток. ХАССП. Halal № 614A/2024. Поставки от производителя.{exp}">
  <meta name="keywords" content="сосиски для хот-догов {city.lower()}, сосиски для франч-догов {city.lower()}, халяль сосиски {city.lower()}, сосиски для хот-догов оптом {city.lower()}, сосиски гриль {city.lower()}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Сосиски для хот-догов халяль — {city}",
    "description": "Сосиски для хот-догов и франч-догов халяль оптом в {city_gen}. Говядина, курица. Заморозка.",
    "brand": {{"@type": "Brand", "name": "Казанские Деликатесы"}},
    "additionalProperty": [
      {{"@type": "PropertyValue", "name": "Сертификация", "value": "Halal № 614A/2024 (ДУМ РТ)"}},
      {{"@type": "PropertyValue", "name": "Контроль качества", "value": "HACCP"}},
      {{"@type": "PropertyValue", "name": "Рынок", "value": "{city}"}}
    ],
    "offers": {{"@type": "Offer", "priceCurrency": "RUB", "price": "290.00", "availability": "https://schema.org/InStock"}}
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "Каталог", "item": "https://pepperoni.tatar/"}},
      {{"@type": "ListItem", "position": 2, "name": "Сосиски для хот-догов", "item": "https://pepperoni.tatar/sosiki-dlya-hotdog"}},
      {{"@type": "ListItem", "position": 3, "name": "{city}", "item": "{url}"}}
    ]
  }}
  </script>
  <style>{CSS}</style>
</head>
<body>
{GTM_NS}
<div class="container">
  <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
    <a href="/" style="color:#0066cc;text-decoration:none;font-weight:600">Каталог</a>
    <a href="/pepperoni" style="color:#0066cc;text-decoration:none">Пепперони</a>
    <a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
    <a href="/delivery" style="color:#0066cc;text-decoration:none">Доставка</a>
    <a href="/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
  </div>
  <nav aria-label="Breadcrumb" style="font-size:.85rem;color:#888;margin-bottom:24px">
    <a href="/">Каталог</a> &rsaquo; <a href="/sosiki-dlya-hotdog">Сосиски для хот-догов</a> &rsaquo; <span>{city}</span>
  </nav>

  <h1>Халяль сосиски для хот-догов и франч-догов — {flag} {city}</h1>
  <p class="hero-subtitle">Говядина, курица, «Три перца с сыром». Заморозка 360 суток. {loc["logistics"]}</p>
  <span class="badge">HALAL № 614A/2024</span>
  <span class="badge badge-outline">ХАССП</span>
  <span class="badge badge-outline">Франч-дог</span>
  <span class="badge badge-outline">{flag} {city}</span>

  <p>{loc["hotdog_angle"]} Поставляем <strong>халяль сосиски для хот-догов и франч-догов</strong> прямо с производства «Казанские Деликатесы» в Казани.</p>

  <h2>Ассортимент для хот-догов и франч-догов</h2>
  <div class="prices-grid">
    <div class="price-card"><div class="name">Из говядины (80 г × 6 шт)</div><div class="weight">0,48 кг | для хот-дога</div><div class="price">290 ₽</div></div>
    <div class="price-card"><div class="name">Два мяса (80 г × 6 шт)</div><div class="weight">0,48 кг | говядина + курица</div><div class="price">286 ₽</div></div>
    <div class="price-card"><div class="name">Три перца с сыром (80 г × 6 шт)</div><div class="weight">0,48 кг | хит для гриля</div><div class="price">316 ₽</div></div>
    <div class="price-card"><div class="name">Куриные (80 г × 6 шт)</div><div class="weight">0,48 кг | из курицы</div><div class="price">286 ₽</div></div>
    <div class="price-card"><div class="name">С бараниной (80 г × 6 шт)</div><div class="weight">0,48 кг | баранина</div><div class="price">366 ₽</div></div>
    <div class="price-card"><div class="name">С сыром (130 г × 5 шт)</div><div class="weight">0,65 кг | для франч-дога</div><div class="price">455 ₽</div></div>
  </div>
  <p style="font-size:.85rem;color:#888">Цены без НДС. Оптовые условия и экспортные цены в {loc["currency"]} — по запросу.</p>
  <p style="font-size:.85rem;color:#666"><strong>Также доступны без оболочки</strong> — специальный формат для франч-догов, 45 г, упаковка 1 кг.</p>

  <h2>Характеристики</h2>
  <div class="card">
    <table>
      <tbody>
        <tr><td>Состав</td><td class="spec-value">Говядина, курица, баранина халяльного убоя</td></tr>
        <tr><td>Варианты</td><td class="spec-value">6 видов + специальный формат без оболочки</td></tr>
        <tr><td>Упаковка</td><td class="spec-value">Вакуум / термоусадка</td></tr>
        <tr><td>Хранение</td><td class="spec-value">360 суток при −18°C</td></tr>
        <tr><td>Сертификация</td><td class="spec-value">Halal № 614A/2024 (ДУМ РТ), ХАССП</td></tr>
        <tr><td>Декларация ЕАЭС</td><td class="spec-value">Есть</td></tr>
      </tbody>
    </table>
  </div>

  <h2>Для {city_gen}: почему выбирают нас</h2>
  <div class="grid-2">
    <div class="feat-card"><div class="icon">🌭</div><div class="title">Для хот-дога и франч-дога</div><div class="desc">Сосиски 80 г и 130 г под стандартные форматы. Есть вариант без оболочки 45 г.</div></div>
    <div class="feat-card"><div class="icon">☪️</div><div class="title">100% халяль</div><div class="desc">Сертификат № 614A/2024 ДУМ РТ. Говядина, курица, баранина халяльного убоя.</div></div>
    <div class="feat-card"><div class="icon">❄️</div><div class="title">360 суток хранения</div><div class="desc">Заморозка. Удобно формировать запас и не зависеть от частых поставок.</div></div>
    <div class="feat-card"><div class="icon">🔥</div><div class="title">Для гриля и жарки</div><div class="desc">Термостабильные. Не лопаются при жарке. Сохраняют форму и сочность.</div></div>
  </div>

  <h2>Логистика в {city_gen}</h2>
  <div class="card"><p>{loc["logistics"]}</p></div>

  <h2>Также поставляем в {city_gen}</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin:16px 0">
    <a href="/geo/pepperoni-{loc['slug_suffix']}" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;text-decoration:none;color:#1a1a1a;font-size:.88rem">🍕 <strong>Пепперони халяль</strong></a>
    <a href="/geo/kotlety-dlya-burgerov-{loc['slug_suffix']}" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;text-decoration:none;color:#1a1a1a;font-size:.88rem">🍔 <strong>Котлеты для бургеров</strong></a>
  </div>

  <h2>Связаться</h2>
  <p>Обсудим объёмы, цены и условия поставки в {city_gen}. Ответим в течение нескольких часов.</p>
  <a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
  <a href="mailto:info@kazandelikates.tatar" class="cta cta-outline">📧 info@kazandelikates.tatar</a>

  <footer>
    <p><a href="/">← Каталог</a> &middot; <a href="/pepperoni">Пепперони</a> &middot; <a href="/about">О компании</a> &middot; <a href="/delivery">Доставка</a></p>
    <p>&copy; <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> &middot; <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
  </footer>
</div>
</body>
</html>"""


def update_sitemap(slugs):
    sitemap_path = PUBLIC / "sitemap.xml"
    content = sitemap_path.read_text(encoding="utf-8")

    for slug in slugs:
        content = re.sub(
            rf'\s*<url>\s*<loc>https://pepperoni\.tatar/geo/{slug}</loc>.*?</url>',
            '', content, flags=re.DOTALL
        )

    today = "2026-03-11"
    new_urls = ""
    for slug in slugs:
        new_urls += f"""  <url>
    <loc>https://pepperoni.tatar/geo/{slug}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
"""
    content = content.replace("</urlset>", new_urls + "</urlset>")
    sitemap_path.write_text(content, encoding="utf-8")
    print(f"✅ sitemap.xml обновлён ({len(slugs)} страниц)")


def main():
    print(f"🔨 Генерация страниц: котлеты и сосиски по {len(LOCATIONS)} локациям...")
    slugs = []

    for loc in LOCATIONS:
        # Burger patties
        burger_slug = f"kotlety-dlya-burgerov-{loc['slug_suffix']}"
        out = GEO_DIR / f"{burger_slug}.html"
        out.write_text(build_burger_page(loc), encoding="utf-8")
        print(f"  ✅ {out.name}")
        slugs.append(burger_slug)

        # Hot dog sausages
        hotdog_slug = f"sosiki-dlya-hotdog-{loc['slug_suffix']}"
        out = GEO_DIR / f"{hotdog_slug}.html"
        out.write_text(build_hotdog_page(loc), encoding="utf-8")
        print(f"  ✅ {out.name}")
        slugs.append(hotdog_slug)

    update_sitemap(slugs)
    print(f"\n🎉 Готово! 36 страниц в public/geo/")
    return slugs


if __name__ == "__main__":
    main()
