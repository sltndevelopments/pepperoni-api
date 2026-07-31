"""
Обогащение лидов без email — тонкая обёртка над contact_research.py.

Весь HTTP/scraping/ранжирование/верификация живёт в contact_research.
Этот модуль отвечает только за: кого брать, когда брать, как сохранять.

Запуск: python3 -m console.cli enrich [--limit N]
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Re-export констант для обратной совместимости (bounce_recovery их импортировал отсюда)
from prospecting.contact_research import (  # noqa: F401
    EMAIL_RE, SKIP_EMAIL, enrich_by_inn, emails_from_site as _emails_from_site,
)

from core.store import Store
from prospecting.contact_research import research_contacts, apply_research_to_lead

# Тир S/A — кандидаты на глубокий ресёрч с Perplexity
_DEEP_TIERS = {"S", "A"}
_OUTREACH_CFG = ROOT / "config" / "outreach.yaml"


def _enrichment_cfg() -> dict:
    try:
        return (yaml.safe_load(_OUTREACH_CFG.read_text(encoding="utf-8")) or {}).get("enrichment", {})
    except Exception:
        return {}


_DEEP_LOOKALIKE_THRESHOLD = int(_enrichment_cfg().get("min_lookalike_for_deep", 45))
_ENRICH_COOLDOWN_DAYS = int(_enrichment_cfg().get("cooldown_days", 30))
_ENRICH_RETRY_DAYS = int(_enrichment_cfg().get("retry_days", 7))


# Качество email из первичного impорта (ОКВЭД-реестр даёт то, что указано в
# ЕГРЮЛ/на сайте — почти всегда общий ok@/sbyt@/lab@, не закупщик). Такое
# «есть хоть какой-то email» раньше блокировало deep-research навсегда
# (баг обнаружен 2026-07-05: 216 холодных писем, 0% ответов — потому что
# письма уходили на общие ящики, которые читает секретарь/HR, а не ЛПР).
_LOW_QUALITY = {"generic", "freemail", None}


def _needs_enrich(lead: dict) -> bool:
    from core import agent_profile as ap
    from channels.email import pick_recipient
    from prospecting.contact_research import is_buyer_contact

    p = lead.get("profile") or {}
    quality = ap.get(p, "email_quality") or p.get("email_quality")
    verified = bool(ap.get(p, "email_verified"))
    buyer_contact = verified and is_buyer_contact(pick_recipient(p), quality)

    # Успешный buyer-contact живёт 30 дней. Неудачный поиск (generic/freemail/
    # ничего) повторяем через короткий retry, а не замораживаем на месяц.
    if buyer_contact:
        checked_at = ap.get(p, "contact_enriched_at") or ap.get(p, "contact_last_attempt_at")
    else:
        checked_at = (
            ap.get(p, "contact_last_attempt_at")
            or ap.get(p, "contact_failed_at")
            or ap.get(p, "contact_enriched_at")
            or ap.get(p, "contact_researched_at")
        )
    if checked_at:
        try:
            checked = datetime.fromisoformat(str(checked_at))
            cooldown_days = _ENRICH_COOLDOWN_DAYS if buyer_contact else _ENRICH_RETRY_DAYS
            if (datetime.now(timezone.utc) - checked).total_seconds() < cooldown_days * 86400:
                return False
        except Exception:
            pass
    return True


def _is_deep(lead: dict) -> bool:
    """Ценный лид — заслуживает Perplexity + ресёрч реального сайта."""
    from core import agent_profile as ap
    if lead.get("tier") in _DEEP_TIERS:
        return True
    p = lead.get("profile") or {}
    la = ap.get(p, "lookalike") or p.get("lookalike") or {}
    if isinstance(la, dict) and (la.get("lookalike_score") or 0) >= _DEEP_LOOKALIKE_THRESHOLD:
        return True
    return False


def enrich_leads(
    *,
    store: Store | None = None,
    limit: int = 30,
    pause_sec: float = 4.0,
) -> dict:
    """Обогатить лиды без email (по ИНН).

    Tier S/A или высокий lookalike → глубокий ресёрч (Perplexity + реальный сайт).
    Остальные → дешёвый ZCB + rank + MX.
    Cooldown глубокого ресёрча: 30 дней (задан в contact_research._research_due).
    """
    store = store or Store()
    store.init()

    targets = [
        l for l in store.list_leads(limit=5000)
        if _needs_enrich(l) and l.get("inn") and (l.get("status") or "new") == "new"
    ]
    targets.sort(key=lambda x: x.get("fit_score") or 0, reverse=True)
    targets = targets[:limit]

    attempted = 0
    enriched = 0
    found_email = 0

    for lead in targets:
        deep = _is_deep(lead)
        research = research_contacts(lead, deep=deep, pause_sec=pause_sec / 4)
        time.sleep(pause_sec)

        apply_research_to_lead(lead, research, store=store, deep=deep)
        attempted += 1
        if research.get("best_email") or research.get("site"):
            enriched += 1
        if research.get("best_email"):
            found_email += 1

    store.audit("enrich", "contacts", detail={
        "attempted": attempted, "enriched": enriched, "found_email": found_email,
    })
    return {"attempted": attempted, "enriched": enriched, "found_email": found_email}


if __name__ == "__main__":
    import json
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print(json.dumps(enrich_leads(limit=limit), ensure_ascii=False, indent=2))
