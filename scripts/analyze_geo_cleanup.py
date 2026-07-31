#!/usr/bin/env python3
"""Geo-cleanup analysis — page-grouped GSC pull + reconciliation gate + disposition.

READ-ONLY w.r.t. production data: this never touches seo_data.db, never edits
public/, never commits. It fetches GSC fresh, reconciles, classifies geo pages,
and writes a single analysis artifact: data/geo_cleanup_analysis.json.

Frozen spec (agreed in design phase):
  - Window [D-93, D-3] (GSC lags ~3d; 90-day body).
  - Pure page-grouped fetch (dimensions=["page"]) for BOTH domains, paginated by
    startRow until exhausted (last response < ROW_LIMIT).
  - Reconciliation gate = COLLAPSE detector, not a traffic-level validator:
      pepperoni total clicks must be "tens" (>0), kazan must be "thousands".
      pepperoni==0 OR kazan in tens/zero  → STOP (broken fetch, not dead site).
      ambiguous middle → escalate (exit 3), do NOT classify.
  - confirmed-zero (absence from page-grouped response) is valid ONLY if the
    fetch passed all validity checks (window correct, pure page dim, pagination
    exhausted). Otherwise a missing URL is "no-data", never 410.
  - Disposition applies ONLY to pepperoni /geo/ pages. kazan is hard-locked keep.
  - keep = clicks>=1 OR in whitelist. Else → 301 (if live 200 parent) or 410.
    301 target MUST be a live keep 200 URL (parent from GEO_SLUG_ALIASES); no
    live parent → 410.
  - age: files younger than 60 days → hold (grace period), not 410.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
GEO_DIR = PUBLIC / "geo"
OUT = DATA / "geo_cleanup_analysis.json"

ROW_LIMIT = 25000
# Grace period. Lowered from 60→30d after data showed the whole geo corpus was
# committed in one June bulk run (git "age" 30-60d is that batch, not real youth).
# Rationale for 30 (not 21): on a 2900-thin-page domain crawl-budget dilution
# stretches indexing, so give a slightly longer benefit of the doubt. 30d clears
# the June batch (~49d) with margin and still shields genuinely fresh July pages.
GRACE_DAYS = 30
WHITELIST_PLACEHOLDER: set[str] = set()  # filled later by owner-approved list

DOMAINS = {
    "pepperoni": "sc-domain:pepperoni.tatar",
    "kazan": "sc-domain:kazandelikates.tatar",
}

# ---- GSC auth (reuse fetch_gsc_queries helpers) ----------------------------
import fetch_gsc_queries as gsc  # noqa: E402


def _window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    end = (now - timedelta(days=3)).strftime("%Y-%m-%d")   # D-3
    start = (now - timedelta(days=93)).strftime("%Y-%m-%d")  # D-93
    return start, end


def _fetch_pages(token: str, site: str, start: str, end: str) -> tuple[list[dict], dict]:
    """Pure page-grouped fetch, paginated until exhausted. Returns (rows, meta)."""
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(site, safe='')}/searchAnalytics/query"
    )
    rows: list[dict] = []
    start_row = 0
    pages = 0
    exhausted = False
    while True:
        body = json.dumps({
            "startDate": start,
            "endDate": end,
            "dimensions": ["page"],
            "rowLimit": ROW_LIMIT,
            "startRow": start_row,
        }).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.loads(resp.read()).get("rows", [])
        pages += 1
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            exhausted = True
            break
        start_row += ROW_LIMIT
        if start_row > 500000:  # hard safety, should never hit for these domains
            break
    meta = {"api_pages": pages, "row_count": len(rows), "pagination_exhausted": exhausted}
    return rows, meta


def _index_by_page(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        keys = r.get("keys", [])
        page = keys[0] if keys else ""
        if not page:
            continue
        out[page] = {
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": r.get("ctr", 0),
            "position": r.get("position", 0),
        }
    return out


def _totals(rows: list[dict]) -> dict:
    return {
        "clicks": round(sum(r.get("clicks", 0) for r in rows)),
        "impressions": round(sum(r.get("impressions", 0) for r in rows)),
        "urls": len(rows),
    }


def _order(n: float) -> str:
    if n <= 0:
        return "zero"
    if n < 100:
        return "tens"
    if n < 1000:
        return "hundreds"
    return "thousands"


def reconciliation_gate(pep_tot: dict, kaz_tot: dict,
                        pep_meta: dict, kaz_meta: dict) -> tuple[str, str]:
    """Return (verdict, reason). verdict in {ok, stop, escalate}."""
    # Fetch integrity first: pagination must be exhausted for confirmed-zero validity.
    if not (pep_meta["pagination_exhausted"] and kaz_meta["pagination_exhausted"]):
        return "stop", "pagination not exhausted — confirmed-zero invalid"
    pep_o = _order(pep_tot["clicks"])
    kaz_o = _order(kaz_tot["clicks"])
    # Hard collapse signals.
    if pep_tot["clicks"] == 0:
        return "stop", f"pepperoni total clicks=0 → broken fetch, not dead site"
    if kaz_o in ("zero", "tens"):
        return "stop", f"kazan clicks order={kaz_o} (expected thousands) → broken fetch"
    # Healthy shape: pepperoni alive (tens+), kazan thousands.
    if pep_o in ("tens", "hundreds") and kaz_o == "thousands":
        return "ok", f"pepperoni={pep_tot['clicks']} ({pep_o}), kazan={kaz_tot['clicks']} ({kaz_o})"
    # Anything else = ambiguous middle → escalate, do not classify.
    return "escalate", (f"ambiguous totals pepperoni={pep_tot['clicks']} ({pep_o}), "
                        f"kazan={kaz_tot['clicks']} ({kaz_o}) — needs human read")


# ---- lineage: geo slug -> canonical non-geo parent -------------------------
def _load_products() -> list[dict]:
    d = json.loads((DATA / "products_geo.json").read_text(encoding="utf-8"))
    return d["products"] if isinstance(d, dict) else d


def _product_prefixes(products: list[dict]) -> list[str]:
    prefixes = set()
    for p in products:
        for key in ("slug_ru",):
            s = (p.get(key) or "").strip()
            if s:
                prefixes.add(s)
        for v in p.get("variants", []) or []:
            s = (v.get("slug") or "").strip()
            if s:
                prefixes.add(s)
    # longest first for longest-prefix match
    return sorted(prefixes, key=len, reverse=True)


def _live_paths() -> set[str]:
    paths = set()
    for f in PUBLIC.rglob("*.html"):
        rel = "/" + str(f.relative_to(PUBLIC))
        paths.add(rel)
        paths.add(rel[:-5])
    return paths


def _import_aliases() -> dict:
    import fix_links
    aliases = dict(fix_links.GEO_SLUG_ALIASES)
    # fix_links.GEO_SLUG_ALIASES keys carry a historical typo ("sosiki" without the
    # second "s") while on-disk product slugs use "sosiski". Without this the 375
    # sosiski pages resolve to no parent and get mis-sent to 410 despite having a
    # live parent + residual impressions (they should be 301). Add correctly-spelled
    # keys + the pepperoni variants, all pointing at pages verified live below.
    fixes = {
        "sosiski-dlya-hotdog": "/sosiski-dlya-hotdog",
        "sosiski-v-teste": "/sosiska-v-teste",   # note: singular "sosiska" page
        "pepperoni-govyadina": "/pepperoni",
        "pepperoni-konina": "/pepperoni",
        "pepperoni-kurica": "/pepperoni",
        "pepperoni-miks": "/pepperoni",
    }
    for k, v in fixes.items():
        aliases.setdefault(k, v)
    return aliases


def split_geo(stem: str, prefixes: list[str]) -> tuple[str, str]:
    for pref in prefixes:
        if stem == pref:
            return pref, ""
        if stem.startswith(pref + "-"):
            return pref, stem[len(pref) + 1:]
    # fallback: unknown product — treat whole stem as product, no city
    return stem, ""


# Products discontinued by the owner — their category page is not a valid 301
# target regardless of HTTP status. Owner fact 2026-07-22: мясные заготовки сняты
# с производства. /myasnyie-zagotovki is the lineage parent of farsh/pelmeni/
# syroje-myaso; редиректить на снятый продукт бессмысленно → эти гео идут в 410.
DISCONTINUED_PARENTS = {"/myasnyie-zagotovki"}

_PARENT_STATUS_CACHE: dict[str, bool] = {}


def _parent_is_live_200(target: str) -> bool:
    """Real HTTP check against prod — a file on disk is NOT proof (prod nginx/CDN
    may 410 a page whose .html still exists in the repo, as found for
    /myasnyie-zagotovki). Cached per unique target (~14 total), so cheap."""
    if target in _PARENT_STATUS_CACHE:
        return _PARENT_STATUS_CACHE[target]
    url = f"https://pepperoni.tatar{target}"
    ok = False
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method,
                                         headers={"User-Agent": "kd-geo-cleanup/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = (r.status == 200)
            break
        except urllib.error.HTTPError as e:
            ok = (e.code == 200)
            if method == "HEAD" and e.code in (403, 405):
                continue  # some servers reject HEAD; retry GET
            break
        except Exception:
            ok = False
            break
    _PARENT_STATUS_CACHE[target] = ok
    return ok


def parent_for(product_slug: str, aliases: dict, live: set[str]) -> str | None:
    target = aliases.get(product_slug)
    if not target:
        return None
    if target in DISCONTINUED_PARENTS:
        return None  # discontinued product → not a redirect target → 410
    # Must be a live 200 on PROD (real HTTP), not merely present on disk.
    if _parent_is_live_200(target):
        return target
    return None


def _geo_age_map() -> dict[str, int]:
    """Map geo file rel-path -> age in days, from a SINGLE git pass.

    Per-file `git log --follow` on ~2900 files spawns thousands of processes and
    is unusably slow. Instead walk history once with --name-only and record the
    EARLIEST commit timestamp that touched each geo/ path (add-or-modify; for our
    purpose earliest-seen ≈ creation, good enough for a 60-day grace check).
    """
    ages: dict[str, int] = {}
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--name-only", "--format=%at", "--", "public/geo/"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except Exception:
        return ages
    now = datetime.now(timezone.utc).timestamp()
    cur_ts: int | None = None
    first_seen: dict[str, int] = {}
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            cur_ts = int(line)
        elif line.startswith("public/geo/") and cur_ts is not None:
            # store WITHOUT the public/ prefix to match f.relative_to(PUBLIC)
            rel = line[len("public/"):]  # -> "geo/<file>.html"
            if rel not in first_seen or cur_ts < first_seen[rel]:
                first_seen[rel] = cur_ts
    for rel, ts in first_seen.items():
        ages[rel] = int((now - ts) / 86400)
    return ages


def _backlink_map() -> dict[str, int]:
    """External backlinks per geo stem.

    HONEST LIMITATION: we have no reliable programmatic backlink source. The GSC
    service-account API does not export per-URL referring domains, and no
    third-party tool (Ahrefs/Majestic) is wired in. For auto-generated thin geo
    landings external backlinks are ~certainly zero, so we record 0 rather than
    fabricate a column. If a backlink source is added later, populate this map;
    the 301-vs-410 rule already reads it.
    """
    return {}


def _internal_inbound_stems() -> set[str]:
    """Geo stems that survivor (non-geo) pages link INTO.

    From lineage recon: only public/pepperoni.html and public/en/pepperoni.html
    embed geo links (a regions grid). We scan them live so the set stays accurate
    if the grid changes. These stems' inbound links must be cleaned in the same
    commit as any 301/410 so survivors don't point at redirects/gone pages.
    """
    import re
    stems: set[str] = set()
    for rel in ("pepperoni.html", "en/pepperoni.html"):
        f = PUBLIC / rel
        if not f.exists():
            continue
        html = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'/(?:en/)?geo/([a-z0-9\-]+?)(?:/|\.html)', html):
            stems.add(m.group(1))
    return stems


def classify(gate_ok: bool):
    products = _load_products()
    prefixes = _product_prefixes(products)
    aliases = _import_aliases()
    live = _live_paths()
    backlink_map = _backlink_map()
    inbound_stems = _internal_inbound_stems()

    token = gsc.get_access_token(json.loads(gsc._load_gsc_key()))
    start, end = _window()

    print(f"fetching pepperoni [{start}..{end}] page-grouped …", flush=True)
    pep_rows, pep_meta = _fetch_pages(token, DOMAINS["pepperoni"], start, end)
    print(f"  pepperoni: {pep_meta['row_count']} urls, {pep_meta['api_pages']} api-page(s), "
          f"exhausted={pep_meta['pagination_exhausted']}", flush=True)
    print(f"fetching kazan …", flush=True)
    kaz_rows, kaz_meta = _fetch_pages(token, DOMAINS["kazan"], start, end)
    print(f"  kazan: {kaz_meta['row_count']} urls, {kaz_meta['api_pages']} api-page(s), "
          f"exhausted={kaz_meta['pagination_exhausted']}", flush=True)
    pep_tot, kaz_tot = _totals(pep_rows), _totals(kaz_rows)
    print(f"totals: pepperoni clicks={pep_tot['clicks']} impr={pep_tot['impressions']}; "
          f"kazan clicks={kaz_tot['clicks']} impr={kaz_tot['impressions']}", flush=True)

    verdict, reason = reconciliation_gate(pep_tot, kaz_tot, pep_meta, kaz_meta)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start, "end": end},
        "fetch": {
            "pepperoni": {**pep_meta, "totals": pep_tot},
            "kazan": {**kaz_meta, "totals": kaz_tot},
        },
        "gate": {"verdict": verdict, "reason": reason},
        "dispositions": {},
        "counts": {},
    }

    if verdict != "ok":
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"GATE {verdict.upper()}: {reason}")
        return verdict

    pep_by_page = _index_by_page(pep_rows)
    age_map = _geo_age_map()
    print(f"age map: {len(age_map)} geo files dated from git", flush=True)

    # geo files (RU top-level only for this pass)
    geo_files = sorted(p for p in GEO_DIR.glob("*.html"))
    rows_out = []
    counts = {"keep": 0, "301": 0, "410": 0, "hold": 0}
    for f in geo_files:
        stem = f.stem
        url_slash = f"https://pepperoni.tatar/geo/{stem}/"
        url_html = f"https://pepperoni.tatar/geo/{stem}.html"
        rec = pep_by_page.get(url_slash) or pep_by_page.get(url_html)
        clicks = rec["clicks"] if rec else 0
        impressions = rec["impressions"] if rec else 0
        position = round(rec["position"], 1) if rec else None
        confirmed_zero = rec is None  # valid because gate passed (pagination exhausted)

        product_slug, city_slug = split_geo(stem, prefixes)
        age = age_map.get(str(f.relative_to(PUBLIC)))
        parent = parent_for(product_slug, aliases, live)
        backlinks = backlink_map.get(stem, 0)

        # disposition (agreed principle + population-aware grace):
        #   keep  = proven interest (clicks>=1) OR whitelist city.
        #   hold  = younger than grace period (30d git-age).
        #           Population note: for confirmed-zero pages there is no
        #           "first-impression" metric to measure youth by, so git/deploy
        #           age is the ONLY available proxy. For impr>=1 pages git-age is a
        #           CONSERVATIVE proxy (the page has been live at least git-age, and
        #           its first impression came after deploy), so the same threshold
        #           is safe for them too. Undefined-youth is treated as "unknown",
        #           never silently as "old".
        #   301   = there is something to CONSOLIDATE (residual impressions OR a
        #           backlink) AND a live 200 parent exists. Having a parent is NOT
        #           enough — a never-shown page has nothing to pass on.
        #   410   = everything else (incl. confirmed-zero with a parent but no
        #           signal). Nothing to consolidate → clean removal.
        has_signal = (impressions > 0) or (backlinks > 0)
        if clicks >= 1 or city_slug in WHITELIST_PLACEHOLDER:
            disp = "keep"
        elif age is not None and age < GRACE_DAYS:
            disp = "hold"
        elif parent and has_signal:
            disp = "301"
        else:
            disp = "410"
        counts[disp] += 1

        rows_out.append({
            "file": str(f.relative_to(PUBLIC)),
            "stem": stem,
            "product_slug": product_slug,
            "city_slug": city_slug,
            "clicks": clicks,
            "impressions": impressions,
            "position": position,
            "confirmed_zero": confirmed_zero,
            "age_days": age,
            "parent": parent,
            "backlinks": backlinks,
            "internal_inbound": stem in inbound_stems,
            "disposition": disp,
        })

    result["dispositions"] = rows_out
    result["counts"] = {
        "geo_files": len(geo_files),
        **counts,
        "in_gsc_with_impressions": sum(1 for r in rows_out if not r["confirmed_zero"]),
        "confirmed_zero": sum(1 for r in rows_out if r["confirmed_zero"]),
        "with_clicks": sum(1 for r in rows_out if r["clicks"] >= 1),
        "internal_inbound_from_survivors": sum(1 for r in rows_out if r["internal_inbound"]),
        "hold_young": sum(1 for r in rows_out if r["disposition"] == "hold"),
    }
    # Wave-1 = pre-validated clean 410: confirmed-zero, no signal, past grace, no
    # inbound survivor link. Safest possible removal, launchable on a single "yes".
    result["wave1_clean_410"] = sum(
        1 for r in rows_out
        if r["disposition"] == "410" and r["confirmed_zero"]
        and r["impressions"] == 0 and r["backlinks"] == 0
        and not r["internal_inbound"]
        and (r["age_days"] is None or r["age_days"] >= GRACE_DAYS)
    )
    result["parent_http_status"] = dict(sorted(_PARENT_STATUS_CACHE.items()))
    result["discontinued_parents"] = sorted(DISCONTINUED_PARENTS)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("GATE OK:", reason)
    print("counts:", json.dumps(result["counts"], ensure_ascii=False))
    print("parent_http_status:", json.dumps(result["parent_http_status"], ensure_ascii=False))
    return "ok"


if __name__ == "__main__":
    v = classify(gate_ok=True)
    sys.exit(0 if v == "ok" else (3 if v == "escalate" else 2))
