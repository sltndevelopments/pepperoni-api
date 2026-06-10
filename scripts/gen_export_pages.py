#!/usr/bin/env python3
"""EXPORT-PAGES — country landing pages for international SEO/AIO expansion.

Builds /export/{country}, /en/export/{country}, /ar/export/{country} pages for
the 15 target export markets (CIS + Gulf + Egypt).

Hard rule: certification/accreditation FACTS are rendered from the CERT_FACTS
data below (sourced from public/export.html — ДУМ РТ № 614A/2024, Цербер
RU-016/SB88273). The LLM only writes market/intro/FAQ prose and is explicitly
forbidden from claiming certifications. This prevents halal/cert hallucinations.

Usage:
  python3 scripts/gen_export_pages.py             # build all missing pages
  python3 scripts/gen_export_pages.py --only uae  # one country
  python3 scripts/gen_export_pages.py --max 6     # limit LLM calls this run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from claude_client import call_claude  # noqa: E402

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
SITEMAP = PUBLIC / "sitemap.xml"
BASE = "https://pepperoni.tatar"
TODAY = date.today().isoformat()

PHONE = "+7 987 217-02-02"
PHONE_RAW = "79872170202"
EMAIL = "info@kazandelikates.tatar"

# ───────────────────────────── country data ─────────────────────────────────
# halal: "gso"        — ДУМ РТ accredited by GSO/GCC → recognized in GCC states
#        "gso_member" — country is a GSO member (Yemen) but not a GCC state
#        "recognized" — direct recognition (KG)
#        "memorandum" — mutual-recognition memorandum (KZ, BY)
#        "smiic"      — only the SMIIC umbrella applies (EG) → "уточняется"
# vet:   True — in Rosselkhoznadzor "Cerberus" attested export list
COUNTRIES = [
    {"slug": "kazakhstan", "iso": "KZ", "gsc": "kaz", "flag": "🇰🇿",
     "ru": "Казахстан", "ru_loc": "Казахстан", "en": "Kazakhstan", "ar": "كازاخستان",
     "langs": ["ru", "en"], "vet": True, "halal": "memorandum", "eaeu": True,
     "cities": "Алматы, Астана, Шымкент, Караганда"},
    {"slug": "belarus", "iso": "BY", "gsc": "blr", "flag": "🇧🇾",
     "ru": "Беларусь", "ru_loc": "Беларусь", "en": "Belarus", "ar": "بيلاروسيا",
     "langs": ["ru", "en"], "vet": True, "halal": "memorandum", "eaeu": True,
     "cities": "Минск, Гомель, Брест, Гродно"},
    {"slug": "armenia", "iso": "AM", "gsc": "arm", "flag": "🇦🇲",
     "ru": "Армения", "ru_loc": "Армению", "en": "Armenia", "ar": "أرمينيا",
     "langs": ["ru", "en"], "vet": True, "halal": None, "eaeu": True,
     "cities": "Ереван, Гюмри"},
    {"slug": "azerbaijan", "iso": "AZ", "gsc": "aze", "flag": "🇦🇿",
     "ru": "Азербайджан", "ru_loc": "Азербайджан", "en": "Azerbaijan", "ar": "أذربيجان",
     "langs": ["ru", "en"], "vet": True, "halal": None, "eaeu": False,
     "cities": "Баку, Гянджа, Сумгаит"},
    {"slug": "kyrgyzstan", "iso": "KG", "gsc": "kgz", "flag": "🇰🇬",
     "ru": "Кыргызстан", "ru_loc": "Кыргызстан", "en": "Kyrgyzstan", "ar": "قيرغيزستان",
     "langs": ["ru", "en"], "vet": True, "halal": "recognized", "eaeu": True,
     "cities": "Бишкек, Ош"},
    {"slug": "tajikistan", "iso": "TJ", "gsc": "tjk", "flag": "🇹🇯",
     "ru": "Таджикистан", "ru_loc": "Таджикистан", "en": "Tajikistan", "ar": "طاجيكستان",
     "langs": ["ru", "en"], "vet": True, "halal": None, "eaeu": False,
     "cities": "Душанбе, Худжанд"},
    {"slug": "georgia", "iso": "GE", "gsc": "geo", "flag": "🇬🇪",
     "ru": "Грузия", "ru_loc": "Грузию", "en": "Georgia", "ar": "جورجيا",
     "langs": ["ru", "en"], "vet": True, "halal": None, "eaeu": False,
     "cities": "Тбилиси, Батуми"},
    {"slug": "uae", "iso": "AE", "gsc": "are", "flag": "🇦🇪",
     "ru": "ОАЭ", "ru_loc": "ОАЭ", "en": "United Arab Emirates", "ar": "الإمارات العربية المتحدة",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso", "eaeu": False,
     "cities": "Дубай, Абу-Даби, Шарджа"},
    {"slug": "saudi-arabia", "iso": "SA", "gsc": "sau", "flag": "🇸🇦",
     "ru": "Саудовская Аравия", "ru_loc": "Саудовскую Аравию", "en": "Saudi Arabia",
     "ar": "المملكة العربية السعودية",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso", "eaeu": False,
     "cities": "Эр-Рияд, Джидда, Даммам"},
    {"slug": "kuwait", "iso": "KW", "gsc": "kwt", "flag": "🇰🇼",
     "ru": "Кувейт", "ru_loc": "Кувейт", "en": "Kuwait", "ar": "الكويت",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso", "eaeu": False,
     "cities": "Эль-Кувейт"},
    {"slug": "bahrain", "iso": "BH", "gsc": "bhr", "flag": "🇧🇭",
     "ru": "Бахрейн", "ru_loc": "Бахрейн", "en": "Bahrain", "ar": "البحرين",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso", "eaeu": False,
     "cities": "Манама"},
    {"slug": "oman", "iso": "OM", "gsc": "omn", "flag": "🇴🇲",
     "ru": "Оман", "ru_loc": "Оман", "en": "Oman", "ar": "عُمان",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso", "eaeu": False,
     "cities": "Маскат, Салала"},
    {"slug": "qatar", "iso": "QA", "gsc": "qat", "flag": "🇶🇦",
     "ru": "Катар", "ru_loc": "Катар", "en": "Qatar", "ar": "قطر",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso", "eaeu": False,
     "cities": "Доха"},
    {"slug": "yemen", "iso": "YE", "gsc": "yem", "flag": "🇾🇪",
     "ru": "Йемен", "ru_loc": "Йемен", "en": "Yemen", "ar": "اليمن",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "gso_member", "eaeu": False,
     "cities": "Сана, Аден"},
    {"slug": "egypt", "iso": "EG", "gsc": "egy", "flag": "🇪🇬",
     "ru": "Египет", "ru_loc": "Египет", "en": "Egypt", "ar": "مصر",
     "langs": ["ru", "en", "ar"], "vet": False, "halal": "smiic", "eaeu": False,
     "cities": "Каир, Александрия"},
]

# ─────────────────────── certification fact sentences ───────────────────────
# Rendered verbatim from data — the LLM never writes this section.
HALAL_FACTS = {
    "gso": {
        "ru": "Продукция сертифицирована Комитетом по стандарту «Халяль» ДУМ РТ "
              "(свидетельство № 614A/2024). Орган аккредитован GSO/GCC, поэтому "
              "халяль-сертификат признаётся в {name}.",
        "en": "Products are certified by the Halal Standard Committee of the Muslim "
              "Religious Board of Tatarstan (certificate No. 614A/2024). The body holds "
              "GSO/GCC accreditation, so the halal certificate is recognized in {name}.",
        "ar": "المنتجات حاصلة على شهادة حلال من لجنة معيار الحلال التابعة للإدارة الدينية "
              "لمسلمي تتارستان (شهادة رقم 614A/2024). الجهة معتمدة من هيئة التقييس الخليجية "
              "GSO/GCC، لذا فإن شهادة الحلال معترف بها في {name}.",
    },
    "gso_member": {
        "ru": "Халяль-сертификат выдан Комитетом «Халяль» ДУМ РТ (№ 614A/2024), "
              "аккредитованным GSO — организацией по стандартизации, в которую входит "
              "{name}. Признание подтверждается при оформлении конкретной поставки.",
        "en": "The halal certificate is issued by the Halal Committee of the Muslim Board "
              "of Tatarstan (No. 614A/2024), accredited by GSO — the standardization "
              "organization that includes {name}. Recognition is confirmed per shipment.",
        "ar": "شهادة الحلال صادرة عن لجنة الحلال التابعة للإدارة الدينية لمسلمي تتارستان "
              "(رقم 614A/2024) المعتمدة من هيئة التقييس GSO التي تضم {name} في عضويتها. "
              "ويتم تأكيد الاعتراف عند ترتيب كل شحنة.",
    },
    "recognized": {
        "ru": "Халяль-сертификат ДУМ РТ (№ 614A/2024) признаётся в {name} напрямую.",
        "en": "The halal certificate of the Muslim Board of Tatarstan (No. 614A/2024) is "
              "directly recognized in {name}.",
        "ar": "شهادة الحلال (رقم 614A/2024) معترف بها مباشرة في {name}.",
    },
    "memorandum": {
        "ru": "Между органами сертификации действует меморандум о взаимном признании "
              "халяль-сертификата ДУМ РТ (№ 614A/2024) — он принимается в {name}.",
        "en": "A mutual-recognition memorandum applies: the halal certificate of the "
              "Muslim Board of Tatarstan (No. 614A/2024) is accepted in {name}.",
        "ar": "بموجب مذكرة اعتراف متبادل، تُقبل شهادة الحلال (رقم 614A/2024) في {name}.",
    },
    "smiic": {
        "ru": "Комитет «Халяль» ДУМ РТ (№ 614A/2024) имеет международную аккредитацию "
              "SMIIC. Порядок признания сертификата в {name} подтверждается "
              "индивидуально при проработке поставки.",
        "en": "The Halal Committee of the Muslim Board of Tatarstan (No. 614A/2024) holds "
              "international SMIIC accreditation. Certificate recognition in {name} is "
              "confirmed individually when arranging a shipment.",
        "ar": "تحمل لجنة الحلال (رقم 614A/2024) اعتماد SMIIC الدولي. ويتم تأكيد إجراءات "
              "الاعتراف بالشهادة في {name} بشكل فردي عند ترتيب التوريد.",
    },
    None: {
        "ru": "Продукция имеет халяль-сертификат ДУМ РТ (№ 614A/2024) с международной "
              "аккредитацией SMIIC и GSO/GCC; условия признания в {name} уточняются "
              "при оформлении поставки.",
        "en": "Products carry the halal certificate of the Muslim Board of Tatarstan "
              "(No. 614A/2024) with international SMIIC and GSO/GCC accreditation; "
              "recognition terms in {name} are confirmed when arranging supply.",
        "ar": "تحمل المنتجات شهادة حلال (رقم 614A/2024) باعتماد SMIIC وGSO/GCC الدوليين؛ "
              "وتُحدد شروط الاعتراف في {name} عند ترتيب التوريد.",
    },
}

VET_FACTS = {
    True: {
        "ru": "Предприятие (№ RU-016/SB88273) внесено в реестр «Цербер» "
              "Россельхознадзора и аттестовано для экспорта в {name}.",
        "en": "The facility (No. RU-016/SB88273) is listed in the Rosselkhoznadzor "
              "“Cerberus” registry and attested for export to {name}.",
        "ar": "المنشأة (رقم RU-016/SB88273) مدرجة في سجل «سيربر» التابع لهيئة الرقابة "
              "البيطرية الروسية ومعتمدة للتصدير إلى {name}.",
    },
    False: {
        "ru": "Предприятие внесено в реестр «Цербер» Россельхознадзора "
              "(№ RU-016/SB88273); ветеринарные условия поставки в {name} "
              "уточняются индивидуально под контракт.",
        "en": "The facility is listed in the Rosselkhoznadzor “Cerberus” registry "
              "(No. RU-016/SB88273); veterinary terms for {name} are confirmed "
              "individually per contract.",
        "ar": "المنشأة مدرجة في سجل «سيربر» (رقم RU-016/SB88273)؛ وتُحدد الشروط البيطرية "
              "للتوريد إلى {name} بشكل فردي حسب العقد.",
    },
}

COMMON_FACTS = {
    "ru": ["Условия поставки: EXW Казань (Incoterms 2020); иные условия — по согласованию.",
           "Документы: халяль-свидетельство, ветеринарные сертификаты, декларации соответствия ЕАЭС.",
           "Расчёты: RUB, USD, KZT, UZS, KGS, BYN, AZN.",
           "Ассортимент: 77 наименований халяль — пепперони, сосиски, котлеты, копчёные колбасы, казылык, татарская выпечка.",
           "Private Label / СТМ: производство под маркой заказчика от 500 кг/мес."],
    "en": ["Delivery terms: EXW Kazan (Incoterms 2020); other terms negotiable.",
           "Documents: halal certificate, veterinary certificates, EAEU declarations of conformity.",
           "Payment currencies: RUB, USD, KZT, UZS, KGS, BYN, AZN.",
           "Range: 77 halal SKUs — pepperoni, sausages, burger patties, smoked sausages, kazylyk, Tatar pastry.",
           "Private Label / OEM: production under the customer's brand from 500 kg/month."],
    "ar": ["شروط التسليم: EXW قازان (إنكوتيرمز 2020)؛ وتُتاح شروط أخرى بالاتفاق.",
           "المستندات: شهادة الحلال، الشهادات البيطرية، إقرارات مطابقة الاتحاد الاقتصادي الأوراسي.",
           "عملات الدفع: RUB, USD, KZT, UZS, KGS, BYN, AZN.",
           "التشكيلة: 77 صنفاً حلالاً — بيبروني، نقانق، أقراص برغر، نقانق مدخنة، قازيليك، معجنات تتارية.",
           "العلامة الخاصة / OEM: الإنتاج تحت علامة العميل ابتداءً من 500 كغم شهرياً."],
}

UI = {
    "ru": {"dir": "ltr", "home": "Главная", "export": "Экспорт", "catalog": "Каталог",
           "cert_h": "Сертификация и допуск", "how_h": "Как организована поставка",
           "faq_h": "Вопросы и ответы", "cta_h": "Запросить экспортные условия",
           "cta_p": "Подберём ассортимент, рассчитаем условия и подготовим документы.",
           "locale": "ru_RU"},
    "en": {"dir": "ltr", "home": "Home", "export": "Export", "catalog": "Catalog",
           "cert_h": "Certification & market access", "how_h": "How supply works",
           "faq_h": "FAQ", "cta_h": "Request export terms",
           "cta_p": "We will tailor the assortment, quote terms and prepare documents.",
           "locale": "en_US"},
    "ar": {"dir": "rtl", "home": "الرئيسية", "export": "التصدير", "catalog": "الكتالوج",
           "cert_h": "الشهادات والاعتماد", "how_h": "كيف يتم التوريد",
           "faq_h": "أسئلة وأجوبة", "cta_h": "اطلب شروط التصدير",
           "cta_p": "سنختار التشكيلة المناسبة ونحسب الشروط ونجهّز المستندات.",
           "locale": "ar_AE"},
}

LANG_PREFIX = {"ru": "", "en": "/en", "ar": "/ar"}

STYLE = """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
.container{max-width:800px;margin:0 auto;padding:40px 24px}
nav{font-size:.85rem;color:#888;margin-bottom:32px}
nav a{color:#0066cc;text-decoration:none}
h1{font-size:2rem;font-weight:700;margin-bottom:8px}
h2{font-size:1.3rem;font-weight:700;margin:32px 0 12px;color:#1b7a3d}
.badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:8px 0 24px;letter-spacing:.5px}
p{margin-bottom:16px}
.card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}
.lead{background:#f0f9f3;border-left:4px solid #1b7a3d;padding:14px 18px;border-radius:4px;font-size:1.05rem}
[dir=rtl] .lead{border-left:none;border-right:4px solid #1b7a3d}
ul{margin:0 0 16px 22px}
[dir=rtl] ul{margin:0 22px 16px 0}
li{margin-bottom:8px}
.faq-q{font-weight:700;margin:18px 0 6px}
.cta{background:#1b7a3d;color:#fff;border-radius:10px;padding:28px;text-align:center;margin:32px 0}
.cta a.btn{display:inline-block;background:#fff;color:#1b7a3d;font-weight:700;padding:12px 26px;border-radius:8px;text-decoration:none;margin:8px 6px 0}
.cta a.wa{background:#25d366;color:#fff}
footer{text-align:center;color:#aaa;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}
footer a{color:#888;text-decoration:none}"""

SYSTEM = """Ты — SEO-копирайтер B2B-производителя халяльных мясных изделий «Казанские Деликатесы»
(pepperoni.tatar, Казань, Россия). Пишешь экспортные страницы. ЖЁСТКИЕ ПРАВИЛА:
1. ЗАПРЕЩЕНО упоминать сертификаты, номера, аккредитации, ГОСТы — этот блок уже есть на странице.
2. ЗАПРЕЩЕНО упоминать свинину, бекон, шпик, алкоголь в любом контексте. Вся продукция 100% халяль
   (говядина, мясо птицы) — но НЕ пиши фраз вида «без свинины»: просто говори «халяль», «из говядины и птицы».
3. НЕ выдумывай точную статистику, цифры рынка, имена клиентов. Общие консервативные формулировки.
4. Пиши на языке, указанном в задании, профессионально, для B2B-закупщика (дистрибьютор, сеть, HoReCa).
5. Ответ — СТРОГО валидный JSON без markdown-обёртки."""

PROMPT = """Страница: экспорт халяльной мясной продукции из Казани (Россия) в страну {country} ({iso}).
Язык страницы: {lang}.
Ключевые города страны: {cities}.
Продукция: пепперони, сосиски для хот-догов, котлеты для бургеров, копчёные колбасы, казылык,
татарская выпечка (эчпочмак, чак-чак). B2B: опт, дистрибуция, HoReCa, Private Label/СТМ от 500 кг/мес.
Покупатель: импортёр/дистрибьютор/сеть в {country}.

Верни JSON:
{{
 "title": "SEO title до 60 знаков, формат: интент + страна + бренд",
 "meta_description": "до 155 знаков, конкретика и CTA",
 "h1": "заголовок страницы",
 "tagline": "1 фраза-подзаголовок",
 "intro_html": "<p>...</p><p>...</p> — 2 абзаца: кто мы, что поставляем в {country}, для кого",
 "market_html": "<p>...</p><p>...</p><p>...</p> — 2-3 абзаца: спрос на халяль в {country}, ниши (пиццерии, хорека, ритейл), почему поставка из России/Татарстана выгодна (логистика, цена, халяль-культура)",
 "logistics_html": "<p>...</p><p>...</p> — 2 абзаца: как идёт поставка из Казани в {country} (рефрижератор, сроки годности продукции позволяют, партии от паллеты), что нужно от покупателя",
 "faq": [{{"q":"...","a":"..."}}, {{"q":"...","a":"..."}}, {{"q":"...","a":"..."}}, {{"q":"...","a":"..."}}]
}}
4 FAQ — практические вопросы импортёра (MOQ, документы, сроки, Private Label). Без вопросов о сертификатах."""


def hreflang_block(slug: str, langs: list, iso: str) -> str:
    """Full regional hreflang matrix; all lang versions cross-reference each other."""
    lines = []
    for lg in langs:
        url = f"{BASE}{LANG_PREFIX[lg]}/export/{slug}"
        lines.append(f'<link rel="alternate" hreflang="{lg}" href="{url}">')
        lines.append(f'<link rel="alternate" hreflang="{lg}-{iso}" href="{url}">')
    xdef = f"{BASE}{LANG_PREFIX['en' if 'en' in langs else langs[0]]}/export/{slug}"
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{xdef}">')
    return "\n".join(lines)


def lang_switcher(slug: str, langs: list, cur: str) -> str:
    names = {"ru": "Русский", "en": "English", "ar": "العربية"}
    parts = []
    for lg in langs:
        if lg == cur:
            continue
        parts.append(f'<a href="{LANG_PREFIX[lg]}/export/{slug}">{names[lg]}</a>')
    return " · ".join(parts)


def render(c: dict, lang: str, gen: dict) -> str:
    ui = UI[lang]
    name = c[lang] if lang != "ru" else c["ru_loc"]
    plain_name = c[lang]
    url = f"{BASE}{LANG_PREFIX[lang]}/export/{c['slug']}"
    halal_fact = HALAL_FACTS[c["halal"]][lang].format(name=plain_name)
    vet_fact = VET_FACTS[c["vet"]][lang].format(name=plain_name)
    facts_li = "\n".join(f"<li>{f}</li>" for f in COMMON_FACTS[lang])
    if c["eaeu"]:
        eaeu_note = {"ru": "<li>Страна входит в ЕАЭС — упрощённое таможенное оформление.</li>",
                     "en": "<li>The country is an EAEU member — simplified customs clearance.</li>",
                     "ar": ""}[lang]
    else:
        eaeu_note = ""
    faq_html = "\n".join(
        f'<p class="faq-q">{f["q"]}</p><p>{f["a"]}</p>' for f in gen["faq"])
    faq_ld = [{"@type": "Question", "name": f["q"],
               "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in gen["faq"]]
    ld = json.dumps([
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": ui["home"], "item": BASE + (LANG_PREFIX[lang] or "/")},
            {"@type": "ListItem", "position": 2, "name": ui["export"], "item": f"{BASE}{LANG_PREFIX[lang]}/export"},
            {"@type": "ListItem", "position": 3, "name": plain_name, "item": url}]},
        {"@context": "https://schema.org", "@type": "Service",
         "name": gen["h1"], "serviceType": "Wholesale halal meat export",
         "areaServed": {"@type": "Country", "name": c["en"]},
         "provider": {"@type": "Organization", "name": "Kazan Delicacies",
                      "url": BASE, "email": EMAIL,
                      "contactPoint": {"@type": "ContactPoint", "telephone": PHONE,
                                       "url": f"https://wa.me/{PHONE_RAW}",
                                       "contactType": "sales",
                                       "areaServed": c["iso"],
                                       "availableLanguage": ["ru", "en", "ar"]}}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq_ld},
    ], ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{ui['dir']}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{gen['title']}</title>
<meta name="description" content="{gen['meta_description']}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="llms" href="/llms.txt" type="text/plain" title="LLM instructions">
{hreflang_block(c['slug'], c['langs'], c['iso'])}
<meta property="og:type" content="website">
<meta property="og:title" content="{gen['title']}">
<meta property="og:description" content="{gen['meta_description']}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}/images/logo.png">
<meta property="og:locale" content="{ui['locale']}">
<script type="application/ld+json">{ld}</script>
<style>{STYLE}</style>
</head>
<body>
<div class="container">
<nav><a href="{LANG_PREFIX[lang] or '/'}">{ui['home']}</a> → <a href="{LANG_PREFIX[lang]}/export">{ui['export']}</a> → {plain_name} &nbsp;|&nbsp; {lang_switcher(c['slug'], c['langs'], lang)}</nav>
<h1>{c['flag']} {gen['h1']}</h1>
<p>{gen['tagline']}</p>
<span class="badge">HALAL · B2B · {c['iso']}</span>
<div class="lead">{gen['intro_html']}</div>
<h2>{ui['cert_h']}</h2>
<div class="card"><p>{halal_fact}</p><p>{vet_fact}</p></div>
{gen['market_html']}
<h2>{ui['how_h']}</h2>
{gen['logistics_html']}
<div class="card"><ul>
{facts_li}
{eaeu_note}
</ul></div>
<h2>{ui['faq_h']}</h2>
{faq_html}
<div class="cta">
<h2 style="color:#fff;margin-top:0">{ui['cta_h']}</h2>
<p>{ui['cta_p']}</p>
<a class="btn" href="tel:+{PHONE_RAW}">📞 {PHONE}</a>
<a class="btn wa" href="https://wa.me/{PHONE_RAW}">WhatsApp</a>
<a class="btn" href="mailto:{EMAIL}">{EMAIL}</a>
</div>
<footer><a href="{LANG_PREFIX[lang] or '/'}">pepperoni.tatar</a> · {ui['catalog']}: <a href="{LANG_PREFIX['en'] if lang != 'ru' else ''}/products">{ui['catalog']}</a> · © Kazan Delicacies</footer>
</div>
</body>
</html>"""


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


def add_to_sitemap(urls: list) -> None:
    if not SITEMAP.exists():
        return
    content = SITEMAP.read_text(encoding="utf-8")
    existing = set(re.findall(r"<loc>(.*?)</loc>", content))
    new = [f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
           f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>"
           for u in urls if u not in existing]
    if new:
        content = content.replace("</urlset>", "\n".join(new) + "\n</urlset>")
        SITEMAP.write_text(content, encoding="utf-8")
        print(f"  ✅ sitemap += {len(new)} url")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="country slug")
    ap.add_argument("--max", type=int, default=int(os.environ.get("EXPORT_MAX", "60")),
                    help="max LLM page generations this run")
    args = ap.parse_args()

    made, new_urls = 0, []
    lang_names = {"ru": "русский", "en": "английский (English)", "ar": "арабский (العربية، فصحى)"}
    for c in COUNTRIES:
        if args.only and c["slug"] != args.only:
            continue
        for lang in c["langs"]:
            if made >= args.max:
                break
            out = PUBLIC / (LANG_PREFIX[lang].strip("/") or ".") / "export" / f"{c['slug']}.html"
            if out.exists():
                continue
            print(f"→ {c['slug']} [{lang}] …", flush=True)
            prompt = PROMPT.format(country=c["ru"] if lang == "ru" else c["en"],
                                   iso=c["iso"], lang=lang_names[lang], cities=c["cities"])
            try:
                # Flagship export pages: Opus advisor + Sonnet executor (beta,
                # auto-fallback to plain call when unavailable).
                raw, _tok = call_claude(prompt, system=SYSTEM, max_tokens=3500,
                                        advisor=True)
                gen = parse_json(raw)
                html = render(c, lang, gen)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(html, encoding="utf-8")
                new_urls.append(f"{BASE}{LANG_PREFIX[lang]}/export/{c['slug']}")
                made += 1
                print(f"  ✅ {out.relative_to(ROOT)} ({len(html)} bytes)")
            except Exception as e:
                print(f"  ✗ {c['slug']} [{lang}]: {e}", file=sys.stderr)
    add_to_sitemap(new_urls)
    print(f"✅ export pages: {made} generated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
