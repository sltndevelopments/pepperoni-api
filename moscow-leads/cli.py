"""CLI: создать тестовый лид, прогнать воронку, дайджест.

  PYTHONPATH=. python3 cli.py create --company "Пицца Рулит" --city Москва
  PYTHONPATH=. python3 cli.py path LEAD-00001
  PYTHONPATH=. python3 cli.py digest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from command import apply_report, build_exceptions, build_my_day  # noqa: E402
from digest import build_weekly_digest  # noqa: E402
from ingest import ingest_text  # noqa: E402
from model import DISTRIBUTORS, MANAGER_IDS  # noqa: E402
from store import Store  # noqa: E402


def cmd_create(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    lead = store.create_lead(
        source=args.source,
        company=args.company,
        contact=args.contact,
        phone=args.phone,
        city=args.city,
        request=args.request,
        volume=args.volume,
        actor="cli",
    )
    print(json.dumps(lead, ensure_ascii=False, indent=2))


def cmd_ingest(args: argparse.Namespace) -> None:
    text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    lead = ingest_text(text, store=Store(args.db))
    print(json.dumps(lead, ensure_ascii=False, indent=2))


def cmd_path(args: argparse.Namespace) -> None:
    """Полный путь new → first_shipment для проверки."""
    store = Store(args.db)
    store.init()
    lead_id = args.lead_id
    if not lead_id:
        lead = store.create_lead(
            source="manual",
            company="Тест Путь",
            contact="Арби",
            phone="+79990001122",
            city="Москва",
            request="халяльная пепперони",
            actor="cli",
        )
        lead_id = lead["id"]
        print(f"created {lead_id}")
    steps = [
        ("contacted", {}),
        ("samples_sent", {}),
        ("meeting_done", {}),
        ("passed_to_distributor", {"distributor": "GFC"}),
        ("first_shipment", {}),
    ]
    log = []
    for status, kw in steps:
        lead = store.set_status(lead_id, status, actor="cli", **kw)
        log.append({"status": lead["status"], "at": lead["status_changed_at"], "dist": lead.get("distributor")})
        print(f"→ {lead['status']} @ {lead['status_changed_at']}")
    print(json.dumps({"lead_id": lead_id, "log": log, "events": store.events(lead_id)}, ensure_ascii=False, indent=2))


def cmd_digest(args: argparse.Namespace) -> None:
    print(build_weekly_digest(Store(args.db)))


def cmd_day(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    print(build_my_day(store, args.manager))


def cmd_exceptions(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    print(build_exceptions(store))


def cmd_assign(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    lead = store.assign_lead(args.lead_id, args.manager, actor="cli")
    print(json.dumps(lead, ensure_ascii=False, indent=2))


def cmd_report(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    print(json.dumps(apply_report(store, args.task_id, args.text, actor="cli"), ensure_ascii=False, indent=2, default=str))


def cmd_resolve_challenge(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    ch = store.resolve_challenge(args.id, args.status, note=args.note, actor="cli")
    print(json.dumps(ch, ensure_ascii=False, indent=2, default=str))


def cmd_backfill(args: argparse.Namespace) -> None:
    store = Store(args.db)
    store.init()
    n = store.backfill_opening_tasks(limit=args.limit, actor="cli")
    print(json.dumps({"opening_tasks_created": n}, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(prog="moscow-leads")
    p.add_argument("--db", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--source", default="manual")
    c.add_argument("--company", default="Тест")
    c.add_argument("--contact", default="")
    c.add_argument("--phone", default="")
    c.add_argument("--city", default="Москва")
    c.add_argument("--request", default="пепперони")
    c.add_argument("--volume", default="")
    c.set_defaults(func=cmd_create)

    i = sub.add_parser("ingest")
    i.add_argument("--text", default="")
    i.add_argument("--file", default="")
    i.set_defaults(func=cmd_ingest)

    path = sub.add_parser("path")
    path.add_argument("lead_id", nargs="?", default="")
    path.set_defaults(func=cmd_path)

    d = sub.add_parser("digest")
    d.set_defaults(func=cmd_digest)

    day = sub.add_parser("day")
    day.add_argument("--manager", choices=MANAGER_IDS, default="arbi")
    day.set_defaults(func=cmd_day)

    ex = sub.add_parser("exceptions")
    ex.set_defaults(func=cmd_exceptions)

    asg = sub.add_parser("assign")
    asg.add_argument("lead_id")
    asg.add_argument("manager", choices=MANAGER_IDS)
    asg.set_defaults(func=cmd_assign)

    rep = sub.add_parser("report")
    rep.add_argument("task_id")
    rep.add_argument("text")
    rep.set_defaults(func=cmd_report)

    rc = sub.add_parser("resolve-challenge")
    rc.add_argument("id", type=int)
    rc.add_argument("status", choices=("accepted", "rejected"))
    rc.add_argument("--note", default="")
    rc.set_defaults(func=cmd_resolve_challenge)

    bf = sub.add_parser("backfill-tasks")
    bf.add_argument("--limit", type=int, default=40)
    bf.set_defaults(func=cmd_backfill)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
