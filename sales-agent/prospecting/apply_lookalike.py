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
    skipped_unchanged = 0
    for lead in store.list_leads(limit=limit):
        if is_excluded(lead)[0]:
            continue
        la = score_lookalike(lead)
        profile = dict(lead.get("profile") or {})
        prev_la = profile.get("lookalike") or {}
        new_fit_score = max(lead.get("fit_score") or 0, la["lookalike_score"])
        # Не трогать updated_at (и не слать в CRM push), если реального
        # изменения нет — иначе каждый 2-часовой цикл "воскрешает" одни и те
        # же escalated/hot лиды наверх ORDER BY updated_at DESC и повторно
        # триггерит proactive-уведомления (баг обнаружен 2026-07-05: одни и
        # те же 5 named targets слались владельцу каждые 2 часа несколько дней).
        if (
            prev_la.get("lookalike_score") == la.get("lookalike_score")
            and prev_la.get("best_match") == la.get("best_match")
            and prev_la.get("reasons") == la.get("reasons")
            and (lead.get("fit_score") or 0) == new_fit_score
        ):
            skipped_unchanged += 1
            continue
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
            fit_score=new_fit_score,
            status=lead.get("status"),
            source=lead.get("source"),
            profile=profile,
        )
        updated += 1
    store.audit("lookalike", "applied", detail={"updated": updated, "skipped_unchanged": skipped_unchanged})
    return {"updated": updated, "skipped_unchanged": skipped_unchanged}
