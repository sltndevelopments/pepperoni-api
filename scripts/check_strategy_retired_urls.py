#!/usr/bin/env python3
"""Fail if an active strategy rewrite target is already retired.

Read-only. The canonical registry is data/url_consolidation_map.json.
Statuses 410, 301, and noindex are not eligible for rewrite_pages.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
STRATEGY = ROOT / "data" / "strategy.json"
CONSOLIDATION = ROOT / "data" / "url_consolidation_map.json"
RETIRED_STATUSES = frozenset({"410", "301", "noindex"})


def normalize_url(value: str) -> str:
    raw = str(value).strip().split("?", 1)[0].split("#", 1)[0]
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme else raw
    if path.endswith(".html"):
        path = path[:-5]
    path = "/" + path.lstrip("/")
    return path.rstrip("/") or "/"


def retired_status_by_url(consolidation: dict) -> dict[str, str]:
    found: dict[str, str] = {}
    for entry in consolidation.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        status = entry.get("status")
        if not isinstance(url, str) or not isinstance(status, str):
            continue
        if status in RETIRED_STATUSES:
            found[normalize_url(url)] = status
    return found


def active_rewrite_pages(strategy: dict) -> list:
    proposals = strategy.get("engineering_proposals")
    if not isinstance(proposals, dict):
        return []
    pages = proposals.get("rewrite_pages")
    return pages if isinstance(pages, list) else []


def drop_retired_rewrite_pages(
    pages: list, retired: dict[str, str]
) -> tuple[list, list[tuple[str, str]]]:
    kept: list = []
    dropped: list[tuple[str, str]] = []
    for item in pages:
        path = item.get("path") if isinstance(item, dict) else None
        status = retired.get(normalize_url(path)) if isinstance(path, str) else None
        if status:
            dropped.append((path, status))
        else:
            kept.append(item)
    return kept, dropped


def retired_rewrite_hits(strategy: dict, consolidation: dict) -> list[tuple[str, str]]:
    return drop_retired_rewrite_pages(
        active_rewrite_pages(strategy),
        retired_status_by_url(consolidation),
    )[1]


def main() -> int:
    strategy = json.loads(STRATEGY.read_text(encoding="utf-8"))
    consolidation = json.loads(CONSOLIDATION.read_text(encoding="utf-8"))
    hits = retired_rewrite_hits(strategy, consolidation)
    if not hits:
        print("strategy retired rewrite targets: []")
        return 0
    print("FAIL: strategy contains retired rewrite targets:", file=sys.stderr)
    for path, status in hits:
        print(f"  {path} → {status}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
