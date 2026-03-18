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

USER_ID  = "238539242"
HOST_ID  = "https:pepperoni.tatar:443"
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


def fetch_queries(token: str, date_from: str, date_to: str) -> list:
    """Fetch popular search queries via Yandex Webmaster query stats API."""
    path = (
        f"/user/{USER_ID}/hosts/{urllib.parse.quote(HOST_ID, safe='')}"
        f"/search-queries/popular"
        f"?query_indicator=TOTAL_SHOWS&query_indicator=TOTAL_CLICKS"
        f"&order_by=TOTAL_SHOWS"
        f"&date_from={date_from}&date_to={date_to}&limit=500&offset=0"
    )
    data = api_get(token, path)
    return data.get("queries", [])


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
        indicators = {i["query_indicator"]: i["value"] for i in q.get("indicators", []) if isinstance(i, dict)}
        try:
            conn.execute(
                """INSERT OR IGNORE INTO yandex_queries
                   (fetched_at, date, query, clicks, impressions, ctr, position)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    fetched_at, date, query_text,
                    int(indicators.get("TOTAL_CLICKS", 0)),
                    int(indicators.get("TOTAL_SHOWS", 0)),
                    0.0,
                    float(indicators.get("AVG_SHOW_POSITION", 0)),
                ),
            )
            inserted += 1
        except Exception as ex:
            print(f"  DB insert error: {ex}", file=sys.stderr)
    conn.commit()
    conn.close()
    return inserted


def main():
    token = os.environ.get("YANDEX_WM_TOKEN", "")
    if not token:
        print("❌ YANDEX_WM_TOKEN not set", file=sys.stderr)
        sys.exit(1)

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
