#!/usr/bin/env python3
"""Inject shared kd-landing chrome onto existing commercial pages.

Does not regenerate article text, schema or facts. Safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from landing_chrome import LANDINGS, apply_file  # noqa: E402


def main() -> int:
    changed = 0
    for rel, lang, slug in LANDINGS:
        if apply_file(rel, lang, slug):
            print(f"  updated {rel}")
            changed += 1
        else:
            print(f"  unchanged {rel}")
    print(f"landing chrome: {changed}/{len(LANDINGS)} files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
