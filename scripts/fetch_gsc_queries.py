#!/usr/bin/env python3
"""
Fetch search query data from Google Search Console API.
Saves results to SQLite via seo_db.py.
Env: GSC_SERVICE_ACCOUNT_KEY (JSON string)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

SITE_URL = "https://pepperoni.tatar/"
DAYS_BACK = int(os.environ.get("GSC_DAYS_BACK", "30"))
ROW_LIMIT = 25000


def _jwt_token(sa_info: dict) -> str:
    """Minimal JWT for Google OAuth2 — no third-party libs required."""
    import base64
    import hashlib
    import hmac

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        USE_CRYPTO = True
    except ImportError:
        USE_CRYPTO = False

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": sa_info["client_email"],
        "scope": "https://www.googleapis.com/auth/webmasters.readonly",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    hdr_b64 = b64url(json.dumps(header).encode())
    pay_b64 = b64url(json.dumps(payload).encode())
    signing_input = f"{hdr_b64}.{pay_b64}".encode()

    if USE_CRYPTO:
        private_key = serialization.load_pem_private_key(
            sa_info["private_key"].encode(), password=None
        )
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    else:
        raise RuntimeError("Install cryptography: pip install cryptography")

    return f"{hdr_b64}.{pay_b64}.{b64url(signature)}"


def get_access_token(sa_info: dict) -> str:
    jwt = _jwt_token(sa_info)
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


import urllib.parse  # noqa: E402 (needed above)


def fetch_queries(token: str, start_date: str, end_date: str) -> list:
    url = (
        f"https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(SITE_URL, safe='')}/searchAnalytics/query"
    )
    body = json.dumps({
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query", "page", "country", "device"],
        "rowLimit": ROW_LIMIT,
        "startRow": 0,
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()).get("rows", [])
    except urllib.error.HTTPError as e:
        print(f"  GSC API error {e.code}: {e.read().decode()}", file=sys.stderr)
        return []


def save_rows(rows: list, fetched_at: str, start_date: str):
    conn = get_conn()
    inserted = 0
    for row in rows:
        keys = row.get("keys", [])
        query   = keys[0] if len(keys) > 0 else ""
        page    = keys[1] if len(keys) > 1 else ""
        country = keys[2] if len(keys) > 2 else ""
        device  = keys[3] if len(keys) > 3 else ""
        try:
            conn.execute(
                """INSERT OR IGNORE INTO gsc_queries
                   (fetched_at, date, query, page, country, device,
                    clicks, impressions, ctr, position)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    fetched_at, start_date, query, page, country, device,
                    row.get("clicks", 0),
                    row.get("impressions", 0),
                    row.get("ctr", 0),
                    row.get("position", 0),
                ),
            )
            inserted += 1
        except Exception as ex:
            print(f"  DB insert error: {ex}", file=sys.stderr)
    conn.commit()
    conn.close()
    return inserted


def main():
    sa_raw = os.environ.get("GSC_SERVICE_ACCOUNT_KEY", "")
    if not sa_raw:
        print("❌ GSC_SERVICE_ACCOUNT_KEY not set", file=sys.stderr)
        sys.exit(1)

    sa_info = json.loads(sa_raw)
    init_db()

    now = datetime.now(timezone.utc)
    end_date   = (now - timedelta(days=3)).strftime("%Y-%m-%d")  # GSC lags ~3 days
    start_date = (now - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    fetched_at = now.isoformat()

    print(f"📊 Fetching GSC queries {start_date} → {end_date} …")
    token = get_access_token(sa_info)
    rows  = fetch_queries(token, start_date, end_date)
    print(f"  Got {len(rows)} rows from GSC")

    inserted = save_rows(rows, fetched_at, start_date)
    print(f"  Saved {inserted} new rows to DB")


if __name__ == "__main__":
    main()
