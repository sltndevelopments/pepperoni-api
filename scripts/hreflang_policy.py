"""Single rule for RU↔EN language links, shared by sitemap and pages.

Live check 2026-09-09 (scripts/verify_sitemap_live.py) found 72 sitemap URLs
whose page-level hreflang disagreed with the sitemap: eight generators each
carried their own idea of x-default, RU category pages lacked the EN link,
and hand-written hubs had no x-default at all. Google evaluates hreflang per
cluster and ignores clusters that do not agree, so the sitemap and the pages
must be produced from one rule. This module is that rule; `rebuild_sitemap.py`
and `fix_hreflang.py` both import it.

x-default: the page an unknown-language visitor should get.
  * export cluster (`/export`, `/export/<country>`) and the `/pepperoni` Google
    Ads export landing exist for foreign buyers → EN.
  * everything else → RU (the site root is RU).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BASE = "https://pepperoni.tatar"
_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = _ROOT / "data" / "index_manifest.json"

EN_DEFAULT_KEYS = {"export", "pepperoni"}
EN_DEFAULT_PREFIXES = ("export/",)


def href_path(href: str) -> str:
    """`https://pepperoni.tatar/export/kuwait` → `/export/kuwait`."""
    href = (href or "").strip()
    if href.startswith(BASE):
        href = href[len(BASE):]
    if not href.startswith("/"):
        href = "/" + href
    return href.rstrip("/") or "/"


@lru_cache(maxsize=1)
def manifest_status() -> dict[str, str]:
    """Allowlist URL → keep/noindex/301/410."""
    if not _MANIFEST.is_file():
        return {}
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for row in payload.get("entries") or []:
        url = href_path(str(row.get("url") or ""))
        status = str(row.get("status") or "")
        if url and status:
            out[url] = status
    return out


def is_keep(href: str) -> bool:
    return manifest_status().get(href_path(href)) == "keep"


def is_noindex(href: str) -> bool:
    return manifest_status().get(href_path(href)) == "noindex"


def filter_page_alternates(
    page_href: str, alts: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Drop hreflang that would mix an indexable page with a noindex twin.

    Allowlist-driven: keep pages must not point at noindex/301/410 URLs;
    a noindex page must not advertise a keep twin.
    """
    page_keep = is_keep(page_href)
    page = href_path(page_href)
    out: list[tuple[str, str]] = []
    for lang, href in alts:
        target = href_path(href)
        target_keep = is_keep(href)
        if page_keep and not target_keep:
            continue
        if not page_keep and target_keep and target != page:
            continue
        out.append((lang, href))
    return out


def pair_key(rel: str) -> str:
    """Canonical key shared by RU↔EN versions of the same page (from a file path)."""
    if rel.startswith("en/"):
        rel = rel[3:]
    if rel.endswith(".html"):
        rel = rel[:-5]
    if rel.endswith("/index"):
        rel = rel[:-6]
    return rel


def x_default_lang(key: str) -> str:
    if key in EN_DEFAULT_KEYS or key.startswith(EN_DEFAULT_PREFIXES):
        return "en"
    return "ru"


def alternates(key: str, urls: dict[str, str]) -> list[tuple[str, str]]:
    """Ordered (hreflang, href) list for a pair; empty when only one language exists."""
    urls = {lang: href for lang, href in urls.items() if is_keep(href)}
    if not ("ru" in urls and "en" in urls):
        return []
    out = [("ru", urls["ru"]), ("en", urls["en"])]
    out.append(("x-default", urls[x_default_lang(key)]))
    return out
