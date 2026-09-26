#!/usr/bin/env python3
"""Run qa_pages.py on public HTML changed since merge-base with main.

Read-only. Does not call fix_hreflang.py and does not pass --all.
On a clean checkout git status is empty, so this uses the branch diff
instead. Works locally and in GitHub Actions when the base ref is fetched.

Base ref, first match that resolves:
  QA_BASE_REF
  origin/$GITHUB_BASE_REF
  origin/main
  main
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _resolve_base() -> str | None:
    candidates: list[str] = []
    if os.environ.get("QA_BASE_REF"):
        candidates.append(os.environ["QA_BASE_REF"])
    if os.environ.get("GITHUB_BASE_REF"):
        candidates.append(f"origin/{os.environ['GITHUB_BASE_REF']}")
    candidates.extend(("origin/main", "main"))
    for ref in candidates:
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=ROOT, capture_output=True, text=True,
        )
        if probe.returncode == 0:
            return ref
    return None


def changed_html(base: str) -> list[str]:
    mb = subprocess.run(
        ["git", "merge-base", "HEAD", base],
        cwd=ROOT, capture_output=True, text=True,
    )
    if mb.returncode != 0:
        raise SystemExit(
            f"qa_changed_html: merge-base HEAD {base} failed: {mb.stderr.strip()}"
        )
    merge_base = mb.stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", merge_base, "--", "public"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if diff.returncode != 0:
        raise SystemExit(f"qa_changed_html: git diff failed: {diff.stderr.strip()}")
    others = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "public"],
        cwd=ROOT, capture_output=True, text=True,
    )
    names = diff.stdout.splitlines() + others.stdout.splitlines()
    files: list[str] = []
    seen: set[str] = set()
    for line in names:
        rel = line.strip()
        if not rel.startswith("public/") or not rel.endswith(".html"):
            continue
        if rel in seen:
            continue
        if (ROOT / rel).is_file():
            seen.add(rel)
            files.append(rel)
    return files


def main() -> int:
    base = _resolve_base()
    if not base:
        print(
            "qa_changed_html: no base ref (tried QA_BASE_REF, "
            "GITHUB_BASE_REF, origin/main, main)",
            file=sys.stderr,
        )
        return 1
    files = changed_html(base)
    if not files:
        print(f"qa_changed_html: no changed HTML since merge-base with {base}")
        return 0
    print(f"qa_changed_html: checking {len(files)} file(s) since merge-base with {base}")
    for rel in files:
        print(f"  {rel}")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa_pages.py"), *files],
        cwd=ROOT,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
