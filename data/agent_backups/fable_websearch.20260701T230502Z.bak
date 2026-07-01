#!/usr/bin/env python3
"""Fable Web Search — Fable's own eyes on the live internet.

Until now Fable was blind to the live web: it could reason but not look. It could
not check "are we cited by AI assistants for «халяль пепперони оптом»?" or "who
ranks for this query right now?" — a human had to bring the data. This tool gives
Fable that capability directly, the same idea Anthropic's Managed Agents bake in
as a built-in web tool, but on OUR infra with OUR Perplexity key (no vendor lock,
no 30-day server retention).

Built bulletproof:
  • Hard per-cycle cap (FABLE_WEB_MAX) so a runaway strategy can't burn budget.
  • Budget guard: refuses if the brain's monthly cap is already hit.
  • Per-query timeout + total wall-clock guard; one bad query never hangs a run.
  • Graceful no-key / failure degradation — returns a clear status, never raises.
  • Every call is cost-logged via the shared ledger (pplx_client._ledger).

Fable triggers it by emitting "web_queries" in its strategy (see seo_brain). The
results are written to data/fable_websearch.json and folded into the next digest
so Fable SEES what it found and acts on it (e.g. fix pages where AI ignores us).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = DATA / "fable_websearch.json"
sys.path.insert(0, str(ROOT / "scripts"))

# Hard limits — defence in depth.
MAX_QUERIES = int(os.environ.get("FABLE_WEB_MAX", "6"))        # per cycle
PER_QUERY_TIMEOUT = int(os.environ.get("FABLE_WEB_TIMEOUT", "45"))
TOTAL_WALL_S = int(os.environ.get("FABLE_WEB_WALL", "240"))    # whole run cap
KEEP_RUNS = int(os.environ.get("FABLE_WEB_KEEP", "20"))

# Brand-mention patterns (kept in sync with aio_visibility intent).
US_PATTERNS = [
    r"pepperoni\.tatar", r"казанские\s+деликатес", r"kazandelikates",
    r"kazan\s+delicac", r"пепперони\s+татар", r"217-02-02", r"\+?7\s*9?87\s*217",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mentions_us(text: str) -> bool:
    import re
    t = (text or "").lower()
    return any(re.search(p, t, re.I) for p in US_PATTERNS)


def _budget_ok() -> bool:
    """Don't search if the brain's monthly budget is already exhausted."""
    try:
        from opus_brain_client import brain_available
        return bool(brain_available())
    except Exception:
        return True  # never block solely on a budget-probe failure


def _search_one(query: str, mode: str) -> dict:
    """One grounded web answer. mode: 'visibility' adds a buyer-intent framing."""
    from pplx_client import pplx_search
    system = ("Отвечай по актуальным данным из интернета, называй конкретные "
              "компании, бренды и сайты-источники.")
    prompt = query
    if mode == "visibility":
        prompt = (f"{query}\nНазови конкретных производителей/поставщиков "
                  f"и их сайты.")
    text, citations = pplx_search(prompt, system=system,
                                  timeout=PER_QUERY_TIMEOUT)
    cites = []
    for c in (citations or [])[:8]:
        if isinstance(c, str):
            cites.append(c)
        elif isinstance(c, dict):
            cites.append(c.get("url") or c.get("title") or "")
    return {
        "query": query, "mode": mode,
        "cited_us": _mentions_us(text),
        "answer": text[:1200],
        "citations": [c for c in cites if c],
        "at": _now(),
    }


def search(queries: list, mode: str = "search") -> dict:
    """Run a capped batch of live web searches. Never raises — returns a report."""
    if not os.environ.get("PPLX_API_KEY", "").strip():
        return {"status": "no_key", "results": [], "ran": 0,
                "note": "PPLX_API_KEY not set — web search unavailable"}
    if not _budget_ok():
        return {"status": "budget_exhausted", "results": [], "ran": 0,
                "note": "brain monthly budget reached — skipping web search"}

    queries = [q.strip() for q in (queries or []) if q and q.strip()][:MAX_QUERIES]
    if not queries:
        return {"status": "empty", "results": [], "ran": 0}

    started = time.time()
    results, errors = [], 0
    for q in queries:
        if time.time() - started > TOTAL_WALL_S:
            break
        try:
            results.append(_search_one(q, mode))
        except Exception as e:
            errors += 1
            results.append({"query": q, "mode": mode, "cited_us": False,
                            "answer": "", "citations": [],
                            "error": str(e)[:160], "at": _now()})

    cited = sum(1 for r in results if r.get("cited_us"))
    report = {
        "status": "ok",
        "generated_at": _now(),
        "ran": len(results),
        "errors": errors,
        "cited_us_count": cited,
        "results": results,
    }
    _persist(report)
    return report


def _persist(report: dict) -> None:
    try:
        hist = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else []
        if not isinstance(hist, list):
            hist = []
    except Exception:
        hist = []
    hist.append(report)
    hist = hist[-KEEP_RUNS:]
    DATA.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(hist, ensure_ascii=False, indent=1),
                       encoding="utf-8")


def digest() -> dict:
    """Compact view of the latest web-search run for Fable's prompt."""
    try:
        hist = json.loads(RESULTS.read_text(encoding="utf-8"))
        last = hist[-1] if hist else {}
    except Exception:
        return {"ran": 0, "cited_us_count": 0, "findings": []}
    return {
        "ran": last.get("ran", 0),
        "cited_us_count": last.get("cited_us_count", 0),
        "at": last.get("generated_at"),
        "findings": [
            {"query": r["query"], "cited_us": r.get("cited_us"),
             "answer": (r.get("answer") or "")[:240],
             "sources": r.get("citations", [])[:3]}
            for r in last.get("results", [])[:10]
        ],
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Fable's live web search / AI-visibility probe")
    ap.add_argument("--query", action="append", default=[], help="query (repeatable)")
    ap.add_argument("--mode", default="search", choices=["search", "visibility"])
    args = ap.parse_args()
    qs = args.query or [
        "Где купить халяльную пепперони оптом в России? Назови производителей.",
    ]
    rep = search(qs, mode=args.mode)
    print(f"🔎 fable_websearch: status={rep['status']} ran={rep.get('ran',0)} "
          f"cited_us={rep.get('cited_us_count',0)} errors={rep.get('errors',0)}")
    for r in rep.get("results", []):
        mark = "✅ нас цитируют" if r.get("cited_us") else "❌ нас НЕТ"
        print(f"  [{mark}] «{r['query'][:50]}»"
              + (f"  ⚠{r['error']}" if r.get("error") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
