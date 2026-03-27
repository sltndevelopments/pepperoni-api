#!/usr/bin/env python3
"""
Submit URLs via IndexNow protocol (Bing, Yandex, Seznam, Naver).
IndexNow is the fastest indexing method — no daily limits, batch submission.

Reads ALL URLs from public/sitemap.xml — no hardcoded lists.
New page → appears in Bing/Yandex within hours.

Env: INDEXNOW_KEY (optional, defaults to value below)
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

INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "2164b9a639c7455aad8651dc19e48641")
SITEMAP_FILE = Path(__file__).parent.parent / "public" / "sitemap.xml"
SITEMAP_URL  = "https://pepperoni.tatar/sitemap.xml"
HOST         = "pepperoni.tatar"
BATCH_SIZE   = 100  # IndexNow supports up to 10 000 per batch


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
            root = ET.fromstring(r.read())
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
        print(f"📋 Fetched {len(urls)} URLs")
        return urls
    except Exception as e:
        print(f"❌ Could not load sitemap: {e}")
        return []


def submit_batch(urls: list[str], endpoint: str) -> str:
    body = json.dumps({
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://{HOST}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"✅ {r.status} — {len(urls)} URLs"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"⚠️  {e.code}: {body[:150]}"
    except Exception as e:
        return f"⚠️  {e}"


def main():
    urls = load_sitemap_urls()
    if not urls:
        print("❌ No URLs to submit")
        sys.exit(1)

    print(f"\n📤 Submitting {len(urls)} URLs via IndexNow...\n")

    # IndexNow endpoints (one submission notifies all participating engines)
    endpoints = [
        "https://api.indexnow.org/indexnow",  # notifies Bing, Yandex, Seznam, Naver
    ]

    total_ok = 0
    for endpoint in endpoints:
        print(f"  → {endpoint}")
        # Send in batches
        for i in range(0, len(urls), BATCH_SIZE):
            batch = urls[i : i + BATCH_SIZE]
            result = submit_batch(batch, endpoint)
            print(f"    Batch {i//BATCH_SIZE + 1}: {result}")
            if result.startswith("✅"):
                total_ok += len(batch)
            time.sleep(1)

    print(f"\n✅ IndexNow done: {total_ok}/{len(urls)} URLs submitted")
    print("ℹ️  Bing, Yandex, Seznam will start crawling within hours")


if __name__ == "__main__":
    main()
