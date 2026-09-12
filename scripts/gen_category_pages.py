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
MANIFEST_PATH = Path(__file__).parent.parent / "data" / "index_manifest.json"

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
    """Deprecated: SKU numbers are positional (KD-${index} from Sheets row
    order) and drift whenever rows are reordered/removed upstream — this
    silently pointed pages at the wrong product after such a shift (see
    data/audit_reconcile.md, 2026-07-05 incident). Prefer
    get_products_by_category, keyed on the stable `category` field.
    """
    sku_set = {s.upper() for s in skus}
    return [p for p in PRODUCTS if p["sku"].upper() in sku_set]


def get_products_by_category(categories):
    """Look products up by the stable `category` field from products.json
    instead of a hardcoded, positional SKU list. Order follows PRODUCTS
    (i.e. catalog/Sheets row order) so page output is stable run-to-run.
    """
    cat_set = {c for c in categories}
    return [p for p in PRODUCTS if p.get("category") in cat_set]


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
          <a href="/products/{p["sku"].lower()}">Подробнее →</a>
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
    """Build a catalog-backed category hub.

    Category copy is deliberately derived here instead of accepted from page
    config. This prevents fixed MOQ, delivery, shelf-life and composition
    claims from drifting away from the approved catalog.
    """
    if "categories" in cfg:
        products = get_products_by_category(cfg["categories"])
    else:
        products = get_products_by_skus(cfg["skus"])
    cards = "\n".join(product_card_html(p) for p in products)

    label = cfg["label"]
    title = f"{label} оптом — каталог Казанских Деликатесов"
    desc = (
        f"{label}: {len(products)} SKU в актуальном каталоге. "
        "Масса, состав, хранение и срок годности указаны в карточках товаров; "
        "условия оптового заказа подтверждает отдел продаж."
    )
    h1 = f"{label} — оптовый каталог"
    intro = (
        f"В категории «{label}» опубликованы {len(products)} позиций из "
        "актуального каталога. Ниже приведены SKU и характеристики из "
        "products.json; коммерческие условия согласуются для конкретного запроса."
    )
    features = [
        f"{len(products)} SKU из синхронизированного каталога",
        "Масса, состав, хранение и срок годности — в карточке каждого SKU",
        "Халяль ДУМ РТ № 614A/2024; HACCP; ISO 22000:2018",
        "MOQ, наличие, документы и логистика подтверждаются для запроса",
    ]
    faq_pairs = [
        (
            f"Какие позиции входят в категорию «{label}»?",
            f"На странице показаны {len(products)} актуальных SKU. "
            "Список формируется из products.json и обновляется вместе с каталогом.",
        ),
        (
            "Где проверить состав и срок хранения?",
            "Точные состав, масса, условия хранения и срок годности указаны "
            "в карточке каждого SKU и на маркировке продукта.",
        ),
        (
            "Как подтверждается статус халяль?",
            "Организация указана в реестре Комитета по стандарту «Халяль» "
            "ДУМ РТ, сертификат № 614A/2024. Актуальный комплект документов "
            "для выбранного SKU предоставляется по запросу.",
        ),
        (
            "Как оформить оптовый запрос?",
            "Укажите SKU, объём и пункт назначения. Наличие, минимальный заказ, "
            "документы и логистику подтвердит отдел продаж: "
            "info@kazandelikates.tatar, +7 987 217-02-02.",
        ),
    ]
    faq_ld = faq_schema(faq_pairs)
    faq_block = faq_html(faq_pairs)

    features_html = "\n".join(f"<li>{f}</li>" for f in features)

    related_html = ""
    if cfg.get("related_links"):
        links = " · ".join(f'<a href="{u}">{t}</a>' for t, u in cfg["related_links"])
        related_html = f'<p style="margin-top:12px;font-size:.9rem;color:#555;">Смотрите также: {links}</p>'

    url = f"https://pepperoni.tatar/{cfg['slug']}"

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="content-language" content="ru">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <meta name="keywords" content="{cfg["keywords"]}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <link rel="alternate" hreflang="ru" href="{url}">
  <link rel="alternate" hreflang="x-default" href="{url}">

  <meta property="og:type" content="product.group">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
  <meta property="og:locale" content="ru_RU">
  <meta property="og:site_name" content="Pepperoni.tatar — Казанские деликатесы">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": {json.dumps(h1, ensure_ascii=False)},
    "description": {json.dumps(desc, ensure_ascii=False)},
    "url": "{url}",
    "numberOfItems": {len(products)},
    "itemListElement": [{", ".join(f'{{"@type":"ListItem","position":{i+1},"url":"https://pepperoni.tatar/products/{p["sku"].lower()}","name":{json.dumps(p["name"],ensure_ascii=False)}}}' for i, p in enumerate(products))}]
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
      {{"@type": "ListItem", "position": 2, "name": {json.dumps(h1, ensure_ascii=False)}, "item": "{url}"}}
    ]
  }}
  </script>

  <style>{BASE_STYLE}</style>
</head>
<body>
{GTM_BODY}
<div class="container">
  <nav><a href="/">← Все продукты</a></nav>

  <p class="hero-subtitle">Казанские Деликатесы · данные актуального каталога</p>
  <h1>{h1}</h1>
  <span class="badge">Халяль ДУМ РТ</span>
  <span class="badge badge-outline">ХАССП / ISO 22000</span>
  <span class="badge badge-outline">Оптовые поставки</span>

  <p>{intro}</p>

  <h2>Ассортимент ({len(products)} SKU)</h2>
  <div class="products-grid">
{cards}
  </div>

  <h2>Преимущества</h2>
  <ul>
{features_html}
  </ul>

  <h2>Заказать оптом</h2>
  <p>Условия заказа, наличие, логистика и доступные документы подтверждаются отделом продаж для выбранных SKU.</p>
  <a class="cta" href="mailto:info@kazandelikates.tatar">Запросить условия</a>
  <a class="cta cta-outline" href="tel:+79872170202">+7 987 217-02-02</a>

  {related_html}

  <section class="faq-section">
    <h2>Частые вопросы</h2>
{faq_block}
  </section>

  <footer>
    <p>ООО «Казанские Деликатесы» · <a href="/">pepperoni.tatar</a> · г. Казань, ул. Аграрная, 2, оф. 7 · <a href="tel:+79872170202">+7 987 217-02-02</a></p>
  </footer>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Commercial category page (pilot 2026-09: /sosiski-dlya-hotdog RU + EN).
# Every number on the page comes from products.json: name, pack format (parsed
# from the name), net weight, price incl./excl. VAT, price per piece, storage,
# shelf life, casing, packaging, gross box weight, photo. Nothing about minimum
# lots, equipment, nutrition or cooking is stated — those are "confirmed by
# sales" until the technologist answers docs/sprint-2026-09/technologist-questions.md.
# ---------------------------------------------------------------------------

CATALOG_META = json.loads((PUBLIC / "products.json").read_text())
LAST_SYNCED = CATALOG_META.get("lastSynced", "")
_HOLDS_PATH = Path(__file__).parent.parent / "data" / "spec_holds.json"
HELD_COMMERCIAL = {
    sku for sku, h in (json.loads(_HOLDS_PATH.read_text(encoding="utf-8")).get("holds", {}) if _HOLDS_PATH.exists() else {}).items()
    if h.get("exclude_from_commercial_pages")
}

COMMERCIAL_STYLE = """
    .container{max-width:1040px}
    .hero{display:grid;grid-template-columns:1.2fr .8fr;gap:28px;align-items:start;margin:12px 0 8px}
    .hero-facts{background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:18px 20px;font-size:.92rem}
    .hero-facts dt{color:#888;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;margin-top:10px}
    .hero-facts dt:first-child{margin-top:0}
    .hero-facts dd{font-weight:600}
    .price-note{font-size:.85rem;color:#666;margin:6px 0 18px}
    .hold-note{font-size:.85rem;color:#8a5a00;background:#fff7e6;border:1px solid #f0d9a8;border-radius:8px;padding:10px 12px;margin:-8px 0 18px}
    .sku-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:18px;margin:16px 0 8px}
    .sku{background:#fff;border:1px solid #e5e5e5;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
    .sku img{width:100%;aspect-ratio:4/3;object-fit:cover;background:#f3f3f3;display:block}
    .sku .body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
    .sku .code{font-size:.75rem;color:#aaa}
    .sku .title{font-weight:650;font-size:.98rem;line-height:1.35}
    .sku .fmt{font-size:.85rem;color:#555}
    .sku .price{font-size:1.25rem;font-weight:700;color:#1b7a3d;margin-top:4px}
    .sku .price small{font-size:.78rem;font-weight:500;color:#777;display:block}
    .sku .derived{font-size:.8rem;color:#777}
    .sku .store{font-size:.8rem;color:#555;border-top:1px dashed #e5e5e5;padding-top:8px;margin-top:6px}
    .sku .links{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:8px;font-size:.85rem}
    .sku .links a{color:#1b7a3d;font-weight:600;text-decoration:none}
    .sku label.pick{display:flex;gap:6px;align-items:center;font-weight:600;color:#333;cursor:pointer}
    .cmp{overflow-x:auto}
    .cmp table{min-width:640px}
    .cmp td.num{text-align:right;white-space:nowrap}
    .order{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start;margin-top:12px}
    .lead-form{background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:20px 22px;position:relative}
    .lead-form label{display:block;font-size:.82rem;font-weight:650;color:#666;margin:14px 0 5px}
    .lead-form label:first-of-type{margin-top:0}
    .lead-form input[type=text],.lead-form input[type=tel],.lead-form textarea{width:100%;padding:10px 12px;border:1px solid #d8d8d8;border-radius:8px;font:inherit;font-size:.95rem}
    .lead-form textarea{resize:vertical}
    .lead-form .consent{display:flex;gap:10px;align-items:flex-start;font-size:.82rem;color:#555;font-weight:400;margin-top:14px}
    .lead-form .consent input{margin-top:3px}
    .lead-form button{margin-top:16px;width:100%;border:0;cursor:pointer}
    .lead-form__status{min-height:1.4em;font-size:.9rem;margin-top:10px}
    .shortlist{font-size:.85rem;color:#555;background:#f5faf6;border:1px dashed #b9dcc3;border-radius:8px;padding:10px 12px;margin-top:8px}
    .shortlist:empty{display:none}
    .clarify{background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:18px 20px}
    .clarify ul{margin-left:20px}
    .clarify li{margin-bottom:8px;font-size:.92rem}
    .contact-line{font-size:.95rem;margin-top:10px}
    .contact-line a{color:#1b7a3d;font-weight:600;text-decoration:none}
    .sku label.pick input{width:20px;height:20px;accent-color:#1b7a3d}
    @media(max-width:720px){.hero,.order{grid-template-columns:1fr}h1{font-size:1.5rem}.sku label.pick{padding:8px 0;min-height:40px}.badge{margin-bottom:8px}}
"""

COMMERCIAL_T = {
    "ru": {
        "lang": "ru", "prefix": "", "home": "Главная", "back": "← Все продукты",
        "title": "Сосиски для хот-догов халяль оптом — цены, форматы, заказ | Казанские Деликатесы",
        "h1": "Сосиски для хот-догов халяль — оптом от производителя",
        "meta": "{n} позиций сосисок для хот-догов халяль: форматы {fmts}, цены за упаковку с НДС по каталогу на {date}, заморозка {storage} и срок годности {shelf}. Фото, масса, ссылки на карточки и форма запроса условий.",
        "eyebrow": "Казанские Деликатесы · Казань · каталог синхронизирован {date}",
        "lead": "Ниже — {n} позиций категории из действующего каталога с ценами и фото. Выберите нужные, укажите объём и город — отдел продаж подтвердит наличие, минимальную партию и доставку.",
        "facts_h": "Общее для категории",
        "f_formats": "Форматы", "f_storage": "Хранение", "f_shelf": "Срок годности", "f_pack": "Упаковка",
        "f_cert": "Сертификаты", "cert": "Халяль ДУМ РТ № 614A/2024 · ХАССП · ISO 22000:2018 · ТР ТС 021/2011",
        "price_note": "Цены — за упаковку, в рублях с НДС, из каталога на {date}; цена без НДС указана под каждой ценой. Цена за килограмм = цена упаковки с НДС ÷ масса нетто (округление до рубля); цена за штуку — из каталога (с НДС, до копейки). Цены при объёме подтверждает отдел продаж. Полный прайс: <a href=\"/wholesale-price-list-ru.md\">MD</a> · <a href=\"/wholesale-price-list-ru.txt\">TXT</a>.",
        "h_assort": "Ассортимент — {n} позиций",
        "hold_note": "Ещё {n_held} позиции категории ({held_list}) временно не показаны: по ним уточняется спецификация состава. Актуальную маркировку запрашивайте у отдела продаж.",
        "per_pack": "за упаковку", "excl": "без НДС {v} ₽", "per_kg": "≈ {v} ₽/кг", "per_pc": "≈ {v} ₽/шт",
        "store": "{storage}, {shelf}", "box": "короб {v} кг брутто",
        "card": "Карточка →", "pick": "В запрос",
        "h_cmp": "Сравнение позиций",
        "cmp_cols": ["SKU", "Название", "Формат", "Масса нетто", "Цена за уп., ₽ с НДС", "≈ ₽/кг", "≈ ₽/шт", "Хранение"],
        "h_order": "Запросить условия",
        "order_lead": "Одна форма — один запрос. Отметьте позиции в карточках выше или напишите свободно: город, формат точки, ориентировочный объём в месяц.",
        "l_name": "Имя", "ph_name": "Как к вам обращаться", "l_phone": "Телефон или WhatsApp *", "ph_phone": "+7 …",
        "l_msg": "Город, тип заведения, объём", "ph_msg": "Например: Уфа, сеть из 4 точек, 300 упаковок в месяц",
        "consent": "Согласен на обработку персональных данных согласно <a href=\"/privacy\">политике конфиденциальности</a>.",
        "submit": "Отправить запрос",
        "msg": {"sending": "Отправляем…", "ok": "Спасибо! Запрос принят — менеджер свяжется с вами.", "err-phone": "Укажите телефон.",
                "err-phone-invalid": "Проверьте номер телефона.", "err-consent": "Необходимо согласие на обработку данных.",
                "err-rate": "Слишком много попыток. Попробуйте позже.", "err-generic": "Не удалось отправить. Позвоните: +7 987 217-02-02.",
                "err-network": "Сеть недоступна. Позвоните: +7 987 217-02-02."},
        "shortlist_prefix": "Позиции в запросе: ",
        "h_clarify": "Что подтверждает отдел продаж",
        "clarify": [
            "Состав паллеты: минимальный заказ — одна паллета, сборная из разных позиций возможна; объём считаем кратно паллете.",
            "Наличие на складе и срок отгрузки на дату заказа.",
            "Доставку: цены — со склада в Казани (EXW); доставку рассчитываем индивидуально (в т. ч. попутным транспортом), оплачивает покупатель; сроки — по согласованию.",
            "Комплект документов: сертификат халяль, декларация соответствия, ВСД (ФГИС «Меркурий»), маркировка «Честный знак», электронная транспортная накладная (ЭТрН).",
            "Цену при объёме и условия оплаты — обсуждаются и подтверждаются по каждому заказу.",
        ],
        "samples": "Перед контрактом рекомендуем проверить продукт на своём оборудовании — образцы для теста согласуем индивидуально, как правило бесплатно.",
        "contact": "Телефон и WhatsApp: <a href=\"tel:+79872170202\">+7 987 217-02-02</a> · <a href=\"mailto:info@kazandelikates.tatar\">info@kazandelikates.tatar</a>",
        "h_faq": "Частые вопросы",
        "faq": [
            ("В каких форматах выпускаются сосиски для хот-догов?",
             "Показанные позиции: {fmts}; масса нетто упаковки — {weights}. Все позиции без оболочки, в вакуумной упаковке. Полный перечень форматов категории подтверждает отдел продаж."),
            ("Как хранить и какой срок годности?",
             "Заморозка {storage}, срок годности {shelf} в закрытой упаковке. Условия после размораживания и вскрытия — на этикетке и в карточке товара."),
            ("Из какого мяса сосиски и где посмотреть состав?",
             "Состав каждой позиции указан в её карточке и на этикетке; в категории есть позиции из говядины, мяса кур, с бараниной и из конины. Свинины нет ни в одной позиции: производство сертифицировано Комитетом по стандарту «Халяль» ДУМ РТ, сертификат № 614A/2024."),
            ("Какая минимальная партия и как быстро отгрузка?",
             "Минимальный заказ — одна паллета; сборная паллета из нескольких позиций возможна, объём считаем кратно паллете. Цены — со склада в Казани (EXW). Наличие и срок отгрузки подтверждает отдел продаж на дату запроса. Укажите позиции и объём в форме выше."),
            ("Цены на странице — актуальные?",
             "Цены берутся из каталога компании и обновляются вместе с ним; на странице указана дата синхронизации ({date}). Цена в заказе фиксируется в счёте."),
        ],
        "footer": "ООО «Казанские Деликатесы» · <a href=\"/\">pepperoni.tatar</a> · г. Казань, ул. Аграрная, 2, оф. 7 · <a href=\"tel:+79872170202\">+7 987 217-02-02</a>",
        "related": [("Копчёные колбасы и деликатесы", "/kolbasy-kopchyonye"), ("Котлеты для бургеров", "/kotlety-dlya-burgerov"), ("Пепперони для пиццерий", "/pepperoni")],
        "related_h": "Смотрите также: ",
    },
    "en": {
        "lang": "en", "prefix": "/en", "home": "Home", "back": "← All products",
        "title": "Halal Hot Dog Sausages Wholesale — Prices, Formats, Enquiry | Kazan Delicacies",
        "h1": "Halal hot dog sausages — wholesale from the manufacturer",
        "meta": "{n} halal hot dog sausage SKUs: formats {fmts}, per-pack prices incl. VAT from the catalog as of {date}, frozen at {storage}, shelf life {shelf}. Photos, weights, product links and an enquiry form.",
        "eyebrow": "Kazan Delicacies · Kazan, Russia · catalog synced {date}",
        "lead": "{n} SKUs of the category from the live catalog, with prices and photos. Tick the ones you need, state volume and city — sales will confirm availability, minimum lot and delivery.",
        "facts_h": "Category facts",
        "f_formats": "Formats", "f_storage": "Storage", "f_shelf": "Shelf life", "f_pack": "Packaging",
        "f_cert": "Certificates", "cert": "Halal DUM RT No. 614A/2024 · HACCP · ISO 22000:2018 · TR CU 021/2011",
        "price_note": "Prices are per pack in RUB incl. VAT from the catalog as of {date}; the excl.-VAT price is shown under each price. Per-kg = pack price incl. VAT ÷ net weight (rounded to the rouble); per-piece comes from the catalog (incl. VAT, to the kopeck). Volume pricing is confirmed by sales. Full price list: <a href=\"/wholesale-price-list.md\">MD</a> · <a href=\"/wholesale-price-list.txt\">TXT</a>.",
        "h_assort": "Assortment — {n} SKUs",
        "hold_note": "{n_held} more SKUs of this category ({held_list}) are temporarily not shown while their ingredient specification is being verified. Request the current label from sales.",
        "per_pack": "per pack", "excl": "excl. VAT {v} ₽", "per_kg": "≈ {v} ₽/kg", "per_pc": "≈ {v} ₽/pc",
        "store": "{storage}, {shelf}", "box": "case {v} kg gross",
        "card": "Product page →", "pick": "Add to enquiry",
        "h_cmp": "Compare SKUs",
        "cmp_cols": ["SKU", "Name", "Format", "Net weight", "Price per pack, ₽ incl. VAT", "≈ ₽/kg", "≈ ₽/pc", "Storage"],
        "h_order": "Request terms",
        "order_lead": "One form — one enquiry. Tick SKUs in the cards above or write freely: city, type of outlet, approximate monthly volume.",
        "l_name": "Name", "ph_name": "How should we address you", "l_phone": "Phone or WhatsApp *", "ph_phone": "+7 … / +998 …",
        "l_msg": "City, outlet type, volume", "ph_msg": "e.g. Tashkent, 4 kiosks, 300 packs per month",
        "consent": "I agree to the processing of personal data under the <a href=\"/privacy\">privacy policy</a>.",
        "submit": "Send enquiry",
        "msg": {"sending": "Sending…", "ok": "Thank you! Enquiry received — a manager will contact you.", "err-phone": "Please enter a phone number.",
                "err-phone-invalid": "Please check the phone number.", "err-consent": "Consent to data processing is required.",
                "err-rate": "Too many attempts. Please try later.", "err-generic": "Could not send. Call us: +7 987 217-02-02.",
                "err-network": "Network unavailable. Call us: +7 987 217-02-02."},
        "shortlist_prefix": "SKUs in enquiry: ",
        "h_clarify": "What sales confirms",
        "clarify": [
            "Pallet build: minimum order is one pallet, mixed pallets of several SKUs are possible; volumes are quoted in pallet multiples.",
            "Stock availability and dispatch lead time on the order date.",
            "Delivery: prices are EXW Kazan warehouse; delivery is quoted individually (including backhaul transport) and paid by the buyer; lead times are agreed per order.",
            "Documents: halal certificate, declaration of conformity, veterinary certificate (Mercury), Chestny ZNAK marking, electronic waybill (ETrN).",
            "Volume pricing and payment terms — discussed and confirmed for each order.",
        ],
        "samples": "Before a contract we recommend testing the product on your own equipment — samples are agreed individually, usually free of charge.",
        "contact": "Phone & WhatsApp: <a href=\"tel:+79872170202\">+7 987 217-02-02</a> · <a href=\"mailto:info@kazandelikates.tatar\">info@kazandelikates.tatar</a>",
        "h_faq": "FAQ",
        "faq": [
            ("Which formats are the hot dog sausages made in?",
             "SKUs shown here: {fmts}; net pack weight — {weights}. All SKUs are skinless, vacuum packed. Sales confirms the full list of formats in the category."),
            ("How are they stored and what is the shelf life?",
             "Frozen at {storage}, shelf life {shelf} in sealed packaging. Conditions after thawing and opening are on the label and product page."),
            ("What meat are they made from and where is the ingredient list?",
             "The ingredient list of every SKU is on its product page and label; the category includes beef, chicken, lamb-containing and horse-meat SKUs. No SKU contains pork: production is certified by the Halal Standards Committee of DUM RT, certificate No. 614A/2024."),
            ("What is the minimum order and how fast is dispatch?",
             "The minimum order is one pallet; a mixed pallet of several SKUs is possible and volumes are quoted in pallet multiples. Prices are EXW Kazan. Stock and dispatch date are confirmed by sales on the enquiry date. State SKUs and volume in the form above."),
            ("Are the prices on this page current?",
             "Prices come from the company catalog and update with it; the sync date is shown on the page ({date}). The order price is fixed in the invoice."),
        ],
        "footer": "Kazan Delicacies LLC · <a href=\"/en/\">pepperoni.tatar/en</a> · Kazan, Agrarnaya st. 2, office 7 · <a href=\"tel:+79872170202\">+7 987 217-02-02</a>",
        "related": [("Smoked sausages and deli meats", "/en/kolbasy-kopchyonye"), ("Burger patties", "/en/kotlety-dlya-burgerov"), ("Pepperoni for pizzerias", "/en/pepperoni")],
        "related_h": "See also: ",
    },
}

_FMT_RE = __import__("re").compile(r"\(?\s*(\d+)\s*г\s*[×xх]\s*(\d+)\s*шт\s*\)?", __import__("re").I)


def _num(v):
    try:
        return float(str(v).replace(",", ".").replace(" ", "").replace("кг", ""))
    except ValueError:
        return None


_DECIMAL_COMMA = True  # RU formatting; build_commercial_page() flips it per language


def _fmt_money(v, digits=0):
    if v is None:
        return "—"
    s = f"{v:,.{digits}f}".replace(",", " ")
    return s.replace(".", ",") if _DECIMAL_COMMA else s


def _pack_format(p, lang):
    m = _FMT_RE.search(p["name"])
    if not m:
        return ""
    g, n = m.group(1), m.group(2)
    return f"{n} × {g} г" if lang == "ru" else f"{n} × {g} g"


_TRANSLATIONS = json.loads((Path(__file__).parent / "translations.json").read_text(encoding="utf-8"))
_EN_FMT_RE = __import__("re").compile(r"\(\s*\d+\s*g\s*[×x]\s*\d+\s*pcs\s*\)", __import__("re").I)


def _clean_name(p, lang):
    """Product name without the pack-format suffix (shown separately).
    EN names come from scripts/translations.json — the same source the EN
    product cards and the EN price list use — never invented here."""
    if lang == "en":
        en = _TRANSLATIONS.get("products", {}).get(p["name"].strip().lower())
        if not en:
            raise SystemExit(f"no EN translation for {p['sku']} «{p['name']}» in scripts/translations.json")
        return _EN_FMT_RE.sub("", en).strip(" ,")
    name = _FMT_RE.sub("", p["name"]).strip(" ,")
    # KD-008 is stored in Sheets as `Сосиски Из конины"` (stray quote, no guillemets) —
    # reported in technologist-questions.md; render consistently until the cell is fixed.
    name = __import__("re").sub(r'^(Сосиски)\s+"?([^«»"]+?)"?$', r"\1 «\2»", name)
    return name.replace('"', "")


def build_commercial_page(cfg, lang):
    global _DECIMAL_COMMA
    _DECIMAL_COMMA = lang == "ru"
    t = COMMERCIAL_T[lang]
    all_products = get_products_by_category(cfg["categories"])
    # Information quarantine: SKUs whose Sheet row contradicts their name are
    # kept out of the active pick list until the technologist confirms them
    # (data/spec_holds.json, exclude_from_commercial_pages). Counts, table and
    # JSON-LD are computed from the shown set only — no "8 SKUs" promise with 6 shown.
    held = [p for p in all_products if p["sku"] in HELD_COMMERCIAL]
    products = [p for p in all_products if p["sku"] not in HELD_COMMERCIAL]
    if not products:
        raise SystemExit(f"no products for {cfg['categories']}")

    formats = sorted({_pack_format(p, lang) for p in products if _pack_format(p, lang)},
                     key=lambda s: int(s.split("×")[1].split()[0]))
    weights = sorted({_num(p.get("weight")) for p in products if _num(p.get("weight"))})
    storage = sorted({p.get("storage", "") for p in products if p.get("storage")})
    shelf = sorted({p.get("shelfLife", "") for p in products if p.get("shelfLife")})
    casings = sorted({p.get("casing", "") for p in products if p.get("casing")})
    packs = sorted({p.get("packageType", "") for p in products if p.get("packageType")})
    if lang == "en":
        shelf = [s.replace("суток", "days").replace("сут", "days") for s in shelf]
        casings = ["skinless" if c == "без оболочки" else c for c in casings]
        packs = ["vacuum" if c == "Вакуум" else c for c in packs]
    else:
        packs = [c.lower() for c in packs]
    fmts = " and ".join(formats) if lang == "en" else " и ".join(formats)
    weights_s = ("; ".join(f"{_fmt_money(w, 2)} kg" for w in weights) if lang == "en"
                 else "; ".join(f"{_fmt_money(w, 2)} кг" for w in weights))
    ctx = {"n": len(products), "fmts": fmts, "date": LAST_SYNCED, "storage": " / ".join(storage),
           "shelf": " / ".join(shelf), "weights": weights_s, "n_held": len(held),
           "held_list": ", ".join(f"{p['sku']} {_clean_name(p, lang)}" for p in held)}
    hold_note = t["hold_note"].format(**ctx) if held else ""

    url = f"https://pepperoni.tatar{t['prefix']}/{cfg['slug']}"
    ru_url = f"https://pepperoni.tatar/{cfg['slug']}"
    en_url = f"https://pepperoni.tatar/en/{cfg['slug']}"
    title = t["title"]
    desc = t["meta"].format(**ctx)

    cards, rows, ld_items = [], [], []
    for i, p in enumerate(products, 1):
        o = p.get("offers") or {}
        price = _num(o.get("price"))
        excl = _num(o.get("priceExclVAT"))
        w = _num(p.get("weight"))
        per_kg = price / w if price and w else None
        # ₽/pc comes only from offers.pricePerPiece (Sheet column / sync-sheets.mjs);
        # the piece count parsed from the name is display-only and must agree with it.
        per_pc = _num(o.get("pricePerPiece"))
        fmt = _pack_format(p, lang)
        m = _FMT_RE.search(p["name"])
        if per_pc and price and m and abs(per_pc * int(m.group(2)) - price) > 1.0:
            fmt = ""  # name and price-per-piece disagree → do not show a pack format
        name = _clean_name(p, lang)
        sku = p["sku"]
        img = p.get("imageMain") or p.get("image") or ""
        card_url = f"{t['prefix']}/products/{sku.lower()}"
        store = t["store"].format(storage=p.get("storage", ""), shelf=(p.get("shelfLife", "").replace("суток", "days") if lang == "en" else p.get("shelfLife", "")))
        box = _num(p.get("boxWeightGross"))
        box_s = (" · " + t["box"].format(v=_fmt_money(box, 1))) if box else ""
        w_s = f"{_fmt_money(w, 2)} {'kg' if lang == 'en' else 'кг'}" if w else ""
        cards.append(f"""      <article class="sku" data-sku="{sku}">
        {'<img src="' + img + '" alt="' + name + '" loading="lazy" width="400" height="300">' if img else ''}
        <div class="body">
          <div class="code">{sku}</div>
          <div class="title">{name}</div>
          <div class="fmt">{fmt}{' · ' if fmt and w_s else ''}{w_s}</div>
          <div class="price">{_fmt_money(price)} ₽ <small>{t['per_pack']} · {t['excl'].format(v=_fmt_money(excl, 2))}</small></div>
          <div class="derived">{t['per_kg'].format(v=_fmt_money(per_kg))}{' · ' + t['per_pc'].format(v=_fmt_money(per_pc, 2)) if per_pc else ''}</div>
          <div class="store">{store}{box_s}</div>
          <div class="links"><label class="pick"><input type="checkbox" data-pick value="{sku} {name}"> {t['pick']}</label><a href="{card_url}">{t['card']}</a></div>
        </div>
      </article>""")
        rows.append(f"<tr><td><a href=\"{card_url}\">{sku}</a></td><td>{name}</td><td>{fmt}</td><td class=\"num\">{w_s}</td>"
                    f"<td class=\"num\">{_fmt_money(price)}</td><td class=\"num\">{_fmt_money(per_kg)}</td><td class=\"num\">{_fmt_money(per_pc, 2) if per_pc else '—'}</td><td>{store}</td></tr>")
        ld_items.append({"@type": "ListItem", "position": i, "url": f"https://pepperoni.tatar{card_url}", "name": p["name"]})

    faq_pairs = [(q.format(**ctx), a.format(**ctx)) for q, a in t["faq"]]
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq_pairs]},
                        ensure_ascii=False)
    list_ld = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "name": t["h1"], "description": desc,
                          "url": url, "numberOfItems": len(products), "itemListElement": ld_items}, ensure_ascii=False)
    crumbs_ld = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": t["home"], "item": f"https://pepperoni.tatar{t['prefix']}/"},
        {"@type": "ListItem", "position": 2, "name": t["h1"], "item": url}]}, ensure_ascii=False)

    msg_attrs = " ".join(f'data-msg-{k}="{v}"' for k, v in t["msg"].items())
    other_lang = ("en", en_url, "English") if lang == "ru" else ("ru", ru_url, "Русский")
    related = " · ".join(f'<a href="{u}">{x}</a>' for x, u in t["related"])
    cmp_head = "".join(f"<th>{c}</th>" for c in t["cmp_cols"])
    clarify = "\n".join(f"<li>{x}</li>" for x in t["clarify"])

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="content-language" content="{lang}">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <link rel="alternate" hreflang="ru" href="{ru_url}">
  <link rel="alternate" hreflang="en" href="{en_url}">
  <link rel="alternate" hreflang="x-default" href="{ru_url}">
  <meta property="og:type" content="product.group">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{products[0].get('imageMain') or 'https://pepperoni.tatar/images/pepperoni-halal.png'}">
  <meta property="og:locale" content="{'ru_RU' if lang == 'ru' else 'en_US'}">
  <meta property="og:site_name" content="Pepperoni.tatar — Казанские деликатесы">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <script type="application/ld+json">{list_ld}</script>
  <script type="application/ld+json">{faq_ld}</script>
  <script type="application/ld+json">{crumbs_ld}</script>
  <style>{BASE_STYLE}{COMMERCIAL_STYLE}</style>
</head>
<body>
{GTM_BODY}
<div class="container">
  <nav><a href="{t['prefix'] or '/'}">{t['back']}</a> · <a href="{other_lang[1]}" hreflang="{other_lang[0]}">{other_lang[2]}</a></nav>

  <p class="hero-subtitle">{t['eyebrow'].format(**ctx)}</p>
  <h1>{t['h1']}</h1>
  <span class="badge">Halal ДУМ РТ № 614A/2024</span>
  <span class="badge badge-outline">HACCP / ISO 22000:2018</span>
  <span class="badge badge-outline">{ctx['storage']} · {ctx['shelf']}</span>

  <div class="hero">
    <div>
      <p>{t['lead'].format(**ctx)}</p>
      <p><a class="cta" href="#zayavka">{t['h_order']}</a> <a class="cta cta-outline" href="tel:+79872170202">+7 987 217-02-02</a></p>
    </div>
    <dl class="hero-facts">
      <dt>{t['f_formats']}</dt><dd>{fmts}</dd>
      <dt>{t['f_storage']}</dt><dd>{ctx['storage']}</dd>
      <dt>{t['f_shelf']}</dt><dd>{ctx['shelf']}</dd>
      <dt>{t['f_pack']}</dt><dd>{', '.join(casings + packs)}</dd>
      <dt>{t['f_cert']}</dt><dd>{t['cert']}</dd>
    </dl>
  </div>

  <h2 id="assortiment">{t['h_assort'].format(**ctx)}</h2>
  <p class="price-note">{t['price_note'].format(**ctx)}</p>
{('  <p class="hold-note">' + hold_note + '</p>') if hold_note else ''}
  <div class="sku-grid">
{chr(10).join(cards)}
  </div>

  <h2>{t['h_cmp']}</h2>
  <div class="cmp"><table><thead><tr>{cmp_head}</tr></thead><tbody>
{chr(10).join(rows)}
  </tbody></table></div>

  <h2 id="zayavka">{t['h_order']}</h2>
  <div class="order">
    <form class="lead-form" id="lead-{cfg['slug']}-{lang}" novalidate data-experiment-id="{cfg['slug']}-{lang}" {msg_attrs}>
      <p style="margin:0 0 4px;font-size:.92rem;color:#555">{t['order_lead']}</p>
      <div class="shortlist" data-shortlist aria-live="polite"></div>
      <input type="hidden" name="category" value="{cfg['label']}">
      <input type="hidden" name="shortlist" value="">
      <label for="lf-name-{lang}">{t['l_name']}</label>
      <input id="lf-name-{lang}" type="text" name="name" placeholder="{t['ph_name']}" autocomplete="name">
      <label for="lf-phone-{lang}">{t['l_phone']}</label>
      <input id="lf-phone-{lang}" type="tel" name="phone" required placeholder="{t['ph_phone']}" autocomplete="tel">
      <label for="lf-msg-{lang}">{t['l_msg']}</label>
      <textarea id="lf-msg-{lang}" name="message" rows="3" placeholder="{t['ph_msg']}"></textarea>
      <input type="text" name="company" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px">
      <label class="consent"><input type="checkbox" name="consent" required><span>{t['consent']}</span></label>
      <button class="cta" type="submit">{t['submit']}</button>
      <p class="lead-form__status" role="status" aria-live="polite"></p>
    </form>
    <div class="clarify">
      <h3 style="margin-top:0">{t['h_clarify']}</h3>
      <ul>
{clarify}
      </ul>
      <p style="font-size:.92rem">{t['samples']}</p>
      <p class="contact-line">{t['contact']}</p>
    </div>
  </div>

  <p style="margin-top:20px;font-size:.9rem;color:#555">{t['related_h']}{related}</p>

  <section class="faq-section">
    <h2>{t['h_faq']}</h2>
{faq_html(faq_pairs)}
  </section>

  <footer><p>{t['footer']}</p></footer>
</div>
<script>
(function(){{
  var box=document.querySelector('[data-shortlist]'),field=document.querySelector('input[name="shortlist"]');
  if(!box||!field)return;
  function sync(){{
    var picked=[].slice.call(document.querySelectorAll('[data-pick]:checked')).map(function(c){{return c.value;}});
    field.value=picked.join('; ');
    box.textContent=picked.length?{json.dumps(t['shortlist_prefix'], ensure_ascii=False)}+picked.join('; '):'';
  }}
  document.addEventListener('change',function(e){{if(e.target&&e.target.hasAttribute('data-pick'))sync();}});
  // The intake server forwards only name/phone/message: fold category + picked
  // SKUs into the message text (capture phase = before lead-form.js reads it).
  var form=field.form,msg=form&&form.querySelector('[name="message"]'),cat=form&&form.querySelector('[name="category"]');
  if(form&&msg)form.addEventListener('submit',function(){{
    var tag='['+(cat?cat.value:'')+']',parts=[];
    var body=msg.value.replace(/\\n*\\[[^\\]]*\\]\\s*(SKU|Позиции)[^\\n]*/g,'').trim();
    parts.push(tag+(field.value?' SKU: '+field.value:''));
    if(body)parts.push(body);
    msg.value=parts.join('\\n').slice(0,1000);
  }},true);
}})();
</script>
<script src="/assets/lead-form.js" defer></script>
</body>
</html>"""


PAGES = [
    {
        "slug": "sosiski-halyal",
        "label": "Сосиски халяль",
        "title": "Сосиски халяль оптом — купить халяльные сосиски из Казани | pepperoni.tatar",
        "desc": "Сосиски халяль оптом от производителя в Казани. 9 видов: к завтраку, нежные, с сыром, казанские, из говядины. Сертификат ДУМ РТ, ХАССП, без ГМО. Доставка по России и СНГ.",
        "h1": "Сосиски халяль — купить оптом от производителя",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "сосиски халяль, халяльные сосиски, сосиски без свинины, сосиски из говядины халяль, сосиски оптом Казань, купить сосиски халяль",
        "categories": ["Сосиски, сардельки"],
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
        "commercial": True,  # pilot 2026-09: build_commercial_page(), text below is legacy and unused
        "label": "Сосиски для хот-догов халяль",
        "title": "Сосиски для хот-догов халяль оптом — гриль-сосиски из Казани | pepperoni.tatar",
        "desc": "Сосиски для хот-догов халяль оптом. 7 видов гриль-сосисок из говядины, курицы, баранины. Срок хранения 360 суток. Сертификат ДУМ РТ. Доставка по России и СНГ.",
        "h1": "Сосиски для хот-догов халяль — гриль, 360 суток хранения",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "сосиски для хот-догов халяль, гриль сосиски халяль, сосиски хот-дог оптом, халяльные хот-дог, сосиски 360 суток хранения",
        "categories": ["Сосиски гриль для хот-догов"],
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
        "label": "Ветчина халяль",
        "title": "Ветчина халяль оптом — купить ветчину из говядины и индейки | pepperoni.tatar",
        "desc": "Ветчина халяль оптом от производителя: из индейки, говядины, курицы, мраморная. 4 SKU. Сертификат ДУМ РТ, ХАССП. Производство Казань, доставка по России и СНГ.",
        "h1": "Ветчина халяль оптом — из говядины, индейки, курицы",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "ветчина халяль, ветчина из говядины халяль, ветчина оптом Казань, халяльная ветчина купить, ветчина без свинины оптом",
        "categories": ["Ветчины"],
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
        "label": "Копчёные колбасы халяль",
        "title": "Копчёные колбасы халяль оптом — сервелат, в/к колбасы из Казани | pepperoni.tatar",
        "desc": "Копчёные колбасы халяль оптом: 15 SKU — сервелат Ханский, по-татарски, Рамазан, Мраморная, Филейный, Княжеская. Без свинины. Сертификат ДУМ РТ. Доставка по России.",
        "h1": "Копчёные колбасы халяль — 15 SKU оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "копчёные колбасы халяль, сервелат халяль, варено-копчёная колбаса халяль, колбасы без свинины оптом, Рамазан колбаса, Ханский сервелат",
        "categories": ["Копченые"],
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
            ("Как организовать оптовый запрос?", "Укажите нужные SKU, объём и пункт назначения. Актуальные наличие, минимальный заказ, документы и логистику подтвердит отдел продаж: info@kazandelikates.tatar, +7 987 217-02-02."),
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
        "label": "Варёные колбасы халяль",
        "title": "Варёные колбасы халяль оптом — купить вареную колбасу из говядины | pepperoni.tatar",
        "desc": "Варёные колбасы халяль оптом: 3 SKU — «Из Говядины», «Ассорти», «Нежная». Без свинины. Сертификат ДУМ РТ. Производство Казань. Доставка по России и СНГ.",
        "h1": "Варёные колбасы халяль — купить оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "варёная колбаса халяль, вареная колбаса без свинины, купить варёную колбасу оптом, халяльная варёная колбаса Казань",
        "categories": ["Вареные"],
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
        "label": "Котлеты для бургеров халяль",
        "title": "Котлеты для бургеров халяль оптом — говяжьи котлеты из Казани | pepperoni.tatar",
        "desc": "Котлеты для бургеров халяль оптом: 100 г × 3 шт и 150 г × 2 шт. Говяжьи, прожаренные. Сертификат ДУМ РТ. Производство Казань. Доставка по России и СНГ.",
        "h1": "Котлеты для бургеров халяль — говяжьи, оптом",
        "subtitle": "Казанские деликатесы · Производство с 2018 года",
        "keywords": "котлеты для бургеров халяль, халяльные бургер котлеты, говяжьи котлеты оптом, котлеты без свинины, котлеты для бургеров оптом Казань",
        "categories": ["Котлеты для бургеров"],
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
        "label": "Выпечка халяль",
        "title": "Выпечка халяль оптом — татарская и классическая выпечка из Казани | pepperoni.tatar",
        "desc": "Выпечка халяль оптом: 19 SKU — губадия, чебурек, перемяч, сочник, пирожки. Национальная татарская и классическая выпечка. Сертификат ДУМ РТ. Доставка по России.",
        "h1": "Выпечка халяль — татарская и классическая, оптом",
        "subtitle": "Казанские деликатесы · Хлебопечный цех",
        "keywords": "выпечка халяль, татарская выпечка оптом, губадия, чебурек халяль, перемяч, пирожки халяль, сочник купить, выпечка без свинины оптом",
        "categories": ["Национальная татарская выпечка", "Классическая выпечка"],
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
            ("Казылык", "/kazylyk"),
            ("Сосиски халяль", "/sosiski-halyal/"),
            ("О компании", "/about"),
        ],
    },
    # "myasnyie-zagotovki" (farsh/meat-preps) removed 2026-07-05: the product
    # line no longer exists in products.json (discontinued from Google Sheets
    # catalog). Page returns 410 via nginx — see data/audit_reconcile.md.
    # Do not re-add unless the product line actually returns to the catalog.
]


def main():
    if not MANIFEST_PATH.exists():
        raise SystemExit("index manifest is required before category generation")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    approved = {
        entry["file"]
        for entry in manifest.get("entries", [])
        if entry.get("status") == "keep"
    }
    created = 0
    for cfg in PAGES:
        out = PUBLIC / f'{cfg["slug"]}.html'
        rel = out.relative_to(PUBLIC).as_posix()
        if rel not in approved:
            print(f"⏭️  {out.name} skipped (not in index allowlist)")
            continue
        if cfg.get("commercial"):
            out.write_text(build_commercial_page(cfg, "ru"), encoding="utf-8")
            out_en = PUBLIC / "en" / f'{cfg["slug"]}.html'
            if out_en.relative_to(PUBLIC).as_posix() in approved:
                out_en.write_text(build_commercial_page(cfg, "en"), encoding="utf-8")
                print(f"✅ en/{out_en.name} (commercial)")
            else:
                print(f"⏭️  en/{out_en.name} skipped (not in index allowlist)")
            shown = [p for p in get_products_by_category(cfg["categories"]) if p["sku"] not in HELD_COMMERCIAL]
            print(f"✅ {out.name} (commercial, {len(shown)} SKU shown, {len(HELD_COMMERCIAL & {p['sku'] for p in get_products_by_category(cfg['categories'])})} on hold)")
            created += 1
            continue
        html = build_page(cfg)
        out.write_text(html, encoding="utf-8")
        n_skus = len(get_products_by_category(cfg["categories"])) if "categories" in cfg else len(cfg["skus"])
        print(f"✅ {out.name} ({n_skus} SKU)")
        created += 1
    print(f"\nВсего создано категорийных страниц: {created}")


if __name__ == "__main__":
    main()
