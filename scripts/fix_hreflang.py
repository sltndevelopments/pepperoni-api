#!/usr/bin/env python3
"""Make page-level hreflang match the sitemap (one rule: scripts/hreflang_policy.py).

For every RU↔EN pair of `keep` pages in data/index_manifest.json, rewrite the
`<link rel="alternate" hreflang="ru|en|x-default">` tags in both files so they
equal what rebuild_sitemap.py emits. Regional variants (`en-KZ`, …) and
retired-locale links are left untouched. Pages without a partner language are
skipped: the sitemap lists no alternates for them either.

  python3 scripts/fix_hreflang.py            # rewrite files, print changes
  python3 scripts/fix_hreflang.py --check    # exit 1 if any page disagrees

Runs in scripts/sync-vps.sh right after rebuild_sitemap.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
sys.path.insert(0, str(ROOT / "scripts"))

from hreflang_policy import BASE, alternates, pair_key  # noqa: E402

RE_ALT = re.compile(
    r'[ \t]*<link\s+rel=["\']alternate["\']\s+hreflang=["\'](ru|en|x-default)["\']\s+href=["\']([^"\']+)["\']\s*/?>[ \t]*\n?',
    re.I,
)
RE_CANON = re.compile(r'[ \t]*<link[^>]+rel=["\']canonical["\'][^>]*>[ \t]*\n?', re.I)


def render(alts: list[tuple[str, str]], indent: str) -> str:
    return "".join(f'{indent}<link rel="alternate" hreflang="{lang}" href="{href}">\n'
                   for lang, href in alts)


def fix_file(path: Path, alts: list[tuple[str, str]], check: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    found = [(m.group(1).lower(), m.group(2)) for m in RE_ALT.finditer(text)]
    # Order is irrelevant to Google; only the set matters (and no duplicates).
    if len(found) == len(alts) and set(found) == set(alts):
        return False
    if check:
        return True
    matches = list(RE_ALT.finditer(text))
    if matches:
        first = matches[0]
        indent = re.match(r"[ \t]*", first.group(0)).group(0)
        block = render(alts, indent)
        # Strip every existing ru/en/x-default link, then put the block where the first one was.
        head, tail = text[: first.start()], text[first.start():]
        tail = RE_ALT.sub("", tail)
        text = head + block + tail
    else:
        canon = RE_CANON.search(text)
        if not canon:
            print(f"  ! {path.relative_to(ROOT)}: no canonical link, cannot place hreflang")
            return True
        indent = re.match(r"[ \t]*", canon.group(0)).group(0)
        text = text[: canon.end()] + render(alts, indent) + text[canon.end():]
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ns = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep = [r for r in manifest["entries"] if r.get("status") == "keep"]
    pairs: dict[str, dict[str, dict]] = {}
    for row in keep:
        pairs.setdefault(pair_key(row["file"]), {})[row["language"]] = row

    changed = []
    for key, langs in sorted(pairs.items()):
        urls = {lang: BASE + row["url"] for lang, row in langs.items()}
        alts = alternates(key, urls)
        if not alts:
            continue
        for lang, row in langs.items():
            path = PUBLIC / row["file"]
            if not path.is_file():
                continue
            if fix_file(path, alts, ns.check):
                changed.append(row["file"])

    verb = "disagree with sitemap" if ns.check else "rewritten"
    print(f"hreflang: {len(changed)} page(s) {verb}" + (":" if changed else ""))
    for f in changed:
        print(f"  {f}")
    return 1 if (ns.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
