#!/usr/bin/env python3
"""Generate the compact trust/proof layer from the evidence registry.

The pages deliberately publish fewer claims than the legacy templates.  Every
identity, credential and third-party proof link comes from
``data/evidence_registry.json``; unknown experts, customers and market-access
claims are omitted instead of being filled with synthetic copy.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
EVIDENCE = ROOT / "data" / "evidence_registry.json"
BASE = "https://pepperoni.tatar"


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def link(url: str, label: str) -> str:
    return f'<a href="{e(url)}" rel="noopener noreferrer">{e(label)}</a>'


def facts() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def organization_schema(data: dict) -> dict:
    org = data["organization"]
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": org["@id"],
        "name": org["name"],
        "alternateName": org["alternateName"],
        "legalName": org["legalName"],
        "url": org["url"],
        "telephone": org["telephone"],
        "email": org["email"],
        "address": {
            "@type": "PostalAddress",
            **org["address"],
        },
        "sameAs": org["sameAs"],
    }


def shell(*, lang: str, slug: str, title: str, description: str,
          eyebrow: str, heading: str, lead: str, content: str,
          data: dict) -> str:
    prefix = "/en" if lang == "en" else ""
    canonical = f"{BASE}{prefix}/{slug}" if slug else f"{BASE}{prefix}/"
    alt_slug = slug
    ru_url = f"{BASE}/{alt_slug}" if alt_slug else f"{BASE}/"
    en_url = f"{BASE}/en/{alt_slug}" if alt_slug else f"{BASE}/en/"
    if lang == "ru":
        nav = [
            ("/products", "Каталог"),
            ("/pepperoni", "Пепперони"),
            ("/kontraktnoe-proizvodstvo", "СТМ"),
            ("/certificates", "Сертификаты"),
            ("/about", "О компании"),
        ]
        cta = "Запросить спецификацию"
        menu = "Меню"
    else:
        nav = [
            ("/en/products", "Catalog"),
            ("/en/pepperoni", "Pepperoni"),
            ("/en/private-label", "Private label"),
            ("/en/certificates", "Certificates"),
            ("/en/about", "Company"),
        ]
        cta = "Request specification"
        menu = "Menu"
    nav_html = "".join(f'<a href="{href}">{e(label)}</a>' for href, label in nav)
    org_json = json.dumps(
        organization_schema(data), ensure_ascii=False, separators=(",", ":"))
    web_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": canonical + "#webpage",
        "url": canonical,
        "name": title,
        "description": description,
        "inLanguage": "en" if lang == "en" else "ru",
        "dateModified": data["updated_at"],
        "about": {"@id": data["organization"]["@id"]},
    }, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{e(canonical)}">
<link rel="alternate" hreflang="ru" href="{e(ru_url)}">
<link rel="alternate" hreflang="en" href="{e(en_url)}">
<link rel="alternate" hreflang="x-default" href="{e(ru_url)}">
<script type="application/ld+json">{org_json}</script>
<script type="application/ld+json">{web_json}</script>
<style>
:root{{--green:#166b3a;--green-dark:#0d4b28;--cream:#f7f3e8;--ink:#17231b;--line:#dce3dc;--red:#9e2f25}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:16px/1.65 system-ui,-apple-system,Segoe UI,sans-serif;background:#fff}}
a{{color:var(--green-dark)}}.nav{{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}}
.nav__in{{max-width:1120px;margin:auto;padding:14px 24px;display:flex;align-items:center;gap:24px}}.brand{{font-weight:800;text-decoration:none;color:var(--ink)}}
.nav__links{{margin-left:auto;display:flex;gap:18px;align-items:center}}.nav__links a{{text-decoration:none;font-weight:600;font-size:14px}}
.lang{{border-left:1px solid var(--line);padding-left:18px}}.hero{{background:linear-gradient(135deg,var(--green-dark),var(--green));color:#fff}}
.hero__in,.main{{max-width:960px;margin:auto;padding:64px 24px}}.hero__in{{padding-top:72px;padding-bottom:72px}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-weight:800;font-size:12px;opacity:.78}}
h1{{font-size:clamp(36px,6vw,64px);line-height:1.05;margin:12px 0 20px;max-width:900px}}.lead{{font-size:20px;max-width:760px;opacity:.94}}
h2{{font-size:30px;line-height:1.2;margin:48px 0 16px}}h3{{font-size:20px;margin:28px 0 8px}}p{{max-width:780px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:24px 0}}.card{{border:1px solid var(--line);border-radius:16px;padding:22px;background:#fff}}
.proof{{border-left:4px solid var(--green);padding:14px 18px;background:var(--cream);margin:18px 0}}.muted{{color:#56655b}}.tag{{display:inline-block;padding:4px 9px;border-radius:99px;background:#e7f2eb;color:var(--green-dark);font-size:12px;font-weight:800}}
ul,ol{{padding-left:22px;max-width:780px}}li{{margin:8px 0}}.cta{{margin-top:48px;padding:28px;border-radius:18px;background:var(--green-dark);color:#fff}}.cta a{{color:#fff;font-weight:800}}
footer{{border-top:1px solid var(--line);padding:28px 24px;color:#56655b}}footer div{{max-width:960px;margin:auto}}
@media(max-width:760px){{.nav__links a:not(.lang){{display:none}}.grid{{grid-template-columns:1fr}}.hero__in,.main{{padding-left:18px;padding-right:18px}}}}
</style>
</head>
<body>
<header class="nav"><div class="nav__in"><a class="brand" href="{prefix or '/'}">Kazan Delicacies</a><nav class="nav__links" aria-label="{e(menu)}">{nav_html}<a class="lang" href="{'/' + alt_slug if lang == 'en' else '/en/' + alt_slug}">{'RU' if lang == 'en' else 'EN'}</a></nav></div></header>
<section class="hero"><div class="hero__in"><div class="eyebrow">{e(eyebrow)}</div><h1>{e(heading)}</h1><p class="lead">{e(lead)}</p></div></section>
<main class="main">{content}
<section class="cta"><h2>{e(cta)}</h2><p><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a> · <a href="tel:+79872170202">+7 987 217-02-02</a></p></section>
</main>
<footer><div>© Казанские Деликатесы / Kazan Delicacies · 420061, г. Казань, ул. Аграрная, 2, оф. 7</div></footer>
</body>
</html>
"""


def ru_pages(data: dict) -> dict[str, dict]:
    nodes = {n["id"]: n for n in data["independent_nodes"]}
    dum = nodes["dum_rt_company_119"]["url"]
    iaf = nodes["iaf_fsms_2351_a"]["url"]
    gfc = nodes["gfc_pepperoni_240111"]["url"]
    sweet = nodes["sweet_life_pepperoni_118665"]["url"]
    expo = nodes["prodexpo_2025_profile"]["url"]
    gulfood = nodes["gulfood_russia_profile"]["url"]
    return {
        "about": {
            "title": "О производителе — Казанские Деликатесы",
            "description": "Проверяемые сведения об ООО «Казанские Деликатесы»: адрес, контакты, сертификаты и независимые реестры.",
            "eyebrow": "Проверяемая компания",
            "heading": "Казанские Деликатесы",
            "lead": "Производитель халяльных мясных продуктов и татарской выпечки в Казани. На этой странице — только сведения, которые можно сверить по реестру или первичному документу.",
            "content": f"""
<h2>Идентификация</h2>
<div class="grid"><div class="card"><span class="tag">Юридическое лицо</span><h3>ООО «Казанские Деликатесы»</h3><p>420061, Республика Татарстан, г. Казань, ул. Аграрная, 2, оф. 7.</p></div>
<div class="card"><span class="tag">Связь</span><h3>Единые контакты</h3><p><a href="tel:+79872170202">+7 987 217-02-02</a><br><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a></p></div></div>
<h2>Независимая проверка</h2>
<ul><li>{link(dum, "Карточка компании в реестре Комитета по стандарту «Халяль» ДУМ РТ")}</li><li>{link(iaf, "Запись ISO 22000:2018 в IAF CertSearch")}</li><li>{link(expo, "Профиль участника ПРОДЭКСПО")}</li><li>{link(gulfood, "Экспортный профиль Kazan Delicacies LLC")}</li></ul>
<div class="proof"><strong>Граница утверждений.</strong> География поставки, импортёр, MOQ, срок производства, рецептура и допуск на рынок подтверждаются отдельно для конкретного запроса.</div>
<h2>Что является источником данных</h2><p>Ассортимент, SKU, масса, состав, хранение и цены поступают из утверждённого каталога Google Sheets в <a href="/products">карточки товаров</a>. Сведения о компании и сертификатах ведутся в реестре доказательств.</p>""",
        },
        "capabilities": {
            "title": "Производственные возможности — Казанские Деликатесы",
            "description": "Подтверждённые категории продукции, контроль безопасности и порядок оценки СТМ-проекта без выдуманных объёмов и сроков.",
            "eyebrow": "Возможности по спецификации",
            "heading": "Что можно проверить до запроса цены",
            "lead": "Категории и характеристики товара берутся из действующего каталога. Параметры контрактного производства определяются после проверки технического задания.",
            "content": f"""
<h2>Действующий ассортимент</h2><div class="grid"><div class="card"><h3>Мясные продукты</h3><p>Пепперони, сосиски для хот-догов и гриля, котлеты для бургеров, колбасы, ветчина и казылык. Точный состав и формат — в <a href="/products">карточке SKU</a>.</p></div><div class="card"><h3>Татарская выпечка</h3><p>Актуальные позиции, масса и хранение — в каталоге, синхронизированном с Google Sheets.</p></div></div>
<h2>Контроль</h2><ul><li>{link(dum, "Халяль ДУМ РТ №614А/2024 — реестр")}</li><li>{link(iaf, "ISO 22000:2018 — IAF CertSearch")}</li><li>HACCP и требования ТР ТС 021/2011 — документы для квалификации поставщика предоставляются по запросу.</li></ul>
<h2>СТМ и контрактное производство</h2><p>Для оценки проекта отправьте категорию продукта, состав или референс, массу единицы, тип упаковки, маркировку, предполагаемый канал продаж и объём. После этого компания подтверждает технологическую возможность, документы, образец, коммерческие условия и срок. До такой проверки сайт не публикует универсальный MOQ или обещание запуска.</p>
<p><a href="/kontraktnoe-proizvodstvo">Перейти на единый RU-хаб контрактного производства →</a></p>""",
        },
        "certificates": {
            "title": "Сертификаты и проверка — Казанские Деликатесы",
            "description": "Халяль ДУМ РТ №614А/2024, ISO 22000:2018, HACCP и ТР ТС 021/2011: что подтверждает каждый контур и где проверить запись.",
            "eyebrow": "Документы без сверхобещаний",
            "heading": "Сертификаты и контуры контроля",
            "lead": "Халяль и безопасность пищевой продукции — разные контуры. Мы показываем источник, дату проверки и границы каждого утверждения.",
            "content": f"""
<div class="grid"><div class="card"><span class="tag">Халяль</span><h3>ДУМ РТ №614А/2024</h3><p>Подтверждение халяль-статуса. {link(dum, "Открыть карточку компании в реестре")}.</p></div>
<div class="card"><span class="tag">Food safety</span><h3>ISO 22000:2018</h3><p>Публичная запись FSMS-2351/А. {link(iaf, "Проверить в IAF CertSearch")}.</p></div>
<div class="card"><span class="tag">Процесс</span><h3>HACCP</h3><p>Система анализа рисков и критических контрольных точек. Копия для квалификации поставщика — по запросу.</p></div>
<div class="card"><span class="tag">Регламент</span><h3>ТР ТС 021/2011</h3><p>Требования безопасности пищевой продукции учитываются в производственном контуре.</p></div></div>
<div class="proof"><strong>Граница документов.</strong> Сертификат не означает автоматического допуска на любой рынок. Требования страны импорта проверяются по конкретной поставке.</div>
<h2>Комплект для закупщика</h2><p>Напишите категорию товара и рынок: отдел продаж соберёт актуальную карточку SKU и доступные документы. Дата проверки публичных ссылок в реестре сайта — 26 августа 2026 года.</p>""",
        },
        "cases": {
            "title": "Публичные подтверждения поставщика — Казанские Деликатесы",
            "description": "Независимые карточки дистрибьюторов, выставочные и сертификационные реестры без выдуманных отзывов и результатов.",
            "eyebrow": "Proof, не отзывы",
            "heading": "Публичные подтверждения",
            "lead": "Мы не публикуем анонимные отзывы и не приписываем клиентам результаты. Ниже — внешние страницы, которые закупщик может открыть самостоятельно.",
            "content": f"""
<h2>Дистрибьюторские карточки</h2><div class="grid"><div class="card"><h3>GFC</h3><p>Карточка халяльной пепперони «Казанские Деликатесы» у независимого HoReCa-дистрибьютора.</p><p>{link(gfc, "Открыть карточку GFC →")}</p></div>
<div class="card"><h3>Свит Лайф</h3><p>Публичная товарная карточка пепперони бренда у независимого дистрибьютора.</p><p>{link(sweet, "Открыть карточку Свит Лайф →")}</p></div></div>
<h2>Реестры и выставки</h2><ul><li>{link(dum, "Комитет по стандарту «Халяль» ДУМ РТ")}</li><li>{link(iaf, "IAF CertSearch")}</li><li>{link(expo, "ПРОДЭКСПО")}</li><li>{link(gulfood, "Kazan Delicacies LLC — экспортный профиль")}</li></ul>
<div class="proof"><strong>Как читать страницу.</strong> Внешняя карточка подтверждает только то, что написано на ней. Она не доказывает объём продаж, эксклюзивность, текущий остаток или право поставки в конкретную страну.</div>""",
        },
        "export": {
            "title": "Экспортный запрос — Казанские Деликатесы",
            "description": "Порядок проверки экспортного запроса: SKU, температура, документы, рынок назначения и коммерческие условия без неподтверждённых допусков.",
            "eyebrow": "Экспорт только после проверки",
            "heading": "Что подтвердить до экспортного предложения",
            "lead": "Базис действующего каталога — EXW Казань. Возможность поставки, документы и маршрут проверяются отдельно для выбранного SKU и страны назначения.",
            "content": f"""
<h2>Исходные данные</h2><ol><li>Выберите SKU и приложите требуемую спецификацию.</li><li>Укажите страну и пункт назначения, планируемый объём и температурный режим.</li><li>Передайте требования импортёра, брокера и местного органа сертификации.</li><li>После проверки компания подтверждает доступные документы, упаковку, цену, срок и базис поставки.</li></ol>
<h2>Что можно проверить заранее</h2><ul><li>{link(dum, "Карточка компании и халяль-сертификация в реестре ДУМ РТ")}</li><li>{link(iaf, "ISO 22000:2018 в IAF CertSearch")}</li><li>{link(gulfood, "Публичный экспортный профиль Kazan Delicacies LLC")}</li><li><a href="/products">Актуальные SKU, масса, хранение и цены каталога</a></li></ul>
<div class="proof"><strong>Граница утверждений.</strong> Действующий импортёр, поставка или допуск на рынок публикуются только после появления датированного публичного доказательства.</div>
<h2>Запрос для отдела продаж</h2><p>В письме укажите SKU, рынок назначения, объём, Incoterms, температурный режим, язык маркировки и список обязательных документов. Ответ фиксирует условия только для этого проекта.</p>""",
        },
        "editorial-policy": {
            "title": "Редакционная политика — pepperoni.tatar",
            "description": "Как pepperoni.tatar проверяет факты, обновляет каталог, раскрывает автоматизацию и исправляет ошибки.",
            "eyebrow": "Ответственность за факты",
            "heading": "Редакционная политика",
            "lead": "Автоматизация используется для синхронизации каталога и технической проверки, а не для массового создания похожих страниц или выдумывания фактов.",
            "content": """
<h2>Иерархия источников</h2><ol><li>Google Sheets — ассортимент, SKU, состав, масса, хранение, упаковка, цена и наличие.</li><li>Официальные реестры и первичные документы — сертификаты и юридические сведения.</li><li>Публичные карточки независимых дистрибьюторов и выставок — только для утверждений, прямо указанных на этих страницах.</li><li>Экспертное мнение публикуется только с именем, ролью, согласием и областью проверки. Пока этих данных нет, сайт не создаёт фиктивного автора Person.</li></ol>
<h2>Автоматизация</h2><p>Генераторы допустимы для карточек реальных SKU, фидов, цен и технических файлов. Новая индексируемая страница требует доказанного спроса, отдельной пользовательской задачи и собственного доказательства или данных. Городские клоны и неподтверждённые локали не входят в индекс.</p>
<h2>Исправления</h2><p>Сообщите URL и спорную формулировку на <a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a>. Проверяем источник, исправляем каноническую страницу и обновляем дату только при содержательном изменении.</p>
<h2>Реклама и ИИ</h2><p>Материалы не маскируют рекламу под независимый обзор. ИИ может помогать в структуре и переводе, но факты допускаются к публикации только из утверждённых источников и проходят автоматические проверки на контакты, халяль и запрещённые утверждения.</p>""",
        },
    }


def en_pages(data: dict) -> dict[str, dict]:
    nodes = {n["id"]: n for n in data["independent_nodes"]}
    dum = nodes["dum_rt_company_119"]["url"]
    iaf = nodes["iaf_fsms_2351_a"]["url"]
    gfc = nodes["gfc_pepperoni_240111"]["url"]
    sweet = nodes["sweet_life_pepperoni_118665"]["url"]
    expo = nodes["prodexpo_2025_profile"]["url"]
    gulfood = nodes["gulfood_russia_profile"]["url"]
    return {
        "about": {
            "title": "About the manufacturer — Kazan Delicacies",
            "description": "Verifiable company identity, address, contacts, certifications and independent records for Kazan Delicacies LLC.",
            "eyebrow": "Verifiable company",
            "heading": "Kazan Delicacies",
            "lead": "A halal meat products and Tatar bakery manufacturer in Kazan, Russia. This page publishes only facts that buyers can verify in a registry or primary record.",
            "content": f"""
<h2>Identity</h2><div class="grid"><div class="card"><span class="tag">Legal entity</span><h3>ООО «Казанские Деликатесы»</h3><p>420061, 2 Agrarnaya Street, office 7, Kazan, Republic of Tatarstan, Russia.</p></div><div class="card"><span class="tag">Contact</span><h3>One contact record</h3><p><a href="tel:+79872170202">+7 987 217-02-02</a><br><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a></p></div></div>
<h2>Independent verification</h2><ul><li>{link(dum, "Company record in the Halal Standards Committee registry")}</li><li>{link(iaf, "ISO 22000:2018 record in IAF CertSearch")}</li><li>{link(expo, "PRODEXPO exhibitor profile")}</li><li>{link(gulfood, "Kazan Delicacies LLC export profile")}</li></ul>
<div class="proof"><strong>Claim boundary.</strong> Destination, importer, MOQ, production time, recipe and market access are confirmed per enquiry.</div>
<h2>Data ownership</h2><p>Assortment, SKU, weight, ingredients, storage and price are synchronized from the approved Google Sheets catalog into the <a href="/en/products">product records</a>. Company and certification facts are controlled through the evidence registry.</p>""",
        },
        "capabilities": {
            "title": "Manufacturing capabilities — Kazan Delicacies",
            "description": "Documented product categories, food-safety controls and private-label project qualification without unsupported volumes or timelines.",
            "eyebrow": "Specification-led capability",
            "heading": "What a buyer can verify before pricing",
            "lead": "Product categories and specifications come from the current catalog. Contract-manufacturing parameters are confirmed after a technical brief is reviewed.",
            "content": f"""
<h2>Current assortment</h2><div class="grid"><div class="card"><h3>Meat products</h3><p>Pepperoni, hot-dog and grill sausages, burger patties, sausages, halal ham and kazylyk. Use the <a href="/en/products">SKU record</a> for the current specification.</p></div><div class="card"><h3>Tatar bakery</h3><p>Current products, weights and storage requirements are listed in the catalog synchronized from Google Sheets.</p></div></div>
<h2>Controls</h2><ul><li>{link(dum, "Halal certificate No. 614A/2024 — registry")}</li><li>{link(iaf, "ISO 22000:2018 — IAF CertSearch")}</li><li>HACCP and TR CU 021/2011 documentation is available for supplier qualification on request.</li></ul>
<h2>Private label and contract manufacturing</h2><p>Send the product category, reference or composition, unit weight, packaging, label requirements, sales channel and expected volume. The company then confirms technical feasibility, documentation, sample route, commercial terms and timing. No universal MOQ or launch promise is published before that review.</p><p><a href="/en/private-label">Open the single English private-label hub →</a></p>""",
        },
        "certificates": {
            "title": "Certificates and verification — Kazan Delicacies",
            "description": "Halal No. 614A/2024, ISO 22000:2018, HACCP and TR CU 021/2011 with sources and clear claim boundaries.",
            "eyebrow": "Documents without overclaiming",
            "heading": "Certificates and control frameworks",
            "lead": "Halal status and food safety are separate controls. Each published claim has a source, verification date and stated boundary.",
            "content": f"""
<div class="grid"><div class="card"><span class="tag">Halal</span><h3>DUM RT No. 614A/2024</h3><p>Halal status. {link(dum, "Open the company registry record")}.</p></div><div class="card"><span class="tag">Food safety</span><h3>ISO 22000:2018</h3><p>Public record FSMS-2351/A. {link(iaf, "Verify in IAF CertSearch")}.</p></div><div class="card"><span class="tag">Process</span><h3>HACCP</h3><p>Hazard analysis and critical control points. A supplier-qualification copy is available on request.</p></div><div class="card"><span class="tag">Regulation</span><h3>TR CU 021/2011</h3><p>Food-safety requirements are accounted for in the production control framework.</p></div></div>
<div class="proof"><strong>Document boundary.</strong> A certificate does not grant automatic access to every market. Destination requirements are checked for each proposed shipment.</div>
<h2>Buyer document pack</h2><p>Send the product category and destination market. Sales will provide the current SKU specification and available documents. Public links in this site's registry were checked on 26 August 2026.</p>""",
        },
        "cases": {
            "title": "Public supplier proof — Kazan Delicacies",
            "description": "Independent distributor listings, certification records and exhibition profiles without fabricated testimonials or performance claims.",
            "eyebrow": "Proof, not testimonials",
            "heading": "Public verification points",
            "lead": "We do not publish anonymous testimonials or attribute results to customers. These are third-party pages that a buyer can inspect directly.",
            "content": f"""
<h2>Distributor listings</h2><div class="grid"><div class="card"><h3>GFC</h3><p>An independent HoReCa distributor's listing for Kazan Delicacies halal pepperoni.</p><p>{link(gfc, "Open GFC listing →")}</p></div><div class="card"><h3>Sweet Life</h3><p>A public pepperoni product listing from an independent distributor.</p><p>{link(sweet, "Open Sweet Life listing →")}</p></div></div>
<h2>Registries and exhibitions</h2><ul><li>{link(dum, "Halal Standards Committee registry")}</li><li>{link(iaf, "IAF CertSearch")}</li><li>{link(expo, "PRODEXPO")}</li><li>{link(gulfood, "Kazan Delicacies LLC export profile")}</li></ul>
<div class="proof"><strong>How to read this page.</strong> A third-party listing supports only the statements visible on that page. It does not prove sales volume, exclusivity, current stock or authorization for a destination market.</div>""",
        },
        "export": {
            "title": "Export enquiry — Kazan Delicacies",
            "description": "How an export enquiry is qualified by SKU, temperature, documents, destination and commercial terms without unsupported market-access claims.",
            "eyebrow": "Export after verification",
            "heading": "What must be confirmed before an export offer",
            "lead": "The current catalog basis is EXW Kazan. Shipment feasibility, documents and route are checked for the selected SKU and destination.",
            "content": f"""
<h2>Input required</h2><ol><li>Select the SKU and attach the required specification.</li><li>State the destination, expected volume and temperature regime.</li><li>Provide importer, broker and local certification requirements.</li><li>After review, the company confirms available documents, packaging, price, timing and delivery basis.</li></ol>
<h2>What can be checked now</h2><ul><li>{link(dum, "Company and halal-certification record in the DUM RT registry")}</li><li>{link(iaf, "ISO 22000:2018 in IAF CertSearch")}</li><li>{link(gulfood, "Public Kazan Delicacies LLC export profile")}</li><li><a href="/en/products">Current catalog SKU, weight, storage and price data</a></li></ul>
<div class="proof"><strong>Claim boundary.</strong> A current importer, shipment or market approval is published only after a dated public source exists.</div>
<h2>Sales-enquiry fields</h2><p>Include SKU, destination, volume, Incoterms, temperature regime, label language and mandatory-document list. The response applies only to that project.</p>""",
        },
        "editorial-policy": {
            "title": "Editorial policy — pepperoni.tatar",
            "description": "How pepperoni.tatar verifies facts, updates catalog data, discloses automation and corrects errors.",
            "eyebrow": "Accountability for facts",
            "heading": "Editorial policy",
            "lead": "Automation synchronizes catalog data and runs technical checks. It is not used to mass-publish city variants or invent company facts.",
            "content": """
<h2>Source hierarchy</h2><ol><li>Google Sheets for assortment, SKU, ingredients, weight, storage, packaging, price and availability.</li><li>Official registries and primary documents for certificates and company identity.</li><li>Independent distributor and exhibition pages only for statements they explicitly contain.</li><li>Expert opinion only with a real name, role, consent and review scope. Until supplied, the site does not fabricate Person authors.</li></ol>
<h2>Automation</h2><p>Generators are allowed for real SKU records, feeds, pricing and technical files. A new indexable page requires demonstrated demand, a distinct user task and first-party evidence or owned data. City clones and unsupported locales are excluded from the index.</p>
<h2>Corrections</h2><p>Email the URL and disputed statement to <a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a>. We check the source, correct the canonical page and update its date only after a substantive change.</p>
<h2>Advertising and AI</h2><p>Commercial content is not presented as an independent review. AI may assist structure or translation, but facts can be published only from approved sources and pass deterministic contact, halal and prohibited-claim checks.</p>""",
        },
    }


def main() -> int:
    data = facts()
    for lang, pages in (("ru", ru_pages(data)), ("en", en_pages(data))):
        for slug, page in pages.items():
            out = PUBLIC / (f"en/{slug}.html" if lang == "en" else f"{slug}.html")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                shell(lang=lang, slug=slug, data=data, **page),
                encoding="utf-8",
            )
            print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
