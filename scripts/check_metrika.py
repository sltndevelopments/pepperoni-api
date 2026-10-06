#!/usr/bin/env python3
"""T01 gate: exactly one Yandex Metrika init per indexed URL.

Modes:
  python3 scripts/check_metrika.py              # local public/ vs sitemap+manifest
  python3 scripts/check_metrika.py --live        # curl production (post-deploy)
  python3 scripts/check_metrika.py --live-baseline  # curl 8 page types only
  python3 scripts/check_metrika.py --sample      # 8 representative local pages

Owner runs --live after merge/deploy against https://pepperoni.tatar.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SITEMAP = PUBLIC / "sitemap.xml"
sys.path.insert(0, str(ROOT / "scripts"))

from analytics_snippets import (  # noqa: E402
    COUNTER,
    GTM_ID,
    count_metrika_inits,
    has_gtm,
)
from index_safety import keep_entries  # noqa: E402

SITE = "https://pepperoni.tatar"
SAMPLE = [
    ("home", "/"),
    ("pepperoni", "/pepperoni"),
    ("product", "/products/kd-013"),
    ("blog", "/blog/kazylyk"),
    ("category", "/kotlety-dlya-burgerov"),
    ("halal", "/halal"),
    ("export", "/export/kazakhstan"),
    ("en", "/en/"),
]
UA = "pepperoni-metrika-check/1.0 (+https://pepperoni.tatar)"


def url_to_file(url: str) -> Path | None:
    path = url
    if path.startswith(SITE):
        path = path[len(SITE):]
    path = path.split("?", 1)[0]
    if path in {"", "/"}:
        return PUBLIC / "index.html"
    if path.endswith("/"):
        candidate = PUBLIC / path.strip("/") / "index.html"
        if candidate.exists():
            return candidate
    rel = path.strip("/")
    for cand in (PUBLIC / f"{rel}.html", PUBLIC / rel / "index.html", PUBLIC / rel):
        if cand.is_file():
            return cand
    return None


def sitemap_urls() -> list[str]:
    tree = ET.parse(SITEMAP)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [el.text.strip() for el in tree.iterfind(".//sm:loc", ns) if el.text]


def classify(html: str) -> dict:
    inits = count_metrika_inits(html)
    return {
        "inits": inits,
        "ok": inits == 1,
        "gtm": has_gtm(html),
        "watch": f"mc.yandex.ru/watch/{COUNTER}" in html,
    }


def fetch(url: str, timeout: float = 20.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body
    except Exception as e:
        return 0, f"ERROR: {e}"


def check_local(urls: list[str] | None = None) -> dict:
    if urls is None:
        urls = sitemap_urls()
        keep = {SITE + (e["url"] if e["url"].startswith("/") else "/" + e["url"])
                for e in keep_entries()}
        # sitemap is the published index; also require every keep URL
        extra = sorted(keep - set(urls))
        urls = urls + extra
    rows = []
    for url in urls:
        path = url_to_file(url)
        if path is None:
            rows.append({"url": url, "file": None, "ok": False, "error": "file_missing",
                         "inits": 0, "gtm": False})
            continue
        html = path.read_text(encoding="utf-8")
        info = classify(html)
        rel = str(path.relative_to(PUBLIC)).replace("\\", "/")
        rows.append({"url": url, "file": rel, **info})
    return _summarize(rows, source="local")


def check_live(urls: list[str]) -> dict:
    rows = []
    for url in urls:
        status, html = fetch(url)
        info = classify(html) if status == 200 else {
            "inits": 0, "ok": False, "gtm": False, "watch": False,
        }
        rows.append({"url": url, "http": status, **info})
    return _summarize(rows, source="live")


def _summarize(rows: list[dict], *, source: str) -> dict:
    ok = [r for r in rows if r.get("ok")]
    missing = [r for r in rows if r.get("inits", 0) == 0]
    doubled = [r for r in rows if r.get("inits", 0) > 1]
    no_gtm = [r for r in rows if r.get("ok") and not r.get("gtm")]
    summary = {
        "source": source,
        "counter": COUNTER,
        "gtm": GTM_ID,
        "total": len(rows),
        "ok": len(ok),
        "missing_metrika": len(missing),
        "double_init": len(doubled),
        "ok_without_gtm": len(no_gtm),
        "pass": len(ok) == len(rows) and not doubled,
        "rows": rows,
    }
    return summary


def print_report(summary: dict, *, verbose: bool = False) -> None:
    print(
        f"check_metrika [{summary['source']}]: "
        f"{summary['ok']}/{summary['total']} exactly-one-init "
        f"missing={summary['missing_metrika']} double={summary['double_init']} "
        f"pass={'YES' if summary['pass'] else 'NO'}"
    )
    if summary["missing_metrika"]:
        print("  without Metrika init:")
        for r in summary["rows"]:
            if r.get("inits", 0) == 0:
                print(f"    {r.get('url')}  file={r.get('file')} http={r.get('http', '-')}")
    if summary["double_init"]:
        print("  more than one Metrika init (double-count risk):")
        for r in summary["rows"]:
            if r.get("inits", 0) > 1:
                print(f"    {r.get('url')} inits={r['inits']}")
    if verbose:
        for r in summary["rows"]:
            flag = "OK" if r.get("ok") else "FAIL"
            print(f"  [{flag}] inits={r.get('inits')} gtm={int(bool(r.get('gtm')))} {r.get('url')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="curl every sitemap URL on production")
    ap.add_argument("--live-baseline", action="store_true",
                    help="curl only the 8 representative production URLs")
    ap.add_argument("--sample", action="store_true", help="check 8 local representative pages")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ns = ap.parse_args()

    if ns.live or ns.live_baseline:
        if ns.live_baseline:
            urls = [SITE + path for _, path in SAMPLE]
        else:
            urls = sitemap_urls()
        summary = check_live(urls)
    elif ns.sample:
        urls = [SITE + path for _, path in SAMPLE]
        summary = check_local(urls)
    else:
        summary = check_local()

    if ns.json:
        print(json.dumps({k: v for k, v in summary.items() if k != "rows" or ns.verbose},
                         ensure_ascii=False, indent=2))
    print_report(summary, verbose=ns.verbose)
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
