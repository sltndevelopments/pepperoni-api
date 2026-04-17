#!/usr/bin/env python3
"""
Add Core Web Vitals / performance hints to every HTML file under public/.

Idempotent — safe to run on every deploy. Each transform is guarded by a
marker check so repeated runs do not duplicate tags.

What it adds/normalises:
1. `<link rel="preconnect">` + `<link rel="dns-prefetch">` for analytics
   origins (Google Tag Manager, Yandex Metrica) right after <head>. This
   lets the browser warm up DNS + TLS while rendering, which reduces
   Interaction-to-Next-Paint (INP) and third-party blocking time.
2. `width="1" height="1"` and `loading="lazy"` on the Yandex Metrica
   tracking pixel <img>. Prevents tiny CLS regressions if the tracker
   ever gets re-positioned and ensures it never competes with LCP.

Ideally generators would emit these tags directly, but a post-processor
is cheaper than duplicating the snippet across 8+ generators and lets us
backfill static hand-written pages in the same pass.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

PERF_MARKER = "<!-- perf-hints: preconnect -->"
PERF_BLOCK = """<!-- perf-hints: preconnect -->
<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
<link rel="dns-prefetch" href="https://www.googletagmanager.com">
<link rel="preconnect" href="https://mc.yandex.ru" crossorigin>
<link rel="dns-prefetch" href="https://mc.yandex.ru">
"""

HEAD_RE = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)
YM_IMG_RE = re.compile(
    r'<img\b[^>]*src=["\']https?://mc\.yandex\.ru/watch/\d+["\'][^>]*/?\s*>',
    re.IGNORECASE,
)


def add_preconnects(html: str) -> str:
    if PERF_MARKER in html:
        return html
    m = HEAD_RE.search(html)
    if not m:
        return html
    return html[: m.end()] + "\n" + PERF_BLOCK + html[m.end():]


def _inject_attrs(tag: str, attrs: dict[str, str]) -> str:
    """Insert attrs into an <img ...> / <img .../> tag before its closing >."""
    lower = tag.lower()
    additions = []
    for k, v in attrs.items():
        if f"{k}=" not in lower:
            additions.append(f'{k}="{v}"')
    if not additions:
        return tag
    insert = " " + " ".join(additions)
    if tag.endswith("/>"):
        body = tag[:-2].rstrip()
        return body + insert + " />"
    if tag.endswith(">"):
        body = tag[:-1].rstrip()
        return body + insert + ">"
    return tag


def normalise_ym_pixel(html: str) -> str:
    return YM_IMG_RE.sub(
        lambda m: _inject_attrs(
            m.group(0),
            {"width": "1", "height": "1", "loading": "lazy"},
        ),
        html,
    )


def process(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:
        return False
    new = add_preconnects(src)
    new = normalise_ym_pixel(new)
    if new != src:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    total = 0
    for path in PUBLIC.rglob("*.html"):
        total += 1
        if process(path):
            changed += 1
    print(f"perf-hints: patched {changed} / {total} HTML files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
