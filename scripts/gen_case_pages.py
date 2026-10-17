#!/usr/bin/env python3
"""Private /cases/<slug> drafts for client consent.

Facts only from evidence_registry, site_facts, products.json and already
published public pages. Missing numbers stay [УТОЧНИТЬ]. Pages are
noindex,nofollow and must not be added to the index allowlist or sitemap.
"""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from landing_chrome import stylesheet_link, topbar_html  # noqa: E402
from organization_ld import ORGANIZATION  # noqa: E402
from site_facts import FACTS, cert_line_ru  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
BASE = "https://pepperoni.tatar"
PHONE = FACTS["company"]["phone"]
EMAIL = FACTS["company"]["email"]
ADDR = FACTS["company"]["address_ru"]
LEGAL = FACTS["company"]["legal_name_ru"]
MOQ = FACTS["terms"]["moq"]
BASIS = FACTS["terms"]["basis"]
PL_MIN = FACTS["terms"]["private_label_min"]
CAPACITY = FACTS["terms"]["capacity"]
SKU_N = FACTS["catalog"]["sku_count"]
KD013 = FACTS["catalog"]["pepperoni"]["KD-013"]


def _org() -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(ORGANIZATION, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def _crumbs(slug: str, name: str) -> str:
    ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная",
             "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": name,
             "item": f"{BASE}/cases/{slug}"},
        ],
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(ld, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )


def page(slug: str, title: str, h1: str, body: str) -> str:
    url = f"{BASE}/cases/{slug}"
    desc = (
        "Черновик страницы для согласования с клиентом. Не для индексации. "
        "Факты только из внутренних источников pepperoni.tatar."
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<meta name="robots" content="noindex, nofollow">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.ico" sizes="any">
{_org()}
{_crumbs(slug, h1)}
{stylesheet_link()}
</head>
<body class="kd-landing">
{topbar_html("ru", f"cases/{slug}", cta_href="/kak-zakazat", bilingual=False)}
<div class="container">
<p class="kd-clarify"><strong>Черновик для согласия клиента.</strong>
Страница закрыта от индексации (noindex, nofollow), не в sitemap и не
в публичной навигации. Публикация в индекс — только после явного согласия.</p>
<h1>{escape(h1)}</h1>
{body}
<p><a class="cta" href="tel:+79872170202">{escape(PHONE)}</a>
<a class="cta cta-outline" href="mailto:{escape(EMAIL)}">{escape(EMAIL)}</a></p>
<footer><p>{escape(LEGAL)} · {escape(ADDR)} · {escape(PHONE)}</p></footer>
</div>
</body>
</html>
"""


def clarify(text: str) -> str:
    return f'<p class="kd-clarify">[УТОЧНИТЬ: {escape(text)}]</p>'


def src_list(rows: list[tuple[str, str]]) -> str:
    items = "".join(
        f"<li><strong>{escape(fact)}</strong> — {escape(src)}</li>"
        for fact, src in rows
    )
    return (
        "<h2>Источники фактов на этой странице</h2>"
        "<p>Список для сверки перед согласием. Новых цифр и цитат здесь нет.</p>"
        f"<ul>{items}</ul>"
    )


def gfc() -> str:
    w = KD013["weight_kg"]
    fmt = KD013["format_ru"]
    body = f"""
<p class="lead">В реестре доказательств есть карточка независимого дистрибьютора
GFC на пепперони халяль производства «Казанские Деликатесы». Это не договор
и не объём отгрузки — только публичная карточка товара.</p>
<h2>Что зафиксировано в реестре</h2>
<p>Запись <code>gfc_pepperoni_240111</code> (тип <code>distributor_product</code>,
проверена 2026-08-26) указывает URL карточки GFC и поддерживает два тезиса:
бренд продаётся через независимого дистрибьютора HoReCa; на карточке —
халяль пепперони в нарезке.</p>
<p>Адрес карточки:
<a href="https://gfc-russia.ru/catalog/myasnaya-gastronomiya/kolbasy-vetchina-bekon/240111-kolbasa-pepperoni-halyal-narezka-v-k-zam-kazanskie-delikatesy-500gr-10sht-kor" rel="nofollow noopener">gfc-russia.ru, позиция 240111</a>.
В slug карточки читаются признаки: пепперони халяль, нарезка, варёно-копчёный,
заморозка, «Казанские Деликатесы», 500 г, 10 шт. в коробе.</p>
<h2>Что есть в каталоге производителя</h2>
<p>В <code>products.json</code> / <code>site_facts.json</code> позиция
<strong>KD-013</strong> — пепперони {escape(fmt)}, масса {w} кг, в продаже.
Совпадение массы и формата с карточкой GFC — наблюдение по полям каталога,
не подтверждённая идентификация SKU.</p>
{clarify("подтвердить, что карточка GFC 240111 = KD-013, а не другая фасовка")}
{clarify("объём отгрузок в GFC, период сотрудничества, география складов дистрибьютора")}
{clarify("цитата или отзыв GFC — сейчас в репозитории цитаты нет")}
<h2>Как это сформулировано на публичных страницах</h2>
<p>На <a href="/cases">/cases</a> и <a href="/about">/about</a> GFC назван
федеральным фудсервис-дистрибьютором вместе со «СвитЛайф». В инвентаре
клиентских упоминаний
(<code>docs/audits/customer-reference-inventory-2026-09.md</code>) у GFC
как раз есть запись в <code>evidence_registry.json</code> — в отличие от
большинства имён на той же странице.</p>
<p>Публичная формулировка «поставляют наш термостабильный пепперони, сосиски
и полуфабрикаты» на /about шире, чем запись реестра (реестр фиксирует
пепперони). Для этой черновой страницы оставляем только реестр + каталог.</p>
<h2>Рамка поставки производителя (не условия GFC)</h2>
<p>Общие условия завода из <code>site_facts.json</code>: базис {escape(BASIS)},
минимум {escape(MOQ)}, в каталоге {SKU_N} SKU. Сертификаты: {escape(cert_line_ru())}.
Это не условия контракта с GFC.</p>
{src_list([
    ("карточка GFC 240111, тип distributor_product",
     "data/evidence_registry.json id=gfc_pepperoni_240111"),
    ("KD-013 нарезка 0,5 кг, on_sale",
     "data/site_facts.json catalog.pepperoni.KD-013 + public/products.json"),
    ("имя GFC на публичных /cases и /about",
     "public/cases.html, public/about.html"),
    ("классификация: реестр есть, роль смесится с другими именами",
     "docs/audits/customer-reference-inventory-2026-09.md"),
    ("базис, MOQ, сертификаты завода",
     "data/site_facts.json terms + certificates"),
])}
"""
    return page("gfc", "Черновик кейса: GFC — Казанские Деликатесы",
                "GFC — карточка дистрибьютора (черновик для согласования)", body)


def sweet_life() -> str:
    body = f"""
<p class="lead">В реестре доказательств есть карточка независимого дистрибьютора
«СвитЛайф» (Sweet Life) на пепперони халяль. Как и у GFC, это факт витрины,
не объём и не срок договора.</p>
<h2>Что зафиксировано в реестре</h2>
<p>Запись <code>sweet_life_pepperoni_118665</code> (тип
<code>distributor_product</code>, проверена 2026-08-26) указывает
<a href="https://swlife.ru/118665" rel="nofollow noopener">swlife.ru/118665</a>
и поддерживает: бренд продаётся через независимого дистрибьютора HoReCa;
на карточке — халяль пепперони.</p>
{clarify("фасовка, SKU производителя и цена на карточке СвитЛайф 118665")}
{clarify("объём, период, какие ещё позиции кроме пепперони идут через СвитЛайф")}
{clarify("цитата или отзыв «СвитЛайф» — в репозитории цитаты нет")}
<h2>Публичные страницы</h2>
<p>На <a href="/cases">/cases</a> имя записано как федеральный
фудсервис-дистрибьютор вместе с GFC. На <a href="/about">/about</a> —
та же пара «GFC и СвитЛайф». Инвентарь 2026-09 отмечает, что у «СвитЛайф»
есть id в реестре; смешение ролей на публичных страницах всё равно
требует классификации владельца.</p>
<p>Формулировку /about про «термостабильный пепперони, сосиски и полуфабрикаты
по всей России» на эту страницу не копируем: реестр подтверждает только
пепперони на одной карточке.</p>
<h2>Рамка поставки производителя (не условия «СвитЛайф»)</h2>
<p>Базис {escape(BASIS)}, минимум {escape(MOQ)}, каталог {SKU_N} SKU.
Сертификаты: {escape(cert_line_ru())}.</p>
{src_list([
    ("карточка swlife.ru/118665",
     "data/evidence_registry.json id=sweet_life_pepperoni_118665"),
    ("имя «СвитЛайф» на /cases и /about",
     "public/cases.html, public/about.html"),
    ("инвентарь: реестр есть, роль смешана с другими именами",
     "docs/audits/customer-reference-inventory-2026-09.md"),
    ("базис, MOQ, сертификаты завода",
     "data/site_facts.json"),
])}
"""
    return page(
        "sweet-life",
        "Черновик кейса: СвитЛайф — Казанские Деликатесы",
        "«СвитЛайф» — карточка дистрибьютора (черновик для согласования)",
        body,
    )


def tatneft() -> str:
    body = f"""
<p class="lead">Имя сети АЗС «Татнефть» уже опубликовано на нескольких
страницах pepperoni.tatar. В <code>evidence_registry.json</code> отдельной
записи на это имя нет. Ниже — только уже сказанное на сайте, без новых
объёмов и без цитат.</p>
<h2>Что уже написано публично</h2>
<p>На <a href="/cases">/cases</a>: «Халяль сосиски для хот-догов и котлеты
для бургеров — во всех АЗС сети. В ряде АЗС региона — также наша татарская
выпечка.»</p>
<p>На <a href="/about">/about</a>: поставки халяльных сосисок для хот-догов
и котлет для бургеров на АЗС по всей сети; татарская выпечка в зоне кафе
на региональных комплексах. Рядом в том же блоке указан оператор АЗС
SMARTEN — это другое имя, не часть этого черновика.</p>
<p>На <a href="/sosiski-dlya-hotdog">/sosiski-dlya-hotdog</a>: сосиски для
хот-догов и котлеты для бургеров этой линейки поставляются в сеть АЗС
«Татнефть»; объёмы и цены по каждому контракту страница прямо не раскрывает.</p>
<p>Инвентарь <code>docs/audits/customer-reference-inventory-2026-09.md</code>
помечает эти формулировки как «supply to petrol stations» без записи в
реестре и с пометкой, что владельцу нужно классифицировать роль
(контракт / полка / пилот).</p>
{clarify("роль: прямой договор с ПАО «Татнефть», оператор АЗС, франчайзи или пилот")}
{clarify("число АЗС, регионы, SKU в матрице, срок сотрудничества")}
{clarify("цитата представителя сети — в репозитории цитаты нет")}
<h2>Что можно сказать про продукт без привязки к объёму клиента</h2>
<p>Сосиски для хот-догов и котлеты описаны на категории
<a href="/sosiski-dlya-hotdog">/sosiski-dlya-hotdog</a> и в каталоге
({SKU_N} SKU). Общие условия завода: базис {escape(BASIS)}, минимум
{escape(MOQ)}. Сертификаты: {escape(cert_line_ru())}.</p>
<p>В очереди Telegram/YouTube (<code>data/youtube-from-telegram/pending.json</code>)
есть черновые тексты про хот-доги на АЗС «Татнефть» и про выпечку в
«Мираторг». Это не опубликованные и не верифицированные цитаты клиента —
на страницу их не переносим.</p>
{src_list([
    ("сосиски и котлеты во всех АЗС сети; выпечка в ряде АЗС региона",
     "public/cases.html"),
    ("сосиски и котлеты по всей сети; выпечка в кафе региональных комплексов",
     "public/about.html"),
    ("поставка в сеть АЗС; объёмы не раскрываем",
     "public/sosiski-dlya-hotdog.html"),
    ("нет id в evidence_registry; нужна классификация роли",
     "docs/audits/customer-reference-inventory-2026-09.md"),
    ("базис, MOQ, сертификаты, число SKU",
     "data/site_facts.json"),
])}
"""
    return page(
        "tatneft",
        "Черновик кейса: Татнефть — Казанские Деликатесы",
        "Сеть АЗС «Татнефть» (черновик для согласования)",
        body,
    )


def aslam() -> str:
    body = f"""
<p class="lead">Публичные страницы описывают контрактную линейку традиционных
колбас под маркой «Aslam» для АО «ОМПК» (Мясокомбинат «Останкино»).
В <code>evidence_registry.json</code> отдельной записи на Aslam / ОМПК нет.
Пепперони в этой линейке публичные тексты прямо исключают.</p>
<h2>Что уже написано публично</h2>
<p>На <a href="/about">/about</a>: контрактное производство линейки
традиционных колбас под маркой «Aslam» для АО «ОМПК» строго по утверждённой
рецептуре заказчика; в скобках — «пепперони в этой линейке нет».</p>
<p>На <a href="/cases">/cases</a>: частная марка для АО «Останкинский
мясоперерабатывающий комбинат»; работа по ТУ заказчика, пакет документов,
сертификат халяль ДУМ РТ. Блок «от 5 тонн» на той странице совпадает с
общим минимумом СТМ завода, это не объём отгрузок Aslam.</p>
<p>Инвентарь 2026-09: это проект СТМ, не закупка пепперони; записи в реестре
нет; роль нужно классифицировать владельцу.</p>
{clarify("какие SKU входят в линейку Aslam, калибры, оболочки, срок договора")}
{clarify("фактический тираж и периодичность отгрузок Aslam — не подставлять общие 5 т")}
{clarify("цитата ОМПК / Aslam — в репозитории цитаты нет")}
<h2>Общие условия СТМ завода (не объём Aslam)</h2>
<p>Из <code>evidence_registry.json</code> id <code>private_label_min_run_5t</code>:
минимальный тираж СТМ — от {escape(PL_MIN)}; остальные условия по договору.
Мощность площадки — {escape(CAPACITY)} (id <code>capacity_12t_per_shift</code>).
Базис опта {escape(BASIS)}, минимум опта {escape(MOQ)}.
Сертификаты: {escape(cert_line_ru())}.</p>
<p>Схему «давальческое сырьё / под ключ» и формулировки про R&amp;D с /about
сюда не копируем как факты Aslam: это общие условия завода, не подтверждённые
для этого клиента в реестре.</p>
{src_list([
    ("линейка традиционных колбас Aslam для АО ОМПК; пепперони нет",
     "public/about.html"),
    ("частная марка для Останкино; работа по ТУ; халяль ДУМ РТ",
     "public/cases.html"),
    ("нет id в evidence_registry; СТМ, не закупка пепперони",
     "docs/audits/customer-reference-inventory-2026-09.md"),
    ("минимум СТМ от 5 т — общий, не объём Aslam",
     "data/evidence_registry.json id=private_label_min_run_5t; data/site_facts.json terms.private_label_min"),
    ("мощность 12 т/смена — завод, не клиент",
     "data/evidence_registry.json id=capacity_12t_per_shift"),
])}
"""
    return page(
        "aslam-ompk",
        "Черновик кейса: Aslam / ОМПК — Казанские Деликатесы",
        "Марка «Aslam» для АО «ОМПК» (черновик для согласования)",
        body,
    )


def main() -> int:
    out = PUBLIC / "cases"
    out.mkdir(parents=True, exist_ok=True)
    writers = {
        "gfc": gfc,
        "sweet-life": sweet_life,
        "tatneft": tatneft,
        "aslam-ompk": aslam,
    }
    for slug, fn in writers.items():
        path = out / f"{slug}.html"
        path.write_text(fn(), encoding="utf-8")
        print(f"  /cases/{slug}")
    print(f"case pages: {len(writers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
