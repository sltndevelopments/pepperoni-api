#!/usr/bin/env python3
"""Idempotent T01 injector: one Metrika init per keep URL; GTM if missing.

Does not rewrite titles, copy, canonicals, or sitemap. Skips files that
already have ym(107064141, "init").
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
sys.path.insert(0, str(ROOT / "scripts"))

from analytics_snippets import inject_gtm, inject_metrika  # noqa: E402
from index_safety import keep_entries  # noqa: E402


def main() -> int:
    entries = keep_entries()
    if not entries:
        print("inject_analytics: no keep entries in index_manifest.json", file=sys.stderr)
        return 1
    metrika_added = 0
    gtm_added = 0
    already = 0
    missing = 0
    for row in entries:
        rel = row.get("file") or ""
        path = PUBLIC / rel
        if not path.is_file():
            print(f"  missing: {rel}")
            missing += 1
            continue
        html = path.read_text(encoding="utf-8")
        html2, did_m = inject_metrika(html)
        html3, did_g = inject_gtm(html2)
        if did_m or did_g:
            path.write_text(html3, encoding="utf-8")
            bits = []
            if did_m:
                metrika_added += 1
                bits.append("metrika")
            if did_g:
                gtm_added += 1
                bits.append("gtm")
            print(f"  + {'+'.join(bits)}: {rel}")
        else:
            already += 1
    print(
        f"inject_analytics: keep={len(entries)} already_ok={already} "
        f"metrika+={metrika_added} gtm+={gtm_added} missing={missing}"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
