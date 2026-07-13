"""
Триаж входящих (Haiku-tier): классификация, intent, привязка к лиду.
Без LLM — rule-based fallback; с ANTHROPIC_API_KEY — cheap model.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

INTENT_PATTERNS = [
    (
        "price_request",
        re.compile(
            r"прайс|цен[аыув]|стоимост|сколько\s+стоит|price\s*list|\bquote\b|"
            r"запрос\w*\s+(?:кп|коммерческ\w*\s+предложен)|"
            r"(?:пришлите|направьте|дайте)\b.{0,30}\b(?:кп|коммерческ\w*\s+предложен)",
            re.I | re.S,
        ),
    ),
    ("sample_request", re.compile(r"образец|пробн|дегуст|sample", re.I)),
    ("halal_question", re.compile(r"халяль|halal|сертификат", re.I)),
    ("sausage_in_dough", re.compile(r"сосис[а-я]*\s+в\s+тесте", re.I)),
    ("tender", re.compile(r"тендер|закупк|конкурс", re.I)),
    ("negative", re.compile(r"отпис|не интерес|не пишите|spam", re.I)),
    (
        "supplier_offer",
        re.compile(
            r"мы\s+(?:производим|предлагаем|поставляем)\s+"
            r"(?:пл[её]нк|упаков|лент|оборуд|сырь|материал)|готовы\s+предложить|"
            r"нашего\s+стенда|производител[ья]\s+(?:пл[её]нок|упаковк|лент)|"
            r"выслать\s+техническое\s+задание|"
            r"(?:направля(?:ю|ем)|высыла(?:ю|ем))\b.{0,30}\bкоммерческ\w*\s+предложен|"
            r"(?:наш|во\s+вложении)\b.{0,30}\bпрайс",
            re.I,
        ),
    ),
]


def triage_inbound(
    message: dict,
    store: Store | None = None,
    *,
    use_llm: bool = True,
) -> dict:
    store = store or Store()
    body = (message.get("body") or "") + " " + (message.get("subject") or "")
    intents = []
    for name, pat in INTENT_PATTERNS:
        if pat.search(body):
            intents.append(name)

    temperature = "cold"
    # Группа лидов и info@ — это пассивный сбор для аналитики Стива, НЕ повод
    # писать владельцу. Температуру по самому факту канала не поднимаем —
    # эскалация только если в тексте реальный покупательский интент (ниже).
    if "price_request" in intents or "sample_request" in intents:
        temperature = "warm"
    if "sausage_in_dough" in intents:
        temperature = "hot"
    if "negative" in intents:
        temperature = "reject"
    # Поставщик, который продаёт нам плёнку/скотч, не является покупателем,
    # даже если в письме встречается «коммерческое предложение» или «прайс».
    if "supplier_offer" in intents:
        temperature = "cold"
        intents = [
            i for i in intents
            if i not in {"price_request", "sample_request", "sausage_in_dough"}
        ]

    gate_check = {"intents": intents, "temperature": temperature}

    # Опционально: Haiku уточняет intent (если есть ключ)
    try:
        from core.llm import brain_available, call_haiku
        if use_llm and brain_available() and body.strip():
            hint, _ = call_haiku(
                f"Классифицируй B2B-входящее одним словом из: price, sample, halal, tender, reject, other.\n{body[:500]}",
                max_tokens=20,
            )
            gate_check["haiku_tag"] = hint.strip()[:40]
    except Exception:
        pass

    from core.gate import Gate
    g = Gate(store)
    product_fit = g.check_fit([], body)
    gate_check["fit"] = product_fit

    store.audit("triage", "classified_inbound", "message", message.get("id"), gate_check)

    return {
        "message_id": message.get("id"),
        "intents": intents,
        "temperature": temperature,
        "fit": product_fit,
        "suggest_escalate": temperature == "hot",
    }
