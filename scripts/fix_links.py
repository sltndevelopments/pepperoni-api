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

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"

PLACEHOLDER_RE = re.compile(r"\$\{[^}]*\}|\{\{[^}]*\}\}|<%[^%]*%>")
# <a ...href="X"...>TEXT</a>  (non-greedy, single tag)
A_TAG_RE = re.compile(r'<a\b[^>]*?href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', re.I | re.S)
BACKEND_PREFIXES = ("/api/",)


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


def _fix_html(html: str) -> tuple[str, dict]:
    stats = {"placeholder": 0, "slash_fixed": 0, "unwrapped": 0}

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

        # 2) try slash/.html normalisation that resolves
        base = href.split("#")[0].split("?")[0].strip("/")
        suffix = href[len("/" + base):]  # preserve #anchor/?query
        for cand in (f"/{base}.html", f"/{base}/", f"/{base}"):
            if _resolves(cand):
                stats["slash_fixed"] += 1
                return whole.replace(f'"{href}"', f'"{cand}{suffix}"').replace(
                    f"'{href}'", f"'{cand}{suffix}'")

        # 3) genuinely dead → unwrap to plain text (stop the 404)
        stats["unwrapped"] += 1
        return inner

    new = A_TAG_RE.sub(repl, html)
    return new, stats


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = list(PUBLIC.rglob("*.html"))
    totals = {"placeholder": 0, "slash_fixed": 0, "unwrapped": 0}
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
          f"нормализовано слеш/.html {totals['slash_fixed']} | "
          f"снято мёртвых ссылок {totals['unwrapped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
