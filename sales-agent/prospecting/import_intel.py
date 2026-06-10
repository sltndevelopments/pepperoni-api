"""
Мост к sales-intel: импорт CSV → лиды в agent.db.
Не трогает sales-intel/data — только читает.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.store import Store

DEFAULT_CSV = ROOT.parent / "sales-intel" / "data" / "bakery-leads-okved-enriched.csv"


def _parse_int(val: str) -> int:
    try:
        return int(float(str(val).replace(" ", "").replace(",", ".")))
    except Exception:
        return 0


def import_from_csv(
    csv_path: Path | str | None = None,
    *,
    store: Store | None = None,
    limit: int | None = None,
    min_score: int = 0,
) -> dict:
    store = store or Store()
    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.exists():
        return {"error": f"file not found: {path}", "imported": 0}

    imported = 0
    skipped = 0

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            score = _parse_int(row.get("score") or row.get("fit_score") or "0")
            if score < min_score:
                skipped += 1
                continue

            inn = (row.get("inn") or "").strip() or None
            name = (row.get("name_short") or row.get("name") or "Без названия").strip()
            region = (row.get("region_name") or row.get("region") or "").strip() or None

            tier = "—"
            sausage = (row.get("sausage_tier") or row.get("tier") or "").strip()
            if sausage in ("S", "A", "B", "C"):
                tier = sausage
            elif (row.get("sausage_in_dough") or "").lower() in ("yes", "true", "1"):
                tier = "S"

            profile = {k: v for k, v in row.items() if v and k not in ("inn", "name_short", "name")}
            store.upsert_lead(
                name,
                inn=inn,
                region=region,
                tier=tier,
                fit_score=score,
                status="new",
                source=f"sales-intel:{path.name}",
                profile=profile,
            )
            imported += 1

    store.audit("import_intel", "csv_import", detail={"path": str(path), "imported": imported, "skipped": skipped})
    return {"imported": imported, "skipped": skipped, "path": str(path)}
