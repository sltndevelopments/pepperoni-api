#!/usr/bin/env python3
"""Outcome Tracker — closes the accountability loop on every SEO action.

The problem this fixes: agents reported "✅ landing built / title rewritten" and
moved on, with NOBODY checking whether it actually moved the needle. A landing
for «пепперони халяль» sat at position 42 for a week while the digest kept saying
"built ✅". Reporting effort instead of results = blind, slow, easy to overtake.

This agent grades each change against reality:
  applied a change → wait MATURE_DAYS → pull current GSC position for its query
  → verdict: improved | flat | worse | not_indexed.
Failures are written to data/outcomes.json and surfaced to Fable's digest so it
is FORCED to see its own misses and act (re-optimise, push indexing, or kill the
page) instead of re-reporting success.

Reads:  data/experiments.json (change ledger), GSC via seo_db.
Writes: data/outcomes.json  {summary, failing[], graded[]}
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

from seo_db import get_conn  # noqa: E402

EXPERIMENTS = DATA / "experiments.json"
OUTCOMES = DATA / "outcomes.json"

# A change needs time to be re-crawled & re-ranked before we judge it.
MATURE_DAYS = float(os.environ.get("OUTCOME_MATURE_DAYS", "5"))
# Position improvement (places) we consider a real win / real loss.
WIN_DELTA = float(os.environ.get("OUTCOME_WIN_DELTA", "3"))
# GSC window to read the "current" position from.
WINDOW_DAYS = int(os.environ.get("OUTCOME_WINDOW_DAYS", "7"))


def _load_experiments() -> list:
    try:
        d = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else d.get("experiments", [])
    except Exception:
        return []


def _current_pos(conn, query: str) -> tuple[float | None, int]:
    """(weighted avg position, impressions) for a query in the recent window."""
    row = conn.execute(
        """SELECT SUM(position*impressions)*1.0/NULLIF(SUM(impressions),0) AS pos,
                  SUM(impressions) AS impr
           FROM gsc_queries
           WHERE query = ? AND date >= date('now','-'||?||' days')""",
        (query, WINDOW_DAYS),
    ).fetchone()
    if not row or row[0] is None:
        return None, 0
    return round(float(row[0]), 1), int(row[1] or 0)


def _age_days(iso: str) -> float:
    try:
        return (datetime.now(timezone.utc)
                - datetime.fromisoformat(iso)).total_seconds() / 86400
    except Exception:
        return 0.0


def grade() -> dict:
    conn = get_conn()
    graded, failing = [], []
    counts = {"improved": 0, "flat": 0, "worse": 0, "not_indexed": 0, "pending": 0}

    for e in _load_experiments():
        q = (e.get("query") or "").strip()
        applied = e.get("applied_at") or ""
        if not q or not applied:
            continue
        age = _age_days(applied)
        if age < MATURE_DAYS:
            counts["pending"] += 1
            continue

        before = e.get("before_pos")
        cur, impr = _current_pos(conn, q)
        item = {
            "query": q, "page": e.get("page"), "change": e.get("change_type"),
            "before_pos": before, "current_pos": cur, "impr": impr,
            "age_days": round(age, 1),
        }
        if cur is None or impr == 0:
            item["verdict"] = "not_indexed"
            counts["not_indexed"] += 1
            failing.append(item)
        elif before is None:
            item["verdict"] = "flat"
            counts["flat"] += 1
        else:
            delta = before - cur  # positive = moved UP (better rank)
            item["delta"] = round(delta, 1)
            if delta >= WIN_DELTA:
                item["verdict"] = "improved"
                counts["improved"] += 1
            elif delta <= -WIN_DELTA:
                item["verdict"] = "worse"
                counts["worse"] += 1
                failing.append(item)
            else:
                item["verdict"] = "flat"
                counts["flat"] += 1
                # Flat AND still on page 4+ with real demand = a miss worth fixing.
                if cur >= 20 and impr >= 20:
                    failing.append(item)
        graded.append(item)

    conn.close()
    # Worst first: not-indexed, then worst current position.
    failing.sort(key=lambda x: (x.get("verdict") != "not_indexed",
                                -(x.get("current_pos") or 999)))
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": counts,
        "failing": failing[:25],
        "graded_total": len(graded),
    }
    OUTCOMES.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return out


def digest() -> dict:
    """Compact view for Fable's prompt — what worked, what is failing NOW."""
    try:
        d = json.loads(OUTCOMES.read_text(encoding="utf-8"))
    except Exception:
        return {"summary": {}, "failing": []}
    return {
        "summary": d.get("summary", {}),
        "failing": [
            {"query": f["query"], "verdict": f["verdict"],
             "pos": f.get("current_pos"), "was": f.get("before_pos"),
             "age_days": f.get("age_days"), "page": f.get("page")}
            for f in d.get("failing", [])[:12]
        ],
    }


def main() -> int:
    out = grade()
    s = out["summary"]
    print(f"📊 Outcomes: ✅improved {s['improved']} · ⏸flat {s['flat']} · "
          f"❌worse {s['worse']} · 🚫not_indexed {s['not_indexed']} · "
          f"⏳pending {s['pending']}")
    for f in out["failing"][:10]:
        print(f"  {f['verdict']:11s} «{f['query'][:32]:32}» "
              f"was {f.get('before_pos')} → now {f.get('current_pos')} "
              f"(impr {f.get('impr')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
