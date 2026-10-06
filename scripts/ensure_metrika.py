#!/usr/bin/env python3
"""Insert the direct Metrika snippet into allowlisted pages that lack it.

Idempotent. Does not add a second ym(..., "init") and does not change
title, canonical, hreflang, or robots.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from index_safety import load_keep  # noqa: E402
from metrika_snippet import ensure_metrika_html, init_count  # noqa: E402

PUBLIC = ROOT / "public"


def main() -> int:
    if "--keep" not in sys.argv:
        print("usage: ensure_metrika.py --keep", file=sys.stderr)
        return 2
    changed = 0
    missing_before = 0
    doubles = 0
    absent = 0
    for rel in sorted(load_keep()):
        path = PUBLIC / rel
        if not path.is_file():
            absent += 1
            print(f"missing file: {rel}", file=sys.stderr)
            continue
        html = path.read_text(encoding="utf-8")
        if init_count(html) == 0:
            missing_before += 1
        updated = ensure_metrika_html(html)
        if init_count(updated) != 1:
            doubles += 1
            print(f"init count {init_count(updated)}: {rel}", file=sys.stderr)
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(
        f"ensure_metrika: changed={changed} "
        f"missing_before={missing_before} bad_init={doubles} absent={absent}"
    )
    return 1 if doubles or absent else 0


if __name__ == "__main__":
    sys.exit(main())
