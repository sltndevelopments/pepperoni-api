#!/usr/bin/env python3
"""Repair Outcomes — deterministic first-aid for changes that did not work.

Pairs with outcome_tracker.py: the tracker DIAGNOSES misses, this agent applies
the cheap, non-LLM fixes immediately so Fable's LLM budget is spent only on the
hard cases. Closes the "build → check → fix" loop with action, not reports.

Fixes applied here:
  • not_indexed → resubmit the URL to Yandex (recrawl) + ensure it's in sitemap.
  • worse/flat-with-demand → post a task on the agent bus for Fable to re-optimise
    the EXISTING page (never build a new one on top — playbook rule).

Anti-cycle guard (fix_attempts):
  • Each failing verdict increments the attempt counter for that query.
  • After MAX_FIX_ATTEMPTS consecutive failures the query is marked abandoned.
  • Abandoned queries are NOT re-queued; a needs_help escalation is sent instead.
  • Improved verdicts reset the counter (Trigger A also runs for abandoned entries).

Reads data/outcomes.json (produced by outcome_tracker). Safe to run every cycle.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

OUTCOMES = DATA / "outcomes.json"
SITEMAP = ROOT / "public" / "sitemap.xml"

# Daily ceiling so we never blow the Yandex recrawl quota in one run.
MAX_REINDEX = int(os.environ.get("REPAIR_MAX_REINDEX", "10"))
# Pages to actively strengthen (LLM title/meta rewrite) per run. Small = cheap,
# but it runs every 30 min, so misses get re-worked fast instead of waiting.
MAX_STRENGTHEN = int(os.environ.get("REPAIR_MAX_STRENGTHEN", "3"))


def _load_outcomes() -> dict:
    try:
        return json.loads(OUTCOMES.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_failing() -> list:
    return _load_outcomes().get("failing", [])


def _load_improved() -> list:
    return _load_outcomes().get("graded", [])


def _load_hyphenated(name: str, filename: str):
    """Import a script whose filename has a hyphen (importlib by path)."""
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _indexnow(urls: list) -> int:
    """Fast, unlimited, multi-engine ping (Bing/Yandex/Seznam/Naver). No quota."""
    if not urls:
        return 0
    try:
        bi = _load_hyphenated("bing_index", "bing-index.py")
        res = bi.submit_batch(urls, "https://api.indexnow.org/indexnow")
        return len(urls) if str(res).startswith("✅") else 0
    except Exception as e:
        print(f"⚠️  indexnow failed: {e}")
        return 0


def _strengthen_pages(failing: list) -> int:
    """Immediately rewrite title/meta of failing pages (don't wait for a crawl).

    A weak/not-indexed page won't fix itself by re-pinging — its snippet must
    actually match the query intent. Reuse the optimizer's safe rewrite (backup,
    HTML validation, experiment logging) so the next outcome cycle re-grades it.
    """
    if not failing:
        return 0
    try:
        opt = _load_hyphenated("optimize_seo", "optimize_seo.py")
        from seo_db import get_conn
        from datetime import datetime, timezone
        import json as _json
    except Exception as e:
        print(f"⚠️  strengthen unavailable: {e}")
        return 0

    conn = get_conn()
    ledger_path = DATA / "experiments.json"
    try:
        ledger = _json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        ledger = []
    done = 0
    for f in failing:
        if done >= MAX_STRENGTHEN:
            break
        page, query = f.get("page"), (f.get("query") or "").strip()
        if not page or not query:
            continue
        path = opt.url_to_path(page)
        if not path or not path.exists():
            continue
        lang = "en" if "/en/" in page else "ru"
        cur_title, cur_desc = opt.get_title(path), opt.get_description(path)
        pos = f.get("pos") or f.get("current_pos") or 50.0
        new = opt.rewrite_title_meta(query, cur_title, cur_desc, float(pos), lang)
        if not new or new.get("title") == cur_title:
            continue
        opt.set_title_meta_h1(path, new["title"], new["description"])
        if not opt.is_valid_html(path):
            opt.set_title_meta_h1(path, cur_title, cur_desc)  # revert
            continue
        ledger.append({
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "change_type": "strengthen_failing",
            "page": page, "file_path": str(path.relative_to(ROOT)),
            "query": query, "before_pos": float(pos),
            "before_title": cur_title, "before_desc": cur_desc,
        })
        done += 1
    if done:
        ledger_path.write_text(_json.dumps(ledger, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    conn.close()
    return done


def _in_sitemap(url: str) -> bool:
    try:
        return url in SITEMAP.read_text(encoding="utf-8")
    except Exception:
        return True  # don't block on a missing sitemap


def repair() -> dict:
    import fix_attempts as fa

    failing = _load_failing()
    reindexed, queued_fable, missing_sitemap = 0, 0, []
    abandoned_skipped = 0

    not_indexed = [f for f in failing if f.get("verdict") == "not_indexed" and f.get("page")]
    need_optimise = [f for f in failing if f.get("verdict") in ("worse", "flat") and f.get("page")]

    # Anti-cycle: reset counters for any queries that improved this cycle.
    for item in _load_improved():
        q = (item.get("query") or "").strip()
        verdict = item.get("verdict", "")
        if verdict == "improved" and q:
            # Trigger A: also fires automatically inside fix_attempts.check_trigger_a
            # but we reset explicitly here for improved verdicts.
            fa.reset(q, reason="outcome improved (Trigger A)")

    # 1) Fast path: IndexNow — instant, unlimited, notifies Bing+Yandex+Seznam.
    #    Anti-cycle: skip abandoned queries; increment counters for failing ones.
    urls = []
    for f in not_indexed:
        q = (f.get("query") or "").strip()
        u = f.get("page")
        # Trigger A: check if a new experiment unblocks an abandoned entry.
        if q:
            fa.check_trigger_a(q)
        if q and fa.is_abandoned(q):
            print(f"  ⏭  skipping abandoned query: «{q}»")
            abandoned_skipped += 1
            continue
        if u:
            urls.append(u)
            if not _in_sitemap(u):
                missing_sitemap.append(u)
        if q:
            fa.increment(q, verdict="not_indexed")
    reindexed = _indexnow(urls)

    # 2) Bonus path: Yandex recrawl when its small monthly quota still has room.
    token = os.environ.get("YANDEX_WM_TOKEN")
    if token and urls:
        try:
            yi = _load_hyphenated("yandex_index", "yandex-index.py")
            for u in urls[:MAX_REINDEX]:
                if yi.submit_url(token, u) == "⛔ QUOTA_EXCEEDED":
                    break
        except Exception as e:
            print(f"⚠️  yandex recrawl skipped: {e}")

    # 3) Hand the hard cases (need content/intent work) to Fable via the bus —
    #    re-optimise the EXISTING page, deduped so we don't pile up tasks.
    #    Anti-cycle: abandoned queries are NOT re-queued; emit needs_help instead.
    try:
        import agent_bus
        for f in (not_indexed + need_optimise)[:15]:
            q = (f.get("query") or "").strip()
            if not q:
                continue
            fa.check_trigger_a(q)
            if fa.is_abandoned(q):
                # Already emitted needs_help on the cycle it was abandoned.
                abandoned_skipped += 1
                continue
            fa.increment(q, verdict=f.get("verdict", ""))
            agent_bus.post(
                frm="outcome_tracker", to="fable", type_="fix_failing_page",
                payload={"query": q, "page": f.get("page"),
                         "verdict": f.get("verdict"), "current_pos": f.get("pos"),
                         "was": f.get("was")},
                trigger="outcome.failing",
                note=f"НЕ сработало: «{q}» — {f.get('verdict')} "
                     f"(поз {f.get('was')}→{f.get('pos')}). Чинить существующую страницу.",
                dedup_key=f"failing:{q.lower().strip()}")
            queued_fable += 1
    except Exception as e:
        print(f"⚠️  bus handoff failed: {e}")

    # 4) Immediate content strengthening — rewrite snippets NOW, don't wait.
    #    Skip abandoned queries.
    eligible = [f for f in (not_indexed + need_optimise)
                if not fa.is_abandoned((f.get("query") or "").strip())]
    strengthened = _strengthen_pages(eligible)

    return {"reindexed": reindexed, "strengthened": strengthened,
            "queued_for_fable": queued_fable,
            "missing_from_sitemap": missing_sitemap,
            "abandoned_skipped": abandoned_skipped}


def main() -> int:
    r = repair()
    print(f"🔧 repair: reindexed {r['reindexed']} · "
          f"strengthened {r.get('strengthened', 0)} · "
          f"→fable {r['queued_for_fable']} · "
          f"abandoned_skipped {r.get('abandoned_skipped', 0)} · "
          f"missing_sitemap {len(r['missing_from_sitemap'])}")
    for u in r["missing_from_sitemap"]:
        print(f"   ⚠ not in sitemap: {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
