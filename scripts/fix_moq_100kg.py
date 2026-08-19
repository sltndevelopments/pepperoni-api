#!/usr/bin/env python3
"""Remove invented 100 kg (and close) MOQ claims. Volume is by agreement / logistics.

Does not invent new kg numbers. Does not touch pack weights, 100%, phones,
populations, or archived public/{1,2,3,4,5,x}.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PUBLIC_DIRS = frozenset({"1", "2", "3", "4", "5", "x"})
SKIP_SUFFIXES = (".bak", ".orig")
SKIP_NAME_PREFIXES = ("_removed",)

# --- phrase replacements: longest / most specific first ---

RU_PHRASES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"Минимальный заказ на оптовую поставку\s*[—–\-]\s*от\s*100\s*кг",
            re.I,
        ),
        "Минимальный заказ на оптовую поставку — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"Минимальный заказ составляет от\s*100\s*кг", re.I),
        "Минимальный заказ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(
            r"минимальн(?:ый|ая|ого)\s+заказ(?:а)?(?:\s+для\s+[\w.«»\"-]{1,40})?\s*[—–\-]?\s*от\s*100\s*кг",
            re.I,
        ),
        "минимальный заказ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(
            r"минимальн(?:ый|ая|ого)\s+объ[её]м(?:а)?(?:\s+[—–\-])?\s*от\s*100\s*кг"
            r"(?:\s+(?:по|на)\s+одн(?:у|ой)\s+позици\w*)?",
            re.I,
        ),
        "минимальный объём — по договорённости, зависит от логистики",
    ),
    (
        re.compile(
            r"минимальн(?:ая|ой|ый)\s+парти(?:я|и|ю)(?:\s+для\s+[\w\s,]{1,50})?\s*[—–\-]?\s*от\s*100\s*кг"
            r"(?:\s+(?:по|на)\s+одн(?:у|ой)\s+позици\w*)?",
            re.I,
        ),
        "минимальная партия — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"минимальн(?:ый|ая|ого)\s+тираж(?:а)?\s+от\s*100\s*кг", re.I),
        "минимальный тираж — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"Мин\.\s*парти(?:я|и)\s*(?:от\s*)?100\s*кг", re.I),
        "Мин. партия — по договорённости",
    ),
    (
        re.compile(
            r"пробн(?:ая|ой|ую)\s+парти(?:я|и|ю)\s*[—–\-]?\s*от\s*100\s*кг",
            re.I,
        ),
        "пробная партия — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"оптовые\s+партии\s+от\s*100\s*кг", re.I),
        "оптовые партии — по договорённости, зависят от логистики",
    ),
    (
        re.compile(r"отгрузк[аи]\s+от\s*100\s*кг", re.I),
        "отгрузка — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"стартуем\s+от\s*100\s*кг(?:\s+на\s+позици\w*)?", re.I),
        "объём — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"От\s+100\s*кг\s*[—–\-]\s*старт\s+СТМ", re.I),
        "Объём — по договорённости — старт СТМ",
    ),
    (
        re.compile(r"От\s+100\s*кг\s*[—–\-]\s*индивидуальная\s+этикетка", re.I),
        "Объём — по договорённости — индивидуальная этикетка",
    ),
    (
        re.compile(
            r"Private Label(?:\s*/\s*СТМ)?\s+от\s*100\s*кг",
            re.I,
        ),
        "Private Label / СТМ — объём по договорённости",
    ),
    (
        re.compile(r"СТМ\s*[—–\-]?\s*от\s*100\s*кг", re.I),
        "СТМ — объём по договорённости",
    ),
    (
        re.compile(r"при\s+объ[её]ме\s+заказа\s+от\s*100\s*кг(?:\s+и\s+выше)?", re.I),
        "при объёме по договорённости",
    ),
    (
        re.compile(r"при\s+объ[её]ме\s+от\s*100\s*кг", re.I),
        "при объёме по договорённости",
    ),
    (
        re.compile(r"при\s+заказе\s+от\s*100\s*кг", re.I),
        "при заказе по договорённости",
    ),
    (
        re.compile(r"при\s+контракте\s+от\s*100\s*кг(?:/месяц)?", re.I),
        "при контракте по договорённости",
    ),
    (
        re.compile(r"скидк[аи]\s+от\s*100\s*кг", re.I),
        "скидки — по договорённости",
    ),
    (
        re.compile(r"заказами\s+от\s*100\s*кг", re.I),
        "заказами по договорённости",
    ),
    (
        re.compile(r"от\s+партии\s+100\s*кг", re.I),
        "по договорённости",
    ),
    (
        re.compile(r"от\s*100\s*кг\s+партии", re.I),
        "по договорённости",
    ),
    (
        re.compile(
            r"от\s*(?:<[^>]+>\s*)*100\s*(?:<[^>]+>\s*)*кг"
            r"(?:\s*/\s*(?:мес\.?|SKU))?"
            r"(?:\s+(?:на|по)\s+одн(?:у|ой)\s+позици\w*)?"
            r"(?:\s+до\s+1\s+тонн\w*)?",
            re.I,
        ),
        "по договорённости",
    ),
    (
        re.compile(
            r"минимальн(?:ая|ый|ой|ого)\s+(?:парти(?:я|и)|заказ|тираж|объ[её]м)"
            r"(?:\s+для\s+[\w\s./]{1,40})?\s*[—–\-]?\s*100\s*кг"
            r"(?:\s+одного\s+(?:наименования|вида\s+продукции))?",
            re.I,
        ),
        "минимальный заказ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(
            r"Мінімальн(?:ая|ы|ый)\s+(?:партыя|тыраж|заказ)\s*[—–\-]?\s*(?:ад\s+)?100\s*кг",
            re.I,
        ),
        "мінімальны заказ — па дамоўленасці, залежыць ад лагістыкі",
    ),
    (
        re.compile(r"Минималды\s+тапсырыс\s*[—–:]?\s*100\s*кг(?:\s+бастап)?", re.I),
        "минималды тапсырыс — келісім бойынша, логистикаға байланысты",
    ),
    (
        re.compile(r"100\s*кг\s+бастап", re.I),
        "келісім бойынша, логистикаға байланысты",
    ),
    (
        re.compile(r"Минимальная партия СТМ\s*[—–\-]?\s*100\s*кг", re.I),
        "минимальная партия СТМ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"Мин(?:имум|\.)\s*парти(?:я|и)\s*[—–\-]?\s*100\s*кг", re.I),
        "Мин. партия — по договорённости",
    ),
    (
        re.compile(r"пробн(?:ая|ой|ую)\s+парти(?:я|и|ю)\s*[—–\-]?\s*100\s*кг", re.I),
        "пробная партия — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"Аз\s+100\s*кг", re.I),
        "ҳаҷм — бо мувофиқа, вобаста ба логистика",
    ),
    (
        re.compile(r"Від\s+100\s*кг", re.I),
        "обсяг — за домовленістю, залежить від логістики",
    ),
    (
        re.compile(r"Ад\s+100\s*кг", re.I),
        "аб'ём — па дамоўленасці, залежыць ад лагістыкі",
    ),
    (
        re.compile(r"100\s*кг-нан(?:\s+бастап)?", re.I),
        "келісім бойынша, логистикаға байланысты",
    ),
    (
        re.compile(r"100\s*кг\s+дан(?:\s+баштайбыз|\s+баштап)?", re.I),
        "макулдашуу боюнча, логистикага жараша",
    ),
    (
        re.compile(
            r'(<(?:div|span|td|h[1-6]|p|strong|li)\b[^>]*(?:stat-number|card-num|display-number|num|"num")[^>]*>)\s*100\s*кг\s*(</)',
            re.I,
        ),
        r"\1по договорённости\2",
    ),
    (
        re.compile(r'(<(?:div|span) class="(?:stat-number|card-num|display-number|num)">)\s*100\s*кг\s*(</)', re.I),
        r"\1по договорённости\2",
    ),
]

EN_PHRASES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"Minimum wholesale order is 100\s*kg",
            re.I,
        ),
        "Minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(
            r"minimum order quantities(?:\s+for[\w\s,]{0,60})?\s+typically range from 100\s*kg to 1 ton",
            re.I,
        ),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"starting from 100\s*kg", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"MOQ(?:\s+is|\s+of|:)?\s*100\s*kg(?:\s+per\s+SKU)?", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"100\s*kg/SKU", re.I),
        "volume agreed per contract",
    ),
    (
        re.compile(r"from a minimum batch of 100\s*kg", re.I),
        "volume agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"from 100\s*kg batches", re.I),
        "volume agreed per contract, depends on logistics",
    ),
    (
        re.compile(
            r"Minimum order:\s*100\s*kg(?:\s+per\s+SKU)?",
            re.I,
        ),
        "Minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"minimum batch for [\w\s]{1,40} is from 100\s*kg", re.I),
        "minimum batch agreed per contract, depends on logistics",
    ),
    (
        re.compile(
            r"Minimum 100\s*kg(?:\s+untuk\s+[\w\s]{1,40})?",
            re.I,
        ),
        "volume agreed per contract",
    ),
    (
        re.compile(r"wholesale purchases from 100\s*kg", re.I),
        "wholesale purchases — volume agreed per contract",
    ),
    (
        re.compile(r"for orders from 100\s*kg", re.I),
        "for orders — volume agreed per contract",
    ),
    (
        re.compile(r"orders from 100\s*kg", re.I),
        "orders — volume agreed per contract",
    ),
    (
        re.compile(r"from 100\s*kg\s*[—–\-]\s*from", re.I),
        "volume agreed per contract — from",
    ),
    (
        re.compile(
            r"from\s*(?:<[^>]+>\s*)*100\s*(?:<[^>]+>\s*)*kg"
            r"(?:\s*/\s*(?:month|SKU|mo\.?))?"
            r"(?:\s+to\s+1\s+ton(?:ne)?)?",
            re.I,
        ),
        "volume agreed per contract",
    ),
    (
        re.compile(r"À partir de 100\s*kg(?:\s+par\s+SKU)?", re.I),
        "volume convenu au contrat, selon la logistique",
    ),
    (
        re.compile(r"[Dd]ès 100\s*kg(?:\s+par\s+SKU)?"),
        "volume convenu au contrat, selon la logistique",
    ),
    (
        re.compile(r"lots dès 100\s*kg", re.I),
        "lots convenus au contrat, selon la logistique",
    ),
    (
        re.compile(r"Contrat dès 100\s*kg", re.I),
        "contrat selon accord, selon la logistique",
    ),
    (
        re.compile(r"100\s*kg min\.?", re.I),
        "accord contrat",
    ),
    (
        re.compile(r"100\s*kg minimum", re.I),
        "minimum convenu au contrat",
    ),
    (
        re.compile(r"Mulai(?:\s+dari)?\s+100\s*kg(?:\s+per\s+SKU)?", re.I),
        "volume disepakati kontrak, tergantung logistik",
    ),
    (
        re.compile(r"Pesan dari 100\s*kg", re.I),
        "pesanan disepakati kontrak, tergantung logistik",
    ),
    (
        re.compile(r"Minimal(?:\s+order)?\s+100\s*kg(?:\s+per\s+SKU)?", re.I),
        "minimum disepakati kontrak, tergantung logistik",
    ),
    (
        re.compile(r"(?:Tempah(?:an)?|Kuantiti)\s+dari 100\s*kg", re.I),
        "kuantiti dipersetujui kontrak, bergantung logistik",
    ),
    (
        re.compile(r"Dari 100\s*kg", re.I),
        "mengikut kontrak, bergantung logistik",
    ),
    (
        re.compile(r"Min\.\s*100\s*kg", re.I),
        "mengikut kontrak",
    ),
    (
        re.compile(r"100\s*kg dan boshlab(?:\s+buyurtma)?", re.I),
        "hajm shartnoma bo‘yicha, logistikaga bog‘liq",
    ),
    (
        re.compile(r"100\s*kg dan boshlaymiz", re.I),
        "hajm shartnoma bo‘yicha, logistikaga bog‘liq",
    ),
    (
        re.compile(
            r"100\s*kg['\u2018\u2019`´]dan(?:\s+itibaren|\s+başlayan|\s+başlıyoruz)?",
            re.I,
        ),
        "sözleşmeye göre, lojistiğe bağlı",
    ),
    (
        re.compile(r"Kuantiti minimum ialah 100\s*kg", re.I),
        "kuantiti minimum dipersetujui kontrak, bergantung logistik",
    ),
    (
        re.compile(r"avec 100\s*kg par SKU", re.I),
        "selon accord contractuel, selon la logistique",
    ),
    (
        re.compile(r"min 100\s*kg", re.I),
        "volume agreed per contract",
    ),
    (
        re.compile(r'"100\s*kg\.\s+Özel', re.I),
        '"Sözleşmeye göre, lojistiğe bağlı. Özel',
    ),
    (
        re.compile(r'(<(?:div|span)[^>]*stat-number[^>]*>)\s*100\s*kg\s*(</)', re.I),
        r"\1agreed per contract\2",
    ),
]

AR_PHRASES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"الحد الأدنى للطلب\s*[–—\-]?\s*100\s*كجم(?:\s+لكل\s+منتج)?"),
        "الحد الأدنى للطلب حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"الحد الأدنى للطلب\s+100\s*كيلوغرام(?:\s+لكل\s+صنف)?"),
        "الحد الأدنى للطلب حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"نبدأ من 100\s*كجم(?:\s+لكل\s+منتج)?"),
        "الحجم حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"بكميات من 100\s*كجم"),
        "بكميات حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"للطلبات من 100\s*كجم"),
        "للطلبات حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"من 100\s*كجم(?:\s+لكل\s+منتج)?"),
        "حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"الحد الأدنى للطلب هو 100\s*كجم(?:\s+لكل\s+منتج)?"),
        "الحد الأدنى للطلب حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"الحد الأدنى(?:\s+هو)?\s+100\s*كجم(?:\s+لكل\s+منتج|\s+لأي\s+منتج)?"),
        "الحد الأدنى حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"أقل كمية(?:\s+طلب)?(?:\s+هي)?\s+100\s*كجم(?:\s+لكل\s+منتج)?"),
        "الكمية حسب الاتفاق، يعتمد على اللوجستيات",
    ),
]

# Invented 300/500 kg MOQ / pilot / STM floors (not pack weights).
SITE_MOQ_300_500: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"минимальн(?:ая|ый|ой|ого)\s+(?:парти(?:я|и)|заказ|тираж|объ[её]м)"
            r"(?:\s+для\s+[\w\s./]{1,40})?\s*[—–\-]?\s*(?:от\s*)?(?:300|500)\s*кг"
            r"(?:\s*/\s*мес\.?)?(?:\s+в\s+месяц)?(?:\s+на\s+позици\w*)?",
            re.I,
        ),
        "минимальная партия — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"MOQ\s+500\s*kg(?:\s+per\s+SKU)?", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"500\s*kg/mo(?:nth)?\s*\(pilot\)", re.I),
        "agreed per contract (pilot)",
    ),
    (
        re.compile(
            r"(?:Our\s+)?standard MOQ(?:\s+for export(?:\s+orders|\s+supply)?)?\s+is 500\s*kg(?:\s+per\s+month)?",
            re.I,
        ),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"standard minimum order starts at 500\s*kg(?:\s+per\s+month)?", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"typically 500\s*kg per month per SKU", re.I),
        "agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"Kuantiti min:\s*</strong>\s*500\s*kg", re.I),
        "Kuantiti min:</strong> dipersetujui kontrak",
    ),
    (
        re.compile(r"MOQ يبدأ من 500\s*كجم"),
        "الحد الأدنى حسب الاتفاق، يعتمد على اللوجستيات",
    ),
    (
        re.compile(r"500\s*كجم"),
        "حسب الاتفاق",
    ),
    (
        re.compile(
            r"Мінімальн(?:ая|ы|ый)\s+партыя\s*[—–\-]?\s*(?:ад\s+)?500\s*кг",
            re.I,
        ),
        "мінімальны заказ — па дамоўленасці, залежыць ад лагістыкі",
    ),
    (
        re.compile(r"Пастаўкі ад 500\s*кг", re.I),
        "пастаўкі па дамоўленасці, залежыць ад лагістыкі",
    ),
    (
        re.compile(r"Від\s+500\s*кг", re.I),
        "обсяг — за домовленістю, залежить від логістики",
    ),
    (
        re.compile(r"Поставки від 500\s*кг", re.I),
        "поставки за домовленістю, залежить від логістики",
    ),
    (
        re.compile(r"Мин\.\s*партия\s*[—–\-]?\s*500\s*кг", re.I),
        "Мин. партия — по договорённости",
    ),
    (
        re.compile(r"Минимальная партия СТМ\s*[—–\-]?\s*500\s*кг", re.I),
        "минимальная партия СТМ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"starts at 500\s*kg/month", re.I),
        "agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"500\s*kg/month\s*→"),
        "agreed per contract →",
    ),
    (
        re.compile(r'(<div class="num">)500\s*kg/mo(</div>)', re.I),
        r"\1agreed per contract\2",
    ),
    (
        re.compile(
            r"минимальн(?:ая|ый|ой)\s+парти(?:я|и)\s+для\s+[\w\s/]{1,40}[—–\-]?\s*от\s*(?:300|500)\s*кг",
            re.I,
        ),
        "минимальная партия — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"Мин(?:имум|\.)\s*(?:парти(?:я|и)|заказ)\s+от\s*(?:300|500)\s*кг", re.I),
        "Мин. партия — по договорённости",
    ),
    (
        re.compile(r"МИН(?:имум)?\s+заказ\s+от\s*(?:300|500)\s*кг", re.I),
        "минимальный заказ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"пилот\s+от\s*(?:300|500)\s*кг(?:\s*/\s*мес\.?)?", re.I),
        "объём — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"MOQ\s+от\s*(?:300|500)\s*кг(?:\s*/\s*мес\.?)?", re.I),
        "минимальный заказ — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"опт\s+от\s*500\s*кг(?:\s*/\s*мес\.?)?", re.I),
        "опт — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"СТМ\s+от\s*500\s*кг(?:\s*/\s*мес\.?)?", re.I),
        "СТМ — объём по договорённости",
    ),
    (
        re.compile(r"От\s+500\s*кг/мес", re.I),
        "по договорённости",
    ),
    (
        re.compile(r"от\s+500\s*кг/мес", re.I),
        "по договорённости",
    ),
    (
        re.compile(r"от\s+500\s*кг\s+в\s+месяц(?:\s+на\s+позици\w*)?", re.I),
        "по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"500\s*кг/мес\s*→"),
        "по договорённости →",
    ),
    (
        re.compile(r"500\s*кг/мес\s*\(пилот\)"),
        "по договорённости (пилот)",
    ),
    (
        re.compile(r'(<div class="num">)500\s*кг(</div>)'),
        r"\1по договорённости\2",
    ),
    (
        re.compile(r"pilot from(?:\s+~)?\s*500\s*kg(?:\s*/\s*month)?", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"from 500\s*kg(?:\s*/\s*month|\s+per\s+month)?(?:\s+per\s+(?:SKU|item))?", re.I),
        "volume agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"MOQ from 500\s*kg(?:/mo(?:nth)?)?", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"starting from 500\s*kg", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(
            r"1 pallet\s*\([^)]*500\s*kg[^)]*\)[^.]*\.",
            re.I,
        ),
        "Minimum order agreed per contract, depends on logistics.",
    ),
    (
        re.compile(r"from 300\s*kg\b(?:\s+per\s+production\s+cycle)?", re.I),
        "volume agreed per contract",
    ),
    (
        re.compile(r"От\s+300\s*кг\b", re.I),
        "Объём — по договорённости",
    ),
    (
        re.compile(r"от\s+300\s*кг\b", re.I),
        "по договорённости",
    ),
    (
        re.compile(r"От\s+500\s*кг\b", re.I),
        "Объём — по договорённости",
    ),
    (
        re.compile(r"от\s+500\s*кг\b", re.I),
        "по договорённости",
    ),
    (
        re.compile(
            r"минимальн(?:ый|ого|ая)\s+объ[её]м(?:\s+(?:составляет|для\s+[\w\s]{1,40}|сотрудничества|поставки))?\s*[—–\-]?\s*500\s*кг"
            r"(?:\s+в\s+месяц)?",
            re.I,
        ),
        "минимальный объём — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"Минимальная партия:\s*500\s*кг", re.I),
        "Минимальная партия — по договорённости, зависит от логистики",
    ),
    (
        re.compile(r"standard MOQ(?:\s+for export)? is 500\s*kg(?:\s+per\s+month)?", re.I),
        "minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"Our standard MOQ is 500\s*kg(?:\s+per\s+month)?", re.I),
        "Minimum order agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"500\s*kg per month per product SKU", re.I),
        "volume agreed per contract, depends on logistics",
    ),
    (
        re.compile(r"500\s*кг в месяц", re.I),
        "по договорённости, зависит от логистики",
    ),
]

CLEANUPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"contractnth", re.I), "agreed per contract"),
    (re.compile(r"от\s+по\s+договор[её]нност\w*"), "по договорённости"),
    (re.compile(r"от\s+по\s+договору"), "по договорённости"),
    (re.compile(r"по\s+договорённости\s*/\s*мес\.?"), "по договорённости"),
    (re.compile(r"по\s+договорённости\s*/\s*SKU"), "по договорённости"),
    (re.compile(r"volume agreed per contract\s*/\s*(?:month|SKU|mo\.?)"), "volume agreed per contract"),
    (re.compile(r"from\s+volume agreed per contract"), "volume agreed per contract"),
    (re.compile(r"работают\s+Объём\s+[—–\-]\s+по договорённости"), "работают по договорённости"),
    (re.compile(r"партиями\s+Объём\s+[—–\-]\s+по договорённости"), "партиями по договорённости"),
    (re.compile(r"работают с крупными партиями по договорённости"), "работают по договорённости"),
    (re.compile(r"work volume agreed per contract"), "work — volume agreed per contract"),
    (re.compile(r"batches volume agreed per contract"), "batches — volume agreed per contract"),
    (re.compile(r"orders — volume agreed per contract\s+save"), "orders — volume agreed per contract — save"),
    (re.compile(r"по договорённости\s*/\s*мес"), "по договорённости"),
    (re.compile(r"volume agreed per contract, depends on logistics / month"), "volume agreed per contract, depends on logistics"),
    (re.compile(r"от\s+\."), "по договорённости."),
    (re.compile(r"от\s+\.\s*"), "по договорённости "),
    (re.compile(r"[ \t]{2,}"), " "),
    (re.compile(r" *\n[ \t]+"), "\n"),
    (re.compile(r"[—–\-]\s*[—–\-]"), "—"),
    (re.compile(r",\s*,"), ","),
    (re.compile(r"\s+,"), ","),
    (re.compile(r"\s+\."), "."),
]


def is_archived_public(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT / "public")
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in SKIP_PUBLIC_DIRS


def should_skip_file(path: Path) -> bool:
    name = path.name
    if name.startswith(SKIP_NAME_PREFIXES) or name.endswith(SKIP_SUFFIXES):
        return True
    if is_archived_public(path):
        return True
    return False


def is_geo_or_export(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if "geo" in parts or "export" in parts:
        return True
    name = path.name.lower()
    return name in {"export.html", "en/export.html"} or path.name == "export.html"


def apply_pairs(text: str, pairs: list[tuple[re.Pattern[str], str]]) -> str:
    for rx, repl in pairs:
        text = rx.sub(repl, text)
    return text


def cleanup(text: str) -> str:
    for rx, repl in CLEANUPS:
        text = rx.sub(repl, text)
    # leftover broken "от ." after prior pass
    text = re.sub(r"от\s+\.(?=\s|<|\"|')", "по договорённости.", text)
    return text


def fix_text(text: str, *, geo_export: bool) -> str:
    text = apply_pairs(text, RU_PHRASES)
    text = apply_pairs(text, EN_PHRASES)
    text = apply_pairs(text, AR_PHRASES)
    text = apply_pairs(text, SITE_MOQ_300_500)
    text = cleanup(text)
    return text


TEXT_SUFFIXES = {".html", ".txt", ".json", ".md", ".py"}


def iter_files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for base in paths:
        if base.is_file():
            if not should_skip_file(base):
                out.append(base)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dp = Path(dirpath)
            if base == ROOT / "public":
                dirnames[:] = [d for d in dirnames if d not in SKIP_PUBLIC_DIRS]
            for fn in filenames:
                fp = dp / fn
                if fp.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                if should_skip_file(fp):
                    continue
                out.append(fp)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = [
        ROOT / "public",
        ROOT / "data" / "products_geo.json",
        ROOT / "data" / "product_overrides",
        ROOT / "data" / "jerky_landing_i18n.json",
    ]
    files = iter_files(targets)
    changed = 0
    scanned = 0
    for fp in files:
        scanned += 1
        try:
            original = fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        fixed = fix_text(original, geo_export=False)
        if fixed != original:
            changed += 1
            if not args.dry_run:
                fp.write_text(fixed, encoding="utf-8")
    print(f"scanned={scanned} changed={changed} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
