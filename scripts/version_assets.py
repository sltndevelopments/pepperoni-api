#!/usr/bin/env python3
"""Stamp `/assets/*.js|css` references with a content hash (`?v=<sha8>`).

nginx serves /assets/ with `Cache-Control: public, max-age=31536000, immutable`
(sites-enabled/pepperoni.tatar:84), but every page referenced the bare
`/assets/lead-form.js`. A change to the file therefore never reached a
returning browser for up to a year — the 2026-09-09 measurement fix would have
been invisible to exactly the visitors we measure. This post-processor rewrites
the references to `/assets/<name>.<ext>?v=<first 8 hex of sha256>` so any
change to an asset busts the cache on the next deploy. Idempotent; the query
string is recomputed from the current file each run. Runs in sync-vps.sh
after the generators and before fix_pages.

  python3 scripts/version_assets.py            # rewrite
  python3 scripts/version_assets.py --check    # exit 1 if any reference is stale
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
ASSETS = PUBLIC / "assets"

RE_REF = re.compile(r'((?:src|href)=["\'])/assets/([A-Za-z0-9._-]+\.(?:js|css))(?:\?v=[0-9a-f]{8})?(["\'])')


def digests() -> dict[str, str]:
    out = {}
    for p in ASSETS.iterdir():
        if p.suffix in {".js", ".css"} and p.is_file():
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
    return out


def process(path: Path, hashes: dict[str, str], check: bool) -> bool:
    text = path.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        name = m.group(2)
        if name not in hashes:
            return m.group(0)
        return f"{m.group(1)}/assets/{name}?v={hashes[name]}{m.group(3)}"

    new = RE_REF.sub(repl, text)
    if new == text:
        return False
    if not check:
        path.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ns = ap.parse_args()
    hashes = digests()
    changed = [p for p in PUBLIC.rglob("*.html") if process(p, hashes, ns.check)]
    verb = "stale" if ns.check else "restamped"
    print(f"assets: {len(hashes)} files; {len(changed)} page(s) {verb}")
    return 1 if (ns.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
