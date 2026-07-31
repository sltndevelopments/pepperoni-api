"""Автозаведение лидов из карточек ИИ-ассистента, сайта и Avito."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from model import SOURCES
from store import Store

# Карточка звонка (kazandel-ai-operator / Telegram group).
CALL_HEADER_RE = re.compile(
    r"(?:📞\s*)?Новая заявка\s*[—\-]\s*Казанские\s+Деликатесы|"
    r"(?:☎️\s*)?Запрос менеджера\s*[—\-]\s*Казанские\s+Деликатесы",
    re.I,
)
SITE_HEADER_RE = re.compile(r"🌐\s*Заявка с сайта|заявка с сайта", re.I)
AVITO_HEADER_RE = re.compile(r"🟣\s*Лид Авито|авито", re.I)

FIELD_RE = {
    "company": re.compile(r"(?:Компания|company)\s*:\s*(.+)", re.I),
    "contact": re.compile(r"(?:Контакт|contact|Имя|имя)\s*:\s*(.+)", re.I),
    "phone": re.compile(r"(?:Телефон|phone|звонили с номера)\s*:\s*(.+)", re.I),
    "city": re.compile(r"(?:Город|city)\s*:\s*(.+)", re.I),
    "request": re.compile(
        r"(?:Запрос|интерес|продукц|products?|Сообщение|сообщение)\s*:\s*(.+)",
        re.I,
    ),
    "volume": re.compile(r"(?:Объём|Объем|quantity|объём)\s*:\s*(.+)", re.I),
}
CALL_ID_RE = re.compile(r"ID\s*звонка\s*:\s*(\S+)", re.I)
PHONE_FALLBACK = re.compile(r"(?:\+?7|8)[\s()\-]*\d[\d\s()\-]{8,16}\d")


def detect_source(text: str) -> str | None:
    if CALL_HEADER_RE.search(text) or CALL_ID_RE.search(text):
        return "call"
    if SITE_HEADER_RE.search(text):
        return "site"
    if AVITO_HEADER_RE.search(text):
        return "avito"
    return None


def _field(text: str, key: str) -> str:
    m = FIELD_RE[key].search(text)
    return (m.group(1).strip() if m else "")[:200]


def _external_ref(source: str, text: str, phone: str) -> str:
    call_id = CALL_ID_RE.search(text)
    if call_id:
        return f"call:{call_id.group(1)}"
    raw = f"{source}|{phone}|{text[:240]}".encode("utf-8", errors="ignore")
    return f"{source}:{hashlib.sha1(raw).hexdigest()[:16]}"


def parse_card(text: str) -> dict[str, Any] | None:
    """Разобрать карточку. None — не заявка покупателя."""
    source = detect_source(text)
    if not source:
        return None
    # Предложения «хочет нам что-то предложить» — не лид продаж.
    if "хочет нам что-то предложить" in text.lower() or "отправлен на info@" in text.lower():
        return None

    company = _field(text, "company")
    contact = _field(text, "contact")
    phone = _field(text, "phone")
    if not phone:
        pm = PHONE_FALLBACK.search(text)
        phone = pm.group(0) if pm else ""
    city = _field(text, "city")
    request = _field(text, "request")
    volume = _field(text, "volume")
    if not company and not contact and not phone:
        return None
    return {
        "source": source if source in SOURCES else "manual",
        "company": company or contact or "Без названия",
        "contact": contact,
        "phone": phone,
        "city": city,
        "request": request,
        "volume": volume,
        "external_ref": _external_ref(source, text, phone),
        "note": "",
    }


def ingest_text(text: str, *, store: Store | None = None, actor: str = "ingest") -> dict | None:
    """Создать LEAD из текста карточки. Идемпотентно по external_ref."""
    parsed = parse_card(text)
    if not parsed:
        return None
    store = store or Store()
    store.init()
    return store.create_lead(actor=actor, **parsed)


def ingest_from_leads_json_record(rec: dict, *, store: Store | None = None) -> dict | None:
    """Подхватить запись из data/leads.json (userbot mirror)."""
    text = rec.get("text") or ""
    # Если текст уже в формате карточки — парсим как есть.
    created = ingest_text(text, store=store, actor="leads_json")
    if created:
        return created
    # Иначе — коммерческий лид без карточки: минимальная запись.
    if rec.get("intent") != "commercial":
        return None
    phone = rec.get("phone") or ""
    channel = rec.get("channel") or "telegram"
    source = {
        "avito": "avito",
        "site": "site",
        "phone": "call",
    }.get(channel, "telegram")
    store = store or Store()
    store.init()
    ref = f"json:{rec.get('msg_id') or rec.get('at') or phone}"
    return store.create_lead(
        source=source,
        company="",
        contact="",
        phone=phone,
        city="",
        request=text[:300],
        volume="",
        external_ref=ref,
        actor="leads_json",
    )
