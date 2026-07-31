#!/usr/bin/env python3
"""Single outcome-oriented registry for new Site Brain work.

Legacy ``experiments.json`` remains readable for history, but all new operator
work is deduplicated and capped here.  An experiment is identified by
normalised ``query + canonical page`` and may be active only once.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REGISTRY = DATA / "operator_experiments.json"
ACTIVE = {"approved", "running", "measuring"}
FINAL = {"win", "worse", "flat", "not_indexed", "stopped", "reverted", "expired"}


def _load() -> list[dict]:
    try:
        rows = json.loads(REGISTRY.read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) else rows.get("experiments", [])
    except Exception:
        return []


def _save(rows: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".operator-experiments-", dir=DATA, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(name, REGISTRY)
    finally:
        Path(name).unlink(missing_ok=True)


def normalize_page(page: str) -> str:
    value = (page or "").strip()
    if value.startswith("http"):
        value = urlparse(value).path
    value = "/" + value.lstrip("/")
    return value.rstrip("/") or "/"


def key_for(query: str, page: str) -> str:
    return f"{(query or '').strip().casefold()}|{normalize_page(page)}"


def active() -> list[dict]:
    return [row for row in _load() if row.get("status") in ACTIVE]


def can_start(query: str, page: str, *, max_active: int = 3) -> tuple[bool, str]:
    key = key_for(query, page)
    norm_query = (query or "").strip().casefold()
    norm_page = normalize_page(page)
    rows = _load()
    for row in rows:
        if row.get("status") not in ACTIVE:
            continue
        if row.get("key") == key:
            return False, "duplicate active query+page"
        if str(row.get("query", "")).strip().casefold() == norm_query:
            return False, "query already has an active experiment"
        if normalize_page(str(row.get("page", ""))) == norm_page:
            return False, "page already has an active experiment"
    if sum(1 for row in rows if row.get("status") in ACTIVE) >= max_active:
        return False, f"active experiment limit {max_active}"
    failures = [
        row for row in rows
        if row.get("key") == key and row.get("status") in {"worse", "flat", "not_indexed"}
    ]
    if len(failures) >= 2:
        return False, "two failed hypotheses; owner decision required"
    return True, ""


def start(
    *,
    query: str,
    page: str,
    hypothesis: str,
    change_type: str,
    primary_metric: str = "qualified_inquiries",
    baseline: dict | None = None,
    cost_usd: float = 0.0,
) -> dict:
    ok, reason = can_start(query, page)
    if not ok:
        raise ValueError(reason)
    rows = _load()
    now = datetime.now(timezone.utc)
    row = {
        "id": f"exp-{now:%Y%m%d%H%M%S}-{len(rows)+1}",
        "key": key_for(query, page),
        "query": query.strip(),
        "page": normalize_page(page),
        "hypothesis": hypothesis.strip(),
        "change_type": change_type,
        "primary_metric": primary_metric,
        "baseline": baseline or {},
        "cost_usd": round(float(cost_usd), 4),
        "status": "measuring",
        "started_at": now.isoformat(),
        "measure_at": (now + timedelta(days=21)).replace(microsecond=0).isoformat(),
        "maturity_days": 21,
    }
    rows.append(row)
    _save(rows)
    return row


def finish(experiment_id: str, verdict: str, metrics: dict, *, note: str = "") -> dict:
    if verdict not in FINAL:
        raise ValueError(f"unsupported verdict: {verdict}")
    rows = _load()
    for row in rows:
        if row.get("id") != experiment_id:
            continue
        final_verdict = verdict
        if verdict == "worse" and str(row.get("change_type", "")).startswith("new_"):
            if _noindex_new_page(row.get("page", "")):
                final_verdict = "reverted"
                row["revert_action"] = "noindex,nofollow"
            else:
                row["revert_required"] = True
        row["status"] = final_verdict
        row["result"] = metrics
        row["finished_at"] = datetime.now(timezone.utc).isoformat()
        if note:
            row["note"] = note[:500]
        _save(rows)
        return row
    raise KeyError(experiment_id)


def _noindex_new_page(page: str) -> bool:
    rel = normalize_page(page).lstrip("/")
    candidates = [ROOT / "public" / f"{rel}.html", ROOT / "public" / rel / "index.html"]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return False
    html = path.read_text(encoding="utf-8")
    robots = '<meta name="robots" content="noindex,nofollow">'
    if re.search(r'<meta[^>]+name=["\']robots["\']', html, re.I):
        html = re.sub(
            r'<meta[^>]+name=["\']robots["\'][^>]*>',
            robots, html, count=1, flags=re.I,
        )
    elif "</head>" in html.lower():
        html = re.sub(r"</head>", f"  {robots}\n</head>", html, count=1, flags=re.I)
    else:
        return False
    path.write_text(html, encoding="utf-8")
    return True


def weekly_summary() -> dict:
    rows = _load()
    verdicts: dict[str, int] = {}
    for row in rows:
        status = row.get("status", "unknown")
        verdicts[status] = verdicts.get(status, 0) + 1
    return {
        "active": len([r for r in rows if r.get("status") in ACTIVE]),
        "verdicts": verdicts,
        "cost_usd": round(sum(float(r.get("cost_usd", 0)) for r in rows), 2),
        "next_actions": [
            {"query": r.get("query", ""), "page": r.get("page", ""),
             "measure_at": r.get("measure_at", "")[:10]}
            for r in rows if r.get("status") in ACTIVE
        ][:3],
    }


if __name__ == "__main__":
    print(json.dumps(weekly_summary(), ensure_ascii=False, indent=2))
