#!/usr/bin/env python3
"""One source of truth for URLs pushed by post-SEO indexing clients."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://pepperoni.tatar"
WATCHLIST = ROOT / "data" / "commercial_watchlist.json"

# Keep this deliberately small: these are canonical commercial/discovery URLs,
# not a replacement for sitemap rotation.
HOT_PATHS = (
    "/",
    "/pepperoni",
    "/pepperoni-dlya-pizzerii",
    "/en/pepperoni",
    "/jerky",
    "/en/jerky",
    "/llms.txt",
    "/llms-full.txt",
    "/en/llms.txt",
    "/.well-known/llms.txt",
    *(f"/{lang}/pepperoni" for lang in ("kk", "uz", "az", "hy", "ka", "ky", "tg")),
)


def absolute(url_or_path: str) -> str:
    value = (url_or_path or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return f"{ORIGIN}/{value.lstrip('/')}"


def load_hot_urls(watchlist: Path = WATCHLIST) -> list[str]:
    """Return canonical hot URLs plus tracked commercial pages, deduplicated."""
    urls = [absolute(path) for path in HOT_PATHS]
    try:
        data = json.loads(watchlist.read_text(encoding="utf-8"))
        urls.extend(
            absolute(item.get("page") or "")
            for item in (data.get("items") or [])
            if isinstance(item, dict)
        )
        urls.append(absolute(data.get("money_hub") or ""))
    except (OSError, ValueError, TypeError):
        pass

    seen: set[str] = set()
    return [url for url in urls if url and not (url in seen or seen.add(url))]
