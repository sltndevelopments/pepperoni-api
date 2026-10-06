#!/usr/bin/env python3
"""PHASE 1 regression audit: status/canonical/hreflang/sitemap/robots/links.

Local mode inspects generated HTML in the repo (no deploy required).
--live curls production for the same checks on a sample + sitemap size.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
sys.path.insert(0, str(ROOT / "scripts"))

from index_safety import keep_entries  # noqa: E402

SITE = "https://pepperoni.tatar"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
      "xhtml": "http://www.w3.org/1999/xhtml"}
CANON_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*>', re.I)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
HREFLANG_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]+hreflang=["\']([^"\']+)["\'][^>]*>',
    re.I,
)
INTERNAL_RE = re.compile(
    r'''href=["'](?:https://pepperoni\.tatar)?(/[^"']+)["']''', re.I
)
SAMPLE = [
    "/", "/pepperoni", "/products/kd-013", "/blog/kazylyk",
    "/kotlety-dlya-burgerov", "/halal", "/export/kazakhstan", "/en/",
]


def url_to_file(url: str) -> Path | None:
    path = url[len(SITE):] if url.startswith(SITE) else url
    path = path.split("?", 1)[0]
    if path in {"", "/"}:
        return PUBLIC / "index.html"
    if path.endswith("/"):
        cand = PUBLIC / path.strip("/") / "index.html"
        if cand.exists():
            return cand
    rel = path.strip("/")
    for cand in (PUBLIC / f"{rel}.html", PUBLIC / rel / "index.html", PUBLIC / rel):
        if cand.is_file():
            return cand
    return None


def sitemap_urls() -> list[str]:
    tree = ET.parse(PUBLIC / "sitemap.xml")
    return [el.text.strip() for el in tree.iterfind(".//sm:loc", NS) if el.text]


def check_page(url: str, html: str) -> dict:
    issues = []
    if not re.search(r"<title[^>]*>", html, re.I):
        issues.append("no title")
    if not CANON_RE.search(html):
        issues.append("no canonical")
    langs = HREFLANG_RE.findall(html)
    # product/home/hub pages should have hreflang; skip only if none expected
    return {
        "url": url,
        "canonical": bool(CANON_RE.search(html)),
        "hreflang": langs,
        "robots_meta": bool(re.search(r'name=["\']robots["\']', html, re.I)),
        "issues": issues,
    }


def local_audit() -> dict:
    urls = sitemap_urls()
    keep = keep_entries()
    keep_abs = []
    for e in keep:
        u = e["url"]
        keep_abs.append(SITE + (u if u.startswith("/") else "/" + u))
    missing_in_sitemap = sorted(set(keep_abs) - set(urls))
    extra_in_sitemap = sorted(set(urls) - set(keep_abs))
    files_missing = []
    page_issues = []
    broken_internal = []
    existing_hrefs = {u[len(SITE):] if u.startswith(SITE) else u for u in urls}
    existing_hrefs.update({e["url"] for e in keep})
    existing_hrefs.add("/")
    existing_hrefs.add("/en/")

    for url in urls:
        path = url_to_file(url)
        if path is None:
            files_missing.append(url)
            continue
        html = path.read_text(encoding="utf-8")
        info = check_page(url, html)
        if info["issues"]:
            page_issues.append(info)
        for href in INTERNAL_RE.findall(html):
            clean = href.split("#", 1)[0].split("?", 1)[0]
            if clean.endswith(".xml") or clean.startswith("/images/") or clean.startswith("/assets/"):
                continue
            if clean.endswith(".html"):
                clean = clean[: -len(".html")]
            # ignore deep assets / mailto already excluded by regex
            file = url_to_file(SITE + clean) if clean.startswith("/") else None
            if file is None and clean not in existing_hrefs:
                # only flag keep-looking paths that 404 locally
                if re.match(r"^/(en/)?(blog|products|export)/", clean) or clean in {
                    "/pepperoni", "/halal", "/kazylyk",
                }:
                    broken_internal.append((url, clean))

    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    robots_ok = (
        "Sitemap: https://pepperoni.tatar/sitemap.xml" in robots
        and "Host: https://pepperoni.tatar" in robots
        and "Disallow: /" not in robots.split("User-agent: *", 1)[-1].split("User-agent:", 1)[0]
    )
    return {
        "mode": "local",
        "sitemap_urls": len(urls),
        "keep_urls": len(keep),
        "keep_missing_from_sitemap": missing_in_sitemap,
        "sitemap_not_in_keep": extra_in_sitemap,
        "html_files_missing": files_missing,
        "page_issues": page_issues[:20],
        "page_issue_count": len(page_issues),
        "sample_broken_internal": broken_internal[:20],
        "broken_internal_count": len(broken_internal),
        "robots_ok": robots_ok,
        "pass": (
            not missing_in_sitemap
            and not files_missing
            and robots_ok
            and not page_issues
        ),
    }


def fetch(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "pepperoni-phase1-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception:
        return 0, "", url


def live_audit() -> dict:
    rows = []
    for path in SAMPLE:
        status, html, final = fetch(SITE + path)
        info = check_page(SITE + path, html) if status == 200 else {
            "url": SITE + path, "issues": [f"http {status}"],
            "canonical": False, "hreflang": [],
        }
        info["http"] = status
        info["final"] = final
        rows.append(info)
    robots_status, robots, _ = fetch(SITE + "/robots.txt")
    sm_status, sm, _ = fetch(SITE + "/sitemap.xml")
    sm_count = sm.count("<loc>") if sm_status == 200 else 0
    return {
        "mode": "live",
        "sample": rows,
        "robots_http": robots_status,
        "sitemap_http": sm_status,
        "sitemap_loc_count": sm_count,
        "pass": all(r.get("http") == 200 for r in rows) and robots_status == 200 and sm_status == 200,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()
    report = live_audit() if ns.live else local_audit()
    if ns.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"phase1_regression_audit [{report['mode']}]: pass={'YES' if report['pass'] else 'NO'}")
        for k, v in report.items():
            if k in {"page_issues", "sample", "sample_broken_internal"}:
                continue
            print(f"  {k}: {v}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
