#!/usr/bin/env python3
"""
CLI-консоль sales-agent.

  python -m console.cli init
  python -m console.cli stats
  python -m console.cli leads [--tier S] [--status new]
  python -m console.cli inbox
  python -m console.cli drafts [--status pending]
  python -m console.cli approvals
  python -m console.cli approve <approval_id>
  python -m console.cli reject <approval_id>
  python -m console.cli import-intel [--limit N] [--min-score N]
  python -m console.cli qualify <lead_id> [--crawl]
  python -m console.cli draft <lead_id>
  python -m console.cli cycle
  python -m console.cli serve [--port 8765]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.gate import Gate
from core.store import Store
from orchestrator.run_cycle import run_cycle
from prospecting.import_intel import import_from_csv
from prospecting.qualify import qualify_lead_tier
from workers.draft_outreach import draft_cold_email


def cmd_init(_: argparse.Namespace) -> None:
    store = Store()
    store.init()
    print(f"OK: {store.db_path}")


def cmd_stats(_: argparse.Namespace) -> None:
    store = Store()
    store.init()
    print(json.dumps(store.stats(), ensure_ascii=False, indent=2))


def cmd_apply_lookalike(_: argparse.Namespace) -> None:
    from prospecting.apply_lookalike import apply_all
    print(json.dumps(apply_all(), ensure_ascii=False, indent=2))


def cmd_lookalike(args: argparse.Namespace) -> None:
    from prospecting.lookalike import rank_leads
    from core.exclusions import is_excluded
    store = Store()
    leads = [l for l in store.list_leads(limit=500) if not is_excluded(l)[0]]
    for r in rank_leads(leads, min_score=args.min_score)[:args.limit]:
        la = r["lookalike"]
        print(f"{la['lookalike_score']:3} → {la['best_match']:20} {r['name'][:50]}")
        print(f"     {', '.join(la['reasons'][:4])}")


def cmd_hot(_: argparse.Namespace) -> None:
    store = Store()
    from workers.escalate import format_contacts
    rows = store.list_hot_leads(15)
    if not rows:
        print("Нет горячих лидов")
        return
    for r in rows:
        print(format_contacts(r).replace("<b>", "").replace("</b>", ""))
        print("---")


def cmd_leads(args: argparse.Namespace) -> None:
    store = Store()
    rows = store.list_leads(status=args.status, tier=args.tier, limit=args.limit)
    for r in rows:
        print(f"{r['id'][:8]}  tier={r['tier']}  score={r['fit_score']}  {r['status']:12}  {r['name'][:50]}")


def cmd_inbox(args: argparse.Namespace) -> None:
    store = Store()
    for m in store.inbox(limit=args.limit):
        subj = m.get("subject") or ""
        print(f"{m['created_at'][:19]}  {m.get('channel','?'):8}  {subj[:40]}  { (m.get('body') or '')[:80]}")


def cmd_drafts(args: argparse.Namespace) -> None:
    store = Store()
    for d in store.list_drafts(status=args.status, limit=args.limit):
        print(f"{d['id'][:8]}  {d['status']:10}  {d['channel']:12}  {d.get('lead_name','')[:30]}")
        if args.verbose:
            print(f"  SUBJ: {d.get('subject','')}")
            print(f"  { (d.get('body') or '')[:200]}...")


def cmd_approvals(args: argparse.Namespace) -> None:
    store = Store()
    gate = Gate(store)
    for i, a in enumerate(store.list_approvals("pending", limit=args.limit), 1):
        print(f"{i}. [{a['id'][:8]}] {a['action']} — {a.get('lead_name','?')}")
        print(f"   {a.get('title','')}")
        if args.verbose:
            print(f"   {(a.get('body') or '')[:300]}")


def cmd_approve(args: argparse.Namespace) -> None:
    gate = Gate()
    r = gate.approve(args.id, decided_by="cli")
    print("approved" if r else "not found or already decided")


def cmd_reject(args: argparse.Namespace) -> None:
    gate = Gate()
    r = gate.reject(args.id, decided_by="cli", reason=args.reason or "")
    print("rejected" if r else "not found or already decided")


def cmd_import_intel(args: argparse.Namespace) -> None:
    r = import_from_csv(args.csv, limit=args.limit, min_score=args.min_score)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_sync_sheet(args: argparse.Namespace) -> None:
    from prospecting.sync_crm_sheet import sync
    r = sync(limit=args.limit)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_enrich(args: argparse.Namespace) -> None:
    from prospecting.enrich_contacts import enrich_leads
    print(json.dumps(enrich_leads(limit=args.limit), ensure_ascii=False, indent=2))


def cmd_fetch_mail(_: argparse.Namespace) -> None:
    from channels.imap_inbox import fetch_inbox
    print(json.dumps(fetch_inbox(), ensure_ascii=False, indent=2))


def cmd_crm_setup(args: argparse.Namespace) -> None:
    from crm.google_sync import setup_crm
    r = setup_crm()
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_crm_pull(args: argparse.Namespace) -> None:
    from crm.google_sync import pull_leads
    r = pull_leads(limit=args.limit)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_crm_push(args: argparse.Namespace) -> None:
    from crm.google_sync import push_leads, push_activity
    r = push_leads(limit=args.limit)
    if args.activity:
        r["activity"] = push_activity()
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_crm_sync(args: argparse.Namespace) -> None:
    from crm.google_sync import crm_sync
    r = crm_sync()
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_qualify(args: argparse.Namespace) -> None:
    r = qualify_lead_tier(args.lead_id, crawl=args.crawl)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_draft(args: argparse.Namespace) -> None:
    r = draft_cold_email(args.lead_id, auto_submit=args.submit)
    print(json.dumps(r, ensure_ascii=False, indent=2) if r else "skipped")


def cmd_cycle(args: argparse.Namespace) -> None:
    r = run_cycle(dry_run_send=not args.live_send, max_drafts=args.max_drafts)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_serve(args: argparse.Namespace) -> None:
    from console.server import main as serve_main
    serve_main(port=args.port)


def cmd_bot(_: argparse.Namespace) -> None:
    from telegram.bot import main as bot_main
    raise SystemExit(bot_main())


def cmd_audit(args: argparse.Namespace) -> None:
    store = Store()
    for row in store.audit_tail(args.limit):
        print(f"{row['created_at'][:19]}  {row['actor']:12}  {row['action']:20}  {row.get('entity_id','')}")


def main() -> None:
    p = argparse.ArgumentParser(prog="sales-agent", description="B2B sales agent console")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=cmd_init)
    sub.add_parser("stats").set_defaults(func=cmd_stats)

    sub.add_parser("apply-lookalike", help="Записать lookalike-скоры в лиды + CRM").set_defaults(func=cmd_apply_lookalike)

    pla = sub.add_parser("lookalike", help="Ранжирование похожих на эталонных клиентов")
    pla.add_argument("--min-score", type=int, default=50)
    pla.add_argument("--limit", type=int, default=20)
    pla.set_defaults(func=cmd_lookalike)

    sub.add_parser("hot", help="Заинтересованные лиды с контактами").set_defaults(func=cmd_hot)

    pl = sub.add_parser("leads")
    pl.add_argument("--tier")
    pl.add_argument("--status")
    pl.add_argument("--limit", type=int, default=30)
    pl.set_defaults(func=cmd_leads)

    pi = sub.add_parser("inbox")
    pi.add_argument("--limit", type=int, default=20)
    pi.set_defaults(func=cmd_inbox)

    pd = sub.add_parser("drafts")
    pd.add_argument("--status")
    pd.add_argument("--limit", type=int, default=20)
    pd.add_argument("-v", "--verbose", action="store_true")
    pd.set_defaults(func=cmd_drafts)

    pa = sub.add_parser("approvals")
    pa.add_argument("--limit", type=int, default=20)
    pa.add_argument("-v", "--verbose", action="store_true")
    pa.set_defaults(func=cmd_approvals)

    pap = sub.add_parser("approve")
    pap.add_argument("id")
    pap.set_defaults(func=cmd_approve)

    pr = sub.add_parser("reject")
    pr.add_argument("id")
    pr.add_argument("--reason", default="")
    pr.set_defaults(func=cmd_reject)

    pss = sub.add_parser("sync-sheet", help="Импорт из Google Sheets (API или pub CSV)")
    pss.add_argument("--limit", type=int, default=None)
    pss.set_defaults(func=cmd_sync_sheet)

    pen = sub.add_parser("enrich", help="Обогащение контактов лидов без email (по ИНН)")
    pen.add_argument("--limit", type=int, default=30)
    pen.set_defaults(func=cmd_enrich)

    sub.add_parser("fetch-mail", help="Забрать входящие IMAP sales@").set_defaults(func=cmd_fetch_mail)

    sub.add_parser("crm-setup", help="Создать/перестроить CRM в Google Sheets").set_defaults(func=cmd_crm_setup)

    pcp = sub.add_parser("crm-pull", help="Импорт лидов из приватной таблицы")
    pcp.add_argument("--limit", type=int, default=None)
    pcp.set_defaults(func=cmd_crm_pull)

    pcu = sub.add_parser("crm-push", help="Запись лидов агента в таблицу")
    pcu.add_argument("--limit", type=int, default=5000)
    pcu.add_argument("--activity", action="store_true", help="также дописать журнал Активность")
    pcu.set_defaults(func=cmd_crm_push)

    sub.add_parser("crm-sync", help="pull + push + activity").set_defaults(func=cmd_crm_sync)

    pii = sub.add_parser("import-intel")
    pii.add_argument("--csv", default=None)
    pii.add_argument("--limit", type=int, default=None)
    pii.add_argument("--min-score", type=int, default=50)
    pii.set_defaults(func=cmd_import_intel)

    pq = sub.add_parser("qualify")
    pq.add_argument("lead_id")
    pq.add_argument("--crawl", action="store_true")
    pq.set_defaults(func=cmd_qualify)

    pdr = sub.add_parser("draft")
    pdr.add_argument("lead_id")
    pdr.add_argument("--submit", action="store_true")
    pdr.set_defaults(func=cmd_draft)

    pc = sub.add_parser("cycle")
    pc.add_argument("--max-drafts", type=int, default=5)
    pc.add_argument("--live-send", action="store_true", help="реальная отправка (по умолчанию dry-run)")
    pc.set_defaults(func=cmd_cycle)

    ps = sub.add_parser("serve")
    ps.add_argument("--port", type=int, default=8765)
    ps.set_defaults(func=cmd_serve)

    sub.add_parser("bot", help="Запуск @KDSalesManagerBot").set_defaults(func=cmd_bot)

    pau = sub.add_parser("audit")
    pau.add_argument("--limit", type=int, default=25)
    pau.set_defaults(func=cmd_audit)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
