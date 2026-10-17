#!/usr/bin/env python3
"""Regression: keep pages and core landings have ≥3 inbound keep links."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_inbound_links as inbound  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    entries = inbound.keep_entries()
    check(len(entries) == 250, f"allowlist keep is 250 (got {len(entries)})")
    graph = inbound.inbound_graph(entries)
    required = inbound.required_urls(entries)
    check(len(required) >= 250, "core landings are a subset of keep or extra keep URLs")
    for url in inbound.CORE_LANDINGS:
        path = inbound.norm_path(url)
        if path in inbound.keep_url_set(entries):
            check(path in required, f"core {path} is required")
    weak = inbound.orphans(graph, entries)
    check(not weak, "no keep/core URL has fewer than 3 inbound keep links")
    for url, count in weak:
        print(f"    orphan {url} inbound={count}")
    # Pack-weight style sanity: a known hub is well linked.
    check(len(graph.get("/halal", set())) >= 3, "/halal has ≥3 inbound")
    check(len(graph.get("/kazylyk", set())) >= 3, "/kazylyk has ≥3 inbound")
    if fail:
        print(f"test_inbound_links: {fail} FAIL")
        return 1
    print("test_inbound_links: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
