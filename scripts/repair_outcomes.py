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
# Pages to actively strengthen (LLM title/meta rewrite) per run. Small = cheap,
# but it runs every 30 min, so misses get re-worked fast instead of waiting.
MAX_STRENGTHEN = int(os.environ.get("REPAIR_MAX_STRENGTHEN", "3"))


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

    # 3) Immediate content strengthening — rewrite snippets NOW, don't wait.
    strengthened = _strengthen_pages(not_indexed + need_optimise)

    return {"reindexed": reindexed, "strengthened": strengthened,
            "queued_for_fable": queued_fable,
            "missing_from_sitemap": missing_sitemap}


def main() -> int:
    r = repair()
    print(f"🔧 repair: reindexed {r['reindexed']} · "
          f"strengthened {r.get('strengthened', 0)} · "
          f"→fable {r['queued_for_fable']} · "
          f"missing_sitemap {len(r['missing_from_sitemap'])}")
    for u in r["missing_from_sitemap"]:
        print(f"   ⚠ not in sitemap: {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
