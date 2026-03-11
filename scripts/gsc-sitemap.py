#!/usr/bin/env python3
"""
Submit sitemap to Google Search Console via API.
Requires:
1. Search Console API enabled in Google Cloud
2. Service account added as user in GSC (Settings → Users and permissions)
3. GSC_SERVICE_ACCOUNT_KEY env var with service account JSON
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
import time

# Sites to submit sitemap for (URL-prefix properties in GSC)
SITES = [
    ("https://pepperoni.tatar/", "https://pepperoni.tatar/sitemap.xml"),
    ("https://api.pepperoni.tatar/", "https://api.pepperoni.tatar/sitemap.xml"),
]


def get_access_token(service_account_info: dict) -> str:
    """Get OAuth2 token with webmasters scope for Search Console API."""
    import base64

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    now = int(time.time())
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": service_account_info["client_email"],
        "scope": "https://www.googleapis.com/auth/webmasters",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}".encode()

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

    jwt_token = f"{header}.{payload}.{sig_b64}"
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def submit_sitemap(site_url: str, feedpath: str, access_token: str) -> str:
    """Submit sitemap to GSC. PUT sites/{siteUrl}/sitemaps/{feedpath}"""
    site_enc = urllib.parse.quote(site_url, safe="")
    feed_enc = urllib.parse.quote(feedpath, safe="")
    url = f"https://www.googleapis.com/webmasters/v3/sites/{site_enc}/sitemaps/{feed_enc}"

    req = urllib.request.Request(url, data=b"", method="PUT")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Length", "0")

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return f"✅ {site_url} → {feedpath}"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 404:
            return f"⚠️  {site_url}: property not found. Add SA as user in GSC."
        if e.code == 403:
            return f"⚠️  {site_url}: 403. Enable Search Console API, add SA to GSC."
        return f"⚠️  {site_url} → {e.code}: {body[:150]}"


def main():
    key_json = os.environ.get("GSC_SERVICE_ACCOUNT_KEY")
    if not key_json:
        key_file = os.path.join(os.path.dirname(__file__), "gsc-key.json")
        if os.path.exists(key_file):
            key_json = open(key_file).read()
        else:
            print("❌ GSC_SERVICE_ACCOUNT_KEY env var not set and gsc-key.json not found")
            sys.exit(1)

    sa = json.loads(key_json)
    print(f"🔑 Service account: {sa['client_email']}")
    print("🔐 Getting token (webmasters scope)...")

    try:
        token = get_access_token(sa)
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)

    print(f"\n📤 Submitting {len(SITES)} sitemap(s) to Google Search Console...\n")
    for site_url, feedpath in SITES:
        result = submit_sitemap(site_url, feedpath, token)
        print(f"  {result}")
        time.sleep(0.5)

    print("\n✅ Done. Check GSC → Sitemaps to verify.")


if __name__ == "__main__":
    main()
