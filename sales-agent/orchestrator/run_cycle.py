"""
Один цикл оркестратора: наблюдение → план → воркеры → рефлексия.

Запуск: python -m orchestrator.run_cycle
или:    python -m console.cli cycle
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.autonomy import is_autonomous
from core.gate import Gate
from core.store import Store
from orchestrator.planner import observe, plan, reflect
from prospecting.tenders import scan_tenders
from orchestrator.outreach import outreach_candidates
from prospecting.apply_lookalike import apply_all as apply_lookalike_scores
from workers.draft_outreach import draft_cold_email
from workers.interest import scan_contacted_for_replies, scan_inbox


def run_cycle(*, dry_run_send: bool | None = None, max_drafts: int = 5) -> dict:
    if dry_run_send is None:
        dry_run_send = not is_autonomous()
    store = Store()
    store.init()
    gate = Gate(store)

    apply_lookalike_scores(store=store)

    try:
        from channels.imap_inbox import fetch_inbox, imap_configured
        if imap_configured():
            imap_result = fetch_inbox(store=store)
        else:
            imap_result = {"skipped": "imap_not_configured"}
    except Exception as e:
        imap_result = {"error": str(e)[:200]}

    signals = store.unprocessed_signals()
    outreach_pending = outreach_candidates(store, limit=max_drafts * 4)
    pending = store.list_approvals("pending")

    state = {
        "stats": store.stats(),
        "unprocessed_signals": signals,
        "pending_approvals": len(pending),
        "tier_s_no_draft": len(outreach_pending),
        "outreach_queue": [
            {"id": l["id"], "name": l["name"][:40], "lookalike": l.get("_lookalike")}
            for l in outreach_pending[:5]
        ],
    }

    obs = observe(state)
    tasks = plan(obs, max_drafts=max_drafts)
    results: list[dict] = []

    for task in tasks:
        w = task.get("worker")
        if w == "process_signals":
            for sig in signals[:20]:
                if sig.get("signal_type") == "intent" and sig.get("payload", {}).get("text"):
                    store.add_inbound("manual", sig["payload"]["text"], meta={"signal_id": sig["id"]})
                store.mark_signal_processed(sig["id"])
            results.append({"worker": w, "processed": min(20, len(signals))})

        elif w == "scan_interest":
            inbox_hits = scan_inbox(store)
            reply_hits = scan_contacted_for_replies(store)
            results.append({
                "worker": w,
                "inbox_escalations": len(inbox_hits),
                "reply_escalations": len(reply_hits),
            })

        elif w == "draft_outreach":
            count = task.get("count", 1)
            drafted = 0
            for lead in outreach_pending[:count]:
                r = draft_cold_email(lead["id"], store=store, auto_submit=True)
                if r:
                    drafted += 1
            results.append({"worker": w, "drafted": drafted})

        elif w == "remind_approvals":
            results.append({"worker": w, "pending": len(pending)})

        elif w == "tender_scan_stub":
            r = scan_tenders(store)
            results.append({"worker": w, **r})

    # Исполнить одобренные (dry_run по умолчанию)
    sent = gate.execute_approved(dry_run=dry_run_send)
    if sent:
        results.append({"worker": "execute_approved", "count": len(sent), "dry_run": dry_run_send})

    summary = reflect(tasks, results)
    summary["imap"] = imap_result
    store.save_orchestrator_run("full_cycle", {"tasks": tasks}, summary)
    store.audit("orchestrator", "cycle_complete", detail=summary)

    try:
        from crm.google_sync import crm_sync
        summary["crm_sync"] = crm_sync(store=store)
    except Exception as e:
        summary["crm_sync"] = {"skipped": str(e)[:200]}

    # Стив-стратег: думает голосом своей личности (бюджет-гейт $20), пишет память,
    # предлагает себе инструменты. Затем toolsmith строит/прогоняет их в песочнице.
    def _steve_thought_today() -> bool:
        """Стив делает глубокую стратегию раз в сутки, не на каждом 2-часовом цикле."""
        from datetime import date
        marker = ROOT / "data" / "steve_last_think.txt"
        today = date.today().isoformat()
        try:
            if marker.read_text(encoding="utf-8").strip() == today:
                return True
        except Exception:
            pass
        try:
            marker.write_text(today, encoding="utf-8")
        except Exception:
            pass
        return False

    try:
        from core.budget import brain_allowed
        if brain_allowed() and not _steve_thought_today():
            from strategist.insights import think as steve_think
            steve_plan = steve_think(store=store)
            summary["steve_strategy"] = steve_plan
            try:
                from brain.toolsmith import main as toolsmith_main
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    toolsmith_main()
                summary["toolsmith"] = buf.getvalue()[:1000]
            except Exception as e:
                summary["toolsmith"] = {"skipped": str(e)[:160]}
            # отчёт Стива владельцу
            report = (steve_plan or {}).get("report_to_owner")
            if report:
                try:
                    from telegram.notify import notify
                    notify(f"🧠 <b>Стив:</b>\n{report[:3500]}")
                except Exception:
                    pass
        else:
            summary["steve_strategy"] = {"skipped": "already_thought_today_or_budget"}
    except Exception as e:
        summary["steve_strategy"] = {"skipped": str(e)[:200]}

    # Стив сам пишет владельцу, если есть важный повод (с анти-спам кулдауном)
    try:
        from orchestrator.proactive import run as proactive_run
        summary["proactive"] = proactive_run(store=store)
    except Exception as e:
        summary["proactive"] = {"skipped": str(e)[:200]}

    return summary


if __name__ == "__main__":
    import json
    print(json.dumps(run_cycle(), ensure_ascii=False, indent=2))
