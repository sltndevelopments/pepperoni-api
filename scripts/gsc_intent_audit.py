#!/usr/bin/env python3
"""Read-only GSC audit: is our page-one presence on queries that can pay?

Site-wide CTR hides the actual problem. Averaged over everything it looks like
a snippet failure ("we rank, nobody clicks"), but splitting the same 28 days by
intent shows commercial and informational demand converting at an identical
~0.2% while sitting at completely different positions. That is a ranking
problem on the money half, not a snippet problem anywhere.

Usage: python3 scripts/gsc_intent_audit.py [days]
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_gsc_queries import _load_gsc_key, get_access_token  # noqa: E402

SITE = "sc-domain:pepperoni.tatar"

# Buying language, RU/EN/AR. Deliberately literal: a query is "commercial" when
# the searcher spells out wholesale/supplier/price intent, not when we hope so.
COMMERCIAL = re.compile(
    r"оптом|опт\b|поставщик|производител|купить|цена|прайс|заказать|"
    r"контрактн|частн[ая|ой] марк|стм\b|b2b|wholesale|supplier|manufactur|"
    r"bulk|price|buy|import|export|distributor|جملة|مورد|مصنع",
    re.I,
)


def _query(token, start, end, dims):
    url = ("https://www.googleapis.com/webmasters/v3/sites/"
           f"{urllib.parse.quote(SITE, safe='')}/searchAnalytics/query")
    rows, start_row = [], 0
    while True:
        body = json.dumps({"startDate": start, "endDate": end,
                           "dimensions": dims, "rowLimit": 25000,
                           "startRow": start_row}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read()).get("rows", [])
        rows.extend(batch)
        if len(batch) < 25000:
            return rows
        start_row += len(batch)


def _summarize(label, rows):
    if not rows:
        print(f"{label}: no rows")
        return
    imp = sum(r["impressions"] for r in rows)
    clk = sum(r["clicks"] for r in rows)
    wpos = sum(r["position"] * r["impressions"] for r in rows) / imp
    top10 = sum(r["impressions"] for r in rows if r["position"] <= 10)
    print(f"{label}: {len(rows):4} queries  {imp:6.0f} imp  {clk:3.0f} clk  "
          f"CTR {clk / imp * 100:5.2f}%  weighted pos {wpos:5.1f}  "
          f"page-one share {top10 / imp * 100:5.1f}%")


def main() -> int:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 28
    key = _load_gsc_key()
    if not key.strip():
        print("no GSC key in env — nothing to audit")
        return 1
    token = get_access_token(json.loads(key))
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days - 1)
    print(f"window {start} .. {end}\n")

    qrows = _query(token, start.isoformat(), end.isoformat(), ["query"])
    comm = [r for r in qrows if COMMERCIAL.search(r["keys"][0])]
    info = [r for r in qrows if not COMMERCIAL.search(r["keys"][0])]
    print(f"distinct queries: {len(qrows)}")
    _summarize("commercial ", comm)
    _summarize("information", info)

    comm.sort(key=lambda r: -r["impressions"])
    print("\ntop commercial demand:")
    for r in comm[:15]:
        print(f"  {r['impressions']:5.0f} imp {r['clicks']:3.0f} clk "
              f"pos {r['position']:5.1f}  {r['keys'][0][:56]}")

    # Page 2-3 on a buying query is the cheapest ranking work available: the
    # demand is proven and the gap is a few positions, not a new audience.
    near = [r for r in comm if 10 < r["position"] <= 25 and r["impressions"] >= 5]
    near.sort(key=lambda r: -r["impressions"])
    print(f"\ncommercial queries on page 2-3 ({len(near)}) — closest wins:")
    for r in near:
        print(f"  {r['impressions']:5.0f} imp pos {r['position']:5.1f}  "
              f"{r['keys'][0][:56]}")

    # Page-one rows earning nothing. On informational queries this is usually
    # Google answering in the SERP, not a bad title — worth knowing before
    # anyone "fixes" the snippet.
    pairs = _query(token, start.isoformat(), end.isoformat(), ["query", "page"])
    dead = [r for r in pairs
            if r["position"] <= 10 and r["clicks"] == 0 and r["impressions"] >= 20]
    dead.sort(key=lambda r: -r["impressions"])
    dead_imp = sum(r["impressions"] for r in dead)
    total_imp = sum(r["impressions"] for r in pairs) or 1
    print(f"\npage-one rows with 0 clicks (>=20 imp): {len(dead)} "
          f"= {dead_imp / total_imp * 100:.1f}% of impressions")
    by_page = defaultdict(float)
    for r in dead:
        page = r["keys"][1].replace("https://pepperoni.tatar", "") or "/"
        by_page[page] += r["impressions"]
        commercial = "money" if COMMERCIAL.search(r["keys"][0]) else "info "
        print(f"  {r['impressions']:5.0f} imp pos {r['position']:4.1f} {commercial} "
              f"{r['keys'][0][:38]:38} {page[:36]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
