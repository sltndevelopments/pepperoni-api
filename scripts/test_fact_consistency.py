#!/usr/bin/env python3
"""Auto-discovered wrapper for scripts/check_fact_consistency.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_fact_consistency import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
