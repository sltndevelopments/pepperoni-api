#!/usr/bin/env python3
"""
Submit URLs to Google Indexing API after deploy.
Uses service account credentials from GSC_SERVICE_ACCOUNT_KEY env var.
Indexing API: 68 URLs (main, geo, commercial, key products).
"""

import json
import os
import sys
import urllib.request
import urllib.error
import time

# All URLs to submit for indexing
URLS = [
    # Main pages
    "https://pepperoni.tatar/",
    "https://pepperoni.tatar/pepperoni",
    "https://pepperoni.tatar/en/",
    "https://pepperoni.tatar/en/pepperoni",

    # Commercial pages
    "https://pepperoni.tatar/pepperoni-optom",
    "https://pepperoni.tatar/pepperoni-dlya-pizzerii",
    "https://pepperoni.tatar/pepperoni-dlya-horeca",
    "https://pepperoni.tatar/pepperoni-private-label",
    "https://pepperoni.tatar/pepperoni-v-narezke",

    # Geo pages - Russia
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

    # Geo pages - CIS
    "https://pepperoni.tatar/geo/pepperoni-kazakhstan",
    "https://pepperoni.tatar/geo/pepperoni-uzbekistan",
    "https://pepperoni.tatar/geo/pepperoni-belarus",
    "https://pepperoni.tatar/geo/pepperoni-armenia",
    "https://pepperoni.tatar/geo/pepperoni-azerbaijan",
    "https://pepperoni.tatar/geo/pepperoni-kyrgyzstan",

    # Burger patties geo pages - Russia
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

    # Burger patties geo pages - CIS
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-kazakhstan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-uzbekistan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-belarus",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-armenia",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-azerbaijan",
    "https://pepperoni.tatar/geo/kotlety-dlya-burgerov-kyrgyzstan",

    # Hot dog sausages geo pages - Russia
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

    # Hot dog sausages geo pages - CIS
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-kazakhstan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-uzbekistan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-belarus",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-armenia",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-azerbaijan",
    "https://pepperoni.tatar/geo/sosiki-dlya-hotdog-kyrgyzstan",

    # Key product pages (pepperoni, sausages)
    "https://pepperoni.tatar/products/kd-001",
    "https://pepperoni.tatar/products/kd-002",
    "https://pepperoni.tatar/products/kd-014",
    "https://pepperoni.tatar/products/kd-015",
    "https://pepperoni.tatar/products/kd-017",
    "https://pepperoni.tatar/products/kd-018",
]


def get_access_token(service_account_info: dict) -> str:
    """Get OAuth2 access token using JWT for service account."""
    import base64
    import hashlib
    import hmac
    import struct

    # JWT header
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    # JWT payload
    now = int(time.time())
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": service_account_info["client_email"],
        "scope": "https://www.googleapis.com/auth/indexing",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    # Sign with RS256
    signing_input = f"{header}.{payload}".encode()

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend

        private_key = serialization.load_pem_private_key(
            service_account_info["private_key"].encode(),
            password=None,
            backend=default_backend()
        )
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    except ImportError:
        # Fallback: use google-auth if cryptography not available
        print("  ℹ️  cryptography not found, trying google-auth...")
        raise

    jwt_token = f"{header}.{payload}.{sig_b64}"

    # Exchange JWT for access token
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def submit_url(url: str, access_token: str) -> str:
    """Submit a single URL to Google Indexing API."""
    body = json.dumps({
        "url": url,
        "type": "URL_UPDATED"
    }).encode()

    req = urllib.request.Request(
        "https://indexing.googleapis.com/v3/urlNotifications:publish",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            return f"✅ {result.get('urlNotificationMetadata', {}).get('url', url)}"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"⚠️  {url} → {e.code}: {body[:120]}"


def main():
    import urllib.parse

    # Load service account credentials
    key_json = os.environ.get("GSC_SERVICE_ACCOUNT_KEY")
    if not key_json:
        # Try reading from file (local dev)
        key_file = os.path.join(os.path.dirname(__file__), "gsc-key.json")
        if os.path.exists(key_file):
            key_json = open(key_file).read()
        else:
            print("❌ GSC_SERVICE_ACCOUNT_KEY env var not set and gsc-key.json not found")
            sys.exit(1)

    service_account = json.loads(key_json)
    print(f"🔑 Service account: {service_account['client_email']}")

    # Get access token
    print("🔐 Getting access token...")
    try:
        token = get_access_token(service_account)
    except Exception as e:
        print(f"❌ Failed to get token: {e}")
        sys.exit(1)

    # Submit all URLs
    print(f"\n📤 Submitting {len(URLS)} URLs to Google Indexing API...\n")
    ok = 0
    fail = 0
    for url in URLS:
        result = submit_url(url, token)
        print(f"  {result}")
        if result.startswith("✅"):
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)  # Rate limit: stay well under 200 req/day

    print(f"\n{'✅' if fail == 0 else '⚠️ '} Done: {ok} submitted, {fail} errors")


if __name__ == "__main__":
    main()
