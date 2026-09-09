#!/usr/bin/env python3
"""Live check of every sitemap URL against the published site.

For each <loc> in public/sitemap.xml (or --sitemap URL):
  * final status must be 200 with no redirect hop,
  * <link rel=canonical> must equal the sitemap URL,
  * no `noindex` in <meta name=robots> or X-Robots-Tag,
  * hreflang alternates declared in the page must match the sitemap's,
  * lang attribute must match the locale of the URL.
Also probes api.pepperoni.tatar: HTML paths must 301 to pepperoni.tatar and
the API/MCP/discovery routes must still answer.

Writes a CSV (one row per URL) and prints a summary. Exit 1 on any failure.

  python3 scripts/verify_sitemap_live.py --out docs/sprint-2026-09/sitemap-live.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "xhtml": "http://www.w3.org/1999/xhtml"}
UA = "pepperoni-sitemap-verify/1.0 (+https://pepperoni.tatar)"

API_MUST_WORK = [
    ("https://api.pepperoni.tatar/api/products", 200),
    ("https://api.pepperoni.tatar/products.json", 200),
    ("https://api.pepperoni.tatar/llms.txt", 200),
    ("https://api.pepperoni.tatar/openapi.yaml", 200),
    # MCP is a stdio server (`npm run mcp`), not an HTTP route — nothing to probe.
    ("https://api.pepperoni.tatar/.well-known/ai-plugin.json", 200),
    ("https://api.pepperoni.tatar/robots.txt", 200),
]
API_HTML_MUST_REDIRECT = [
    "https://api.pepperoni.tatar/",
    "https://api.pepperoni.tatar/about",
    "https://api.pepperoni.tatar/pepperoni",
    "https://api.pepperoni.tatar/products/kd-001",
    "https://api.pepperoni.tatar/en/",
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def fetch(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            body = resp.read(600_000).decode("utf-8", "replace")
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), ""
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}, ""


def parse_sitemap(source: str):
    if source.startswith("http"):
        _s, _h, body = fetch(source)
        root = ET.fromstring(body)
    else:
        root = ET.parse(source).getroot()
    out = []
    for u in root.iterfind("sm:url", NS):
        loc = u.findtext("sm:loc", namespaces=NS)
        alts = {l.get("hreflang"): l.get("href") for l in u.iterfind("xhtml:link", NS)}
        out.append((loc, alts))
    return out


RE_CANON = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', re.I)
RE_CANON2 = re.compile(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', re.I)
RE_ROBOTS = re.compile(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)["\']', re.I)
RE_ALT = re.compile(r'<link[^>]+rel=["\']alternate["\'][^>]*hreflang=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']', re.I)
RE_LANG = re.compile(r'<html[^>]*\blang=["\']([a-zA-Z-]+)["\']', re.I)


def check_url(loc: str, sm_alts: dict) -> dict:
    status, headers, body = fetch(loc)
    row = {"url": loc, "status": status, "location": headers.get("Location", ""),
           "canonical": "", "robots_meta": "", "x_robots": headers.get("X-Robots-Tag", ""),
           "html_lang": "", "hreflang_ok": "", "problems": ""}
    problems = []
    if status != 200:
        problems.append(f"status {status}" + (f" → {row['location']}" if row["location"] else ""))
    else:
        m = RE_CANON.search(body) or RE_CANON2.search(body)
        row["canonical"] = m.group(1) if m else ""
        if row["canonical"] != loc:
            problems.append(f"canonical={row['canonical'] or 'missing'}")
        rm = RE_ROBOTS.search(body)
        row["robots_meta"] = rm.group(1) if rm else ""
        if "noindex" in row["robots_meta"].lower() or "noindex" in row["x_robots"].lower():
            problems.append("noindex")
        lm = RE_LANG.search(body)
        row["html_lang"] = lm.group(1) if lm else ""
        expect_lang = "en" if "/en/" in loc + "/" else "ru"
        if row["html_lang"].lower()[:2] != expect_lang:
            problems.append(f"lang={row['html_lang'] or 'missing'}")
        page_alts = {l: h for l, h in RE_ALT.findall(body)}
        if sm_alts:
            missing = {k: v for k, v in sm_alts.items() if page_alts.get(k) != v}
            row["hreflang_ok"] = "yes" if not missing else "no"
            if missing:
                problems.append("hreflang≠sitemap: " + "; ".join(f"{k}: page={page_alts.get(k)} sm={v}" for k, v in missing.items()))
        else:
            row["hreflang_ok"] = "n.a."
    row["problems"] = " | ".join(problems)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitemap", default=str(ROOT / "public" / "sitemap.xml"))
    ap.add_argument("--out", type=Path, default=Path("/tmp/sitemap-live.csv"))
    ap.add_argument("--workers", type=int, default=8)
    ns = ap.parse_args()

    entries = parse_sitemap(ns.sitemap)
    with ThreadPoolExecutor(max_workers=ns.workers) as ex:
        rows = list(ex.map(lambda e: check_url(*e), entries))

    api_rows = []
    for url, want in API_MUST_WORK:
        st, hd, _ = fetch(url)
        api_rows.append({"url": url, "status": st, "location": hd.get("Location", ""),
                         "canonical": "", "robots_meta": "", "x_robots": hd.get("X-Robots-Tag", ""),
                         "html_lang": "", "hreflang_ok": "n.a.",
                         "problems": "" if (st == want or (want is None and st not in (0, 301, 302, 404)))
                         else f"expected {want or 'non-redirect answer'}"})
    for url in API_HTML_MUST_REDIRECT:
        st, hd, _ = fetch(url)
        loc = hd.get("Location", "")
        ok = st == 301 and loc.startswith("https://pepperoni.tatar")
        api_rows.append({"url": url, "status": st, "location": loc, "canonical": "",
                         "robots_meta": "", "x_robots": hd.get("X-Robots-Tag", ""),
                         "html_lang": "", "hreflang_ok": "n.a.",
                         "problems": "" if ok else "api host must 301 to pepperoni.tatar"})

    ns.out.parent.mkdir(parents=True, exist_ok=True)
    with ns.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows + api_rows)

    bad = [r for r in rows + api_rows if r["problems"]]
    print(f"sitemap URLs checked: {len(rows)}; api probes: {len(api_rows)}; problems: {len(bad)}")
    for r in bad:
        print(f"  {r['url']}: {r['problems']}")
    print(f"→ {ns.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
