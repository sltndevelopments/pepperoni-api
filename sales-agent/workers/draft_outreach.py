"""
Генерация черновиков аутрича (Sonnet).
Первое касание: OEM + преимущества + discovery. Цены по запросу с дисклеймером.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "scripts"))

from core.gate import Gate
from core.llm import brain_available, call_sonnet
from core.store import Store
from kb.loader import KnowledgeBase

OWNER_NAME  = os.environ.get("OWNER_NAME",  "Ринат Султанов")
# Личные контакты владельца — ТОЛЬКО в подписи писем 1:1, никогда публично
OWNER_PHONE = os.environ.get("OWNER_PHONE", "+7 927 429-72-20")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "kam@kazandelikates.tatar")


def _signature() -> str:
    return f"""С уважением,
{OWNER_NAME}
{OWNER_PHONE}
{OWNER_EMAIL}"""


def _draft_system(kb: KnowledgeBase, channel: str) -> str:
    """Стабильный префикс — одинаков для всех лидов → prompt cache (10% цены входа)."""
    pb = kb.load_playbook()
    disc = (pb.get("pricing") or {}).get("disclaimer", "")
    return f"""B2B sales Kazan Delicacies. Не публикуй контакты вне подписи письма.

Ты пишешь B2B-письма ({channel}), первое касание, от менеджера продаж.

{kb.sales_context(10)}

ЖЁСТКИЙ КОМПЛАЕНС (нарушение недопустимо):
- Говядина/курица/баранина/индейка — свободно для любого рынка.
- Ветчина халяльная (куриная, из индейки, мраморная с говядиной) — использовать свободно.
- Конина/казылык — ТОЛЬКО по-русски для РФ/Казахстан/Кыргызстан. Для англо-, арабоязычных и стран Залива — НИКОГДА.
- Свинина, шпик, сало, алкоголь — НИКОГДА.
- По-арабски ветчина: «جامبون بقري حلال», НИКОГДА «لحم الخنزير». Кошер не заявлять.
- Сертификаты только реальные: Халяль ДУМ РТ №614A/2024 (мясо), №884A/2025 (выпечка), HACCP, ISO 22000:2018.
- Контакты ДВА ЯРУСА: в подписи письма 1:1 — ТОЛЬКО личные (kam@, +7 927 429-72-20). Публичные (info@, +7 987 217-02-02) — НИКОГДА в письма клиентам напрямую (они для сайта/бота/API).
- Бренд: «Казанские Деликатесы» / Kazan Delicacies — не сокращать до «KD».
- Не выдумывать клиентов, цифры, награды, ГОСТы. Факт не подтверждён → не утверждать.

Структура письма:
1. Одно предложение — кто мы (halal, Казань, pepperoni.tatar)
2. Релевантное предложение: каталог SKU + OEM/СТМ (https://pepperoni.tatar/oem) — в первом письме
3. 2–3 преимущества: халяль, ХАССП, ISO, экспорт, R&D
4. Вопрос: что вас интересует, примерный объём, есть ли проходная цена
5. Если уместно — 1 ориентир цены из каталога + фраза: «{disc}»
6. Подпись (точно так):

{_signature()}

Тон: холодный профессионал. 150–220 слов. Без CAPS. Не больше 2 ссылок.
Формат ответа:
SUBJECT: ...
BODY:
..."""


def _llm_draft(lead: dict, kb: KnowledgeBase, channel: str = "email") -> tuple[str, str]:
    name = lead.get("name", "коллеги")
    region = lead.get("region") or ""
    tier = lead.get("tier", "—")
    profile = lead.get("profile") or {}
    evidence = profile.get("sausage_evidence") or profile.get("score_reasons") or ""
    pb = kb.load_playbook()
    disc = (pb.get("pricing") or {}).get("disclaimer", "")

    # Переменная часть — короткая (≈50–100 токенов); всё стабильное в system
    prompt = f"""Получатель: {name}, {region}, tier {tier}
Сигнал: {evidence[:280]}

Напиши письмо."""
    if brain_available():
        try:
            text, _ = call_sonnet(
                prompt,
                system=_draft_system(kb, channel),
                cache_system=True,
                effort="medium",
            )
            return _parse_subject_body(text)
        except Exception:
            pass

    subject = f"Halal OEM и поставки — {name[:45]}"
    body = f"""Здравствуйте!

Казанские Деликатесы (pepperoni.tatar) — halal-производитель полного цикла в Казани: 77 SKU заморозки и выпечки, контрактное производство под СТМ (OEM).

Для вашего профиля{f' ({region})' if region else ''} можем предложить сосиски в тесте / гриль-сосиски из каталога или выпуск под вашим брендом — от 500 кг/мес. Халяль (ДУМ РТ), ХАССП, ISO 22000:2018, экспорт в СНГ и GCC, собственный R&D.

{f'Сигнал: {evidence[:100]}' if evidence else ''}

Подскажите, какие позиции и объёмы вас интересуют? Есть ли ориентир по проходной цене? {disc}

{_signature()}
"""
    return subject, body


def _parse_subject_body(text: str) -> tuple[str, str]:
    subject = "Сотрудничество — halal / OEM Казанские Деликатесы"
    body = text.strip()
    if "SUBJECT:" in text.upper():
        parts = text.split("BODY:", 1) if "BODY:" in text else text.split("body:", 1)
        if len(parts) == 2:
            subject = parts[0].replace("SUBJECT:", "").replace("subject:", "").strip()
            body = parts[1].strip()
    if OWNER_NAME not in body:
        body = body.rstrip() + "\n\n" + _signature()
    return subject, body


def draft_cold_email(
    lead_id: str,
    *,
    store: Store | None = None,
    auto_submit: bool = False,
    channel: str = "email",
) -> dict | None:
    store = store or Store()
    gate = Gate(store)
    lead = store.get_lead(lead_id)
    if not lead:
        return None

    from core.exclusions import is_excluded
    excl, why = is_excluded(lead)
    if excl:
        store.audit("draft_worker", "excluded", "lead", lead_id, {"reason": why})
        return None

    fit_score = lead.get("fit_score") or 0
    min_fit = (gate._capabilities.get("scoring") or {}).get("min_fit_for_draft", 60)
    if fit_score < min_fit:
        store.audit("draft_worker", "skipped_low_fit", "lead", lead_id, {"fit_score": fit_score})
        return None

    kb = KnowledgeBase()
    fit_check = gate.check_fit(
        ["сосиска в тесте", "OEM", "СТМ"],
        (lead.get("profile") or {}).get("name", "") + " " + str(lead.get("profile", {}).get("score_reasons", "")),
    )

    subject, body = _llm_draft(lead, kb, channel)

    draft_id = store.create_draft(
        lead_id,
        channel,
        body,
        subject=subject,
        fit_check=fit_check,
        status="draft",
    )
    store.audit("draft_worker", "created_draft", "draft", draft_id, {"lead_id": lead_id})

    outbound = None
    if auto_submit and fit_check.get("can_proceed_to_draft", True):
        outbound = gate.process_draft_outbound(draft_id, send_now=True, dry_run=False)

    return {
        "draft_id": draft_id,
        "outbound": outbound,
        "subject": subject,
        "fit_check": fit_check,
    }
