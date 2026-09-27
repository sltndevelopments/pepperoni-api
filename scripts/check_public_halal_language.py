#!/usr/bin/env python3
"""Fail if public/ contains swine-family wording.

Read-only. Internal QA scripts may name the forbidden terms; customer-facing
files under public/ may not, including negations and comparisons.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

TEXT_SUFFIXES = {
    ".html", ".txt", ".json", ".xml", ".yaml", ".yml", ".md", ".js",
    ".css", ".svg", ".csv",
}

# Cyrillic boundaries: ASCII \b does not treat Cyrillic as a word char reliably
# across engines, so the RU forms are spelled out.
PATTERNS = [
    re.compile(r"свин(?!ц)", re.I),
    re.compile(r"шпик", re.I),
    re.compile(r"(?<![а-яё])сало(?![а-яё])", re.I),
    re.compile(r"pork", re.I),
    re.compile(r"\bporcine\b", re.I),
    re.compile(r"\bpigs?\b", re.I),
    re.compile(r"\bswine\b", re.I),
    re.compile(r"\bhogs?\b", re.I),
    re.compile(r"\blard\b", re.I),
    re.compile(r"\bfatback\b", re.I),
    re.compile(r"خنزير"),
]


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(ROOT)
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(rx.search(line) for rx in PATTERNS):
                hits.append(f"{rel}:{lineno}")
    return hits


def main() -> int:
    hits = scan(PUBLIC)
    if not hits:
        print("public halal language: clean")
        return 0
    print(f"FAIL: public surface contains swine-family wording ({len(hits)})", file=sys.stderr)
    for hit in hits:
        print(f"  {hit}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
