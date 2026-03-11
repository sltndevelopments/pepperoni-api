#!/usr/bin/env python3
"""
Submit URLs to Yandex Webmaster recrawl queue.
Uses YANDEX_WM_TOKEN env var (OAuth token).
Limit: 150 URLs/day per host.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import time

USER_ID = "238539242"
HOST_ID = "https:pepperoni.tatar:443"

# All URLs to submit for Yandex recrawl
URLS = [
    # Main pages
    "https://pepperoni.tatar/",
    "https://pepperoni.tatar/pepperoni",
    "https://pepperoni.tatar/en/",
    "https://pepperoni.tatar/en/pepperoni",

    # Category pages
    "https://pepperoni.tatar/about",
    "https://pepperoni.tatar/delivery",
    "https://pepperoni.tatar/faq",
    "https://pepperoni.tatar/kazylyk",
    "https://pepperoni.tatar/bakery",
    "https://pepperoni.tatar/pizzeria",

    # Commercial pages
    "https://pepperoni.tatar/pepperoni-optom",
    "https://pepperoni.tatar/pepperoni-dlya-pizzerii",
    "https://pepperoni.tatar/pepperoni-dlya-horeca",
    "https://pepperoni.tatar/pepperoni-private-label",
    "https://pepperoni.tatar/pepperoni-v-narezke",

    # Geo pages — pepperoni
    "https://pepperoni.tatar/geo/pepperoni-moskva",
    "https://pepperoni.tatar/geo/pepperoni-spb",
    "https://pepperoni.tatar/geo/pepperoni-kazan",
    "https://pepperoni.tatar/geo/pepperoni-ufa",
    "https://pepperoni.tatar/geo/pepperoni-ekaterinburg",
    "https://pepperoni.tatar/geo/pepperoni-yanao",
    "https://pepperoni.tatar/geo/pepperoni-dagestan",
    "https://pepperoni.tatar/geo/pepperoni-mahachkala",
    "https://pepperoni.tatar/geo/pepperoni-grozny",
    "https://pepperoni.tatar/geo/pepperoni-sochi",
    "https://pepperoni.tatar/geo/pepperoni-krasnodar",
    "https://pepperoni.tatar/geo/pepperoni-astrahan",
    "https://pepperoni.tatar/geo/pepperoni-kazakhstan",
    "https://pepperoni.tatar/geo/pepperoni-uzbekistan",
    "https://pepperoni.tatar/geo/pepperoni-belarus",
    "https://pepperoni.tatar/geo/pepperoni-armenia",
    "https://pepperoni.tatar/geo/pepperoni-azerbaijan",
    "https://pepperoni.tatar/geo/pepperoni-kyrgyzstan",

    # Geo pages — burger patties
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-moskva",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-spb",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-kazan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-ufa",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-ekaterinburg",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-yanao",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-dagestan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-mahachkala",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-grozny",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-sochi",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-krasnodar",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-astrahan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-kazakhstan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-uzbekistan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-belarus",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-armenia",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-azerbaijan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-kyrgyzstan",

    # Geo pages — hot dog sausages
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-moskva",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-spb",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-kazan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-ufa",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-ekaterinburg",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-yanao",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-dagestan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-mahachkala",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-grozny",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-sochi",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-krasnodar",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-astrahan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-kazakhstan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-uzbekistan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-belarus",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-armenia",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-azerbaijan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-kyrgyzstan",
]


def check_quota(token: str, user_id: str, host_id: str) -> int:
    host_enc = urllib.parse.quote(host_id, safe="")
    url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_enc}/recrawl/quota"
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
            return d.get("quota_remainder", 0)
    except Exception as e:
        print(f"⚠️  Could not check quota: {e}")
        return 0


def submit_url(token: str, user_id: str, host_id: str, url: str) -> str:
    host_enc = urllib.parse.quote(host_id, safe="")
    endpoint = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_enc}/recrawl/queue/"
    body = json.dumps({"url": url}).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"OAuth {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            task_id = result.get("task_id", "ok")
            return f"✅ {url} (task: {task_id})"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 429:
            return f"⛔ {url} → quota exceeded"
        return f"⚠️  {url} → {e.code}: {body[:120]}"


def submit_sitemap(token: str, user_id: str, host_id: str, sitemap_url: str) -> str:
    """Submit sitemap for priority recrawl (Yandex API v4.1)."""
    host_enc = urllib.parse.quote(host_id, safe="")
    sitemap_enc = urllib.parse.quote(sitemap_url, safe="")
    url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_enc}/sitemaps/{sitemap_enc}/recrawl"
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Authorization", f"OAuth {token}")
    req.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"✅ Sitemap submitted: {sitemap_url}"
    except urllib.error.HTTPError as e:
        return f"⚠️  Sitemap {e.code}: {e.read().decode()[:120]}"


def main():
    token = os.environ.get("YANDEX_WM_TOKEN")
    if not token:
        print("❌ YANDEX_WM_TOKEN env var not set")
        sys.exit(1)

    print(f"🔑 User ID: {USER_ID}")
    print(f"🌐 Host: {HOST_ID}")

    # Check quota
    quota = check_quota(token, USER_ID, HOST_ID)
    print(f"📊 Quota remaining: {quota}/150 URLs today")

    if quota == 0:
        print("⛔ No quota remaining for today. Try again tomorrow.")
        sys.exit(0)

    # Submit sitemap first
    print("\n📋 Submitting sitemap...")
    result = submit_sitemap(token, USER_ID, HOST_ID, "https://pepperoni.tatar/sitemap.xml")
    print(f"  {result}")

    # Submit URLs (up to quota limit)
    urls_to_submit = URLS[:quota]
    skipped = len(URLS) - len(urls_to_submit)

    print(f"\n📤 Submitting {len(urls_to_submit)} URLs to Yandex recrawl queue...\n")
    ok = 0
    fail = 0
    for url in urls_to_submit:
        result = submit_url(token, USER_ID, HOST_ID, url)
        print(f"  {result}")
        if result.startswith("✅"):
            ok += 1
        elif "quota exceeded" in result:
            print("  ⛔ Quota exhausted, stopping.")
            break
        else:
            fail += 1
        time.sleep(0.3)

    print(f"\n{'✅' if fail == 0 else '⚠️ '} Done: {ok} submitted, {fail} errors", end="")
    if skipped > 0:
        print(f", {skipped} skipped (quota limit)")
    else:
        print()


if __name__ == "__main__":
    main()
