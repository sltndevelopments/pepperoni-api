#!/usr/bin/env python3
"""Lock npm test to the auto-discovering runner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_tests import (  # noqa: E402
    FIXED,
    ROOT,
    discover_mjs_tests,
    discover_py_tests,
    package_json_test_script,
)

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    script = package_json_test_script()
    check(script == "python3 scripts/run_tests.py",
          f"package.json test is the runner (got {script!r})")
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    check("test_" not in pkg["scripts"]["test"],
          "package.json test line lists no individual test_*.py")

    py_names = {p.name for p in discover_py_tests()}
    for name in (
        "test_sitemap_canonical.py",
        "test_case_pages.py",
        "test_seo_batch_rank.py",
        "test_landing_design.py",
        "test_run_tests.py",
    ):
        check(name in py_names, f"discovers {name}")
    check("ab_test_manager.py" not in py_names,
          "does not pick up ab_test_manager.py")
    check("run_tests.py" not in py_names, "does not treat run_tests.py as a test")

    mjs_names = {p.name for p in discover_mjs_tests()}
    check("test_sheet_public_text.mjs" in mjs_names,
          "discovers test_sheet_public_text.mjs")

    fixed_tails = [Path(cmd[1]).name for cmd in FIXED]
    for name in (
        "index_policy_check.py",
        "check_product_claims.py",
        "qa_changed_html.py",
        "check_strategy_retired_urls.py",
        "check_public_halal_language.py",
    ):
        check(name in fixed_tails, f"FIXED still runs {name}")
    check(all(not Path(cmd[1]).name.startswith("test_") for cmd in FIXED),
          "FIXED has no test_*.py (those are discovered)")

    if fail:
        print(f"test_run_tests: {fail} FAIL")
        return 1
    print("test_run_tests: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
