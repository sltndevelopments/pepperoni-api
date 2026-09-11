#!/usr/bin/env python3
"""Review every retired geo URL that still earned Google clicks.

Produces `redirect-review.csv`: one row per clicked geo URL with the GSC
clicks and period, the decision recorded in data/url_consolidation_map.json,
the live redirect chain (every hop, final status), the final page's canonical
and language, whether the hop crosses languages, whether the product family in
the slug matches the target hub, and a review flag for the rows that need a
human (top-N by clicks and every cross-language move).

GSC input: the `pages_*` block of a dump produced with the Search Analytics
API (dimensions=[page]) — see docs/sprint-2026-09/change-report.md for how the
dump was made; it is not stored in the repo.

  python3 scripts/redirect_review.py --gsc /tmp/gsc_dump.json \
      --period 2026-07-01..2026-09-06 --out docs/sprint-2026-09/redirect-review.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import apply_index_consolidation as aic  # noqa: E402

MAP = ROOT / "data" / "url_consolidation_map.json"
SITE = "https://pepperoni.tatar"
UA = "pepperoni-redirect-review/1.0"
TOP_N = 30

# Order matters: specific product words before the generic "halal" qualifier.
FAMILIES = {
    "private-label": ("private-label", "stm", "oem", "contract", "kontrakt"),
    "not-sold": ("syroje-myaso", "raw-meat", "lahmeh-niya", "farsh", "minced", "pelmeni", "dumpling"),
    "pepperoni": ("pepperoni", "peperoni", "babbroni", "pizza", "topping"),
    "kazylyk": ("kazylyk", "kazy", "horse"),
    "bakery": ("sosiki-v-teste", "corn-dog", "vypech", "bakery", "pastry", "makhbuzat",
               "gubadiya", "peremyach", "echpochmak", "samsa", "pie"),
    "sausages": ("sosis", "sausage", "hot-dog", "hotdog", "frankfurter"),
    "ham": ("vetchina", "ham"),
    "smoked": ("kopch", "smoked", "salami", "servelat"),
    "cooked": ("varen", "cooked", "boiled", "doktorsk", "mortadella"),
    "burger": ("kotlet", "burger", "burgir", "patty", "patties"),
    "jerky": ("jerky", "snack", "biltong"),
    "delivery": ("delivery", "dostavka", "export"),
    "catalog": ("kolbasnye-izdeliya", "delikatesy", "sausage-products"),
    "halal": ("halal", "halyal"),
}
HUB_FAMILY = {
    "/pepperoni": "pepperoni", "/en/pepperoni": "pepperoni",
    "/pepperoni-optom": "pepperoni", "/pepperoni-dlya-pizzerii": "pepperoni",
    "/pepperoni-v-narezke": "pepperoni", "/en/pepperoni-v-narezke": "pepperoni",
    "/kazylyk": "kazylyk", "/en/kazylyk": "kazylyk",
    "/sosiski-dlya-hotdog": "sausages", "/en/sosiski-dlya-hotdog": "sausages",
    "/vetchina-optom": "ham", "/en/vetchina-optom": "ham",
    "/kolbasy-kopchyonye": "smoked", "/en/kolbasy-kopchyonye": "smoked",
    "/kolbasy-varenye": "cooked", "/en/kolbasy-varenye": "cooked",
    "/kotlety-dlya-burgerov": "burger", "/en/kotlety-dlya-burgerov": "burger",
    "/vyipechka-halyal": "bakery", "/en/vyipechka-halyal": "bakery", "/bakery": "bakery", "/en/bakery": "bakery",
    "/jerky": "jerky", "/en/jerky": "jerky",
    "/halal": "halal", "/en/halal": "halal",
    "/private-label": "private-label", "/en/private-label": "private-label",
    "/kontraktnoe-proizvodstvo": "private-label",
    "/delivery": "delivery", "/en/delivery": "delivery", "/export": "delivery", "/en/export": "delivery",
    "/": "home", "/en/": "home",
    "/products": "catalog", "/en/products": "catalog",
}


def family_of_slug(path: str) -> str:
    slug = path.rsplit("/", 1)[-1].lower()
    for fam, needles in FAMILIES.items():
        if any(n in slug for n in needles):
            return fam
    return "unknown"


def family_of_target(path: str) -> str:
    p = aic.normalize_url(path)
    if p in HUB_FAMILY:
        return HUB_FAMILY[p]
    if re.fullmatch(r"(/en)?/products/kd-\d{3}", p):
        return "product"
    return family_of_slug(p)


def lang_of_path(path: str) -> str:
    first = path.strip("/").split("/", 1)[0]
    if first in {"en", "ar", "de", "fr", "es", "tr", "zh", "kk", "uz", "ky", "az", "fa", "ur", "id", "ms"}:
        return first
    return "ru"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)
RE_CANON = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', re.I)
RE_LANG = re.compile(r'<html[^>]*\blang=["\']([a-zA-Z-]+)["\']', re.I)


def chain(url: str, max_hops: int = 6):
    hops, cur = [], url
    canonical = lang = ""
    for _ in range(max_hops):
        req = urllib.request.Request(cur, headers={"User-Agent": UA})
        try:
            with OPENER.open(req, timeout=25) as r:
                hops.append(str(r.status))
                body = r.read(400_000).decode("utf-8", "replace")
                m = RE_CANON.search(body)
                canonical = m.group(1) if m else ""
                lm = RE_LANG.search(body)
                lang = (lm.group(1) if lm else "")[:2].lower()
                return hops, cur, canonical, lang
        except urllib.error.HTTPError as e:
            hops.append(str(e.code))
            loc = e.headers.get("Location") if e.headers else None
            if e.code in (301, 302, 307, 308) and loc:
                cur = loc if loc.startswith("http") else SITE + loc
                continue
            return hops, cur, canonical, lang
        except Exception as exc:  # noqa: BLE001
            hops.append(f"ERR:{exc.__class__.__name__}")
            return hops, cur, canonical, lang
    hops.append("LOOP?")
    return hops, cur, canonical, lang


def load_clicks(dump: Path, key_prefix: str = "pages_") -> tuple[dict[str, float], str]:
    payload = json.loads(dump.read_text(encoding="utf-8"))
    key = next(k for k in payload if k.startswith(key_prefix))
    clicks: dict[str, float] = {}
    for row in payload[key]:
        clicks[row["keys"][0]] = clicks.get(row["keys"][0], 0.0) + float(row.get("clicks", 0))
    return clicks, key[len(key_prefix):].replace("_", "..")


def norm_path(gsc_url: str) -> str:
    path = gsc_url[len(SITE):].split("?", 1)[0]
    if path.endswith(".html"):
        path = path[:-5]
    return path.rstrip("/") or "/"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsc", type=Path, required=True)
    ap.add_argument("--period", help="override period label, e.g. 2026-07-01..2026-09-06")
    ap.add_argument("--out", type=Path, default=Path("/tmp/redirect-review.csv"))
    ap.add_argument("--workers", type=int, default=8)
    ns = ap.parse_args()

    clicks_raw, period = load_clicks(ns.gsc)
    period = ns.period or period
    geo_clicks: dict[str, float] = {}
    for u, n in clicks_raw.items():
        if u.startswith(SITE + "/") and "/geo/" in u:
            p = norm_path(u)
            geo_clicks[p] = geo_clicks.get(p, 0.0) + n
    geo_clicks = {p: n for p, n in geo_clicks.items() if n >= 1}

    entries = {r["url"]: r for r in json.loads(MAP.read_text(encoding="utf-8"))["entries"]}
    keep_urls, _ = aic.load_keep()

    paths = sorted(geo_clicks, key=lambda p: -geo_clicks[p])
    with ThreadPoolExecutor(max_workers=ns.workers) as ex:
        chains = dict(zip(paths, ex.map(lambda p: chain(SITE + p), paths)))

    rows = []
    rank = 0
    for p in paths:
        rank += 1
        n = geo_clicks[p]
        e = entries.get(p, {})
        hops, final_url, canonical, final_lang = chains[p]
        src_lang = lang_of_path(p)
        tgt = e.get("canonical_target", "") if e.get("status") == "301" else ""
        final_path = final_url[len(SITE):] if final_url.startswith(SITE) else final_url
        fam_src = family_of_slug(p)
        fam_tgt = family_of_target(final_path) if hops and hops[-1] == "200" else ""
        cross = src_lang != (final_lang or lang_of_path(final_path)) if fam_tgt else False
        semantic = ("match" if fam_src == fam_tgt else
                    "home-fallback" if fam_tgt == "home" else
                    "generic→catalog" if fam_tgt == "catalog" and fam_src in ("unknown", "halal") else
                    "n.a." if not fam_tgt else "mismatch")
        if e.get("status") == "410" and fam_src == "not-sold":
            semantic = "410 correct (not in catalog)"
        problems = []
        if e.get("status") == "301":
            if hops[-1] != "200":
                problems.append(f"final {hops[-1]}")
            if len(hops) > 2:
                problems.append("chain>1")
            if canonical and aic.normalize_url(canonical) != aic.normalize_url(final_path):
                problems.append("final canonical differs")
            if aic.normalize_url(final_path) not in keep_urls and aic.normalize_url(final_path) != "/":
                problems.append("final not in keep set")
            if semantic == "mismatch":
                problems.append("family mismatch")
        decision = (
            "301 keep" if e.get("status") == "301" and not problems else
            "301 review" if e.get("status") == "301" else
            "410 no matching hub (leftover)" if e.get("status") in ("410", None) else
            e.get("status", "n.a.")
        )
        manual = "yes" if (rank <= TOP_N or (cross and e.get("status") == "301")) else "no"
        rows.append({
            "rank": rank,
            "source_url": SITE + p,
            "clicks": f"{n:g}",
            "period": period,
            "source_lang": src_lang,
            "map_status": e.get("status", "not in map (410 via ^~ /geo/)"),
            "map_target": tgt,
            "live_chain": " → ".join(hops),
            "final_url": final_url,
            "final_canonical": canonical,
            "final_lang": final_lang or "n.a.",
            "cross_language": "yes" if cross else "no",
            "family_source": fam_src,
            "family_target": fam_tgt or "n.a.",
            "semantic": semantic,
            "problems": "; ".join(problems),
            "decision": decision,
            "manual_review": manual,
            "reviewer_note": "",
        })

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    with ns.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n301 = sum(1 for r in rows if r["map_status"] == "301")
    n410 = len(rows) - n301
    total = sum(float(r["clicks"]) for r in rows)
    covered = sum(float(r["clicks"]) for r in rows if r["map_status"] == "301")
    print(f"clicked geo URLs: {len(rows)} (clicks {total:g}); 301: {n301} (clicks {covered:g}); "
          f"410/leftover: {n410}")
    bad = [r for r in rows if r["problems"]]
    print(f"301 rows with problems: {len(bad)}")
    for r in bad[:40]:
        print(f"  {r['source_url']} [{r['clicks']}] {r['live_chain']} → {r['final_url']}: {r['problems']}")
    cross = [r for r in rows if r["cross_language"] == "yes" and r["map_status"] == "301"]
    print(f"cross-language 301s: {len(cross)}")
    print(f"→ {ns.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
