"""Записать lookalike-скоринг в profile лидов и обновить CRM-колонки."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.exclusions import is_excluded
from core.store import Store
from prospecting.lookalike import score_lookalike


def apply_all(*, store: Store | None = None, limit: int = 500) -> dict:
    store = store or Store()
    store.init()
    updated = 0
    for lead in store.list_leads(limit=limit):
        if is_excluded(lead)[0]:
            continue
        la = score_lookalike(lead)
        profile = dict(lead.get("profile") or {})
        profile["lookalike"] = la
        agent = dict(profile.get("agent") or {})
        agent["updated_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        profile["agent"] = agent
        store.upsert_lead(
            lead["name"],
            lead_id=lead["id"],
            inn=lead.get("inn"),
            region=lead.get("region"),
            tier=lead.get("tier"),
            fit_score=max(lead.get("fit_score") or 0, la["lookalike_score"]),
            status=lead.get("status"),
            source=lead.get("source"),
            profile=profile,
        )
        updated += 1
    store.audit("lookalike", "applied", detail={"updated": updated})
    return {"updated": updated}
