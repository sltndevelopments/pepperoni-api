#!/usr/bin/env python3
"""Broken-link repairer — closes the "see → fix" loop on internal links.

site_health.py finds broken links; this script fixes the genuinely broken ones
deterministically (no LLM). It is conservative: when in doubt it leaves the page
untouched and reports it for the brain instead of guessing.

What it repairs:
  1. UNRENDERED TEMPLATE PLACEHOLDERS — href with ${...}, {{...}}, <%...%> (a
     template/JS leak, e.g. /products/${slug}). The whole <a> is unwrapped to its
     visible text (link removed, words kept) — a dead placeholder helps nobody.
  2. TRAILING-SLASH / .html MISMATCH — href="/foo/" or "/foo" where only
     "/foo.html" exists → rewrite to the form that resolves. (Safe, exact.)
  3. DEAD INTERNAL LINKS to a path with no matching file AND no close match —
     unwrap to plain text so users/Googlebot stop hitting 404s.

Always commit via the pipeline, never standalone pushes here. Run AFTER
site_health.py so the report reflects the repair.

Usage: python3 scripts/fix_links.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"

PLACEHOLDER_RE = re.compile(r"\$\{[^}]*\}|\{\{[^}]*\}\}|<%[^%]*%>")
# <a ...href="X"...>TEXT</a>  (non-greedy, single tag)
A_TAG_RE = re.compile(r'<a\b[^>]*?href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', re.I | re.S)
BACKEND_PREFIXES = ("/api/",)

# Index of all existing site paths (built once) for fuzzy "did you mean" repair.
_SITE_PATHS: set[str] | None = None
_GEO_FALLBACK: dict[str, str] | None = None


def _geo_fallback() -> dict[str, str]:
    """Map a product geo-slug → its best existing category page, so a link to a
    not-yet-generated geo page (/geo/pepperoni-astana/) routes to the relevant
    catalog page instead of being deleted (preserves internal-link structure)."""
    global _GEO_FALLBACK
    if _GEO_FALLBACK is not None:
        return _GEO_FALLBACK
    out: dict[str, str] = {}
    try:
        d = json.loads((DATA / "products_geo.json").read_text())
        products = d["products"] if isinstance(d, dict) else d
    except Exception:
        products = []
    sp = _site_paths()
    for p in products:
        slug = (p.get("slug_ru") or "").strip()
        if not slug:
            continue
        # candidate category pages, most specific first
        for cand in (f"/{slug}.html", f"/{slug}-optom.html",
                     f"/{slug}-dlya-pizzerii.html", f"/{slug}.html"):
            if cand[:-5] in sp or cand in sp:
                out[slug] = cand[:-5]
                break
    _GEO_FALLBACK = out
    return out


def _site_paths() -> set[str]:
    global _SITE_PATHS
    if _SITE_PATHS is None:
        paths = set()
        for f in PUBLIC.rglob("*.html"):
            rel = "/" + str(f.relative_to(PUBLIC))
            paths.add(rel)
            paths.add(rel[:-5])               # without .html
            if rel.endswith("/index.html"):
                paths.add(rel[:-len("index.html")].rstrip("/"))
        _SITE_PATHS = paths
    return _SITE_PATHS


def _resolves(path: str) -> bool:
    if path in ("/", ""):
        return (PUBLIC / "index.html").exists()
    if path.startswith(BACKEND_PREFIXES) or path.startswith(("http://", "https://",
                                                             "#", "mailto:", "tel:")):
        return True
    rel = path.split("#")[0].split("?")[0].strip("/")
    if not rel:
        return True
    return any((PUBLIC / c).exists() for c in (rel, f"{rel}.html", f"{rel}/index.html"))


def _suggest(path: str) -> str | None:
    """Find an existing path that's an obvious fix for a broken one.

    Handles the concrete generator bugs seen on this site:
      - duplicated language prefix:  /en/en/foo  →  /en/foo
      - common typo: missing 's' (sosiki→sosiski) or extra segment
    Returns a resolving path or None (caller then unwraps the dead link).
    """
    base = path.split("#")[0].split("?")[0]
    # 1) collapse duplicated /en/en/, /ar/ar/ etc.
    dedup = re.sub(r"^/([a-z]{2})/\1/", r"/\1/", base)
    if dedup != base and _resolves(dedup):
        return dedup
    # 2) exact membership in the site index (with/without slash/.html)
    cand = base.rstrip("/")
    if cand in _site_paths():
        return cand
    # 3) light typo bridge: try inserting 's' (sosiki→sosiski is frequent)
    for variant in (base.replace("sosiki", "sosiski"),
                    base.replace("pepperoni-dlya-", "dlya-")):
        if variant != base and _resolves(variant):
            return variant
    # 4) not-yet-generated geo page → route to the product's category page
    m = re.match(r"^/geo/([a-z-]+?)-[a-z]+/?$", base)
    if m:
        fb = _geo_fallback()
        slug = m.group(1)
        # longest product-slug prefix wins (e.g. sosiki-dlya-hotdog before sosiki)
        for cand_slug in sorted(fb, key=len, reverse=True):
            if slug == cand_slug or slug.startswith(cand_slug + "-"):
                return fb[cand_slug]
    return None


def _fix_html(html: str) -> tuple[str, dict]:
    stats = {"placeholder": 0, "redirected": 0, "unwrapped": 0}

    def repl(m: re.Match) -> str:
        href = m.group(1).strip()
        inner = m.group(2)
        whole = m.group(0)

        # 1) unrendered template placeholder → unwrap to text
        if PLACEHOLDER_RE.search(href):
            stats["placeholder"] += 1
            return inner

        if not href.startswith("/"):
            return whole  # external / relative / anchor — leave alone
        if _resolves(href):
            return whole

        # 2) try to redirect to an obviously-correct existing page
        fix = _suggest(href)
        if fix:
            stats["redirected"] += 1
            return whole.replace(f'"{href}"', f'"{fix}"').replace(
                f"'{href}'", f"'{fix}'")

        # 3) genuinely dead, no good target → unwrap to plain text (stop the 404)
        stats["unwrapped"] += 1
        return inner

    new = A_TAG_RE.sub(repl, html)
    return new, stats


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = list(PUBLIC.rglob("*.html"))
    _site_paths()  # warm the index once
    totals = {"placeholder": 0, "redirected": 0, "unwrapped": 0}
    changed_files = 0
    for f in files:
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        new, stats = _fix_html(html)
        if new != html:
            changed_files += 1
            for k in totals:
                totals[k] += stats[k]
            if not dry:
                f.write_text(new, encoding="utf-8")
    print(f"🔗 fix_links: {'(dry-run) ' if dry else ''}"
          f"изменено страниц {changed_files} | "
          f"шаблонный мусор {totals['placeholder']} | "
          f"перенаправлено на верный URL {totals['redirected']} | "
          f"снято мёртвых ссылок {totals['unwrapped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
