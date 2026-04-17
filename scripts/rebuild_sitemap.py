#!/usr/bin/env python3
"""
Rebuild sitemap.xml covering every HTML page under public/.

Features:
- <lastmod> uses file mtime (real content freshness, not today's date).
- Priority + changefreq assigned per page type.
- Adds <xhtml:link rel="alternate" hreflang="..."> for RU↔EN pairs so
  Google/Yandex can serve the correct language variant in SERP.
- Emits sitemap.xml as a single urlset (works up to 50 000 URLs).

Run: python scripts/rebuild_sitemap.py
"""

from datetime import date, datetime, timezone
from pathlib import Path

PUBLIC  = Path(__file__).parent.parent / "public"
BASE    = "https://pepperoni.tatar"
TODAY   = date.today().isoformat()

# page type → (priority, changefreq)
RULES = {
    "root":     (1.00, "weekly"),
    "catalog":  (0.95, "weekly"),
    "product":  (0.85, "weekly"),
    "geo":      (0.75, "monthly"),
    "blog":     (0.80, "monthly"),
    "static":   (0.60, "monthly"),
    "en_index": (0.90, "weekly"),
}

CATALOG_PAGES = {
    "pepperoni.html", "pepperoni-optom.html", "pepperoni-dlya-pizzerii.html",
    "pepperoni-dlya-horeca.html", "pepperoni-private-label.html",
    "pepperoni-v-narezke.html", "kazylyk.html", "bakery.html",
    "pizzeria.html", "blog.html",
    "en/pepperoni.html", "en/kazylyk.html", "en/bakery.html",
    "en/blog.html", "en/pizzeria.html",
}

SKIP_FILES = {
    "yandex_d0a735c825c78ddf.html",
    "d0a735c825c78ddf.html",
}


def classify(rel: str) -> str:
    if rel in ("", "index.html"):
        return "root"
    if rel.startswith("products/") or rel.startswith("en/products/"):
        return "product"
    if rel.startswith("geo/"):
        return "geo"
    if rel.startswith("blog/") or rel.startswith("en/blog/"):
        return "blog"
    if rel in ("en/index.html", "en/"):
        return "en_index"
    if rel in CATALOG_PAGES:
        return "catalog"
    return "static"


def html_to_url(path: Path) -> str:
    """Convert public/foo/bar.html → https://pepperoni.tatar/foo/bar (clean URLs)."""
    rel = path.relative_to(PUBLIC)
    parts = list(rel.parts)
    last = parts[-1]
    if last == "index.html":
        parts = parts[:-1]
    else:
        parts[-1] = last[:-5]
    if not parts:
        return BASE + "/"
    return BASE + "/" + "/".join(parts)


def mtime_iso(path: Path) -> str:
    """W3C-datetime lastmod from file mtime; falls back to today."""
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return TODAY


def pair_key(rel: str) -> str:
    """Canonical key shared by RU↔EN versions of the same page."""
    if rel.startswith("en/"):
        rel = rel[3:]
    if rel.endswith(".html"):
        rel = rel[:-5]
    if rel.endswith("/index"):
        rel = rel[:-6]
    return rel


def build_entries() -> list:
    pages = []
    for path in sorted(PUBLIC.rglob("*.html")):
        fname = path.name
        rel = str(path.relative_to(PUBLIC))
        if fname in SKIP_FILES:
            continue
        if rel.startswith("faq/") or rel.startswith("en/faq/"):
            continue
        pages.append((path, rel))

    by_key: dict[str, dict[str, Path]] = {}
    for path, rel in pages:
        key = pair_key(rel)
        lang = "en" if rel.startswith("en/") else "ru"
        by_key.setdefault(key, {})[lang] = path

    entries = []
    for path, rel in pages:
        key = pair_key(rel)
        url = html_to_url(path)
        kind = classify(rel)
        pri, freq = RULES[kind]
        lang = "en" if rel.startswith("en/") else "ru"

        alternates = []
        partners = by_key.get(key, {})
        if len(partners) >= 2 or (lang == "en" and "ru" in partners) or (lang == "ru" and "en" in partners):
            for l in ("ru", "en"):
                if l in partners:
                    alternates.append((l, html_to_url(partners[l])))
            x_default = html_to_url(partners.get("ru") or partners.get("en"))
            alternates.append(("x-default", x_default))

        entries.append({
            "url":        url,
            "lastmod":    mtime_iso(path),
            "changefreq": freq,
            "priority":   pri,
            "alternates": alternates,
        })

    entries.sort(key=lambda e: (-e["priority"], e["url"]))
    return entries


def render_xml(entries: list) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    )
    for e in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{e['url']}</loc>")
        lines.append(f"    <lastmod>{e['lastmod']}</lastmod>")
        lines.append(f"    <changefreq>{e['changefreq']}</changefreq>")
        lines.append(f"    <priority>{e['priority']:.2f}</priority>")
        for lang, href in e["alternates"]:
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="{lang}" href="{href}"/>'
            )
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main():
    entries = build_entries()
    xml = render_xml(entries)

    out = PUBLIC / "sitemap.xml"
    out.write_text(xml, encoding="utf-8")
    print(f"✅ sitemap.xml rebuilt: {len(entries)} URLs → {out}")

    from collections import Counter
    kinds = Counter(
        classify(str(p.relative_to(PUBLIC)))
        for p in PUBLIC.rglob("*.html")
        if p.name not in SKIP_FILES
        and not str(p.relative_to(PUBLIC)).startswith(("faq/", "en/faq/"))
    )
    print("\nBreakdown:")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k:12} {v:4} pages")

    with_alt = sum(1 for e in entries if e["alternates"])
    print(f"\nURLs with hreflang alternates: {with_alt}/{len(entries)}")


if __name__ == "__main__":
    main()
