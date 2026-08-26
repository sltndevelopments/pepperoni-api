#!/usr/bin/env python3
"""Fail when two canonical non-product pages are near-duplicates."""
from __future__ import annotations

import html as html_lib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
THRESHOLD = 0.72


def visible_text(source: str) -> str:
    main = re.search(r"<main\b[^>]*>(.*?)</main>", source, re.I | re.S)
    source = main.group(1) if main else source
    source = re.sub(
        r"<(script|style|nav|footer|header)\b[^>]*>.*?</\1>",
        " ",
        source,
        flags=re.I | re.S,
    )
    source = re.sub(r"<[^>]+>", " ", source)
    source = html_lib.unescape(source).lower()
    source = re.sub(r"https?://\S+", " ", source)
    source = re.sub(r"[^\wа-яё]+", " ", source, flags=re.I)
    return re.sub(r"\s+", " ", source).strip()


def shingles(text: str, size: int = 5) -> set[tuple[str, ...]]:
    words = [word for word in text.split() if len(word) > 2]
    return {
        tuple(words[i:i + size])
        for i in range(max(0, len(words) - size + 1))
    }


def score(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def audit(threshold: float = THRESHOLD) -> list[str]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = [
        row for row in payload.get("entries", [])
        if row.get("status") == "keep" and row.get("kind") != "product"
    ]
    docs: list[tuple[dict, set]] = []
    errors: list[str] = []
    for row in rows:
        path = PUBLIC / row["file"]
        if not path.exists():
            errors.append(f"missing canonical file: {row['file']}")
            continue
        docs.append((
            row,
            shingles(visible_text(path.read_text(encoding="utf-8", errors="replace"))),
        ))
    for i, (left, left_shingles) in enumerate(docs):
        for right, right_shingles in docs[i + 1:]:
            if left.get("language") != right.get("language"):
                continue
            similarity = score(left_shingles, right_shingles)
            if similarity >= threshold:
                errors.append(
                    f"near duplicate {similarity:.3f}: "
                    f"{left['url']} ↔ {right['url']}")
    return errors


def main() -> int:
    errors = audit()
    if errors:
        print(f"similarity audit: {len(errors)} FAIL")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print(f"similarity audit: OK (threshold={THRESHOLD:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
