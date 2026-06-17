#!/usr/bin/env python3
"""Single source of truth for the brand voice in every LLM generator.

public/brand.txt (canonical brand book, also served to external AI crawlers)
+ halal guardrails + the contacts rule → one stable system-prompt prefix.

Usage in generators:
    from brand_system import brand_block, CONTACTS_RU, CONTACTS_EN
    system = brand_block(lang) + "\n\n" + task_specific_instructions

Update brand.txt (or the guard text here) once — every generator follows.
The block is stable within a run, so Anthropic prompt caching applies
(claude_client adds cache_control when system ≥ CACHE_MIN_CHARS).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
BRAND_TXT = ROOT / "public" / "brand.txt"

PHONE_DISPLAY = "+7 987 217-02-02"
PHONE_TEL = "+79872170202"
EMAIL = "info@kazandelikates.tatar"
ADDR_RU = "г. Казань, ул. Аграрная, 2, оф. 7"
ADDR_EN = "2 Agrarnaya St., office 7, Kazan, Tatarstan, Russia"

CONTACTS_RU = (
    f"КОНТАКТЫ — используй СТРОГО эти и никакие другие: телефон {PHONE_DISPLAY} "
    f"(tel:{PHONE_TEL}), email {EMAIL}, адрес: {ADDR_RU}. "
    "НИКОГДА не выдумывай номера 8-800, другие адреса или email."
)
CONTACTS_EN = (
    f"CONTACTS — use EXACTLY these and no others: phone {PHONE_DISPLAY} "
    f"(tel:{PHONE_TEL}), email {EMAIL}, address: {ADDR_EN}. "
    "NEVER invent 8-800 numbers, other addresses or emails."
)

HALAL_GUARD_RU = (
    "ЖЕЛЕЗНЫЕ ПРАВИЛА ХАЛЯЛЬ: продукция на 100% халяль (говядина, курица, индейка, "
    "конина). НИКОГДА не упоминай свинину/шпик/сало/алкоголь как ингредиент. "
    "«Бекон» в ассортименте — только говяжий/куриный халяль-бекон. "
    "Не выдумывай сертификаты, ГОСТы, награды, клиентов и проценты — "
    "только факты из брендбука. Сертификаты: Халяль ДУМ РТ #614A/2024, "
    "HACCP, ISO 22000:2018, ТР ТС 021/2011. Кошер-сертификата НЕТ. "
    "По-арабски ветчина/бекон = «جامبون بقري حلال» / «اللحم البقري المدخن», "
    "НИКОГДА не «لحم الخنزير».\n"
    "ЗАПРЕЩЁННЫЕ СЛОВА (не писать НИ В КАКОМ контексте, ни на каком языке, "
    "включая отрицания вроде «не содержит X»): "
    "RU — свинина, свиной, свиное, поросёнок, кабан, шпик, сало, лярд, бекон* "
    "(*кроме явного «халяль-бекон говяжий/куриный»), окорок свиной, ветчина свиная; "
    "EN — pork, pig, swine, hog, lard, fatback, bacon* (*unless explicit halal "
    "beef/chicken bacon), ham (свиная); "
    "AR — خنزير، لحم الخنزير، شحم الخنزير، دهن الخنزير، لحم خنزير. "
    "Если тема требует объяснить халяльность — пиши через позитив "
    "(«только говядина/курица/индейка/конина», «100% халяль-сырьё»), "
    "НЕ называя запрещённые слова."
)

# Arabic-language halal guard — added to brand_block("ar") so the AR generator
# receives the rule in its own language, preventing the semantic trap where
# "ham" → LLM defaults to لحم خنزير (pork) instead of جامبون بقري حلال.
HALAL_GUARD_AR = (
    "قاعدة حلال صارمة (يجب الالتزام بها تماماً):\n"
    "جميع منتجاتنا مصنوعة من لحم البقر والدجاج والديك الرومي ولحم الحصان — 100% حلال.\n"
    "محظور تماماً: كتابة خنزير / لحم خنزير / لحوم خنزير / لحم الخنزير كاسم منتج "
    "أو وصف إيجابي أو في عنوان الصفحة أو وصف JSON-LD.\n"
    "الجامبون (ветчина/ham) بالعربية = جامبون بقري حلال فقط.\n"
    "البيكون (бекон/bacon) بالعربية = بيكون بقري حلال فقط.\n"
    "يُسمح بذكر خنزير فقط في سياق النفي الصريح: "
    "«لا خنزير»، «بدون خنزير»، «خالٍ من الخنزير»، «بدون مشتقات الخنزير».\n"
    "مثال صحيح: «جامبون بقري حلال — بدون خنزير».\n"
    "مثال خاطئ (ممنوع): «مورد لحوم خنزير حلال» — هذا تناقض ويُضر بمصداقية العلامة التجارية."
)

_cache: dict[str, str] = {}


def brand_block(lang: str = "ru") -> str:
    """Stable brand prefix for a system prompt (≈5K chars → cacheable)."""
    if lang in _cache:
        return _cache[lang]
    try:
        book = BRAND_TXT.read_text(encoding="utf-8").strip()
    except OSError:
        book = ""
    contacts = CONTACTS_EN if lang == "en" else CONTACTS_RU
    # AR pages get the halal guard in both Russian (full rule) AND Arabic
    # (prevents the "ham → لحم خنزير" semantic trap in Arabic-language generation).
    extra_ar = f"\n\n{HALAL_GUARD_AR}" if lang == "ar" else ""
    block = (
        "=== БРЕНДБУК (единый источник правды о бренде) ===\n"
        f"{book}\n"
        "=== КОНЕЦ БРЕНДБУКА ===\n\n"
        f"{HALAL_GUARD_RU}{extra_ar}\n\n{contacts}"
    )
    _cache[lang] = block
    return block


if __name__ == "__main__":
    b = brand_block("ru")
    print(f"brand block: {len(b)} chars (cache threshold 2000)")
    print(b[:300] + "…")
