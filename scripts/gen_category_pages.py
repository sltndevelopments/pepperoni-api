#!/usr/bin/env python3
"""
Generate category landing pages for SEO.
Each page targets a specific product category with full schema, FAQ, and internal links.

Run: python scripts/gen_category_pages.py
"""

import json
from pathlib import Path

PUBLIC = Path(__file__).parent.parent / "public"
PRODUCTS = json.loads((PUBLIC / "products.json").read_text())["products"]

GTM = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->"""

GTM_BODY = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

BASE_STYLE = """
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
    .container{max-width:860px;margin:0 auto;padding:40px 24px}
    nav{font-size:.85rem;color:#888;margin-bottom:32px}
    nav a{color:#0066cc;text-decoration:none}
    h1{font-size:2rem;font-weight:700;margin-bottom:8px}
    h2{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}
    h3{font-size:1.05rem;font-weight:600;margin:20px 0 8px}
    p{margin-bottom:14px}
    .badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0;letter-spacing:.5px}
    .badge-outline{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}
    .hero-subtitle{color:#666;font-size:1.05rem;margin-bottom:4px}
    .products-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin:20px 0}
    .product-card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:20px;text-align:left}
    .product-card .sku{font-size:.75rem;color:#aaa;margin-bottom:4px}
    .product-card .name{font-weight:600;font-size:.95rem;margin-bottom:8px;color:#1a1a1a}
    .product-card .meta{font-size:.8rem;color:#888}
    .product-card a{display:inline-block;margin-top:12px;color:#1b7a3d;text-decoration:none;font-weight:600;font-size:.85rem}
    .product-card a:hover{text-decoration:underline}
    table{width:100%;border-collapse:collapse;margin:12px 0}
    th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}
    th{background:#f5f5f5;font-weight:600}
    ul{margin:8px 0 14px 24px}
    li{margin-bottom:4px}
    .cta{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0;font-size:.95rem}
    .cta:hover{background:#15652f}
    .cta-outline{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}
    .cta-outline:hover{background:#1b7a3d;color:#fff}
    .faq-section{margin:48px 0 32px}
    .faq-section details{background:#fff;border:1px solid #e5e5e5;border-radius:8px;margin:8px 0;padding:4px 0}
    .faq-section summary{padding:12px 16px;cursor:pointer;font-weight:600;font-size:.95rem;list-style:none}
    .faq-section summary::-webkit-details-marker{display:none}
    .faq-section summary::before{content:'＋ ';color:#1b7a3d}
    .faq-section details[open] summary::before{content:'－ '}
    .faq-section .ans{padding:4px 16px 14px;color:#555;font-size:.92rem}
    footer{margin-top:60px;padding-top:20px;border-top:1px solid #eee;font-size:.8rem;color:#888;text-align:center}
    footer a{color:#0066cc;text-decoration:none}
"""

def get_products_by_skus(skus):
    sku_set = {s.upper() for s in skus}
    return [p for p in PRODUCTS if p["sku"].upper() in sku_set]


def product_card_html(p):
    slug = p["sku"].lower().replace("-", "-")
    weight = p.get("weight", "")
    shelf = p.get("shelfLife", "")
    meta_parts = []
    if weight:
        meta_parts.append(f"Вес: {weight} кг")
    if shelf:
        meta_parts.append(f"Срок: {shelf}")
    meta = " · ".join(meta_parts)
    return f"""        <div class="product-card">
          <div class="sku">{p["sku"]}</div>
          <div class="name">{p["name"]}</div>
          <div class="meta">{meta}</div>
          <a href="/products/{p["sku"].lower()}/">Подробнее →</a>
        </div>"""


def faq_schema(pairs):
    entities = []
    for q, a in pairs:
        entities.append(f'''    {{
      "@type": "Question",
      "name": {json.dumps(q, ensure_ascii=False)},
      "acceptedAnswer": {{"@type": "Answer", "text": {json.dumps(a, ensure_ascii=False)}}}
    }}''')
    return '[\n' + ',\n'.join(entities) + '\n  ]'


def faq_html(pairs):
    blocks = []
    for q, a in pairs:
        blocks.append(f"""      <details>
        <summary>{q}</summary>
        <div class="ans">{a}</div>
      </details>""")
    return "\n".join(blocks)


def build_page(cfg):
    """cfg keys: slug, title, desc, h1, subtitle, keywords, skus, intro, features, faq_pairs, related_links"""
    products = get_products_by_skus(cfg["skus"])
    cards = "\n".join(product_card_html(p) for p in products)

    offers_json = []
    for p in products:
        offers_json.append(f'''    {{
      "@type": "Offer",
      "name": {json.dumps(p["name"], ensure_ascii=False)},
      "priceCurrency": "RUB",
      "availability": "https://schema.org/InStock",
      "url": "https://pepperoni.tatar/products/{p["sku"].lower()}/"
    }}''')
    offers_str = "[\n" + ",\n".join(offers_json) + "\n  ]"

    faq_pairs = cfg["faq_pairs"]
    faq_ld = faq_schema(faq_pairs)
    faq_block = faq_html(faq_pairs)

    features_html = "\n".join(f"<li>{f}</li>" for f in cfg.get("features", []))

    related_html = ""
    if cfg.get("related_links"):
        links = " · ".join(f'<a href="{u}">{t}</a>' for t, u in cfg["related_links"])
        related_html = f'<p style="margin-top:12px;font-size:.9rem;color:#555;">Смотрите также: {links}</p>'

    url = f"https://pepperoni.tatar/{cfg['slug']}/"

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="content-language" content="ru">
  <title>{cfg["title"]}</title>
  <meta name="description" content="{cfg["desc"]}">
  <meta name="keywords" content="{cfg["keywords"]}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <link rel="alternate" hreflang="ru" href="{url}">
  <link rel="alternate" hreflang="x-default" href="{url}">

  <meta property="og:type" content="product.group">
  <meta property="og:title" content="{cfg["title"]}">
  <meta property="og:description" content="{cfg["desc"]}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
  <meta property="og:locale" content="ru_RU">
  <meta property="og:site_name" content="Pepperoni.tatar — Казанские деликатесы">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{cfg["title"]}">
  <meta name="twitter:description" content="{cfg["desc"]}">
  <meta name="twitter:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": {json.dumps(cfg["h1"], ensure_ascii=False)},
    "description": {json.dumps(cfg["desc"], ensure_ascii=False)},
    "url": "{url}",
    "numberOfItems": {len(products)},
    "itemListElement": [{", ".join(f'{{"@type":"ListItem","position":{i+1},"url":"https://pepperoni.tatar/products/{p["sku"].lower()}/","name":{json.dumps(p["name"],ensure_ascii=False)}}}' for i, p in enumerate(products))}]
  }}
  </script>

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": {faq_ld}
  }}
  </script>

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "Главная", "item": "https://pepperoni.tatar/"}},
      {{"@type": "ListItem", "position": 2, "name": {json.dumps(cfg["h1"], ensure_ascii=False)}, "item": "{url}"}}
    ]
  }}
  </script>

  <style>{BASE_STYLE}</style>
</head>
<body>
{GTM_BODY}
<div class="container">
  <nav><a href="/">← Все продукты</a></nav>

  <p class="hero-subtitle">{cfg["subtitle"]}</p>
  <h1>{cfg["h1"]}</h1>
  <span class="badge">Халяль ДУМ РТ</span>
  <span class="badge badge-outline">ХАССП / ISO 22000</span>
  <span class="badge badge-outline">Без ГМО</span>
  <span class="badge badge-outline">Оптовые поставки</span>

  <p>{cfg["intro"]}</p>

  <h2>Ассортимент ({len(products)} SKU)</h2>
  <div class="products-grid">
{cards}
  </div>

  <h2>Преимущества</h2>
  <ul>
{features_html}
  </ul>

  <h2>Заказать оптом</h2>
  <p>Минимальная партия — от 20 кг. Доставка по России и СНГ. Все сертификаты прилагаются.</p>
  <a class="cta" href="mailto:info@pepperoni.tatar">Запросить прайс</a>
  <a class="cta cta-outline" href="tel:+78432030339">+7 (843) 203-03-39</a>

  {related_html}

  <section class="faq-section">
    <h2>Частые вопросы</h2>
{faq_block}
  </section>

  <footer>
    <p>© 2026 ООО «Казанские Деликатесы» · <a href="/">pepperoni.tatar</a> · Казань, ул. Аграрная, 2 · <a href="tel:+78432030339">+7 (843) 203-03-39</a></p>
  </footer>
</div>
</body>
</html>"""


PAGES = [
    {
        "slug": "sosiski-halyal",
        "title": "Сосиски халяль оптом — купить халяльные сосиски из Казани | pepperoni.tatar",
        "desc": "Сосиски халяль оптом от производителя в Казани. 9 видов: к завтраку, нежные, с сыром, казанские, из говядины. Сертификат ДУМ РТ, ХАССП, без ГМО. Доставка по России и СНГ.",
        "h1": "Сосиски халяль — купить оптом от производителя",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "сосиски халяль, халяльные сосиски, сосиски без свинины, сосиски из говядины халяль, сосиски оптом Казань, купить сосиски халяль",
        "skus": ["KD-026", "KD-027", "KD-028", "KD-029", "KD-030", "KD-031", "KD-032", "KD-033", "KD-034"],
        "intro": "Сосиски и сардельки халяль — натуральные, без ГМО и антибиотиков, из охлаждённого говяжьего и куриного мяса. Производим в Казани с 2018 года по стандартам ХАССП / ISO 22000. Каждая партия сопровождается халяль-сертификатом ДУМ РТ.",
        "features": [
            "Сертификат Halal ДУМ РТ — подходит для мусульман и ЗОЖ-покупателей",
            "9 SKU: от классических к завтраку до сарделек «Буинские»",
            "Без ГМО, без антибиотиков, натуральный состав",
            "Упаковка 0,24–1 кг, хранение 0–6 °C",
            "Оптовые поставки от 20 кг, доставка 2–5 дней по России",
        ],
        "faq_pairs": [
            ("Сосиски халяль — что это значит?", "Все сосиски произведены без использования свинины и свиных субпродуктов, в соответствии с требованиями ислама. Каждая партия сертифицирована Духовным управлением мусульман Республики Татарстан (ДУМ РТ)."),
            ("Можно ли заказать сосиски оптом?", "Да, минимальная партия от 20 кг. Оформите заявку по email info@pepperoni.tatar или по телефону +7 (843) 203-03-39. Предоставляем прайс-лист и образцы."),
            ("Какой состав у сосисок?", "Основа — говядина и/или курица охлаждённая, специи, поваренная соль. Без ГМО, без антибиотиков, без свинины. Подробный состав — в карточке каждого SKU."),
            ("Какой срок хранения?", "Охлаждённые сосиски хранятся при температуре 0–6 °C. Срок хранения указан на упаковке каждого SKU — обычно 30–45 суток."),
        ],
        "related_links": [
            ("Сосиски для хот-догов", "/sosiski-dlya-hotdog/"),
            ("Казылык", "/kazylyk"),
            ("Пепперони", "/pepperoni-dlya-pizzerii"),
        ],
    },
    {
        "slug": "sosiski-dlya-hotdog",
        "title": "Сосиски для хот-догов халяль оптом — гриль-сосиски из Казани | pepperoni.tatar",
        "desc": "Сосиски для хот-догов халяль оптом. 7 видов гриль-сосисок из говядины, курицы, баранины. Срок хранения 360 суток. Сертификат ДУМ РТ. Доставка по России и СНГ.",
        "h1": "Сосиски для хот-догов халяль — гриль, 360 суток хранения",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "сосиски для хот-догов халяль, гриль сосиски халяль, сосиски хот-дог оптом, халяльные хот-дог, сосиски 360 суток хранения",
        "skus": ["KD-001", "KD-002", "KD-003", "KD-004", "KD-005", "KD-006", "KD-007"],
        "intro": "Гриль-сосиски для хот-догов халяль — специально разработаны для уличного фастфуда, кафе, столовых и ресторанов. Срок хранения 360 суток без холодильника (до вскрытия упаковки) делает их идеальными для логистики и торговых точек по всей России и СНГ.",
        "features": [
            "7 SKU: «Из говядины», «Два мяса», «Три перца с сыром», «Куриные», «С бараниной», «С травами», «С сыром»",
            "Срок хранения 360 суток — выгодно для логистики и маленьких точек",
            "Упаковка 80 г × 6 шт и 130 г × 5 шт — форматы для HoReCa",
            "Халяль-сертификат ДУМ РТ, без ГМО, без антибиотиков",
            "Оптовые поставки от 20 кг, доставка по России и СНГ",
        ],
        "faq_pairs": [
            ("Подходят ли сосиски для уличной торговли?", "Да, именно для этого они и созданы. Срок хранения 360 суток (до вскрытия) позволяет хранить продукт без холодильника. После вскрытия — соблюдать холодовую цепочку."),
            ("Можно ли жарить на гриле?", "Да, все 7 SKU разработаны для приготовления на гриле, сковороде или в пароварке. Идеальны для хот-дог станций."),
            ("Есть ли варианты без говядины?", "Да: KD-004 — куриные, KD-005 — с бараниной. Уточняйте состав в карточке продукта."),
            ("Как оформить оптовый заказ?", "Напишите на info@pepperoni.tatar или позвоните +7 (843) 203-03-39. Минимальная партия — от 20 кг. Доставляем по всей России и СНГ."),
        ],
        "related_links": [
            ("Сосиски халяль", "/sosiski-halyal/"),
            ("Котлеты для бургеров", "/kotlety-dlya-burgerov"),
            ("Пепперони для HoReCa", "/pepperoni-dlya-horeca"),
        ],
    },
    {
        "slug": "vetchina-optom",
        "title": "Ветчина халяль оптом — купить ветчину из говядины и индейки | pepperoni.tatar",
        "desc": "Ветчина халяль оптом от производителя: из индейки, говядины, курицы, мраморная. 4 SKU. Сертификат ДУМ РТ, ХАССП. Производство Казань, доставка по России и СНГ.",
        "h1": "Ветчина халяль оптом — из говядины, индейки, курицы",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "ветчина халяль, ветчина из говядины халяль, ветчина оптом Казань, халяльная ветчина купить, ветчина без свинины оптом",
        "skus": ["KD-038", "KD-039", "KD-040", "KD-041"],
        "intro": "Ветчина халяль — натуральный продукт без свинины, приготовленный из цельного мяса говядины, индейки или курицы. Производим в Казани по ХАССП / ISO 22000, каждая партия сопровождается халяль-сертификатом ДУМ РТ. Подходит для розничных магазинов, HoReCa и b2b поставок.",
        "features": [
            "4 SKU: из Индейки, Мраморная с говядиной, из Курицы, Филейная",
            "Цельномышечный продукт — без MDM и механической обвалки",
            "Сертификат Halal ДУМ РТ, без ГМО, без антибиотиков",
            "Упаковка ~0,5 кг, хранение 0–6 °C",
            "Оптом от 20 кг, доставка 2–5 рабочих дней",
        ],
        "faq_pairs": [
            ("Из чего сделана ветчина?", "Ветчина производится из цельного мяса: говядины (KD-039), индейки (KD-038), курицы (KD-040) или куриного филе (KD-041). Без свинины, без ГМО, без антибиотиков."),
            ("Ветчина халяль — можно ли мусульманам?", "Да. Каждая партия проходит халяль-контроль и сертифицируется ДУМ РТ (Духовное управление мусульман Республики Татарстан)."),
            ("Какой срок хранения у ветчины?", "При температуре 0–6 °C срок хранения указан на упаковке. Обычно 20–30 суток для охлаждённой ветчины."),
            ("Как купить ветчину оптом?", "Пишите на info@pepperoni.tatar или звоните +7 (843) 203-03-39. Минимальный заказ — от 20 кг, цена зависит от объёма."),
        ],
        "related_links": [
            ("Копчёные колбасы", "/kolbasy-kopchyonye/"),
            ("Вареные колбасы", "/kolbasy-varenye/"),
            ("Топпинги для пицц", "/toppings"),
        ],
    },
    {
        "slug": "kolbasy-kopchyonye",
        "title": "Копчёные колбасы халяль оптом — сервелат, в/к колбасы из Казани | pepperoni.tatar",
        "desc": "Копчёные колбасы халяль оптом: 15 SKU — сервелат Ханский, по-татарски, Рамазан, Мраморная, Филейный, Княжеская. Без свинины. Сертификат ДУМ РТ. Доставка по России.",
        "h1": "Копчёные колбасы халяль — 15 SKU оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "копчёные колбасы халяль, сервелат халяль, варено-копчёная колбаса халяль, колбасы без свинины оптом, Рамазан колбаса, Ханский сервелат",
        "skus": ["KD-042", "KD-043", "KD-044", "KD-045", "KD-046", "KD-047", "KD-048", "KD-049", "KD-050", "KD-051", "KD-052", "KD-053", "KD-054", "KD-055", "KD-056"],
        "intro": "Копчёные колбасы халяль — 15 SKU для любых форматов торговли. От классического сервелата «Ханский» и «По-татарски» до варено-копчёных батонов «Рамазан», «Мраморная», «Филейный» и «Княжеская» в целом батоне и половинках. Производство в Казани по ХАССП, сертификат Halal ДУМ РТ.",
        "features": [
            "15 SKU: сервелаты, полукопчёные, варено-копчёные батоны в целом и половинном формате",
            "Халяль-сертификат ДУМ РТ — без свинины, без ГМО",
            "Батоны 0,27–1 кг — удобно для нарезки и выкладки",
            "Копчение натуральным дымом на оборудовании из Испании",
            "Оптом от 20 кг, доставка по России и СНГ",
        ],
        "faq_pairs": [
            ("Какие виды копчёных колбас есть?", "Сервелаты: KD-042 Ханский, KD-043 По-татарски. Полукопчёные: KD-044 из Индейки, KD-045 из Говядины, KD-046 Колбаски с Сыром. Варено-копчёные: Рамазан, Мраморная, Филейный, Княжеская — каждая в целом батоне (~0,54 кг) и половинке (~0,27 кг)."),
            ("Колбасы из чего сделаны?", "Из говядины, индейки или курицы. Без свинины, без ГМО, без антибиотиков. Состав каждого SKU — в карточке продукта."),
            ("Как организовать оптовую поставку?", "Email info@pepperoni.tatar или телефон +7 (843) 203-03-39. Минимум 20 кг, доставка 2–5 дней по России."),
            ("Есть ли продукт в нарезке?", "Да, часть SKU доступна в нарезке. Уточните при оформлении заказа."),
        ],
        "related_links": [
            ("Ветчина халяль", "/vetchina-optom/"),
            ("Вареные колбасы", "/kolbasy-varenye/"),
            ("Пепперони топпинги", "/toppings"),
        ],
    },
    {
        "slug": "kolbasy-varenye",
        "title": "Варёные колбасы халяль оптом — купить вареную колбасу из говядины | pepperoni.tatar",
        "desc": "Варёные колбасы халяль оптом: 3 SKU — «Из Говядины», «Ассорти», «Нежная». Без свинины. Сертификат ДУМ РТ. Производство Казань. Доставка по России и СНГ.",
        "h1": "Варёные колбасы халяль — купить оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "варёная колбаса халяль, вареная колбаса без свинины, купить варёную колбасу оптом, халяльная варёная колбаса Казань",
        "skus": ["KD-035", "KD-036", "KD-037"],
        "intro": "Варёные колбасы халяль — классика мясного прилавка без свинины. Три SKU: «Из Говядины» (KD-035), «Ассорти» (KD-036) и «Нежная» (KD-037). Производим в Казани по ХАССП / ISO 22000, каждая партия сопровождается халяль-сертификатом ДУМ РТ.",
        "features": [
            "3 SKU: «Из Говядины», «Ассорти», «Нежная»",
            "Халяль-сертификат ДУМ РТ, без ГМО, без свинины",
            "Упаковка ~0,5 кг, хранение 0–6 °C",
            "Натуральный состав, без лишних добавок",
            "Оптом от 20 кг, доставка по России",
        ],
        "faq_pairs": [
            ("Вареная колбаса халяль — из чего?", "Основа — говядина охлаждённая. «Ассорти» может включать птицу. Без свинины, без ГМО. Точный состав — в карточке SKU."),
            ("Можно ли купить вареную колбасу оптом?", "Да, минимальная партия от 20 кг. Пишите на info@pepperoni.tatar или звоните +7 (843) 203-03-39."),
            ("Какой срок хранения?", "0–6 °C, срок хранения указан на упаковке — обычно 20–30 суток."),
            ("Есть ли аналог «Докторской» без свинины?", "KD-037 «Нежная» — наш аналог нежной вареной колбасы без свинины, с мягким вкусом, подходящий для детей и людей, соблюдающих халяль."),
        ],
        "related_links": [
            ("Сосиски халяль", "/sosiski-halyal/"),
            ("Ветчина оптом", "/vetchina-optom/"),
            ("Копчёные колбасы", "/kolbasy-kopchyonye/"),
        ],
    },
    {
        "slug": "kotlety-dlya-burgerov",
        "title": "Котлеты для бургеров халяль оптом — говяжьи котлеты из Казани | pepperoni.tatar",
        "desc": "Котлеты для бургеров халяль оптом: 100 г × 3 шт и 150 г × 2 шт. Говяжьи, прожаренные. Сертификат ДУМ РТ. Производство Казань. Доставка по России и СНГ.",
        "h1": "Котлеты для бургеров халяль — говяжьи, оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "котлеты для бургеров халяль, халяльные бургер котлеты, говяжьи котлеты оптом, котлеты без свинины, котлеты для бургеров оптом Казань",
        "skus": ["KD-008", "KD-009"],
        "intro": "Котлеты для бургеров халяль — прожаренные говяжьи котлеты, готовые к подаче. Два формата: 100 г × 3 шт (KD-008) и 150 г × 2 шт (KD-009). Идеально для бургерных, кафе, HoReCa. Халяль-сертификат ДУМ РТ, без ГМО.",
        "features": [
            "2 формата: 100 г и 150 г — под любой бургер",
            "Прожаренные — готовы к разогреву и подаче",
            "100% говядина, без свинины, без ГМО",
            "Халяль-сертификат ДУМ РТ",
            "Оптом от 20 кг, доставка по России и СНГ",
        ],
        "faq_pairs": [
            ("Котлеты уже прожарены?", "Да, котлеты прожаренные — достаточно разогреть на гриле, сковороде или в пароварке. Готовы к подаче за 3–5 минут."),
            ("Из чего сделаны котлеты?", "100% говядина охлаждённая, специи, поваренная соль. Без свинины, без ГМО, без антибиотиков."),
            ("Подходят ли для мусульманских заведений?", "Да, каждая партия сертифицирована ДУМ РТ. Вы получаете сертификат Halal с каждой поставкой."),
            ("Как заказать оптом?", "Email info@pepperoni.tatar или +7 (843) 203-03-39. Минимальный заказ от 20 кг."),
        ],
        "related_links": [
            ("Сосиски для хот-догов", "/sosiski-dlya-hotdog/"),
            ("Пепперони для HoReCa", "/pepperoni-dlya-horeca"),
            ("Топпинги для пицц", "/toppings"),
        ],
    },
    {
        "slug": "vyipechka-halyal",
        "title": "Выпечка халяль оптом — татарская и классическая выпечка из Казани | pepperoni.tatar",
        "desc": "Выпечка халяль оптом: 19 SKU — губадия, чебурек, перемяч, сочник, пирожки. Национальная татарская и классическая выпечка. Сертификат ДУМ РТ. Доставка по России.",
        "h1": "Выпечка халяль — татарская и классическая, оптом",
        "subtitle": "Казанские деликатесы · Хлебопечный цех",
        "keywords": "выпечка халяль, татарская выпечка оптом, губадия, чебурек халяль, перемяч, пирожки халяль, сочник купить, выпечка без свинины оптом",
        "skus": ["KD-059", "KD-060", "KD-061", "KD-062", "KD-063", "KD-064", "KD-065", "KD-066", "KD-067",
                 "KD-068", "KD-069", "KD-070", "KD-071", "KD-072", "KD-073", "KD-074", "KD-075", "KD-076", "KD-077"],
        "intro": "Выпечка халяль — 19 SKU национальной татарской и классической выпечки. Губадия с кортом, чебурек, перемяч, эчпочмак, сочник с творогом, пирожки. Производится на отдельном хлебопечном цеху по рецептурам татарской кухни. Сертификат Halal ДУМ РТ.",
        "features": [
            "19 SKU: 9 татарских + 10 классических видов",
            "Национальная татарская выпечка: губадия, чебурек, перемяч, эчпочмак и др.",
            "Классическая: сочник, пирожки, сырники",
            "Халяль-сертификат ДУМ РТ на всю выпечку",
            "Оптом от 20 кг, доставка по России",
        ],
        "faq_pairs": [
            ("Что такое губадия?", "Губадия — традиционный татарский многослойный пирог с рисом, кортом (творогом), яйцом и изюмом. Подаётся на праздники и торжества."),
            ("Чем перемяч отличается от чебурека?", "Перемяч — татарский жареный пирожок с начинкой из мяса с отверстием сверху. Чебурек — большой жареный полукруглый пирог. Оба халяль."),
            ("Можно ли заказать выпечку оптом для кафе?", "Да, оптовые поставки от 20 кг. Доступна штучная и лотковая упаковка для HoReCa. Пишите info@pepperoni.tatar."),
            ("Есть ли выпечка с мясной начинкой?", "Да: чебурек, перемяч, эчпочмак — с говяжьим мясом. Все начинки халяль, без свинины."),
        ],
        "related_links": [
            ("Мясные заготовки", "/myasnyie-zagotovki/"),
            ("Казылык", "/kazylyk"),
            ("О компании", "/about"),
        ],
    },
    {
        "slug": "myasnyie-zagotovki",
        "title": "Мясные заготовки халяль оптом — фарш, филе курицы, куриные кубики | pepperoni.tatar",
        "desc": "Мясные заготовки халяль оптом: фарш говяжий, фарш из куриной кожи, филе бедра куриного в кубике. 5 SKU. Сертификат ДУМ РТ, ХАССП. Казань. Доставка по России.",
        "h1": "Мясные заготовки халяль — фарш и полуфабрикаты оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "мясные заготовки халяль, фарш говяжий халяль, куриные полуфабрикаты халяль, фарш оптом Казань, куриное филе в кубике халяль",
        "skus": ["KD-021", "KD-022", "KD-023", "KD-024", "KD-025"],
        "intro": "Мясные заготовки халяль — 5 SKU для пищевых производств и HoReCa. Фарш говяжий, фарш из куриной кожи, филе бедра куриного в кубике 1×1 см. Используются в производстве пельменей, манты, блюд татарской кухни. Без ГМО, без антибиотиков, сертификат Halal ДУМ РТ.",
        "features": [
            "5 SKU: фарш говяжий, куриный фарш, куриное филе в кубике и др.",
            "Для пищевых производств, HoReCa, кейтеринга",
            "Фасовка по 1 кг — удобно для промышленного использования",
            "Без ГМО, без антибиотиков, сертификат Halal",
            "Оптом от 20 кг, доставка по России",
        ],
        "faq_pairs": [
            ("Для чего используются мясные заготовки?", "Для производства пельменей, манты, блюд татарской кухни (губадия, эчпочмак), котлет, фрикаделей. Популярны у пищевых производств и ресторанов."),
            ("Фарш говяжий — из чего?", "Говяжий фарш KD-021 — из охлаждённой говядины без добавок. Халяль, без свинины, без ГМО."),
            ("Какая фасовка?", "Стандартная — 1 кг. Для больших заказов доступны другие форматы — уточните при заказе."),
            ("Как оформить заказ?", "info@pepperoni.tatar или +7 (843) 203-03-39. Минимум 20 кг."),
        ],
        "related_links": [
            ("Котлеты для бургеров", "/kotlety-dlya-burgerov/"),
            ("Выпечка халяль", "/vyipechka-halyal/"),
            ("Сосиски халяль", "/sosiski-halyal/"),
        ],
    },
]


def main():
    created = 0
    for cfg in PAGES:
        out = PUBLIC / f'{cfg["slug"]}.html'
        html = build_page(cfg)
        out.write_text(html, encoding="utf-8")
        print(f"✅ {out.name} ({len(cfg['skus'])} SKU)")
        created += 1
    print(f"\nВсего создано категорийных страниц: {created}")


if __name__ == "__main__":
    main()
