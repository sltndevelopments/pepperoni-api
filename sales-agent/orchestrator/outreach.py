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


def outreach_candidates(store: Store, *, limit: int = 20) -> list[dict]:
    cfg = _cfg().get("queue", {})
    min_fit = int(cfg.get("min_fit_score", 60))
    min_lookalike = int(cfg.get("min_lookalike_score", 45))
    tiers = set(cfg.get("tiers", ["S", "A"]))
    require_email = bool(cfg.get("require_email", True))
    allowed_quality = set(cfg.get("allowed_email_quality", ["procurement", "corporate"]))
    statuses = set(cfg.get("statuses", ["new"]))

    # Сканируем всю активную базу. Старый limit=500 отрезал подходящие лиды,
    # потому что list_leads сортирует прежде всего по fit_score.
    drafted = {d["lead_id"] for d in store.list_drafts(limit=5000)}
    candidates: list[dict] = []

    for lead in store.list_leads(limit=5000):
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
        # Именные цели (Поток 2) — только через эскалацию, не автоотправка
        if ap.get(lead.get("profile") or {}, "named_target") or \
                (lead.get("profile") or {}).get("named_target"):
            continue

        recipient = pick_recipient(lead.get("profile") or {})
        if require_email and not recipient:
            continue

        # Не отправляем холодное письмо на HR/общий/freemail ящик. Сначала
        # contact enrichment должен найти закупщика или корпоративный адрес.
        email_quality = ap.get(lead.get("profile") or {}, "email_quality")
        if allowed_quality and email_quality not in allowed_quality:
            continue
        if not is_buyer_contact(recipient, email_quality):
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
