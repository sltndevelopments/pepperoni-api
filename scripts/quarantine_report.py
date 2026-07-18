#!/usr/bin/env python3
"""Truthful quarantine inventory and conservative cleanup.

Separates current files from historical gate events and unique rejected paths.
Only ``tmp*.html`` artifacts may be deleted automatically; named pages always
require demand/SEO review.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUARANTINE = DATA / "quarantine"
GATE_LOG = DATA / "page_gate_log.json"
REPORT = DATA / "quarantine_report.json"


def classify_reason(reason: str) -> str:
    text = reason.casefold()
    if any(w in text for w in ("свинин", "pork", "خنز", "халяль", "halal", "сертифик")):
        return "halal_brand"
    if any(w in text for w in ("обрез", "</html>", "incomplete", "невалид")):
        return "truncated_html"
    if any(w in text for w in ("тонк", "слов", "duplicate", "дубл")):
        return "thin_duplicate"
    if any(w in text for w in ("unavailable", "timeout", "non-json", "held")):
        return "temporary_hold"
    return "technical_other"


def build_report() -> dict:
    files = sorted(p for p in QUARANTINE.rglob("*.html") if p.is_file())
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8"))
    except Exception:
        log = []
    rejected = [row for row in log if row.get("verdict") in {"reject", "hold"}]
    latest_by_name = {}
    for row in rejected:
        latest_by_name[Path(str(row.get("path", ""))).name] = row
    reasons = Counter()
    for row in rejected:
        row_reasons = row.get("reasons") or [row.get("error", "")]
        for reason in row_reasons:
            reasons[classify_reason(str(reason))] += 1
    return {
        "current_files": len(files),
        "temporary_files": len([p for p in files if p.name.startswith("tmp")]),
        "named_page_count": len([p for p in files if not p.name.startswith("tmp")]),
        "historical_gate_events": len(log),
        "historical_reject_hold_events": len(rejected),
        "unique_rejected_paths": len({row.get("path") for row in rejected if row.get("path")}),
        "reason_events": dict(reasons),
        "named_pages": [
            {
                "path": str(p.relative_to(QUARANTINE)),
                "category": classify_reason("; ".join(
                    latest_by_name.get(p.name, {}).get("reasons") or
                    [latest_by_name.get(p.name, {}).get("error", "")]
                )),
                "disposition": "kept_closed_pending_demand_evidence",
            }
            for p in files if not p.name.startswith("tmp")
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-temp", action="store_true")
    args = ap.parse_args()
    before = build_report()
    removed = 0
    if args.clean_temp:
        for path in QUARANTINE.rglob("tmp*.html"):
            if path.is_file():
                path.unlink()
                removed += 1
    report = build_report()
    report["temporary_files_removed"] = removed
    report["before_cleanup"] = before
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
