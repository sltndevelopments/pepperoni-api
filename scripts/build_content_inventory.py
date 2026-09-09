#!/usr/bin/env python3
"""Build content-inventory.csv and weekly-search-baseline.csv for the sprint.

Inventory rows = every URL the site has ever exposed that we know of:
  * data/index_manifest.json      (keep / retired, with file and kind)
  * data/url_consolidation_map.json (301 / 410 / noindex decisions)
  * public/sitemap.xml            (what we tell Google today)
  * GSC page rows                 (what Google actually sent clicks to)
Each row records where it was discovered. Clicks/impressions are given for two
full, comparable months (July and August 2026); anything we cannot measure is
`n.a.`, never 0. The status column is the *policy* status (what nginx is
configured to answer), not a live probe — see verify_sitemap_live.py and
redirect_review.py for live checks.

Baseline rows = ISO weeks (Mon–Sun) over the GSC dump, split by page type,
language and brand/non-brand query, with explicit gaps.

  python3 scripts/build_content_inventory.py --gsc /tmp/gsc_dump.json \
      --out-dir docs/sprint-2026-09
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import apply_index_consolidation as aic  # noqa: E402

SITE = "https://pepperoni.tatar"
P1 = ("2026-07-01", "2026-07-31")
P2 = ("2026-08-01", "2026-08-31")
PERIODS = (f"P1={P1[0]}..{P1[1]}; P2={P2[0]}..{P2[1]}; GSC sc-domain:pepperoni.tatar, "
           "web search, all countries/devices, dimensions=date+page; GSC data lag ≤3 days")

BRAND_RE = re.compile(r"казанск\w*\s+деликатес|kazan\s+delicac|pepperoni\.?tatar|kazandelikates|"
                      r"казан\s*деликатес", re.I)

# Blog slug → the commercial page a reader should be led to.
BLOG_TARGET = [
    (("pepperoni",), "/pepperoni"),
    (("sosiski", "hot-dog", "hotdog", "sausage"), "/sosiski-dlya-hotdog"),
    (("kazylyk",), "/kazylyk"),
    (("private-label", "stm", "kontrakt", "contract"), "/kontraktnoe-proizvodstvo"),
    (("halal", "halyal", "certif"), "/halal"),
    (("vetchina", "ham"), "/vetchina-optom"),
    (("kotlet", "burger"), "/kotlety-dlya-burgerov"),
    (("vypech", "bakery", "gubad", "echpoch"), "/vyipechka-halyal"),
    (("kopch", "smoked"), "/kolbasy-kopchyonye"),
    (("export", "dostavka", "delivery"), "/delivery"),
]
# Articles the growth plan schedules for an update this month.
PLANNED_UPDATES = {
    "/blog/pepperoni-iz-kakogo-myasa", "/blog/pepperoni-for-pizzeria-horeca",
    "/blog/narezka-pepperoni-parametry", "/blog/kak-hranit-pepperoni",
    "/blog/sosiski-dlya-hot-dogov-optom", "/blog/kazylyk",
}
PRIORITY_COMMERCIAL = {"/pepperoni": 1, "/sosiski-dlya-hotdog": 2, "/kazylyk": 3,
                       "/kontraktnoe-proizvodstvo": 4}


def norm(u: str) -> str:
    p = u[len(SITE):] if u.startswith(SITE) else u
    p = p.split("?", 1)[0]
    if p.endswith(".html"):
        p = p[:-5]
    if p in ("/en", "/en/"):
        return "/en/"
    return p.rstrip("/") or "/"


def page_type(path: str, kind: str | None) -> str:
    if kind:
        return kind
    if "/geo/" in path:
        return "geo (retired)"
    if "/blog/" in path:
        return "guide"
    if re.search(r"/products/kd-\d{3}$", path):
        return "product"
    if "/export/" in path:
        return "export-country"
    if path in ("/", "/en/"):
        return "home"
    return "hub"


def intent_for(ptype: str, path: str) -> str:
    if ptype in ("product", "catalog"):
        return "commercial: pick SKU / price"
    if ptype == "guide":
        return "informational → commercial"
    if ptype == "geo (retired)":
        return "legacy city×product (retired)"
    if ptype == "export-country":
        return "commercial: export inquiry"
    if ptype == "home":
        return "brand / navigation"
    if any(k in path for k in ("private-label", "kontrakt", "capabilities")):
        return "commercial: private label brief"
    if any(k in path for k in ("about", "halal", "cases", "faq", "delivery", "privacy")):
        return "trust / conditions"
    return "commercial: category"


def commercial_target(ptype: str, path: str) -> str:
    if ptype in ("hub", "catalog", "product", "export-country", "home"):
        return path
    slug = path.rsplit("/", 1)[-1].lower()
    for needles, target in BLOG_TARGET:
        if any(n in slug for n in needles):
            return ("/en" + target) if path.startswith("/en/") else target
    return "n.a."


def facts_source(ptype: str) -> str:
    if ptype in ("product", "catalog"):
        return "products.json (Google Sheets)"
    if ptype in ("hub", "home", "export-country"):
        return "products.json + brand.txt; claims need technologist/sales"
    if ptype == "guide":
        return "n.a. — needs technologist/sales facts before update"
    return "n.a."


def load_gsc(dump: Path):
    payload = json.loads(dump.read_text(encoding="utf-8"))
    dp = next(v for k, v in payload.items() if k.startswith("date_page_"))
    dq = next(v for k, v in payload.items() if k.startswith("date_query_"))
    return dp, dq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsc", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("docs/sprint-2026-09"))
    ns = ap.parse_args()
    ns.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    cmap = json.loads((ROOT / "data" / "url_consolidation_map.json").read_text(encoding="utf-8"))
    sitemap_urls = {norm(e.text) for e in ET.parse(ROOT / "public" / "sitemap.xml").getroot()
                    .iterfind(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    dp, dq = load_gsc(ns.gsc)

    # ---- per-URL clicks for the two full months
    stats: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in dp:
        d, url = r["keys"]
        p = norm(url)
        per = "1" if P1[0] <= d <= P1[1] else "2" if P2[0] <= d <= P2[1] else None
        stats[p]["seen"] += 1
        if per:
            stats[p][f"c{per}"] += r["clicks"]
            stats[p][f"i{per}"] += r["impressions"]

    rows: dict[str, dict] = {}

    def add(path: str, source: str, **kw):
        row = rows.setdefault(path, {"url": SITE + path, "discovery_source": set()})
        row["discovery_source"].add(source)
        for k, v in kw.items():
            if v not in (None, "") and not row.get(k):
                row[k] = v

    for e in manifest["entries"]:
        add(norm(e["url"]), "index_manifest", language=e.get("language"), kind=e.get("kind"),
            manifest_status=e.get("status"), owner=e.get("owner"), intent_hint=e.get("intent"))
    for e in cmap["entries"]:
        add(norm(e["url"]), "consolidation_map", language=e.get("language"),
            map_status=e.get("status"), canonical_target=e.get("canonical_target"),
            map_reason=e.get("reason"))
    for u in sitemap_urls:
        add(u, "sitemap.xml")
    for p in stats:
        add(p, "GSC pages 2026-06..09")

    out_rows = []
    for path, r in sorted(rows.items()):
        ptype = page_type(path, r.get("kind"))
        lang = r.get("language") or ("en" if path.startswith("/en/") or path == "/en/" else aic.language_for(path.lstrip("/")))
        ms, cs = r.get("manifest_status"), r.get("map_status")
        if ms == "keep":
            status, index_status, canonical = "200", "index", SITE + path
        elif cs == "301":
            status, index_status, canonical = "301", "redirected", SITE + (r.get("canonical_target") or "")
        elif cs == "noindex":
            status, index_status, canonical = "200", "noindex", SITE + path
        elif cs == "410" or ms == "retired":
            status, index_status, canonical = "410", "gone", "n.a."
        else:
            # Never existed in the current tree nor in the policy map: nginx answers
            # 404 (or 410 for /geo/ prefixes). Spot-checked 2026-09-09.
            status = "410" if "/geo/" in path else "404"
            index_status, canonical = "n.a. (legacy URL, not served; GSC history only)", "n.a."
        s = stats.get(path, {})
        c1 = f"{s['c1']:g}" if s else "n.a."
        i1 = f"{s['i1']:g}" if s else "n.a."
        c2 = f"{s['c2']:g}" if s else "n.a."
        i2 = f"{s['i2']:g}" if s else "n.a."
        target = commercial_target(ptype, path)
        if index_status == "index":
            if path in PLANNED_UPDATES:
                decision, reason = "update", "growth plan: one of six article updates this month (facts from technologist first)"
            elif path in PRIORITY_COMMERCIAL:
                decision, reason = "update", f"priority commercial page #{PRIORITY_COMMERCIAL[path]}: buyer answers, proofs, next step"
            elif ptype == "guide":
                decision, reason = "keep → review in month 2", "inventory first; no new URLs; improve or merge after intent overlap check"
            else:
                decision, reason = "keep", "in explicit index allowlist"
        elif index_status == "redirected":
            decision, reason = "keep 301", r.get("map_reason", "")
        elif index_status == "gone":
            decision, reason = "keep 410", r.get("map_reason", "retired in trust reset; no click signal or no honest target")
        elif index_status == "noindex":
            decision, reason = "keep noindex", r.get("map_reason", "")
        elif s and (s["c1"] or s["c2"]):
            decision, reason = "review", "legacy URL still receives clicks; decide 301 target or leave 404"
        else:
            decision, reason = "none", "legacy URL, 0 clicks in both periods; leave 404/410"
        out_rows.append({
            "url": SITE + path, "language": lang, "page_type": ptype,
            "intent": r.get("intent_hint") or intent_for(ptype, path),
            "discovery_source": "; ".join(sorted(r["discovery_source"])),
            "http_status": status, "canonical": canonical, "index_status": index_status,
            "clicks_period_1": c1, "impressions_period_1": i1,
            "clicks_period_2": c2, "impressions_period_2": i2,
            "measurement_periods": PERIODS,
            "commercial_target": target, "verified_facts_source": facts_source(ptype),
            "decision": decision, "reason": reason,
        })

    inv = ns.out_dir / "content-inventory.csv"
    with inv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    # ---- weekly baseline
    def week_start(d: str) -> date:
        dt = date.fromisoformat(d)
        return dt - timedelta(days=dt.weekday())

    weeks: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in dp:
        d, url = r["keys"]
        p = norm(url)
        w = weeks[week_start(d)]
        w["clicks"] += r["clicks"]
        w["impressions"] += r["impressions"]
        t = page_type(p, None)
        key = {"geo (retired)": "geo_retired", "guide": "blog", "product": "product",
               "export-country": "export", "home": "home"}.get(t, "hub")
        w[f"clicks_{key}"] += r["clicks"]
        w["clicks_en" if (p.startswith("/en/") or p == "/en/") else "clicks_ru_other"] += r["clicks"]
    for r in dq:
        d, q = r["keys"]
        w = weeks[week_start(d)]
        w["query_clicks_brand" if BRAND_RE.search(q) else "query_clicks_nonbrand"] += r["clicks"]

    last_date = max(r["keys"][0] for r in dp)
    base_rows = []
    for ws in sorted(weeks):
        we = ws + timedelta(days=6)
        w = weeks[ws]
        complete = we.isoformat() <= last_date and ws.isoformat() >= "2026-06-01"
        base_rows.append({
            "week_start": ws.isoformat(), "week_end": we.isoformat(),
            "complete_week": "yes" if complete else "no",
            "clicks_total": f"{w['clicks']:g}", "impressions_total": f"{w['impressions']:g}",
            "clicks_blog": f"{w['clicks_blog']:g}", "clicks_product": f"{w['clicks_product']:g}",
            "clicks_hub": f"{w['clicks_hub']:g}", "clicks_home": f"{w['clicks_home']:g}",
            "clicks_export": f"{w['clicks_export']:g}", "clicks_geo_retired": f"{w['clicks_geo_retired']:g}",
            "clicks_en_urls": f"{w['clicks_en']:g}", "clicks_ru_and_other_urls": f"{w['clicks_ru_other']:g}",
            "query_clicks_brand": f"{w['query_clicks_brand']:g}",
            "query_clicks_nonbrand": f"{w['query_clicks_nonbrand']:g}",
            "leads_confirmed": "n.a.",
            "source": "GSC Search Analytics API, sc-domain:pepperoni.tatar, type=web",
            "filters": "all countries, all devices; brand = query matches 'казанские деликатесы|kazan delicacies|pepperoni.tatar'",
            "gaps": ("query dims drop anonymised long-tail (query clicks < page clicks); "
                     "Yandex not included (Webmaster API token fixed 2026-09-09, history pending); "
                     "leads: no trustworthy series before analytics change 2026-09-09; "
                     + ("last week incomplete" if not complete else "")),
        })
    base = ns.out_dir / "weekly-search-baseline.csv"
    with base.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(base_rows[0].keys()))
        w.writeheader()
        w.writerows(base_rows)

    kinds = defaultdict(int)
    for r in out_rows:
        kinds[r["index_status"]] += 1
    print(f"content inventory: {len(out_rows)} URLs → {inv}  ({dict(kinds)})")
    print(f"weekly baseline: {len(base_rows)} weeks ({base_rows[0]['week_start']}..{base_rows[-1]['week_end']}) → {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
