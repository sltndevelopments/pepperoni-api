#!/usr/bin/env python3
"""Repair Outcomes — deterministic first-aid for changes that did not work.

Pairs with outcome_tracker.py: the tracker DIAGNOSES misses, this agent applies
the cheap, non-LLM fixes immediately so Fable's LLM budget is spent only on the
hard cases. Closes the "build → check → fix" loop with action, not reports.

Fixes applied here:
  • not_indexed → resubmit the URL to Yandex (recrawl) + ensure it's in sitemap.
  • worse/flat-with-demand → post a task on the agent bus for Fable to re-optimise
    the EXISTING page (never build a new one on top — playbook rule).

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


def _load_failing() -> list:
    try:
        return json.loads(OUTCOMES.read_text(encoding="utf-8")).get("failing", [])
    except Exception:
        return []


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


def _in_sitemap(url: str) -> bool:
    try:
        return url in SITEMAP.read_text(encoding="utf-8")
    except Exception:
        return True  # don't block on a missing sitemap


def repair() -> dict:
    failing = _load_failing()
    reindexed, queued_fable, missing_sitemap = 0, 0, []

    not_indexed = [f for f in failing if f.get("verdict") == "not_indexed" and f.get("page")]
    need_optimise = [f for f in failing if f.get("verdict") in ("worse", "flat") and f.get("page")]

    # 1) Fast path: IndexNow — instant, unlimited, notifies Bing+Yandex+Seznam.
    #    This is the primary reindex channel (no daily quota, crawls within hours).
    urls = []
    for f in not_indexed:
        u = f.get("page")
        if u:
            urls.append(u)
            if not _in_sitemap(u):
                missing_sitemap.append(u)
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

    # 2) Hand the hard cases (need content/intent work) to Fable via the bus —
    #    re-optimise the EXISTING page, deduped so we don't pile up tasks.
    try:
        import agent_bus
        for f in (not_indexed + need_optimise)[:15]:
            agent_bus.post(
                frm="outcome_tracker", to="fable", type_="fix_failing_page",
                payload={"query": f["query"], "page": f.get("page"),
                         "verdict": f.get("verdict"), "current_pos": f.get("pos"),
                         "was": f.get("was")},
                trigger="outcome.failing",
                note=f"НЕ сработало: «{f['query']}» — {f.get('verdict')} "
                     f"(поз {f.get('was')}→{f.get('pos')}). Чинить существующую страницу.",
                dedup_key=f"failing:{f['query'].lower().strip()}")
            queued_fable += 1
    except Exception as e:
        print(f"⚠️  bus handoff failed: {e}")

    return {"reindexed": reindexed, "queued_for_fable": queued_fable,
            "missing_from_sitemap": missing_sitemap}


def main() -> int:
    r = repair()
    print(f"🔧 repair: reindexed {r['reindexed']} · "
          f"→fable {r['queued_for_fable']} · "
          f"missing_sitemap {len(r['missing_from_sitemap'])}")
    for u in r["missing_from_sitemap"]:
        print(f"   ⚠ not in sitemap: {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
