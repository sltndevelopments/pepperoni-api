#!/usr/bin/env python3
"""
Rebuild sitemap.xml covering all 358 pages of pepperoni.tatar.
Assigns priority and changefreq by page type.
Run: python scripts/rebuild_sitemap.py
"""

from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET

PUBLIC  = Path(__file__).parent.parent / "public"
BASE    = "https://pepperoni.tatar"
TODAY   = date.today().isoformat()

# page type → (priority, changefreq)
RULES = {
    "root":     (1.0,  "weekly"),
    "catalog":  (0.95, "weekly"),   # main landing pages
    "product":  (0.85, "weekly"),   # /products/ and /en/products/
    "geo":      (0.75, "monthly"),  # /geo/
    "blog":     (0.80, "monthly"),  # /blog/ and /en/blog/
    "static":   (0.60, "monthly"),  # about, faq, delivery, etc.
    "en_index": (0.90, "weekly"),   # /en/
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
    if rel in (
        "pepperoni.html", "pepperoni-optom.html", "pepperoni-dlya-pizzerii.html",
        "pepperoni-dlya-horeca.html", "pepperoni-private-label.html",
        "pepperoni-v-narezke.html", "kazylyk.html", "bakery.html",
        "pizzeria.html", "blog.html",
        "en/pepperoni.html", "en/kazylyk.html", "en/bakery.html",
        "en/blog.html", "en/pizzeria.html",
    ):
        return "catalog"
    return "static"

def html_to_url(path: Path) -> str:
    """Convert public/foo/bar.html → https://pepperoni.tatar/foo/bar"""
    rel = path.relative_to(PUBLIC)
    parts = list(rel.parts)
    # strip .html and index
    last = parts[-1]
    if last == "index.html":
        parts = parts[:-1]
    else:
        parts[-1] = last[:-5]  # remove .html
    if not parts:
        return BASE + "/"
    return BASE + "/" + "/".join(parts)

# ── collect all html files ──────────────────────────────────────────────────
SKIP = {
    "yandex_d0a735c825c78ddf.html",
    "d0a735c825c78ddf.html",
}

entries = []
for path in sorted(PUBLIC.rglob("*.html")):
    rel = str(path.relative_to(PUBLIC))
    fname = path.name
    if fname in SKIP:
        continue
    # skip faq sub-pages (low value, not main nav)
    if rel.startswith("faq/") or rel.startswith("en/faq/"):
        continue

    url  = html_to_url(path)
    kind = classify(rel)
    pri, freq = RULES[kind]
    entries.append((pri, url, freq))

# Sort: priority desc, then url asc
entries.sort(key=lambda x: (-x[0], x[1]))

# ── build XML ───────────────────────────────────────────────────────────────
lines = ['<?xml version="1.0" encoding="UTF-8"?>']
lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
             '\n        xmlns:xhtml="http://www.w3.org/1999/xhtml">')

for pri, url, freq in entries:
    lines.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{pri:.2f}</priority>
  </url>""")

lines.append("</urlset>")
xml = "\n".join(lines)

out = PUBLIC / "sitemap.xml"
out.write_text(xml, encoding="utf-8")
print(f"✅ sitemap.xml rebuilt: {len(entries)} URLs → {out}")

# Print summary
from collections import Counter
kinds = Counter(classify(str(p.relative_to(PUBLIC)))
                for p in PUBLIC.rglob("*.html")
                if p.name not in SKIP
                and not str(p.relative_to(PUBLIC)).startswith(("faq/","en/faq/")))
print("\nBreakdown:")
for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
    print(f"  {k:12} {v:4} pages")
