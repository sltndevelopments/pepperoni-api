#!/usr/bin/env python3
"""
Audit near-duplicate blog posts (RU + EN). Writes data/blog_dedup_audit.json.

Does NOT apply redirects — owner/executor applies from approved clusters.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blog_topic_dedup import cluster_posts, scan_blog

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "blog_dedup_audit.json"


def main() -> int:
    ru = scan_blog("ru")
    en = scan_blog("en")
    clusters_ru = cluster_posts(ru)
    clusters_en = cluster_posts(en)

    # Cross-lang: same slug under /en/blog as a RU redirect_from or canon
    en_slugs = {r["slug"] for r in en}
    for c in clusters_ru:
        c["en_mirrors"] = sorted(
            s for s in [c["canonical"], *c["redirect_from"]] if s in en_slugs
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "blog_ru": len(ru),
            "blog_en": len(en),
            "clusters_ru": len(clusters_ru),
            "clusters_en": len(clusters_en),
            "redirect_candidates_ru": sum(len(c["redirect_from"]) for c in clusters_ru),
            "redirect_candidates_en": sum(len(c["redirect_from"]) for c in clusters_en),
        },
        "clusters_ru": [
            {
                "canonical": c["canonical"],
                "canonical_path": f"/blog/{c['canonical']}",
                "norm": c["norm"],
                "redirect_from": c["redirect_from"],
                "en_mirrors": c.get("en_mirrors", []),
                "members": [
                    {
                        "slug": m["slug"],
                        "title": m["title"][:120],
                        "datePublished": m.get("datePublished") or "",
                        "text_len": m.get("text_len") or 0,
                    }
                    for m in c["members"]
                ],
                "approved": True,  # high-confidence auto-canon; owner can flip false
            }
            for c in clusters_ru
        ],
        "clusters_en": [
            {
                "canonical": c["canonical"],
                "canonical_path": f"/en/blog/{c['canonical']}",
                "norm": c["norm"],
                "redirect_from": c["redirect_from"],
                "members": [
                    {
                        "slug": m["slug"],
                        "title": m["title"][:120],
                        "datePublished": m.get("datePublished") or "",
                        "text_len": m.get("text_len") or 0,
                    }
                    for m in c["members"]
                ],
                "approved": True,
            }
            for c in clusters_en
        ],
        "notes": (
            "Canonical picked by: spelling penalty, text length, earliest datePublished, "
            "shorter slug. Apply via scripts/apply_blog_canonicals.py."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ wrote {OUT}")
    print(
        f"   RU posts={len(ru)} clusters={len(clusters_ru)} "
        f"redirects={report['counts']['redirect_candidates_ru']}"
    )
    print(
        f"   EN posts={len(en)} clusters={len(clusters_en)} "
        f"redirects={report['counts']['redirect_candidates_en']}"
    )
    for c in clusters_ru[:15]:
        print(f"   • {c['canonical']} ← {', '.join(c['redirect_from'][:6])}"
              + ("…" if len(c["redirect_from"]) > 6 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
