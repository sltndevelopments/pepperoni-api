#!/usr/bin/env python3
"""
Submit URLs to Yandex Webmaster recrawl queue.

Reads ALL URLs from public/sitemap.xml — no hardcoded lists.
Daily limit: 150 URLs/day per host (Yandex API quota).
Submits sitemap first, then top URLs by priority.
Rotates through all pages over multiple days automatically.

Env: YANDEX_WM_TOKEN (OAuth token)
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_ID      = os.environ.get("YANDEX_USER_ID", "238539242")
HOST_ID      = os.environ.get("YANDEX_HOST_ID", "https:pepperoni.tatar:443")
SITEMAP_URL  = "https://pepperoni.tatar/sitemap.xml"
SITEMAP_FILE = Path(__file__).parent.parent / "public" / "sitemap.xml"
WATCHLIST = Path(__file__).resolve().parent.parent / "data" / "commercial_watchlist.json"
ORIGIN = "https://pepperoni.tatar"


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


def _find_sitemap_id(token: str) -> str | None:
    """Resolve the registered sitemap_id for SITEMAP_URL.

    The Yandex Webmaster v4 recrawl endpoint takes a sitemap_id, NOT the
    URL-encoded sitemap URL. Passing an encoded URL (with %2F) makes the
    server reject the request with '400 Ambiguous URI path separator'.
    """
    host_enc = urllib.parse.quote(HOST_ID, safe="")
    data = api_get(token, f"/user/{USER_ID}/hosts/{host_enc}/sitemaps")
    for sm in data.get("sitemaps", []):
        if sm.get("sitemap_url") == SITEMAP_URL:
            return sm.get("sitemap_id")
    # Fallback: first sitemap registered for the host
    sitemaps = data.get("sitemaps", [])
    return sitemaps[0].get("sitemap_id") if sitemaps else None


def submit_sitemap(token: str) -> str:
    sitemap_id = _find_sitemap_id(token)
    if not sitemap_id:
        return f"⚠️  Sitemap not registered in Yandex Webmaster: {SITEMAP_URL}"
    host_enc = urllib.parse.quote(HOST_ID, safe="")
    url = (
        f"https://api.webmaster.yandex.net/v4"
        f"/user/{USER_ID}/hosts/{host_enc}/sitemaps/{sitemap_id}/recrawl"
    )
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Authorization", f"OAuth {token}")
    req.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            # 202 Accepted = queued; recrawl may be rate-limited (allowed=false)
            return f"✅ Sitemap recrawl queued: {SITEMAP_URL} (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        # 409 = a recrawl is already pending for this sitemap (rate-limited by
        # Yandex). That is expected on frequent runs and is not an error.
        if e.code == 409:
            return f"ℹ️  Sitemap recrawl already pending (Yandex rate limit): {SITEMAP_URL}"
        return f"⚠️  Sitemap {e.code}: {e.read().decode()[:100]}"


def _abs(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if u.startswith("http"):
        return u
    if not u.startswith("/"):
        u = "/" + u
    return ORIGIN + u


def load_hot_urls() -> list[str]:
    out = [
        f"{ORIGIN}/",
        f"{ORIGIN}/pepperoni",
        f"{ORIGIN}/pepperoni-dlya-pizzerii",
        f"{ORIGIN}/llms.txt",
        f"{ORIGIN}/llms-full.txt",
        f"{ORIGIN}/en/llms.txt",
        f"{ORIGIN}/.well-known/llms.txt",
        f"{ORIGIN}/en/pepperoni",
    ]
    try:
        data = json.loads(WATCHLIST.read_text(encoding="utf-8"))
        for it in data.get("items") or []:
            page = it.get("page") or ""
            if page:
                out.append(_abs(page))
    except Exception:
        pass
    seen: set[str] = set()
    uniq = []
    for u in out:
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hot", action="store_true", help="Only money/watchlist URLs + sitemap recrawl")
    ap.add_argument("--url", action="append", default=[], help="Extra URL/path to recrawl")
    args = ap.parse_args()

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

    if args.hot or args.url:
        all_urls = load_hot_urls() if args.hot else []
        for u in args.url:
            all_urls.append(_abs(u))
        # unique
        seen: set[str] = set()
        uniq = []
        for u in all_urls:
            if u and u not in seen:
                seen.add(u)
                uniq.append(u)
        all_urls = uniq
    else:
        all_urls = load_sitemap_urls()
        if not all_urls:
            print("❌ No URLs to submit")
            sys.exit(1)
        all_urls.sort(key=priority_score, reverse=True)

    to_submit = all_urls[:quota]
    skipped = len(all_urls) - len(to_submit)

    print(f"\n📊 Candidates: {len(all_urls)} | Submitting: {len(to_submit)} | Skipped: {skipped}")
    print("\n📤 Submitting to Yandex recrawl queue...\n")

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
    if skipped and not args.hot:
        print(f"ℹ️  {skipped} URLs will rotate in on subsequent days (150/day limit)")


if __name__ == "__main__":
    main()
