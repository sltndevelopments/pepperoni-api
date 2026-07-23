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
3. Chrome Speculation Rules (`prerender`, eagerness: moderate) for
   same-origin document links. Hover ~200ms / pointerdown → near-instant
   next navigation on Chromium. Excludes lead-ingest endpoints and
   download / .no-prerender links. Unsupported browsers ignore the tag.
4. Cross-document View Transitions (`@view-transition { navigation: auto }`)
   for same-origin MPA navigations (Chrome/Safari). Respects
   prefers-reduced-motion. Progressive enhancement — no-op elsewhere.

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

SPECULATION_MARKER = "<!-- perf-hints: speculation-rules -->"
# Document rules + moderate eagerness: Chrome prerenders on hover (~200ms)
# or pointerdown; caps concurrent prerenders (~2, FIFO). Static MPA-safe.
SPECULATION_BLOCK = """<!-- perf-hints: speculation-rules -->
<script type="speculationrules">
{
  "prerender": [{
    "source": "document",
    "where": {
      "and": [
        { "href_matches": "/*" },
        { "not": { "href_matches": "/lead-submit*" } },
        { "not": { "href_matches": "/lead-health*" } },
        { "not": { "selector_matches": "[download]" } },
        { "not": { "selector_matches": ".no-prerender" } }
      ]
    },
    "eagerness": "moderate"
  }]
}
</script>
"""

VIEW_TRANSITION_MARKER = "<!-- perf-hints: view-transitions -->"
VIEW_TRANSITION_BLOCK = """<!-- perf-hints: view-transitions -->
<style>
@media (prefers-reduced-motion: no-preference) {
  @view-transition { navigation: auto; }
}
</style>
"""

HEAD_RE = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)
HEAD_CLOSE_RE = re.compile(r"</head\s*>", re.IGNORECASE)
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


def add_speculation_rules(html: str) -> str:
    if SPECULATION_MARKER in html:
        return html
    m = HEAD_CLOSE_RE.search(html)
    if m:
        return html[: m.start()] + SPECULATION_BLOCK + html[m.start():]
    # Fallback: append before </body> or at end
    body_close = re.search(r"</body\s*>", html, re.IGNORECASE)
    if body_close:
        return html[: body_close.start()] + SPECULATION_BLOCK + html[body_close.start():]
    return html + "\n" + SPECULATION_BLOCK


def add_view_transitions(html: str) -> str:
    if VIEW_TRANSITION_MARKER in html:
        return html
    m = HEAD_CLOSE_RE.search(html)
    if m:
        return html[: m.start()] + VIEW_TRANSITION_BLOCK + html[m.start():]
    body_close = re.search(r"</body\s*>", html, re.IGNORECASE)
    if body_close:
        return html[: body_close.start()] + VIEW_TRANSITION_BLOCK + html[body_close.start():]
    return html + "\n" + VIEW_TRANSITION_BLOCK


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
    new = add_speculation_rules(new)
    new = add_view_transitions(new)
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
