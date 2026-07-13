"""Кого ставить в очередь аутрича (не только tier S)."""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from channels.email import pick_recipient
from core import agent_profile as ap
from core.exclusions import is_excluded
from core.store import Store
from prospecting.lookalike import score_lookalike
from prospecting.contact_research import is_buyer_contact

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


def _active_drafted_ids(store: Store, cfg: dict) -> set[str]:
    """Лиды с активным или уже отправленным первым касанием.

    Cancelled/rejected допускают исправленный повторный draft после cooldown.
    """
    blocking = {"draft", "pending", "approved", "sent"}
    retryable = {"cancelled", "rejected"}
    retry_days = int(cfg.get("draft_retry_days", 7))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retry_days)
    blocked: set[str] = set()
    for draft in store.list_drafts(limit=5000):
        status = draft.get("status") or ""
        if status in blocking:
            blocked.add(draft["lead_id"])
            continue
        if status not in retryable:
            continue
        try:
            touched = datetime.fromisoformat(draft.get("updated_at") or draft.get("created_at"))
            if touched.tzinfo is None:
                touched = touched.replace(tzinfo=timezone.utc)
            if touched >= cutoff:
                blocked.add(draft["lead_id"])
        except Exception:
            blocked.add(draft["lead_id"])
    return blocked


def _candidate_rejection(
    lead: dict,
    *,
    drafted: set[str],
    cfg: dict,
) -> tuple[str | None, int, str | None, str | None]:
    min_fit = int(cfg.get("min_fit_score", 60))
    min_lookalike = int(cfg.get("min_lookalike_score", 45))
    tiers = set(cfg.get("tiers", ["S", "A"]))
    require_email = bool(cfg.get("require_email", True))
    allowed_quality = set(cfg.get("allowed_email_quality", ["procurement", "corporate"]))
    statuses = set(cfg.get("statuses", ["new"]))

    profile = lead.get("profile") or {}
    tier = lead.get("tier") or "—"
    fit = lead.get("fit_score") or 0
    la = _lookalike_score(lead)
    recipient = pick_recipient(profile)
    email_quality = ap.get(profile, "email_quality")

    if lead["id"] in drafted:
        return "existing_draft", la, recipient, email_quality
    if (lead.get("status") or "new") not in statuses:
        return "status", la, recipient, email_quality
    if ap.is_handed_off(profile):
        return "handed_off", la, recipient, email_quality
    if is_excluded(lead)[0]:
        return "excluded", la, recipient, email_quality
    if fit < min_fit:
        return "fit_score", la, recipient, email_quality
    if tier not in tiers and not (tier == "S" or la >= min_lookalike + 10):
        return "tier", la, recipient, email_quality
    if la < min_lookalike and tier != "S":
        return "lookalike", la, recipient, email_quality
    if ap.get(profile, "named_target") or profile.get("named_target"):
        return "named_target", la, recipient, email_quality
    if require_email and not recipient:
        return "missing_email", la, recipient, email_quality
    if allowed_quality and email_quality not in allowed_quality:
        return "email_quality", la, recipient, email_quality
    if not is_buyer_contact(recipient, email_quality):
        return "not_buyer_contact", la, recipient, email_quality
    if not ap.get(profile, "email_verified"):
        return "email_unverified", la, recipient, email_quality
    if ap.get(profile, "email_mx_failed"):
        return "email_mx_failed", la, recipient, email_quality
    return None, la, recipient, email_quality


def outreach_candidates(store: Store, *, limit: int = 20) -> list[dict]:
    cfg = _cfg().get("queue", {})
    drafted = _active_drafted_ids(store, cfg)
    candidates: list[dict] = []

    # Сканируем всю активную базу. Старый limit=500 отрезал подходящие лиды,
    # потому что list_leads сортирует прежде всего по fit_score.
    for lead in store.list_leads(limit=5000):
        rejection, la, _recipient, email_quality = _candidate_rejection(
            lead, drafted=drafted, cfg=cfg
        )
        if rejection:
            continue

        # email_quality бонус: корп. почта идёт раньше freemail
        # procurement=+15, corporate=+10, generic=+5, freemail/None=0
        _quality_bonus = {
            "procurement": 15,
            "corporate":   10,
            "generic":      5,
        }
        quality_bonus = _quality_bonus.get(email_quality or "", 0)
        fit = lead.get("fit_score") or 0

        candidates.append({**lead, "_lookalike": la,
                            "_sort": la * 2 + fit + quality_bonus})

    candidates.sort(key=lambda x: x["_sort"], reverse=True)
    return candidates[:limit]


def outreach_diagnostics(store: Store) -> dict:
    """Объяснить пустую очередь числом лидов на каждом отсекающем гейте."""
    cfg = _cfg().get("queue", {})
    drafted = _active_drafted_ids(store, cfg)
    counts: Counter[str] = Counter()
    eligible: list[dict] = []
    for lead in store.list_leads(limit=5000):
        rejection, la, recipient, quality = _candidate_rejection(
            lead, drafted=drafted, cfg=cfg
        )
        if rejection:
            counts[rejection] += 1
        else:
            counts["eligible"] += 1
            if len(eligible) < 10:
                eligible.append({
                    "id": lead["id"],
                    "name": lead["name"],
                    "lookalike": la,
                    "email": recipient,
                    "quality": quality,
                })
    return {"total": sum(counts.values()), "counts": dict(counts), "eligible": eligible}


def named_escalation_candidates(store: Store, *, limit: int = 20) -> list[dict]:
    """Именные лиды (Поток 2), которых Стив должен исследовать и передать владельцу.

    Критерии:
    - profile._agent.named_target=True (или profile.named_target=True)
    - status not in escalated/hot/handed_off/contacted (ещё не обработаны)
    - не исключены (is_excluded)
    Стив по ним не шлёт автоматически — ищет ЛПР через Perplexity и эскалирует.
    """
    result: list[dict] = []
    _skip_statuses = {"hot", "escalated", "handed_off", "contacted", "bounced", "won"}

    for lead in store.list_leads(limit=500):
        p = lead.get("profile") or {}
        is_named = ap.get(p, "named_target") or p.get("named_target")
        if not is_named:
            continue
        if (lead.get("status") or "new") in _skip_statuses:
            continue
        if is_excluded(lead)[0]:
            continue
        result.append(lead)

    result.sort(key=lambda x: x.get("fit_score") or 0, reverse=True)
    return result[:limit]
