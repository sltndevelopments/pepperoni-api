"""
Одноразовая чистка дублей лидов, созданных багом upsert_lead (до фикса
2026-07-05, коммит 44d7ac028): лиды без ИНН дедуплицировались только по
lead_id/inn, поэтому каждый push→pull цикл CRM плодил новую строку для
той же компании. К моменту фикса — 547k+ дублей, 549 756 строк всего.

Стратегия:
  1. Группируем лиды с inn IS NULL/'' по (lower(name), region).
  2. В каждой группе >1 строки выбираем "лучшую" (survivor):
     - выше по рангу status (escalated > contacted > hot > new > остальные)
     - при равенстве — больше непустых полей в profile
     - при равенстве — раньше created_at (старейшая запись)
  3. threads.lead_id и drafts.lead_id, ссылающиеся на удаляемые id,
     переставляем на survivor.id (сохраняем историю переписки/черновики).
  4. Удаляем "проигравшие" строки из leads.

Запуск: python3 scripts/cleanup_duplicates.py [--dry-run] [--db PATH]
Перед запуском на проде: бэкап agent.db делается автоматически (copy рядом
с timestamp), плюс рекомендуется на время выключить crm-pull cron.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "agent.db"

_STATUS_RANK = {
    "escalated": 6,
    "contacted": 5,
    "hot": 4,
    "replied": 4,
    "new": 1,
    "bounced": 0,
    "lost": 0,
}


def _status_rank(status: str | None) -> int:
    return _STATUS_RANK.get((status or "").lower(), 2)


def _profile_richness(profile_json: str | None) -> int:
    try:
        p = json.loads(profile_json or "{}")
    except Exception:
        return 0
    return sum(1 for v in p.values() if v not in (None, "", {}, []))


def _pick_survivor(rows: list[sqlite3.Row]) -> sqlite3.Row:
    def key(r: sqlite3.Row):
        return (
            -_status_rank(r["status"]),
            -_profile_richness(r["profile"]),
            r["created_at"] or "",
        )
    return sorted(rows, key=key)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    if not args.dry_run:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = db_path.with_name(f"{db_path.stem}.bak.{ts}{db_path.suffix}")
        shutil.copy2(db_path, backup)
        print(f"[backup] {backup}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, name, region, status, profile, created_at FROM leads WHERE inn IS NULL OR inn=''"
    ).fetchall()
    print(f"[scan] {len(rows)} leads without inn")

    groups: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        key = ((r["name"] or "").strip().lower(), (r["region"] or "").strip().lower())
        groups[key].append(r)

    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    total_dupe_rows = sum(len(v) - 1 for v in dup_groups.values())
    print(f"[scan] {len(dup_groups)} duplicate groups, {total_dupe_rows} rows to remove")

    removed = 0
    reassigned_threads = 0
    reassigned_drafts = 0

    for (name, region), group_rows in dup_groups.items():
        survivor = _pick_survivor(group_rows)
        losers = [r for r in group_rows if r["id"] != survivor["id"]]
        loser_ids = [r["id"] for r in losers]

        if args.dry_run:
            print(f"  KEEP {survivor['id']} ({survivor['status']})  name={name!r} region={region!r}  "
                  f"DROP {len(loser_ids)}")
            removed += len(loser_ids)
            continue

        placeholders = ",".join("?" * len(loser_ids))
        cur = conn.execute(
            f"UPDATE threads SET lead_id=? WHERE lead_id IN ({placeholders})",
            (survivor["id"], *loser_ids),
        )
        reassigned_threads += cur.rowcount
        cur = conn.execute(
            f"UPDATE drafts SET lead_id=? WHERE lead_id IN ({placeholders})",
            (survivor["id"], *loser_ids),
        )
        reassigned_drafts += cur.rowcount
        conn.execute(f"DELETE FROM leads WHERE id IN ({placeholders})", loser_ids)
        removed += len(loser_ids)

    if args.dry_run:
        print(f"[dry-run] would remove {removed} rows total (no changes made)")
    else:
        conn.commit()
        print(f"[done] removed {removed} duplicate leads, "
              f"reassigned {reassigned_threads} threads, {reassigned_drafts} drafts")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
