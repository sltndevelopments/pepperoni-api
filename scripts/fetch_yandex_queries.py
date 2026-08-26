#!/usr/bin/env python3
"""
Fetch search query data from Yandex Webmaster API.
Saves results to SQLite via seo_db.py.
Env: YANDEX_WM_TOKEN (OAuth token)
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from seo_db import get_conn, init_db

# USER_ID / HOST_ID are resolved automatically from the token (see resolve_*),
# so a token swap never breaks the script. Env overrides allowed for edge cases.
USER_ID  = os.environ.get("YANDEX_USER_ID", "")          # auto-resolved if empty
HOST_ID  = os.environ.get("YANDEX_HOST_ID", "")          # auto-resolved if empty
HOST_DOMAIN = os.environ.get("YANDEX_HOST_DOMAIN", "pepperoni.tatar")
BASE_URL = "https://api.webmaster.yandex.net/v4"
DAYS_BACK = int(os.environ.get("YANDEX_DAYS_BACK", "30"))


def api_get(token: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"OAuth {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Yandex API {e.code} on {path}: {body}", file=sys.stderr)
        return {}


def resolve_user_id(token: str) -> str:
    """Yandex returns the authenticated user_id — no need to hardcode it."""
    if USER_ID:
        return USER_ID
    data = api_get(token, "/user/")
    return str(data.get("user_id", "")) if data else ""


def resolve_host_id(token: str, user_id: str) -> str:
    """Find our verified host in this account; warn clearly if it's missing."""
    if HOST_ID:
        return HOST_ID
    data = api_get(token, f"/user/{user_id}/hosts/")
    hosts = data.get("hosts", []) if data else []
    if not hosts:
        print("❌ No hosts in this Yandex Webmaster account. Add & verify "
              f"'{HOST_DOMAIN}' at webmaster.yandex.ru under the SAME account "
              "that issued this token.", file=sys.stderr)
        return ""
    target = HOST_DOMAIN.lower().strip().rstrip(".")
    exact = []
    for host in hosts:
        urls = [host.get("unicode_host_url", ""), host.get("ascii_host_url", "")]
        names = {
            (urllib.parse.urlparse(url).hostname or "").lower().rstrip(".")
            for url in urls
        }
        if target in names:
            exact.append(host)
    exact.sort(key=lambda host: host.get("verified") is True, reverse=True)
    if exact:
        selected = exact[0]
        if selected.get("verified") is False:
            print(f"⚠️  Host '{HOST_DOMAIN}' found but NOT verified — verify it "
                  "in Yandex Webmaster.", file=sys.stderr)
        return selected.get("host_id", "")
    print(f"❌ '{HOST_DOMAIN}' not among this account's hosts: "
          f"{[h.get('ascii_host_url') for h in hosts]}", file=sys.stderr)
    return ""


def fetch_queries(token: str, date_from: str, date_to: str) -> list:
    """Fetch popular search queries via Yandex Webmaster query stats API."""
    limit = 500
    offset = 0
    queries = []
    while True:
        path = (
            f"/user/{USER_ID}/hosts/{urllib.parse.quote(HOST_ID, safe='')}"
            f"/search-queries/popular"
            f"?query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS"
            f"&order_by=TOTAL_SHOWS"
            f"&date_from={date_from}&date_to={date_to}"
            f"&limit={limit}&offset={offset}"
        )
        data = api_get(token, path)
        batch = data.get("queries", []) if data else []
        queries.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return queries


def fetch_query_history(token: str, date_from: str, date_to: str) -> list:
    """Fetch query history with position data."""
    path = (
        f"/user/{USER_ID}/hosts/{urllib.parse.quote(HOST_ID, safe='')}"
        f"/search-queries/all/history"
        f"?query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS"
        f"&query_indicator=AVG_SHOW_POSITION&query_indicator=AVG_CLICK_POSITION"
        f"&date_from={date_from}&date_to={date_to}"
    )
    data = api_get(token, path)
    return data.get("text_indicator_to_values", [])


def save_queries(queries: list, fetched_at: str, date: str):
    conn = get_conn()
    inserted = 0
    for q in queries:
        query_text = q.get("query_text", "")
        if not query_text:
            continue
        raw_indicators = q.get("indicators") or {}
        if isinstance(raw_indicators, dict):
            indicators = raw_indicators
        else:
            indicators = {
                item["query_indicator"]: item["value"]
                for item in raw_indicators
                if isinstance(item, dict)
                and "query_indicator" in item
                and "value" in item
            }
        clicks = int(float(indicators.get("TOTAL_CLICKS", 0) or 0))
        impressions = int(float(indicators.get("TOTAL_SHOWS", 0) or 0))
        ctr = clicks / impressions if impressions else 0.0
        try:
            conn.execute(
                """INSERT INTO yandex_queries
                   (fetched_at, date, query, clicks, impressions, ctr, position)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(date, query) DO UPDATE SET
                     fetched_at=excluded.fetched_at,
                     clicks=excluded.clicks,
                     impressions=excluded.impressions,
                     ctr=excluded.ctr,
                     position=excluded.position""",
                (
                    fetched_at, date, query_text,
                    clicks,
                    impressions,
                    ctr,
                    float(indicators.get("AVG_SHOW_POSITION", 0)),
                ),
            )
            inserted += 1
        except Exception as ex:
            print(f"  DB insert error: {ex}", file=sys.stderr)
    if any(
        float((q.get("indicators") or {}).get("TOTAL_SHOWS", 0) or 0) > 0
        for q in queries
        if isinstance(q.get("indicators"), dict)
    ):
        conn.execute(
            "DELETE FROM yandex_queries WHERE clicks = 0 AND impressions = 0")
    conn.commit()
    conn.close()
    return inserted


def main():
    global USER_ID, HOST_ID
    token = os.environ.get("YANDEX_WM_TOKEN", "")
    if not token:
        print("❌ YANDEX_WM_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    USER_ID = resolve_user_id(token)
    if not USER_ID:
        print("❌ Could not resolve Yandex user_id (bad/expired token).", file=sys.stderr)
        sys.exit(1)
    HOST_ID = resolve_host_id(token, USER_ID)
    if not HOST_ID:
        # host missing/unverified — resolve_host_id already explained why
        sys.exit(2)
    print(f"  user_id={USER_ID} host_id={HOST_ID}")

    init_db()

    now = datetime.now(timezone.utc)
    date_to   = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    date_from = (now - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    fetched_at = now.isoformat()

    print(f"📊 Fetching Yandex queries {date_from} → {date_to} …")
    queries = fetch_queries(token, date_from, date_to)
    print(f"  Got {len(queries)} queries from Yandex")

    inserted = save_queries(queries, fetched_at, date_to)
    print(f"  Saved {inserted} new rows to DB")


if __name__ == "__main__":
    main()
