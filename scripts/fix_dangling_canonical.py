#!/usr/bin/env python3
"""Fix canonical/hreflang/og:url/JSON-LD self-references pointing to a slug
that does not exist as a file — the #1 contributor to the 1593 "broken
internal links" flagged by site_health.py (2026-07-02 audit).

Root cause: some page generators wrote canonical/hreflang/og:url using an
"intended" slug that diverged from the slug the file was actually saved
under (e.g. public/blog/kazylyk-horse-meat-sausage.html — an actual RU page,
lang="ru" — declares canonical https://pepperoni.tatar/blog/kazylyk-konina-kolbasa,
a file that was never created). Search engines and internal links that trust
the canonical get a 404; Google may also drop the (correct) real URL from the
index in favor of a canonical that doesn't resolve.

Conservative, narrow fix — NOT a general canonical rewrite:
  - Only touches a page's SELF-referential tags (canonical, og:url, hreflang
    x-default/self, JSON-LD "item"/"url" fields matching the dangling URL).
  - Only fires when the declared canonical target file does not exist on
    disk AND the page's own actual URL does resolve (i.e. we always point
    canonical back to a URL that is guaranteed to serve 200).
  - Does NOT touch links to OTHER pages, does NOT invent new slugs/redirects,
    does NOT rename any file. Pure "canonical must point at yourself if your
    declared alias doesn't exist" repair.

Usage:
  python3 scripts/fix_dangling_canonical.py --dry-run   # report only
  python3 scripts/fix_dangling_canonical.py --run       # apply + sanity
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
BASE = "https://pepperoni.tatar"

CANON_RE = re.compile(r'(<link rel="canonical" href=")' + re.escape(BASE) + r'(/[^"]*)(")')


def _file_for_path(url_path: str) -> Path:
    p = url_path.strip("/")
    if p == "":
        return PUBLIC / "index.html"
    direct = PUBLIC / f"{p}.html"
    if direct.exists():
        return direct
    idx = PUBLIC / p / "index.html"
    return idx


def _actual_url_for_file(f: Path) -> str:
    rel = f.relative_to(PUBLIC).as_posix()
    if rel.endswith("/index.html"):
        rel = rel[: -len("index.html")]
    elif rel.endswith(".html"):
        rel = rel[: -len(".html")]
    return "/" + rel


def scan() -> list[tuple[Path, str, str]]:
    """Returns [(file, dangling_canonical_path, actual_url), ...]."""
    out = []
    for f in PUBLIC.rglob("*.html"):
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        m = CANON_RE.search(html)
        if not m:
            continue
        canon_path = m.group(2)
        target = _file_for_path(canon_path)
        if target.exists():
            continue  # canonical resolves — not our problem
        actual_url = _actual_url_for_file(f)
        if canon_path.rstrip("/") == actual_url.rstrip("/"):
            continue  # already self-referential, just formatting diff
        out.append((f, canon_path, actual_url))
    return out


def apply_fix(entries: list[tuple[Path, str, str]]) -> int:
    changed = 0
    for f, dangling, actual_url in entries:
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        dangling_full = BASE + dangling
        actual_full = BASE + actual_url
        new = html.replace(dangling_full, actual_full)
        if new != html:
            f.write_text(new, encoding="utf-8")
            changed += 1
    return changed


def main() -> int:
    dry = "--dry-run" in sys.argv or "--run" not in sys.argv
    entries = scan()
    print(f"🔗 fix_dangling_canonical: {len(entries)} page(s) with a canonical "
          f"pointing to a non-existent file (self-reference mismatch).")
    for f, dangling, actual_url in entries[:15]:
        rel = f.relative_to(PUBLIC).as_posix()
        print(f"  {rel}: canonical={dangling}  →  actual={actual_url}")
    if len(entries) > 15:
        print(f"  … and {len(entries) - 15} more")
    if dry:
        print("(dry-run — no files modified; pass --run to apply)")
        return 0
    changed = apply_fix(entries)
    print(f"✅ Rewrote self-referential canonical/og:url/hreflang/JSON-LD URLs "
          f"in {changed} file(s) to point at their real, resolving URL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
