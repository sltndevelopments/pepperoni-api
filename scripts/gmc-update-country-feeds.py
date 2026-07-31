#!/usr/bin/env python3
"""Point GMC single-country datafeeds at per-country XMLs (Content API v2.1).

Root cause of invalid_currency_for_country: multi-country arab/cis XMLs were
registered as single-country datafeeds, so e.g. KD-025-BH (BHD) landed in SA.

Usage on VPS (after gen-products-feed.py + deploy of public/products-feed-*.xml):
  source /var/www/pepperoni/seo-agent.env
  echo "$GSC_SERVICE_ACCOUNT_KEY_B64" | base64 -d > /tmp/gsc-key.json
  python3 scripts/gmc-update-country-feeds.py [--dry-run] [--fetch-now]
  rm -f /tmp/gsc-key.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

MERCHANT_ID = "513449343"
BASE = "https://pepperoni.tatar"
SCOPES = ["https://www.googleapis.com/auth/content"]

# Country code → fetch URL for that country's GMC datafeed only.
# AE keeps products-feed-ae.xml (already clean). RU keeps products-feed.xml.
COUNTRY_FEED_URLS: dict[str, str] = {
    "SA": f"{BASE}/products-feed-sa.xml",
    "KW": f"{BASE}/products-feed-kw.xml",
    "OM": f"{BASE}/products-feed-om.xml",
    "EG": f"{BASE}/products-feed-eg.xml",
    "BH": f"{BASE}/products-feed-bh.xml",
    "QA": f"{BASE}/products-feed-qa.xml",
    "YE": f"{BASE}/products-feed-ye.xml",
    "AE": f"{BASE}/products-feed-ae.xml",
    "BY": f"{BASE}/products-feed-by.xml",
    "KZ": f"{BASE}/products-feed-kz.xml",
    "UZ": f"{BASE}/products-feed-uz.xml",
    "GE": f"{BASE}/products-feed-ge.xml",
    "KG": f"{BASE}/products-feed-kg.xml",
    "AZ": f"{BASE}/products-feed-az.xml",
    "TJ": f"{BASE}/products-feed-tj.xml",
    "AM": f"{BASE}/products-feed-am.xml",
    "RU": f"{BASE}/products-feed.xml",
}

# Multi-country URLs that must NOT remain as fetchUrl for single-country feeds.
BAD_MULTI_URLS = {
    f"{BASE}/products-feed-arab.xml",
    f"{BASE}/products-feed-cis.xml",
}


def key_path() -> Path:
    env = os.environ.get("GSC_KEY_FILE") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env:
        return Path(env)
    return Path("/tmp/gsc-key.json")


def get_service():
    path = key_path()
    if not path.is_file():
        print(f"ERROR: key file missing: {path}", file=sys.stderr)
        sys.exit(2)
    creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
    return build("content", "v2.1", credentials=creds)


def target_countries(feed: dict) -> list[str]:
    out: list[str] = []
    for t in feed.get("targets") or []:
        cc = (t.get("country") or "").upper()
        if cc:
            out.append(cc)
    return out


def current_fetch_url(feed: dict) -> str:
    fs = feed.get("fetchSchedule") or {}
    return (fs.get("fetchUrl") or feed.get("fileName") or "").strip()


def list_feeds(service) -> list[dict]:
    result = service.datafeeds().list(merchantId=MERCHANT_ID).execute()
    return result.get("resources") or []


def update_feed_url(service, feed: dict, new_url: str, *, dry_run: bool) -> bool:
    """Update fetchSchedule.fetchUrl only.

    Content API returns 409 if `fileName` changes after insert — keep the
    original fileName (often the old multi-country URL) and retarget fetchUrl.
    """
    feed_id = feed["id"]
    body = dict(feed)
    # Do NOT change fileName — immutable after create (HTTP 409 conflict).
    fs = dict(body.get("fetchSchedule") or {})
    fs["fetchUrl"] = new_url
    fs.setdefault("hour", 4)
    fs.setdefault("timeZone", "Europe/Moscow")
    body["fetchSchedule"] = fs
    for k in ("kind",):
        body.pop(k, None)
    print(f"  UPDATE id={feed_id} name={feed.get('name')!r}")
    print(f"    old fetchUrl: {current_fetch_url(feed)}")
    print(f"    new fetchUrl: {new_url}")
    print(f"    fileName (unchanged): {body.get('fileName')}")
    if dry_run:
        return True
    service.datafeeds().update(
        merchantId=MERCHANT_ID, datafeedId=feed_id, body=body
    ).execute()
    return True


def fetch_now(service, feed_id: str, *, dry_run: bool) -> None:
    print(f"  FETCHNOW id={feed_id}")
    if dry_run:
        return
    service.datafeeds().fetchnow(merchantId=MERCHANT_ID, datafeedId=feed_id).execute()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fetch-now", action="store_true", help="Trigger fetch after update")
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()

    service = get_service()
    feeds = list_feeds(service)
    print(f"Merchant {MERCHANT_ID}: {len(feeds)} datafeeds\n")

    updated: list[tuple[str, str, str]] = []  # id, country, url
    skipped: list[str] = []

    for feed in feeds:
        fid = str(feed.get("id"))
        name = feed.get("name")
        url = current_fetch_url(feed)
        countries = target_countries(feed)
        print(f"FEED id={fid} name={name!r} countries={countries} url={url}")

        if args.list_only:
            continue

        if len(countries) != 1:
            skipped.append(f"{fid}: multi/no target {countries}")
            continue

        cc = countries[0]
        desired = COUNTRY_FEED_URLS.get(cc)
        if not desired:
            skipped.append(f"{fid}: no mapping for {cc}")
            continue

        if url == desired:
            print(f"  OK already pointing at {desired}")
            if args.fetch_now and url not in BAD_MULTI_URLS:
                try:
                    fetch_now(service, fid, dry_run=args.dry_run)
                except HttpError as e:
                    print(f"  WARN fetchnow: {e}")
            continue

        # Update if pointing at multi-country aggregate OR wrong country URL
        try:
            update_feed_url(service, feed, desired, dry_run=args.dry_run)
            updated.append((fid, cc, desired))
            if args.fetch_now:
                fetch_now(service, fid, dry_run=args.dry_run)
        except HttpError as e:
            print(f"  ERROR update: {e}")
            skipped.append(f"{fid}: update failed")

    print("\n=== Summary ===")
    print(f"Updated ({len(updated)}):")
    for fid, cc, u in updated:
        print(f"  {fid} → {cc} → {u}")
    if skipped:
        print(f"Skipped ({len(skipped)}):")
        for s in skipped:
            print(f"  {s}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HttpError as e:
        print(f"FATAL Content API: {e}", file=sys.stderr)
        raise SystemExit(1)
