#!/usr/bin/env python3
"""Site-health auditor — the brain's technical eyes on the whole site.

Deterministic, no LLM, no network (operates on the local public/ tree). Catches
the technical-SEO problems the brain previously couldn't see:

  1. BROKEN INTERNAL LINKS — <a href> / canonical pointing to a path that has no
     corresponding file in public/ (would 404 for users and Googlebot).
  2. DUPLICATE / MISSING CANONICAL — pages with no <link rel=canonical>, or many
     pages sharing one canonical (thin/duplicate cluster risk — we have 3500+
     near-identical geo pages, exactly the pattern Google demotes).
  3. THIN / BROKEN HTML — tiny body text, leftover markdown fences, unclosed
     documents, LLM preambles ("Конечно", "Here is") that slipped past QA.

Writes data/site_health.json for the brain digest and prints a summary. Exit 0
always (informational); the brain and watchdog decide what to do with it.

Usage: python3 scripts/site_health.py [--limit-examples 15]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
OUT = DATA / "site_health.json"
BASE = "https://pepperoni.tatar"

HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
CANON_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', re.I)
BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
LLM_JUNK = ("```", "Конечно,", "Вот ", "Here is", "Here's", "I'll ", "Sure,",
            "Certainly,", "Как ИИ", "As an AI")


def _norm_path(href: str) -> str | None:
    """Map an href to a local path under public/, or None if external/anchor."""
    href = href.strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    if href.startswith(("http://", "https://")):
        p = urlparse(href)
        if p.netloc and "pepperoni.tatar" not in p.netloc:
            return None  # external — out of scope
        href = p.path
    href = href.split("#", 1)[0].split("?", 1)[0]
    if not href.startswith("/"):
        return None  # relative; skip (rare on this static site)
    return href


# Paths served by the API backend (api.pepperoni.tatar), not static files.
# Links to these are valid in production even though no local file exists.
BACKEND_PREFIXES = ("/api/",)


def _resolve(path: str) -> bool:
    """Does this site path resolve to a real file under public/?

    Treats a trailing slash as equivalent to the file form (/foo/ == /foo.html),
    and accepts API backend paths as valid (served dynamically, not as files)."""
    if path in ("/", ""):
        return (PUBLIC / "index.html").exists()
    if path.startswith(BACKEND_PREFIXES):
        return True
    rel = path.strip("/")  # tolerate both /foo and /foo/
    cands = [PUBLIC / rel, PUBLIC / f"{rel}.html", PUBLIC / rel / "index.html"]
    return any(c.exists() for c in cands)


def audit(limit_examples: int = 15) -> dict:
    files = list(PUBLIC.rglob("*.html"))
    broken_links: dict[str, list[str]] = defaultdict(list)
    no_canonical: list[str] = []
    canon_clusters: Counter = Counter()
    thin_pages: list[dict] = []
    broken_html: list[dict] = []
    link_cache: dict[str, bool] = {}

    for f in files:
        rel = "/" + str(f.relative_to(PUBLIC))
        try:
            html = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # canonical
        cm = CANON_RE.search(html)
        if not cm:
            no_canonical.append(rel)
        else:
            canon_clusters[cm.group(1).strip()] += 1

        # internal links
        for href in HREF_RE.findall(html):
            tgt = _norm_path(href)
            if tgt is None:
                continue
            if tgt not in link_cache:
                link_cache[tgt] = _resolve(tgt)
            if not link_cache[tgt]:
                broken_links[rel].append(tgt)

        # thin / broken body
        bm = BODY_RE.search(html)
        body_txt = TAG_RE.sub(" ", bm.group(1)) if bm else ""
        words = len(body_txt.split())
        if words < 120:
            thin_pages.append({"page": rel, "words": words})
        junk = [j for j in LLM_JUNK if j in html]
        if junk or html.count("<html") and "</html>" not in html.lower():
            broken_html.append({"page": rel,
                                 "issues": (["unclosed_html"] if "</html>" not in html.lower() and "<html" in html.lower() else [])
                                          + [f"junk:{j[:6]}" for j in junk]})

    # duplicate canonical clusters: one canonical claimed by many pages
    dup_clusters = {c: n for c, n in canon_clusters.items() if n > 1}

    total_broken = sum(len(v) for v in broken_links.values())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pages_scanned": len(files),
        "broken_links_total": total_broken,
        "pages_with_broken_links": len(broken_links),
        "broken_links_examples": dict(list(
            {p: v[:5] for p, v in broken_links.items()}.items())[:limit_examples]),
        "pages_without_canonical": len(no_canonical),
        "no_canonical_examples": no_canonical[:limit_examples],
        "duplicate_canonical_clusters": len(dup_clusters),
        "duplicate_canonical_examples": dict(
            sorted(dup_clusters.items(), key=lambda kv: -kv[1])[:limit_examples]),
        "thin_pages_total": len(thin_pages),
        "thin_pages_examples": sorted(thin_pages, key=lambda x: x["words"])[:limit_examples],
        "broken_html_total": len(broken_html),
        "broken_html_examples": broken_html[:limit_examples],
    }
    return report


def brain_summary() -> dict:
    """Compact view for seo_brain digest (read from the saved report)."""
    try:
        r = json.loads(OUT.read_text())
        return {
            "pages_scanned": r.get("pages_scanned", 0),
            "broken_links_total": r.get("broken_links_total", 0),
            "pages_without_canonical": r.get("pages_without_canonical", 0),
            "duplicate_canonical_clusters": r.get("duplicate_canonical_clusters", 0),
            "thin_pages_total": r.get("thin_pages_total", 0),
            "broken_html_total": r.get("broken_html_total", 0),
            "broken_html_examples": r.get("broken_html_examples", [])[:5],
            "thin_pages_examples": r.get("thin_pages_examples", [])[:5],
        }
    except Exception:
        return {}


def main() -> int:
    limit = 15
    if "--limit-examples" in sys.argv:
        try:
            limit = int(sys.argv[sys.argv.index("--limit-examples") + 1])
        except Exception:
            pass
    report = audit(limit)
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"🩺 site-health: {report['pages_scanned']} стр. | "
          f"битых ссылок {report['broken_links_total']} "
          f"(на {report['pages_with_broken_links']} стр.) | "
          f"без canonical {report['pages_without_canonical']} | "
          f"дубли-canonical {report['duplicate_canonical_clusters']} | "
          f"тонких {report['thin_pages_total']} | "
          f"битый HTML {report['broken_html_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
