#!/usr/bin/env python3
"""
Submit URLs via:
1. IndexNow protocol (Bing, Yandex, Seznam) — batch submission, no daily limit
2. Bing Webmaster Tools API — direct URL submission

Environment vars:
  INDEXNOW_KEY     — IndexNow API key (same as filename in public/)
  BING_CLIENT_ID   — Bing WM OAuth Client ID
  BING_CLIENT_SECRET — Bing WM OAuth Client Secret
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import time

INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "2164b9a639c7455aad8651dc19e48641")
BING_CLIENT_ID = os.environ.get("BING_CLIENT_ID", "")
BING_CLIENT_SECRET = os.environ.get("BING_CLIENT_SECRET", "")

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


def submit_indexnow(urls: list, key: str) -> str:
    """Submit all URLs at once via IndexNow (Bing + Yandex + Seznam)."""
    body = json.dumps({
        "host": "pepperoni.tatar",
        "key": key,
        "keyLocation": f"https://pepperoni.tatar/{key}.txt",
        "urlList": urls,
    }).encode()

    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"✅ IndexNow: {len(urls)} URLs → {r.status}"
    except urllib.error.HTTPError as e:
        body_resp = e.read().decode()
        return f"⚠️  IndexNow {e.code}: {body_resp[:200]}"


def get_bing_token(client_id: str, client_secret: str) -> str:
    """Get Bing Webmaster API OAuth token."""
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://ssl.bing.com/webmaster/api/.default",
    }).encode()

    req = urllib.request.Request(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def submit_bing_urls(urls: list, token: str) -> str:
    """Submit URLs to Bing Webmaster Tools API."""
    body = json.dumps({
        "siteUrl": "https://pepperoni.tatar/",
        "urlList": urls[:500],  # Bing limit: 500 per request
    }).encode()

    req = urllib.request.Request(
        "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlbatch",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            result = json.loads(r.read())
            return f"✅ Bing WM API: {len(urls)} URLs submitted"
    except urllib.error.HTTPError as e:
        body_resp = e.read().decode()
        return f"⚠️  Bing WM {e.code}: {body_resp[:200]}"


def main():
    print(f"🌐 IndexNow key: {INDEXNOW_KEY}")
    print(f"📋 Total URLs: {len(URLS)}\n")

    # 1. IndexNow — batch submit to Bing + Yandex + others
    print("📤 Step 1: IndexNow (Bing + Yandex + Seznam)...")
    result = submit_indexnow(URLS, INDEXNOW_KEY)
    print(f"  {result}\n")

    # 2. Bing Webmaster API (direct, if credentials provided)
    if BING_CLIENT_ID and BING_CLIENT_SECRET:
        print("📤 Step 2: Bing Webmaster Tools API...")
        try:
            token = get_bing_token(BING_CLIENT_ID, BING_CLIENT_SECRET)
            result = submit_bing_urls(URLS, token)
            print(f"  {result}\n")
        except Exception as e:
            print(f"  ⚠️  Bing WM API failed: {e}\n")
    else:
        print("ℹ️  Bing WM API: credentials not provided, skipping.\n")

    print("✅ Done.")


if __name__ == "__main__":
    main()
