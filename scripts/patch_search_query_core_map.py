#!/usr/bin/env python3
"""Retarget the search-query-core URL map and regenerate nginx snippets.

Does not delete HTML. Does not reclassify the whole corpus from GSC.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from apply_index_consolidation import (  # noqa: E402
    load_keep,
    old_redirects,
    write_nginx_snippets,
)

MAP = ROOT / "data" / "url_consolidation_map.json"

# 410 with demand → live product/category. Never invent a missing SKU page.
HAM_TO_VETCHINA = (
    "/blog/halal-ham-wholesale-guide-2026",
    "/blog/vetchina-eto-halal",
    "/blog/vetchina-fileynaya-halyal",
    "/blog/vetchina-iz-indeyki-halyal",
    "/blog/vetchina-iz-kuricy-halyal",
    "/blog/vetchina-mramornaya-govyadina",
    "/blog/vetchina-optom-horeca-2026",
)
TO_301 = {
    "/blog/tatarskaya-kolbasa": "/kazylyk",
    "/blog/tatarskaya-kolbasa-iz-koniny": "/kazylyk",
    "/blog/echpochmak-eto": "/blog/echpochmak",
    "/blog/what-is-echpochmak": "/blog/echpochmak",
    "/what-is-echpochmak-v2": "/blog/echpochmak",
    "/blog/elesh-s-kuricey": "/blog/elesh",
    "/blog/gubadiya-chto-eto": "/vyipechka-halyal",
    "/en/blog/elesh-s-kuricey": "/en/vyipechka-halyal",
    "/blog/kurica-halyal-optom": "/products",
    "/en/blog/halal-ham-wholesale-guide-2026": "/en/vetchina-optom",
}
TO_301.update({url: "/vetchina-optom" for url in HAM_TO_VETCHINA})

DROP_FROM_RETIRE = {
    "/blog/echpochmak",
    "/blog/elesh",
}

NOINDEX = {
    "/blog/gubadiya-eto": {
        "file": "blog/gubadiya-eto.html",
        "intent": "gubadiya explainer held out of the index",
        "language": "ru",
        "canonical_target": "/blog/gubadiya-eto",
        "reason": "restored old URL; not allowlisted",
    },
    "/north-star": {
        "file": "north-star.html",
        "intent": "digital factory strategy",
        "language": "ru",
        "canonical_target": "/north-star",
        "reason": "slot freed for bakery explainers; page kept noindex",
    },
    "/en/editorial-policy": {
        "file": "en/editorial-policy.html",
        "intent": "editorial policy",
        "language": "en",
        "canonical_target": "/en/editorial-policy",
        "reason": "slot freed for bakery explainers; RU editorial-policy stays keep",
    },
}


def _row(url: str, file: str, status: str, target: str | None, reason: str,
         language: str, intent: str = "legacy URL retirement") -> dict:
    return {
        "url": url,
        "file": file,
        "intent": intent,
        "language": language,
        "owner": "seo",
        "source": "search-query-core URL repair",
        "canonical_target": target,
        "status": status,
        "reason": reason,
        "clicks_28d": 0.0,
        "impressions_28d": 0.0,
    }


def main() -> int:
    payload = json.loads(MAP.read_text(encoding="utf-8"))
    by_url = {row["url"]: row for row in payload["entries"]}

    for url in DROP_FROM_RETIRE:
        by_url.pop(url, None)

    for url, target in TO_301.items():
        lang = "en" if url.startswith("/en/") else "ru"
        rel = url.lstrip("/") + ".html"
        if url in by_url:
            row = by_url[url]
            row["status"] = "301"
            row["canonical_target"] = target
            row["reason"] = "equivalent canonical with search signal"
            row["source"] = "search-query-core URL repair"
        else:
            by_url[url] = _row(url, rel, "301", target,
                               "equivalent canonical with search signal", lang)

    for url, meta in NOINDEX.items():
        if url in by_url:
            row = by_url[url]
            row.update({
                "status": "noindex",
                "canonical_target": meta["canonical_target"],
                "reason": meta["reason"],
                "intent": meta["intent"],
                "source": "search-query-core URL repair",
            })
        else:
            by_url[url] = _row(
                url, meta["file"], "noindex", meta["canonical_target"],
                meta["reason"], meta["language"], meta["intent"],
            )

    rows = sorted(by_url.values(), key=lambda r: r["url"])
    counts = {status: sum(1 for r in rows if r["status"] == status)
              for status in ("301", "410", "noindex")}
    payload["entries"] = rows
    payload["counts"] = counts
    payload["generated_at"] = date.today().isoformat()
    MAP.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    keep_urls, _ = load_keep()
    write_nginx_snippets(rows, keep_urls, old_redirects())
    print(
        f"map patched: 301={counts['301']} 410={counts['410']} "
        f"noindex={counts['noindex']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
