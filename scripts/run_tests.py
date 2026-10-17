#!/usr/bin/env python3
"""npm test entrypoint.

Discovers every scripts/test_*.py (and matching test_*.mjs) so feature
PRs do not fight over the package.json test line. Gates that are not
named test_* stay in FIXED — they rarely change.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PY = sys.executable

# Not named test_*.py; keep these explicit. New regression tests go in
# scripts/test_*.py and are picked up automatically.
FIXED: list[list[str]] = [
    [PY, str(SCRIPTS / "index_policy_check.py")],
    [PY, str(SCRIPTS / "check_product_claims.py"), "--quiet"],
    [PY, str(SCRIPTS / "qa_changed_html.py")],
    [PY, str(SCRIPTS / "check_strategy_retired_urls.py")],
    [PY, str(SCRIPTS / "check_public_halal_language.py")],
]


def discover_py_tests() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("test_*.py") if p.is_file())


def discover_mjs_tests() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("test_*.mjs") if p.is_file())


def commands() -> list[list[str]]:
    cmds = [list(cmd) for cmd in FIXED]
    cmds.extend([PY, str(p)] for p in discover_py_tests())
    cmds.extend(["node", str(p)] for p in discover_mjs_tests())
    return cmds


def package_json_test_script() -> str:
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    return str(pkg["scripts"]["test"])


def main() -> int:
    for cmd in commands():
        shown = " ".join(Path(part).name if Path(part).suffix else part for part in cmd)
        print(f"\n==> {shown}")
        proc = subprocess.run(cmd, cwd=ROOT)
        if proc.returncode != 0:
            print(f"run_tests: FAIL {shown} (exit {proc.returncode})", file=sys.stderr)
            return proc.returncode
    print("\nrun_tests: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
