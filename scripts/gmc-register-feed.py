#!/usr/bin/env python3
"""Register product feed in Google Merchant Center via Content API v2.1."""
import json
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

MERCHANT_ID = "513449343"
FEED_URL = "https://pepperoni.tatar/products-feed.xml"
FEED_NAME = "Pepperoni Products Feed"
SCOPES = ["https://www.googleapis.com/auth/content"]

KEY_FILE = "/tmp/gsc-key.json"


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        KEY_FILE, scopes=SCOPES
    )
    return build("content", "v2.1", credentials=creds)


def list_feeds(service):
    """List existing datafeeds."""
    try:
        result = service.datafeeds().list(merchantId=MERCHANT_ID).execute()
        return result.get("resources", [])
    except HttpError as e:
        print(f"Error listing feeds: {e}")
        return None


def insert_feed(service):
    """Register a new primary product feed via URL fetch."""
    # Check if feed already exists
    existing = list_feeds(service)
    if existing is None:
        print("Cannot check existing feeds — likely no access to Merchant Center")
        print(f"Make sure {get_service_account_email()} is added as a user in:")
        print("  Google Merchant Center → Settings → Account access → Add user")
        return False

    for feed in existing:
        if feed.get("name") == FEED_NAME:
            print(f"Feed already exists: ID={feed.get('id')}")
            # Update it instead
            feed_id = feed["id"]
            body = build_feed_body()
            service.datafeeds().update(
                merchantId=MERCHANT_ID, datafeedId=feed_id, body=body
            ).execute()
            print(f"Updated feed {feed_id}")
            return True

    body = build_feed_body()
    try:
        result = service.datafeeds().insert(
            merchantId=MERCHANT_ID, body=body
        ).execute()
        print(f"Created feed: ID={result.get('id')}")
        return True
    except HttpError as e:
        print(f"Error creating feed: {e}")
        content = json.loads(e.content) if hasattr(e, "content") else {}
        for err in content.get("error", {}).get("errors", []):
            print(f"  {err.get('message')}")
        return False


def build_feed_body():
    return {
        "name": FEED_NAME,
        "contentType": "products",
        "attributeLanguage": "ru",
        "fileName": FEED_URL,
        "fetchSchedule": {
            "weekday": "monday",
            "hour": 4,
            "timeZone": "Europe/Moscow",
            "fetchUrl": FEED_URL,
        },
        "targets": [
            {
                "language": "ru",
                "country": "RU",
            }
        ],
    }


def get_service_account_email():
    with open(KEY_FILE) as f:
        return json.load(f).get("client_email", "unknown")


def main():
    service = get_service()
    ok = insert_feed(service)

    if ok:
        print("\nFeed registered. Next steps:")
        print("1. Go to https://merchants.google.com → Products → Feeds")
        print("2. Verify feed status (may take a few minutes to fetch)")
    else:
        print("\nFailed. Manual setup:")
        print("1. Add service account to Merchant Center:")
        print(f"   {get_service_account_email()}")
        print("2. Then re-run this script")
        print("3. Or manually add feed at:")
        print("   https://merchants.google.com → Products → Feeds → Add feed")
        print(f"   Feed URL: {FEED_URL}")


if __name__ == "__main__":
    main()
