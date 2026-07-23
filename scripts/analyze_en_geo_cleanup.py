#!/usr/bin/env python3
"""EN geo cleanup analysis — same rules as RU geo cleanup, scoped to public/en/geo/.

Window [D-93, D-3], page-grouped GSC, collapse-gate, GRACE_DAYS=30,
301 only with residual impressions + live HTTP-200 parent under /en/…,
discontinued meat-preps class → 410.
Writes data/en_geo_cleanup_analysis.json (read-only w.r.t. prod DB).
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
import fetch_gsc_queries as gsc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
GEO_DIR = PUBLIC / "en" / "geo"
OUT = DATA / "en_geo_cleanup_analysis.json"

ROW_LIMIT = 25000
GRACE_DAYS = 30
SITE = "sc-domain:pepperoni.tatar"

# Product slug → EN parent path. Discontinued → None (410).
EN_PARENT_ALIASES = {
    "halal-pepperoni": "/en/pepperoni",
    "pepperoni": "/en/pepperoni",
    "pepperoni-govyadina": "/en/pepperoni",
    "pepperoni-konina": "/en/pepperoni",
    "pepperoni-kurica": "/en/pepperoni",
    "pepperoni-miks": "/en/pepperoni",
    "halal-hot-dog-sausages": "/en/sosiski-dlya-hotdog",
    "sosiski-dlya-hotdog": "/en/sosiski-dlya-hotdog",
    "sosiki-dlya-hotdog": "/en/sosiski-dlya-hotdog",
    "halal-corn-dog-sausages": "/en/sosiska-v-teste",
    "sosiski-v-teste": "/en/sosiska-v-teste",
    "sosiki-v-teste": "/en/sosiska-v-teste",
    "halal-ham": "/en/vetchina-optom",
    "vetchina": "/en/vetchina-optom",
    "halal-burger-patties": "/en/kotlety-dlya-burgerov",
    "kotlety-dlya-burgerov": "/en/kotlety-dlya-burgerov",
    "premium-kazylyk-horse-sausage": "/en/kazylyk",
    "kazylyk-premium": "/en/kazylyk",
    "halal-smoked-delicacies": "/en/kolbasy-kopchyonye",
    "kopchenye-delikatesy": "/en/kolbasy-kopchyonye",
    "halal-sausage-products": "/en/kolbasy-varenye",
    "kolbasnye-izdeliya": "/en/kolbasy-varenye",
    "halal-bakery-classic": "/en/bakery",
    "vypechka-klassicheskaya": "/en/bakery",
    "tatar-halal-bakery": "/en/bakery",
    "vypechka-tatarskaya": "/en/bakery",
    "halal-pizza-toppings": "/en/pepperoni-v-narezke",
    "topping-dlya-pitstsy": "/en/pepperoni-v-narezke",
    "private-label-halal": "/en/oem",
    "private-label-stm": "/en/oem",
    # discontinued meat-preps (owner) — no valid parent
    "halal-minced-meat": None,
    "halal-pelmeni-dumplings": None,
    "halal-raw-meat": None,
    "farsh": None,
    "pelmeni": None,
    "syroje-myaso": None,
}

_PARENT_OK: dict[str, bool] = {}


def _window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=93)).strftime("%Y-%m-%d"), (now - timedelta(days=3)).strftime("%Y-%m-%d")


def _fetch_pages(token: str, start: str, end: str) -> tuple[list[dict], dict]:
    url = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(SITE, safe='')}/searchAnalytics/query"
    )
    rows, start_row, pages = [], 0, 0
    exhausted = False
    while True:
        body = json.dumps({
            "startDate": start, "endDate": end,
            "dimensions": ["page"], "rowLimit": ROW_LIMIT, "startRow": start_row,
        }).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.loads(resp.read()).get("rows", [])
        pages += 1
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            exhausted = True
            break
        start_row += ROW_LIMIT
    return rows, {"api_pages": pages, "row_count": len(rows), "pagination_exhausted": exhausted}


def _totals(rows: list[dict]) -> dict:
    return {
        "clicks": round(sum(r.get("clicks", 0) for r in rows)),
        "impressions": round(sum(r.get("impressions", 0) for r in rows)),
        "urls": len(rows),
    }


def _gate(tot: dict, meta: dict) -> tuple[str, str]:
    if not meta["pagination_exhausted"]:
        return "stop", "pagination not exhausted"
    if tot["clicks"] == 0:
        return "stop", "pepperoni clicks=0 → broken fetch"
    if tot["clicks"] < 100:
        return "escalate", f"pepperoni clicks={tot['clicks']} ambiguous"
    return "ok", f"pepperoni clicks={tot['clicks']} impr={tot['impressions']}"


def _prefixes() -> list[str]:
    d = json.loads((DATA / "products_geo.json").read_text(encoding="utf-8"))
    products = d["products"] if isinstance(d, dict) else d
    prefs = set(EN_PARENT_ALIASES.keys())
    for p in products:
        for key in ("slug_en", "slug_ru"):
            s = (p.get(key) or "").strip()
            if s:
                prefs.add(s)
        for v in p.get("variants") or []:
            s = (v.get("slug") or "").strip()
            if s:
                prefs.add(s)
    return sorted(prefs, key=len, reverse=True)


def split_geo(stem: str, prefixes: list[str]) -> tuple[str, str]:
    for pref in prefixes:
        if stem == pref:
            return pref, ""
        if stem.startswith(pref + "-"):
            return pref, stem[len(pref) + 1:]
    return stem, ""


def _http200(path: str) -> bool:
    if path in _PARENT_OK:
        return _PARENT_OK[path]
    url = f"https://pepperoni.tatar{path}"
    ok = False
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "kd-en-geo/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = r.status == 200
            break
        except urllib.error.HTTPError as e:
            ok = e.code == 200
            if method == "HEAD" and e.code in (403, 405):
                continue
            break
        except Exception:
            ok = False
            break
    _PARENT_OK[path] = ok
    return ok


def parent_for(product_slug: str) -> str | None:
    if product_slug not in EN_PARENT_ALIASES and product_slug not in _prefixes_cache:
        return None
    if product_slug in EN_PARENT_ALIASES:
        target = EN_PARENT_ALIASES[product_slug]
    else:
        return None
    if target is None:
        return None
    return target if _http200(target) else None


_prefixes_cache: list[str] = []


def _age_map() -> dict[str, int]:
    ages: dict[str, int] = {}
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--name-only", "--format=%at", "--", "public/en/geo/"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except Exception:
        return ages
    now = datetime.now(timezone.utc).timestamp()
    cur_ts = None
    first: dict[str, int] = {}
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            cur_ts = int(line)
        elif line.startswith("public/en/geo/") and cur_ts is not None:
            rel = line[len("public/"):]
            if rel not in first or cur_ts < first[rel]:
                first[rel] = cur_ts
    for rel, ts in first.items():
        ages[rel] = int((now - ts) / 86400)
    return ages


def main() -> int:
    global _prefixes_cache
    _prefixes_cache = _prefixes()
    token = gsc.get_access_token(json.loads(gsc._load_gsc_key()))
    start, end = _window()
    print(f"fetching pepperoni [{start}..{end}] page-grouped …", flush=True)
    rows, meta = _fetch_pages(token, start, end)
    tot = _totals(rows)
    print(f"  urls={meta['row_count']} exhausted={meta['pagination_exhausted']} "
          f"clicks={tot['clicks']} impr={tot['impressions']}", flush=True)
    verdict, reason = _gate(tot, meta)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start, "end": end},
        "locale": "en",
        "fetch": {**meta, "totals": tot},
        "gate": {"verdict": verdict, "reason": reason},
        "dispositions": [],
        "counts": {},
        "parent_http_status": {},
    }
    if verdict != "ok":
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"GATE {verdict.upper()}: {reason}")
        return 2 if verdict == "stop" else 3

    by_page = {}
    for r in rows:
        keys = r.get("keys") or []
        if keys:
            by_page[keys[0]] = r
    ages = _age_map()
    geo_files = sorted(GEO_DIR.glob("*.html"))
    out_rows = []
    counts = {"keep": 0, "301": 0, "410": 0, "hold": 0}
    for f in geo_files:
        stem = f.stem
        url_slash = f"https://pepperoni.tatar/en/geo/{stem}/"
        url_html = f"https://pepperoni.tatar/en/geo/{stem}.html"
        rec = by_page.get(url_slash) or by_page.get(url_html)
        clicks = rec.get("clicks", 0) if rec else 0
        impressions = rec.get("impressions", 0) if rec else 0
        position = round(rec["position"], 1) if rec else None
        confirmed_zero = rec is None
        product_slug, city_slug = split_geo(stem, _prefixes_cache)
        age = ages.get(str(f.relative_to(PUBLIC)))
        parent = parent_for(product_slug)
        has_signal = impressions > 0
        if clicks >= 1:
            disp = "keep"
        elif age is not None and age < GRACE_DAYS:
            disp = "hold"
        elif parent and has_signal:
            disp = "301"
        else:
            disp = "410"
        counts[disp] += 1
        out_rows.append({
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
            "disposition": disp,
        })

    result["dispositions"] = out_rows
    result["counts"] = {
        "geo_files": len(geo_files),
        **counts,
        "confirmed_zero": sum(1 for r in out_rows if r["confirmed_zero"]),
        "with_clicks": sum(1 for r in out_rows if r["clicks"] >= 1),
    }
    result["wave1_clean_410"] = sum(
        1 for r in out_rows
        if r["disposition"] == "410" and r["confirmed_zero"]
        and (r["age_days"] is None or r["age_days"] >= GRACE_DAYS)
    )
    result["parent_http_status"] = dict(sorted(_PARENT_OK.items()))
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("GATE OK:", reason)
    print("counts:", json.dumps(result["counts"], ensure_ascii=False))
    print("wave1:", result["wave1_clean_410"])
    print("parents:", result["parent_http_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
