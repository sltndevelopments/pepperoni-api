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
OUTCOMES    = DATA / "outcomes.json"
METRIKA     = DATA / "metrika.json"
LEADS       = DATA / "leads.json"


def _load_inquiries_by_page() -> dict[str, int]:
    """Return {path: inquiries_28d} from metrika.json, normalised to /path form."""
    try:
        m = json.loads(METRIKA.read_text(encoding="utf-8"))
        raw = m.get("inquiries_by_page") or {}
        return {p.rstrip("/"): v.get("28d", 0) for p, v in raw.items()}
    except Exception:
        return {}


def _load_inquiries_by_experiment() -> dict[str, int]:
    try:
        data = json.loads(LEADS.read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        seen = set()
        for lead in data.get("leads", []):
            exp_id = lead.get("experiment_id")
            lead_id = (lead.get("chat_id"), lead.get("msg_id"))
            if not exp_id or lead_id in seen:
                continue
            seen.add(lead_id)
            counts[exp_id] = counts.get(exp_id, 0) + 1
        return counts
    except Exception:
        return {}

# All verdicts use one comparable 21-day window.
MATURE_DAYS = float(os.environ.get("OUTCOME_MATURE_DAYS", "21"))
# Position improvement (places) we consider a real win / real loss.
WIN_DELTA = float(os.environ.get("OUTCOME_WIN_DELTA", "3"))
# GSC window to read the "current" position from.
WINDOW_DAYS = int(os.environ.get("OUTCOME_WINDOW_DAYS", "7"))


def _load_experiments() -> list:
    rows = []
    try:
        d = json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
        rows.extend(d if isinstance(d, list) else d.get("experiments", []))
    except Exception:
        pass
    try:
        op = json.loads((DATA / "operator_experiments.json").read_text(encoding="utf-8"))
        if isinstance(op, dict):
            op = op.get("experiments", [])
        for row in op:
            if row.get("status") not in {"approved", "running", "measuring"}:
                continue
            baseline = row.get("baseline") or {}
            rows.append({
                "query": row.get("query"),
                "page": row.get("page"),
                "change_type": row.get("change_type"),
                "applied_at": row.get("started_at"),
                "before_pos": baseline.get("position"),
                "operator_experiment_id": row.get("id"),
            })
    except Exception:
        pass
    return rows


def _current_pos(conn, query: str, page: str) -> tuple[float | None, int]:
    """Weighted position for this exact query+page, never site-wide."""
    pages = [page]
    if page.startswith("/"):
        pages.extend([
            f"https://pepperoni.tatar{page}",
            f"https://pepperoni.tatar{page}/",
        ])
    placeholders = ",".join("?" for _ in pages)
    row = conn.execute(
        """SELECT SUM(position*impressions)*1.0/NULLIF(SUM(impressions),0) AS pos,
                  SUM(impressions) AS impr
           FROM gsc_queries
           WHERE query = ? AND page IN (""" + placeholders + """)
             AND date >= date('now','-'||?||' days')""",
        (query, *pages, WINDOW_DAYS),
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
    inq_by_page = _load_inquiries_by_page()
    inq_by_experiment = _load_inquiries_by_experiment()
    graded, failing = [], []
    counts = {"improved": 0, "flat": 0, "worse": 0, "not_indexed": 0,
              "pending": 0, "converted": 0}

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
        page = e.get("page") or ""
        cur, impr = _current_pos(conn, q, page)
        # Match page → Metrika path (GSC pages are full URLs; extract path).
        page_path = page
        if page_path.startswith("http"):
            from urllib.parse import urlparse
            page_path = urlparse(page_path).path
        exp_id = e.get("operator_experiment_id")
        inquiries = (
            inq_by_experiment.get(exp_id, 0)
            if exp_id else inq_by_page.get(page_path.rstrip("/"), 0)
        )

        item = {
            "query":       q,
            "page":        page,
            "change":      e.get("change_type"),
            "before_pos":  before,
            "current_pos": cur,
            "impr":        impr,
            "inquiries":   inquiries,   # 28d lead touches on this page
            "age_days":    round(age, 1),
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
                if inquiries > 0:
                    counts["converted"] += 1
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
        if e.get("operator_experiment_id"):
            try:
                from experiment_registry import finish
                mapped = {"improved": "win"}.get(item["verdict"], item["verdict"])
                finish(
                    e["operator_experiment_id"], mapped,
                    {"position": cur, "impressions": impr, "inquiries": inquiries},
                )
            except Exception as exc:
                print(f"⚠️ operator experiment finish failed: {exc}", file=sys.stderr)

    conn.close()
    # Worst first: not-indexed, then worst current position.
    failing.sort(key=lambda x: (x.get("verdict") != "not_indexed",
                                -(x.get("current_pos") or 999)))
    # Pages that are both ranking well AND generating inquiries.
    converting_by_key = {}
    for g in graded:
        if g.get("inquiries", 0) <= 0 or g.get("current_pos") is None:
            continue
        key = (g["page"], g["query"])
        converting_by_key[key] = {
            "page": g["page"], "query": g["query"],
            "pos": g["current_pos"], "inquiries": g["inquiries"],
        }
    converting_pages = list(converting_by_key.values())
    converting_pages.sort(key=lambda x: -x["inquiries"])

    out = {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "summary":         counts,
        "failing":         failing[:25],
        "graded_total":    len(graded),
        "converting_pages": converting_pages[:10],
    }
    OUTCOMES.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return out


def digest() -> dict:
    """Compact view for Fable's prompt — what worked, what is failing NOW."""
    try:
        d = json.loads(OUTCOMES.read_text(encoding="utf-8"))
    except Exception:
        return {"summary": {}, "failing": [], "converting_pages": []}
    return {
        "summary": d.get("summary", {}),
        "failing": [
            {"query": f["query"], "verdict": f["verdict"],
             "pos": f.get("current_pos"), "was": f.get("before_pos"),
             "inquiries": f.get("inquiries", 0),
             "age_days": f.get("age_days"), "page": f.get("page")}
            for f in d.get("failing", [])[:12]
        ],
        # Pages with real inquiries — reinforce these first.
        "converting_pages": d.get("converting_pages", [])[:5],
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
