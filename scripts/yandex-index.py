#!/usr/bin/env python3
"""
Submit URLs to Yandex Webmaster recrawl queue.

Reads ALL URLs from public/sitemap.xml — no hardcoded lists.
Daily limit: 150 URLs/day per host (Yandex API quota).
Submits sitemap first, then top URLs by priority.
Rotates through all pages over multiple days automatically.

Env: YANDEX_WM_TOKEN (OAuth token)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_ID      = "238539242"
HOST_ID      = "https:pepperoni.tatar:443"
SITEMAP_URL  = "https://pepperoni.tatar/sitemap.xml"
SITEMAP_FILE = Path(__file__).parent.parent / "public" / "sitemap.xml"


def priority_score(url: str) -> int:
    if url in ("https://pepperoni.tatar/", "https://pepperoni.tatar/en/"):
        return 100
    if "/pepperoni" in url and "/blog/" not in url and "/geo/" not in url:
        return 90
    if "/kazylyk" in url or "/bakery" in url:
        return 85
    if "/blog/" in url:
        return 80
    if "/products/" in url:
        return 75
    if "/geo/" in url:
        return 60
    return 50


def load_sitemap_urls() -> list[str]:
    if SITEMAP_FILE.exists():
        tree = ET.parse(str(SITEMAP_FILE))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in tree.findall(".//sm:loc", ns) if loc.text]
        print(f"📋 Loaded {len(urls)} URLs from local sitemap.xml")
        return urls
    print("⚠️  Local sitemap not found, fetching from web...")
    try:
        with urllib.request.urlopen(SITEMAP_URL, timeout=15) as r:
            content = r.read()
        root = ET.fromstring(content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
        print(f"📋 Fetched {len(urls)} URLs from {SITEMAP_URL}")
        return urls
    except Exception as e:
        print(f"❌ Could not load sitemap: {e}")
        return []


def api_get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"https://api.webmaster.yandex.net/v4{path}",
        headers={"Authorization": f"OAuth {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️  API {e.code}: {e.read().decode()[:120]}")
        return {}


def check_quota(token: str) -> int:
    host_enc = urllib.parse.quote(HOST_ID, safe="")
    data = api_get(token, f"/user/{USER_ID}/hosts/{host_enc}/recrawl/quota")
    return data.get("quota_remainder", 0)


def submit_url(token: str, url: str) -> str:
    host_enc = urllib.parse.quote(HOST_ID, safe="")
    endpoint = f"https://api.webmaster.yandex.net/v4/user/{USER_ID}/hosts/{host_enc}/recrawl/queue/"
    body = json.dumps({"url": url}).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Authorization": f"OAuth {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            return f"✅ {url} (task: {result.get('task_id', 'ok')})"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 429:
            return "⛔ QUOTA_EXCEEDED"
        return f"⚠️  {url} → {e.code}: {body[:100]}"


def submit_sitemap(token: str) -> str:
    host_enc    = urllib.parse.quote(HOST_ID, safe="")
    sitemap_enc = urllib.parse.quote(SITEMAP_URL, safe="")
    url = (
        f"https://api.webmaster.yandex.net/v4"
        f"/user/{USER_ID}/hosts/{host_enc}/sitemaps/{sitemap_enc}/recrawl"
    )
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Authorization", f"OAuth {token}")
    req.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(req, timeout=15):
            return f"✅ Sitemap submitted: {SITEMAP_URL}"
    except urllib.error.HTTPError as e:
        return f"⚠️  Sitemap {e.code}: {e.read().decode()[:100]}"


def main():
    token = os.environ.get("YANDEX_WM_TOKEN")
    if not token:
        print("❌ YANDEX_WM_TOKEN not set")
        sys.exit(1)

    print(f"🔑 User: {USER_ID} | Host: {HOST_ID}")

    # Submit sitemap (always, doesn't count against URL quota)
    print("\n📋 Submitting sitemap...")
    print(f"  {submit_sitemap(token)}")

    # Check quota
    quota = check_quota(token)
    print(f"📊 Quota remaining today: {quota}/150")
    if quota == 0:
        print("⛔ No quota remaining. Sitemap submitted — Yandex will crawl from it.")
        sys.exit(0)

    # Load all URLs from sitemap
    all_urls = load_sitemap_urls()
    if not all_urls:
        print("❌ No URLs to submit")
        sys.exit(1)

    # Sort by priority, submit up to quota
    all_urls.sort(key=priority_score, reverse=True)
    to_submit = all_urls[:quota]
    skipped   = len(all_urls) - len(to_submit)

    print(f"\n📊 Total in sitemap: {len(all_urls)} | Submitting: {len(to_submit)} | Skipped: {skipped}")
    print(f"\n📤 Submitting to Yandex recrawl queue...\n")

    ok = fail = 0
    for url in to_submit:
        result = submit_url(token, url)
        print(f"  {result}")
        if result.startswith("✅"):
            ok += 1
        elif "QUOTA_EXCEEDED" in result:
            print("  ⛔ Quota exhausted, stopping.")
            break
        else:
            fail += 1
        time.sleep(0.3)

    print(f"\n{'✅' if fail == 0 else '⚠️ '} Done: {ok} submitted, {fail} errors")
    if skipped:
        print(f"ℹ️  {skipped} URLs will rotate in on subsequent days (150/day limit)")


if __name__ == "__main__":
    main()
