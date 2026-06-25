#!/usr/bin/env python3
"""
BRAND MENTIONS — ежедневный мониторинг внешних упоминаний бренда.

Источники (без API-ключей, через requests/RSS):
  A) Google News RSS RU: Казанские Деликатесы
  B) Google News RSS EN: Kazan Delicacies
  C) Reddit public JSON: pepperoni.tatar

Только новые упоминания за последние 7 дней сохраняются в
data/brand_mentions.json. Если есть новые — Telegram-уведомление.

Usage:
  python3 scripts/brand_mentions.py
  python3 scripts/brand_mentions.py --no-telegram
"""

from __future__ import annotations

import email.utils
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
LEDGER = DATA / "brand_mentions.json"

WINDOW_DAYS = 7
MAX_RETRIES = 2
TIMEOUT = 20

SOURCES = [
    {
        "id": "gnews_ru",
        "name": "Google News RU",
        "url": "https://news.google.com/rss/search?q=Казанские+Деликатесы&hl=ru&gl=RU&ceid=RU:ru",
        "type": "rss",
    },
    {
        "id": "gnews_en",
        "name": "Google News EN",
        "url": "https://news.google.com/rss/search?q=Kazan+Delicacies&hl=en&gl=RU&ceid=RU:en",
        "type": "rss",
    },
    {
        "id": "reddit",
        "name": "Reddit",
        "url": "https://www.reddit.com/search.json?q=pepperoni.tatar&sort=new&limit=25",
        "type": "reddit",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PepperoniBot/1.0; +https://pepperoni.tatar)",
    "Accept": "application/rss+xml, application/json, text/xml, */*",
}


def _fetch(url: str) -> bytes | None:
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"  ⚠️  fetch failed {url}: {e}", file=sys.stderr)
            else:
                time.sleep(2)
    return None


def _parse_date(s: str) -> datetime | None:
    """Parse RSS date (RFC 2822) or ISO 8601."""
    if not s:
        return None
    try:
        return datetime(*email.utils.parsedate(s)[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:25], fmt[:len(s[:25])])
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def fetch_rss(source: dict, cutoff: datetime) -> list[dict]:
    raw = _fetch(source["url"])
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  ⚠️  RSS parse error {source['id']}: {e}", file=sys.stderr)
        return []

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or ""
        dt = _parse_date(pub)
        if dt and dt >= cutoff:
            items.append({
                "source_id": source["id"],
                "source_name": source["name"],
                "title": title,
                "url": link,
                "date": dt.strftime("%Y-%m-%d"),
                "ts": dt.isoformat(),
            })
    return items


def fetch_reddit(source: dict, cutoff: datetime) -> list[dict]:
    raw = _fetch(source["url"])
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"  ⚠️  Reddit JSON error: {e}", file=sys.stderr)
        return []

    items = []
    posts = data.get("data", {}).get("children", [])
    for post in posts:
        p = post.get("data", {})
        created = p.get("created_utc", 0)
        dt = datetime.fromtimestamp(created, tz=timezone.utc) if created else None
        if dt and dt >= cutoff:
            items.append({
                "source_id": "reddit",
                "source_name": "Reddit",
                "title": p.get("title", "")[:200],
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "date": dt.strftime("%Y-%m-%d"),
                "ts": dt.isoformat(),
                "subreddit": p.get("subreddit", ""),
                "score": p.get("score", 0),
            })
    return items


def load_ledger() -> list[dict]:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_ledger(entries: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    # Keep last 500 mentions max
    entries = sorted(entries, key=lambda x: x.get("ts", ""), reverse=True)[:500]
    LEDGER.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def notify(new_items: list[dict]) -> None:
    if not new_items:
        return
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import telegram_notify
        lines = [f"<b>📰 Новые упоминания бренда ({len(new_items)})</b>"]
        for item in new_items[:8]:
            src = item.get("source_name", "")
            title = item.get("title", "")[:80]
            url = item.get("url", "")
            lines.append(f"• [{src}] <a href='{url}'>{title}</a>")
        if len(new_items) > 8:
            lines.append(f"  ...и ещё {len(new_items) - 8}")
        telegram_notify.notify("\n".join(lines))
    except Exception as e:
        print(f"· telegram notify failed: {e}", file=sys.stderr)


def main() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    print(f"🔍 Brand mentions: scanning {len(SOURCES)} sources (last {WINDOW_DAYS} days)…")

    existing = load_ledger()
    known_urls = {e.get("url") for e in existing}

    fresh: list[dict] = []
    for source in SOURCES:
        try:
            if source["type"] == "rss":
                items = fetch_rss(source, cutoff)
            elif source["type"] == "reddit":
                items = fetch_reddit(source, cutoff)
            else:
                items = []
            print(f"  {source['name']}: {len(items)} found")
            for item in items:
                if item.get("url") and item["url"] not in known_urls:
                    fresh.append(item)
                    known_urls.add(item["url"])
        except Exception as e:
            print(f"  ⚠️  {source['id']} error: {e}", file=sys.stderr)

    print(f"✅ New mentions: {len(fresh)}")
    if fresh:
        for item in fresh:
            print(f"  [{item['source_name']}] {item['date']} — {item['title'][:60]}")

    # Merge new into ledger
    all_entries = existing + fresh
    save_ledger(all_entries)

    if fresh and "--no-telegram" not in sys.argv[1:]:
        notify(fresh)

    return 0


if __name__ == "__main__":
    sys.exit(main())
