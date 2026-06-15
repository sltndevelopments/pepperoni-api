"""Кого ставить в очередь аутрича (не только tier S)."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from channels.email import pick_recipient
from core import agent_profile as ap
from core.exclusions import is_excluded
from core.store import Store
from prospecting.lookalike import score_lookalike

CFG = ROOT / "config" / "outreach.yaml"


def _cfg() -> dict:
    try:
        return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _lookalike_score(lead: dict) -> int:
    p = lead.get("profile") or {}
    la = ap.get(p, "lookalike") or p.get("lookalike")
    if isinstance(la, dict) and la.get("lookalike_score"):
        return int(la["lookalike_score"])
    return score_lookalike(lead)["lookalike_score"]


def outreach_candidates(store: Store, *, limit: int = 20) -> list[dict]:
    cfg = _cfg().get("queue", {})
    min_fit = int(cfg.get("min_fit_score", 60))
    min_lookalike = int(cfg.get("min_lookalike_score", 45))
    tiers = set(cfg.get("tiers", ["S", "A"]))
    require_email = bool(cfg.get("require_email", True))
    statuses = set(cfg.get("statuses", ["new"]))

    drafted = {d["lead_id"] for d in store.list_drafts(limit=500)}
    candidates: list[dict] = []

    for lead in store.list_leads(limit=500):
        if lead["id"] in drafted:
            continue
        if (lead.get("status") or "new") not in statuses:
            continue
        if ap.is_handed_off(lead.get("profile") or {}):
            continue
        if is_excluded(lead)[0]:
            continue
        tier = lead.get("tier") or "—"
        fit = lead.get("fit_score") or 0
        la = _lookalike_score(lead)

        if fit < min_fit:
            continue
        if tier not in tiers and not (tier == "S" or la >= min_lookalike + 10):
            continue
        if la < min_lookalike and tier != "S":
            continue
        if require_email and not pick_recipient(lead.get("profile") or {}):
            continue

        # Мёртвый домен (нет MX и нет A) — в очередь не идёт НИКОГДА,
        # независимо от require_verified. Это клинически мёртвые адреса.
        if ap.get(lead.get("profile") or {}, "email_mx_failed"):
            continue

        # email_quality бонус: корп. почта идёт раньше freemail
        # procurement=+15, corporate=+10, generic=+5, freemail/None=0
        _quality_bonus = {
            "procurement": 15,
            "corporate":   10,
            "generic":      5,
        }
        eq = ap.get(lead.get("profile") or {}, "email_quality") or ""
        quality_bonus = _quality_bonus.get(eq, 0)

        candidates.append({**lead, "_lookalike": la,
                            "_sort": la * 2 + fit + quality_bonus})

    candidates.sort(key=lambda x: x["_sort"], reverse=True)
    return candidates[:limit]
