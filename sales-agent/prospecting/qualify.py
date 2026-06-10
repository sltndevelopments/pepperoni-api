"""
Квалификация Tier S: детект «сосиска в тесте» на сайте.
Переиспользует логику sales-intel/scan_sausage_in_dough.py (read-only import).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEL = ROOT.parent / "sales-intel" / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(INTEL))

from core.store import Store


def qualify_lead_tier(lead_id: str, *, store: Store | None = None, crawl: bool = False) -> dict:
    store = store or Store()
    lead = store.get_lead(lead_id)
    if not lead:
        return {"error": "lead not found"}

    profile = lead.get("profile") or {}
    tier = lead.get("tier", "—")
    fit = lead.get("fit_score") or 0

    # Уже есть результат скана из sales-intel
    if profile.get("sausage_in_dough") or profile.get("sausage_evidence"):
        tier = "S"
        fit = max(fit, 85)
    elif profile.get("sausage_tier"):
        tier = profile["sausage_tier"]

    if crawl and tier != "S":
        try:
            import scan_sausage_in_dough as scanner  # type: ignore
            site = scanner.pick_website(profile.get("sites", ""), profile.get("emails", ""))
            if site:
                result = scanner.scan_site(site, timeout=12, sleep=0.6)
                label = result.get("evidence_label") or ""
                counts = result.get("counts") or {}
                strong = (
                    counts.get("sausage_in_dough", 0)
                    or counts.get("sausage_pastry", 0)
                    or counts.get("hot_dog", 0)
                )
                if label and strong:
                    tier = "S"
                    fit = max(fit, 85)
                    profile["sausage_evidence"] = (result.get("evidence_snippet") or "")[:200]
                    profile["sausage_url"] = result.get("evidence_url") or site
                    profile["sausage_label"] = label
        except Exception as e:
            profile["qualify_error"] = str(e)[:200]

    status = "qualified" if tier == "S" or fit >= 60 else lead.get("status", "new")
    store.upsert_lead(
        lead["name"],
        lead_id=lead_id,
        inn=lead.get("inn"),
        region=lead.get("region"),
        tier=tier,
        fit_score=fit,
        status=status,
        source=lead.get("source"),
        profile=profile,
    )
    store.audit("qualify", "tier_assigned", "lead", lead_id, {"tier": tier, "fit_score": fit})

    return {"lead_id": lead_id, "tier": tier, "fit_score": fit, "status": status}
