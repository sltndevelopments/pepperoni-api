#!/usr/bin/env python3
"""Turn retired geo URLs that still earn Google clicks from 410 into 301.

Context: the 2026-08-26 trust reset retired every city×product page. Pages with
zero signal are correctly Gone, but GSC shows a long tail of retired geo URLs
that still receive clicks (Jul–Sep 2026: ~370 URLs, ~470 clicks). Serving 410
to a live click is a dead end for the buyer and throws away the URL's equity;
the SEO audit asks for a per-URL decision instead of a blanket 410.

Rule (deterministic, no LLM): a retired geo URL gets a 301 when
  * GSC reports >= MIN_CLICKS clicks in the window, and
  * the product slug maps to an existing keep hub (`geo_target`), RU → RU hub,
    every other locale → EN hub.
Everything else stays 410. The mapping is written back into
``data/url_consolidation_map.json``; nginx snippets are re-rendered through
``apply_index_consolidation.write_nginx_snippets`` so the 301/410 policy has a
single source. Run ``build_index_manifest.py`` + ``index_policy_check.py`` after.

Usage:
  python3 scripts/geo_signal_redirects.py --gsc-json /tmp/gsc_pages.json [--apply]
  python3 scripts/geo_signal_redirects.py --fetch --start 2026-07-01 --end 2026-09-06 --apply

``--gsc-json`` expects {page_url: {"clicks": {..}, "impressions": {..}}} or the
raw GSC rows list ([{"keys": [url], "clicks": n, ...}]).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import apply_index_consolidation as aic  # noqa: E402

MAP = ROOT / "data" / "url_consolidation_map.json"
SITE = "https://pepperoni.tatar"
MIN_CLICKS = 1


def fetch_gsc_pages(start: str, end: str) -> dict[str, float]:
    import fetch_gsc_queries as gsc  # noqa: E402

    sa = json.loads(gsc._load_gsc_key())
    token = gsc.get_access_token(sa)
    url = ("https://www.googleapis.com/webmasters/v3/sites/"
           + urllib.parse.quote("sc-domain:pepperoni.tatar", safe="")
           + "/searchAnalytics/query")
    clicks: dict[str, float] = {}
    start_row = 0
    while True:
        body = json.dumps({"startDate": start, "endDate": end, "dimensions": ["page"],
                           "rowLimit": 25000, "startRow": start_row}).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.loads(resp.read()).get("rows", [])
        for row in batch:
            clicks[row["keys"][0]] = clicks.get(row["keys"][0], 0) + float(row.get("clicks", 0))
        if len(batch) < 25000:
            break
        start_row += 25000
    return clicks


def load_gsc_json(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    clicks: dict[str, float] = {}
    if isinstance(payload, list):
        for row in payload:
            clicks[row["keys"][0]] = clicks.get(row["keys"][0], 0) + float(row.get("clicks", 0))
    else:
        for url, stats in payload.items():
            c = stats.get("clicks", 0)
            clicks[url] = float(sum(c.values()) if isinstance(c, dict) else c)
    return clicks


def clicks_for(url_path: str, clicks: dict[str, float]) -> float:
    """Sum GSC clicks over the URL's plain / slash / .html spellings."""
    total = 0.0
    for variant in (url_path, url_path + "/", url_path + ".html"):
        total += clicks.get(SITE + variant, 0.0)
    return total


def decide(entries: list[dict], clicks: dict[str, float], keep_urls: set[str]) -> list[dict]:
    changes: list[dict] = []
    for row in entries:
        if row.get("status") != "410" or "/geo/" not in row["url"]:
            continue
        n = clicks_for(row["url"], clicks)
        if n < MIN_CLICKS:
            continue
        lang = "ru" if row.get("language") == "ru" else "en"
        target = aic.normalize_url(aic.geo_target(row["url"], lang) or "")
        if not target or target not in keep_urls or target == row["url"]:
            continue
        changes.append({"url": row["url"], "target": target, "clicks": n})
        row["status"] = "301"
        row["canonical_target"] = target
        row["reason"] = f"geo URL still earns search clicks ({n:g}) → equivalent hub"

    # Geo URLs retired before the consolidation map existed (July cleanup) are
    # absent from the map and fall into the ^~ /geo/ prefix → 410. Register the
    # clicked ones so they get an exact-match 301 too.
    known = {row["url"] for row in entries}
    seen: dict[str, float] = {}
    for gsc_url, n in clicks.items():
        if not gsc_url.startswith(SITE + "/") or "/geo/" not in gsc_url:
            continue
        path = gsc_url[len(SITE):].split("?", 1)[0]
        if path.endswith(".html"):
            path = path[:-5]
        path = path.rstrip("/") or "/"
        seen[path] = seen.get(path, 0.0) + n
    for path, n in sorted(seen.items()):
        if path in known or n < MIN_CLICKS:
            continue
        lang = "ru" if path.startswith("/geo/") else "en"
        target = aic.normalize_url(aic.geo_target(path, lang) or "")
        if not target or target not in keep_urls:
            continue
        entries.append({
            "url": path,
            "file": path.lstrip("/") + ".html",
            "intent": "legacy URL retirement",
            "language": aic.language_for(path.lstrip("/")),
            "owner": "seo",
            "source": "GSC page clicks after retirement",
            "canonical_target": target,
            "status": "301",
            "reason": f"geo URL still earns search clicks ({n:g}) → equivalent hub",
            "clicks_28d": 0.0,
            "impressions_28d": 0.0,
        })
        changes.append({"url": path, "target": target, "clicks": n})
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsc-json", type=Path)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--apply", action="store_true")
    ns = ap.parse_args()

    if ns.fetch:
        if not (ns.start and ns.end):
            ap.error("--fetch requires --start and --end")
        clicks = fetch_gsc_pages(ns.start, ns.end)
    elif ns.gsc_json:
        clicks = load_gsc_json(ns.gsc_json)
    else:
        ap.error("need --gsc-json or --fetch")

    payload = json.loads(MAP.read_text(encoding="utf-8"))
    keep_urls, _ = aic.load_keep()
    entries = payload["entries"]
    changes = decide(entries, clicks, keep_urls)

    by_target: dict[str, int] = {}
    for c in changes:
        by_target[c["target"]] = by_target.get(c["target"], 0) + 1
    print(f"geo 410→301 candidates: {len(changes)} "
          f"(clicks {sum(c['clicks'] for c in changes):g})")
    for target, n in sorted(by_target.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d} → {target}")
    if not ns.apply:
        print("dry-run; pass --apply to write map + nginx snippets")
        return 0

    payload["counts"] = {s: sum(1 for r in entries if r["status"] == s)
                         for s in ("301", "410", "noindex")}
    MAP.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aic.write_nginx_snippets(entries, keep_urls, aic.old_redirects())
    print(f"wrote {MAP.relative_to(ROOT)} and deploy/nginx snippets; "
          f"counts={payload['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
