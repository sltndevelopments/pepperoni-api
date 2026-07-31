#!/usr/bin/env python3
"""Truthful quarantine inventory and conservative cleanup.

Separates:
  - current_files — HTML sitting in data/quarantine/ right now
  - historical_reject_hold_events — gate log reject/hold rows over time
  - unique_rejected_paths — distinct paths ever rejected

Auto-delete is limited to:
  - temporary ``tmp*.html`` artifacts
  - named pages that already have a published twin under ``public/``
    (proven duplicates — not a publish queue)

Everything else stays out of the index with an explicit disposition.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
QUARANTINE = DATA / "quarantine"
GATE_LOG = DATA / "page_gate_log.json"
REPORT = DATA / "quarantine_report.json"
OPERATOR_STATE = DATA / "operator_state.json"
# Runtime-only — survives git reset --hard on the VPS.
BASELINE_FILE = DATA / "quarantine_baseline.json"


def classify_reason(reason: str) -> str:
    text = reason.casefold()
    if any(w in text for w in ("свинин", "pork", "خنز", "халяль", "halal", "сертифик", "brand")):
        return "halal_brand"
    if any(w in text for w in ("обрез", "</html>", "incomplete", "невалид", "truncated")):
        return "truncated_html"
    if any(w in text for w in ("тонк", "слов", "duplicate", "дубл", "thin")):
        return "thin_duplicate"
    if any(w in text for w in ("unavailable", "timeout", "non-json", "held", "budget")):
        return "temporary_hold"
    return "technical_other"


def _gate_latest_by_name() -> dict[str, dict]:
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}
    latest: dict[str, dict] = {}
    for row in log:
        if row.get("verdict") not in {"reject", "hold"}:
            continue
        name = Path(str(row.get("path", ""))).name
        if name:
            latest[name] = row
    return latest


def _published_twins() -> dict[str, str]:
    """Map basename → first published relative path under public/."""
    twins: dict[str, str] = {}
    if not PUBLIC.exists():
        return twins
    for path in PUBLIC.rglob("*.html"):
        if "_quarantine" in path.parts or path.name.startswith("_removed_"):
            continue
        twins.setdefault(path.name, str(path.relative_to(ROOT)))
    return twins


def _content_category(path: Path, gate_row: dict | None) -> str:
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        html = ""
    if html and "</html>" not in html.casefold():
        return "truncated_html"
    if path.stat().st_size < 1500:
        return "thin_duplicate"
    reasons = []
    if gate_row:
        reasons = gate_row.get("reasons") or [gate_row.get("error", "")]
    if reasons:
        return classify_reason("; ".join(str(r) for r in reasons))
    return "technical_other"


def build_report() -> dict:
    files = sorted(p for p in QUARANTINE.rglob("*.html") if p.is_file())
    try:
        log = json.loads(GATE_LOG.read_text(encoding="utf-8"))
    except Exception:
        log = []
    rejected = [row for row in log if row.get("verdict") in {"reject", "hold"}]
    latest_by_name = _gate_latest_by_name()
    twins = _published_twins()

    reason_events = Counter()
    for row in rejected:
        row_reasons = row.get("reasons") or [row.get("error", "")]
        for reason in row_reasons:
            reason_events[classify_reason(str(reason))] += 1

    categories = Counter()
    named_pages = []
    duplicate_count = 0
    for path in files:
        if path.name.startswith("tmp"):
            continue
        gate_row = latest_by_name.get(path.name)
        category = _content_category(path, gate_row)
        published = twins.get(path.name)
        if published:
            duplicate_count += 1
            disposition = "duplicate_of_published"
        else:
            disposition = "kept_closed_pending_demand_evidence"
        categories[category] += 1
        named_pages.append({
            "path": str(path.relative_to(QUARANTINE)),
            "category": category,
            "disposition": disposition,
            "published_twin": published,
            "bytes": path.stat().st_size,
        })

    return {
        "current_files": len(files),
        "temporary_files": len([p for p in files if p.name.startswith("tmp")]),
        "named_page_count": len([p for p in files if not p.name.startswith("tmp")]),
        "published_duplicates": duplicate_count,
        "kept_closed": len(named_pages) - duplicate_count,
        "historical_gate_events": len(log),
        "historical_reject_hold_events": len(rejected),
        "unique_rejected_paths": len({row.get("path") for row in rejected if row.get("path")}),
        "reason_events": dict(reason_events),
        "current_categories": dict(categories),
        "named_pages": named_pages,
        "counters_note": (
            "current_files = files on disk now; "
            "historical_reject_hold_events = cumulative gate rejects/holds; "
            "do not show historical as the live quarantine queue"
        ),
    }


def clean_temp() -> int:
    removed = 0
    if not QUARANTINE.exists():
        return 0
    for path in QUARANTINE.rglob("tmp*.html"):
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def clean_published_duplicates() -> list[str]:
    """Remove quarantine HTML that already exists under public/."""
    removed: list[str] = []
    twins = _published_twins()
    if not QUARANTINE.exists():
        return removed
    for path in list(QUARANTINE.rglob("*.html")):
        if not path.is_file() or path.name.startswith("tmp"):
            continue
        if path.name in twins:
            rel = str(path.relative_to(QUARANTINE))
            path.unlink()
            removed.append(rel)
    return removed


def read_baseline() -> int | None:
    try:
        raw = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        return int(raw["quarantine_baseline"])
    except Exception:
        try:
            state = json.loads(OPERATOR_STATE.read_text(encoding="utf-8"))
            value = state.get("quarantine_baseline")
            return int(value) if value is not None else None
        except Exception:
            return None


def sync_baseline(current_files: int, *, force: bool = False) -> dict:
    """Persist baseline used by activation growth checks.

    First successful sync (or ``force``) writes the number. Later cleanups do
    **not** silently raise the baseline — otherwise growth can never block
    operator activation. Stored in a runtime file so VPS ``git reset --hard``
    does not wipe the watermark.
    """
    previous = read_baseline()
    if previous is not None and not force:
        return {"wrote": False, "baseline": previous, "previous": previous,
                "current": current_files}
    payload = {
        "quarantine_baseline": current_files,
        "synced_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BASELINE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(BASELINE_FILE)
    return {"wrote": True, "baseline": current_files, "previous": previous}


def summary_line(report: dict) -> str:
    return (
        f"карантин сейчас {report['current_files']} "
        f"(дубли опубликованы {report.get('published_duplicates', 0)}, "
        f"закрыто {report.get('kept_closed', 0)}); "
        f"reject за период {report['historical_reject_hold_events']}; "
        f"уник. путей {report['unique_rejected_paths']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-temp", action="store_true")
    ap.add_argument(
        "--clean-duplicates",
        action="store_true",
        help="Delete quarantine files that already have a public/ twin",
    )
    ap.add_argument(
        "--sync-baseline",
        action="store_true",
        help="Write current_files into data/quarantine_baseline.json (first time only)",
    )
    ap.add_argument(
        "--force-baseline",
        action="store_true",
        help="Overwrite quarantine baseline even if one already exists",
    )
    args = ap.parse_args()

    before = build_report()
    removed_temp = clean_temp() if args.clean_temp else 0
    removed_dupes = clean_published_duplicates() if args.clean_duplicates else []
    report = build_report()
    report["temporary_files_removed"] = removed_temp
    report["duplicates_removed"] = len(removed_dupes)
    report["duplicates_removed_paths"] = removed_dupes[:50]
    report["before_cleanup"] = {
        "current_files": before["current_files"],
        "published_duplicates": before["published_duplicates"],
        "temporary_files": before["temporary_files"],
    }
    if args.sync_baseline or args.force_baseline:
        sync_info = sync_baseline(
            report["current_files"], force=bool(args.force_baseline)
        )
        report["baseline_sync"] = sync_info
        report["quarantine_baseline"] = sync_info["baseline"]
    else:
        report["quarantine_baseline"] = read_baseline()
    report["summary"] = summary_line(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    printable = {k: v for k, v in report.items() if k != "named_pages"}
    printable["named_pages_sample"] = report["named_pages"][:8]
    printable["named_pages_total"] = len(report["named_pages"])
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
