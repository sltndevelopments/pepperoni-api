"""
import_named.py — импорт именного списка целевых сетей (Поток 2) в agent.db.

Читает sales-agent/config/named_targets.yaml.
Для каждой цели:
  - Upsert по имени/бренду (нет ИНН → дедупликация по name.lower()).
  - Tier S/A, fit_score=120 (выше любого реестрового лида).
  - source="named_targets".
  - Если лид уже есть (contacted/hot/handed_off) — не перезаписываем статус.
  - После импорта: research_contacts(deep=True) на следующем enrich-цикле
    (contact_researched_at пустой → _research_due вернёт True).

Запуск:
  python3 sales-agent/prospecting/import_named.py [--dry-run]
  или через feed_agent.py --named
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

CFG = ROOT / "config" / "named_targets.yaml"

_TIER_FIT = {"S": 120, "A": 100, "B": 80}
_PROTECTED_STATUSES = {"contacted", "hot", "escalated", "handed_off", "bounced"}


def _load_targets() -> list[dict]:
    data = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    return data.get("targets", [])


def import_named(*, store: Store | None = None, dry_run: bool = False) -> dict:
    """Импортировать именной список в agent.db.

    Возвращает {"imported": int, "skipped": int, "updated": int}.
    """
    store = store or Store()
    store.init()

    targets = _load_targets()
    active = [t for t in targets if t.get("status", "active") != "skip"]

    imported = skipped = updated = 0

    for t in active:
        name = (t.get("brand") or t.get("name") or "").strip()
        if not name:
            continue

        tier = t.get("tier", "A")
        fit = _TIER_FIT.get(tier, 80)
        profile = {
            "segment": t.get("segment", ""),
            "named_target": True,
            "pitch_hint": t.get("pitch", ""),
            "halal_relevant": t.get("halal", False),
            "notes": t.get("notes", ""),
            "brand": t.get("brand", ""),
            "legal_name": t.get("name", ""),
        }

        # Проверяем, есть ли уже такой лид
        existing = None
        for lead in store.list_leads(limit=1000):
            ln = (lead.get("name") or "").strip().lower()
            if ln == name.lower() or ln == (t.get("name") or "").strip().lower():
                existing = lead
                break

        if existing:
            cur_status = existing.get("status") or "new"
            if cur_status in _PROTECTED_STATUSES:
                skipped += 1
                continue
            if not dry_run:
                # Повышаем tier/fit если наш список задаёт выше
                cur_fit = existing.get("fit_score") or 0
                new_fit = max(fit, cur_fit)
                cur_tier_rank = {"S": 4, "A": 3, "B": 2, "C": 1}.get(existing.get("tier") or "—", 0)
                new_tier_rank = {"S": 4, "A": 3, "B": 2, "C": 1}.get(tier, 0)
                new_tier = tier if new_tier_rank >= cur_tier_rank else (existing.get("tier") or tier)
                ep = dict(existing.get("profile") or {})
                ep.update({k: v for k, v in profile.items() if k not in ep or not ep[k]})
                ep["named_target"] = True
                store.upsert_lead(
                    name, lead_id=existing["id"],
                    tier=new_tier, fit_score=new_fit,
                    status=cur_status, source="named_targets",
                    profile=ep,
                )
            updated += 1
        else:
            if not dry_run:
                store.upsert_lead(
                    name, inn=None,
                    region=None, tier=tier, fit_score=fit,
                    status="new", source="named_targets",
                    profile=profile,
                )
            imported += 1

    if not dry_run:
        store.audit("import_named", "done", detail={
            "imported": imported, "updated": updated, "skipped": skipped,
        })

    return {"imported": imported, "updated": updated, "skipped": skipped,
            "dry_run": dry_run}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = import_named(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
