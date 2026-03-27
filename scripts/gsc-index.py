#!/usr/bin/env python3
"""
Submit URLs to Google Indexing API.

Reads ALL URLs from public/sitemap.xml — no hardcoded lists.
Priority order: newest blog articles first, then products, geo, static.
Daily limit: 200 URLs/day (Google quota). Submits top-200 by priority.

Env: GSC_SERVICE_ACCOUNT_KEY (service account JSON)
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

SITEMAP_URL  = "https://pepperoni.tatar/sitemap.xml"
SITEMAP_FILE = Path(__file__).parent.parent / "public" / "sitemap.xml"
DAILY_LIMIT  = 180  # stay under 200/day hard limit

# Priority for submission order (higher = submit first)
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
    """Load URLs from local sitemap.xml (generated fresh before this step)."""
    if SITEMAP_FILE.exists():
        tree = ET.parse(str(SITEMAP_FILE))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in tree.findall(".//sm:loc", ns) if loc.text]
        print(f"📋 Loaded {len(urls)} URLs from local sitemap.xml")
        return urls
    # Fallback: fetch from web
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


def get_access_token(sa: dict) -> str:
    import base64

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    now = int(time.time())
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/indexing",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}".encode()

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    pk = serialization.load_pem_private_key(
        sa["private_key"].encode(), password=None, backend=default_backend()
    )
    sig = pk.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    jwt_token = f"{header}.{payload}.{sig_b64}"
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def submit_url(url: str, token: str) -> str:
    body = json.dumps({"url": url, "type": "URL_UPDATED"}).encode()
    req = urllib.request.Request(
        "https://indexing.googleapis.com/v3/urlNotifications:publish",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            return f"✅ {result.get('urlNotificationMetadata', {}).get('url', url)}"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 429:
            return f"⛔ QUOTA_EXCEEDED"
        return f"⚠️  {url} → {e.code}: {body[:100]}"


def main():
    key_json = os.environ.get("GSC_SERVICE_ACCOUNT_KEY")
    if not key_json:
        key_file = Path(__file__).parent / "gsc-key.json"
        if key_file.exists():
            key_json = key_file.read_text()
        else:
            print("❌ GSC_SERVICE_ACCOUNT_KEY not set")
            sys.exit(1)

    sa = json.loads(key_json)
    print(f"🔑 Service account: {sa['client_email']}")

    # Load all URLs from sitemap
    all_urls = load_sitemap_urls()
    if not all_urls:
        print("❌ No URLs to submit")
        sys.exit(1)

    # Sort by priority, submit top DAILY_LIMIT
    all_urls.sort(key=priority_score, reverse=True)
    to_submit = all_urls[:DAILY_LIMIT]
    skipped   = len(all_urls) - len(to_submit)

    print(f"\n📊 Total in sitemap: {len(all_urls)} | Submitting: {len(to_submit)} | Skipped: {skipped}")
    print("🔐 Getting access token...")
    try:
        token = get_access_token(sa)
    except Exception as e:
        print(f"❌ Token error: {e}")
        sys.exit(1)

    print(f"\n📤 Submitting to Google Indexing API...\n")
    ok = fail = 0
    for url in to_submit:
        result = submit_url(url, token)
        print(f"  {result}")
        if result.startswith("✅"):
            ok += 1
        elif "QUOTA_EXCEEDED" in result:
            print("  ⛔ Daily quota reached, stopping.")
            break
        else:
            fail += 1
        time.sleep(0.35)

    print(f"\n{'✅' if fail == 0 else '⚠️ '} Done: {ok} submitted, {fail} errors")
    if skipped:
        print(f"ℹ️  {skipped} URLs will rotate in on subsequent days")


if __name__ == "__main__":
    main()
