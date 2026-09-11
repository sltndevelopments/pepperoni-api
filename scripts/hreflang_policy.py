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

BASE = "https://pepperoni.tatar"

EN_DEFAULT_KEYS = {"export", "pepperoni"}
EN_DEFAULT_PREFIXES = ("export/",)


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
    if not ("ru" in urls and "en" in urls):
        return []
    out = [("ru", urls["ru"]), ("en", urls["en"])]
    out.append(("x-default", urls[x_default_lang(key)]))
    return out
