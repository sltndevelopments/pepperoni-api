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

import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

ROOT    = Path(__file__).parent.parent
PUBLIC  = ROOT / "public"
NGINX   = ROOT / "deploy" / "nginx"
BASE    = "https://pepperoni.tatar"
TODAY   = date.today().isoformat()

# page type → (priority, changefreq)
RULES = {
    "root":     (1.00, "weekly"),
    "catalog":  (0.70, "weekly"),
    "product":  (0.80, "weekly"),
    "geo":      (0.70, "monthly"),
    "blog":     (0.70, "monthly"),
    "static":   (0.60, "monthly"),
    "en_index": (0.90, "weekly"),
}

CATALOG_PAGES = {
    "pepperoni.html", "pepperoni-optom.html", "pepperoni-dlya-pizzerii.html",
    "pepperoni-dlya-horeca.html", "pepperoni-private-label.html",
    "pepperoni-v-narezke.html", "kazylyk.html", "bakery.html",
    "pizzeria.html", "blog.html", "jerky.html",
    "en/pepperoni.html", "en/kazylyk.html", "en/bakery.html",
    "en/blog.html", "en/pizzeria.html", "en/jerky.html",
}

PEPPERONI_HREFLANGS = (
    "ru", "en", "kk", "uz", "az", "hy", "ka", "ky", "tg",
)

SKIP_FILES = {
    "yandex_d0a735c825c78ddf.html",
    "d0a735c825c78ddf.html",
    "jerks.html",
    "dzherki.html",
}

# Directory names whose index.html we skip (duplicate homepages, noindex pages, etc.)
SKIP_DIRS = {
    "1", "2", "3", "4", "5",          # duplicate homepages
    "x",                              # experimental homepage (77653a74c)
    "search", "en/search",            # noindex (X-Robots-Tag)
    "china",                          # noindex
}

# The stale .html file of a 301'd URL stays on disk and keeps a self-canonical,
# so neither the filesystem nor the canonical tells us it is dead — only nginx
# does. Read the redirect maps instead of maintaining a hand-written skip list:
# a URL that answers 301 must never be advertised in the sitemap, and any
# redirect added later is excluded automatically.
_LOC_EXACT = re.compile(r"location\s*=\s*(\S+)\s*\{([^}]*)\}", re.S)
_ROBOTS_META = re.compile(
    r"""<meta[^>]+name=["']robots["'][^>]*content=["'][^"']*noindex""", re.I
)


def redirect_sources() -> set[str]:
    """Exact-match paths that nginx 301s, taken from deploy/nginx/*redirects.conf.

    Only `location = /exact` blocks count. The `location ^~ /geo/` blocks in the
    *gone.conf files are try_files fallbacks that still serve surviving files.
    """
    paths: set[str] = set()
    for conf in sorted(NGINX.glob("*redirects.conf")):
        text = conf.read_text(encoding="utf-8", errors="replace")
        for path, body in _LOC_EXACT.findall(text):
            if "return 30" in body:
                # Exact `/foo/` and `/foo` are different nginx locations.
                # Stripping the slash removed canonical `/foo` from the sitemap
                # whenever only its trailing-slash variant redirected.
                paths.add(path.strip().strip('"') or "/")
    return paths


def has_noindex(path: Path) -> bool:
    """True when the page carries a robots noindex meta.

    Pages are noindexed on purpose — e.g. experiment_registry.py reverts a
    losing new page that way. Listing them in the sitemap turns a deliberate
    revert into a Search Console error ("submitted URL marked noindex").
    """
    try:
        return bool(_ROBOTS_META.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


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


def existing_lastmods() -> dict[str, str]:
    """Preserve dates for unchanged files; checkout mtimes are not content dates."""
    sitemap = PUBLIC / "sitemap.xml"
    if not sitemap.exists():
        return {}
    try:
        root = ET.parse(sitemap).getroot()
    except (ET.ParseError, OSError):
        return {}
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    result = {}
    for node in root.findall(f"{ns}url"):
        loc = node.find(f"{ns}loc")
        lastmod = node.find(f"{ns}lastmod")
        if loc is not None and loc.text and lastmod is not None and lastmod.text:
            result[loc.text.strip()] = lastmod.text.strip()
    return result


def changed_public_paths() -> set[Path]:
    """Paths changed against HEAD, including untracked files."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", "public"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return set(PUBLIC.rglob("*.html"))
    paths = set()
    for line in result.stdout.splitlines():
        raw = line[3:]
        if " -> " in raw:
            raw = raw.rsplit(" -> ", 1)[1]
        paths.add((ROOT / raw.strip('"')).resolve())
    return paths


def mtime_iso(
    path: Path,
    url: str,
    previous: dict[str, str],
    changed: set[Path],
) -> str:
    """W3C lastmod: preserve unchanged URL dates, refresh changed content."""
    if path.resolve() not in changed and url in previous:
        return previous[url]
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


def pepperoni_alternates(rel: str) -> list[tuple[str, str]]:
    """Full locale cluster emitted by gen_pepperoni_landing.py, if applicable."""
    clean = rel[:-5] if rel.endswith(".html") else rel
    expected = {
        "pepperoni" if lang == "ru" else f"{lang}/pepperoni"
        for lang in PEPPERONI_HREFLANGS
    }
    if clean not in expected:
        return []
    alternates = [
        (lang, f"{BASE}/pepperoni" if lang == "ru" else f"{BASE}/{lang}/pepperoni")
        for lang in PEPPERONI_HREFLANGS
    ]
    # Keep this aligned with gen_pepperoni_landing.py: the international EN
    # page is the language-neutral fallback, not the RU domestic page.
    alternates.append(("x-default", f"{BASE}/en/pepperoni"))
    return alternates


def build_entries() -> list:
    redirected = redirect_sources()
    previous_lastmod = existing_lastmods()
    changed = changed_public_paths()
    dropped = {"redirect": 0, "noindex": 0}
    pages = []
    for path in sorted(PUBLIC.rglob("*.html")):
        fname = path.name
        rel = str(path.relative_to(PUBLIC))
        if fname in SKIP_FILES:
            continue
        if rel.startswith("faq/") or rel.startswith("en/faq/"):
            continue
        # Skip directories containing duplicate/noindex pages
        parts = set(Path(rel).parent.parts)
        if parts & SKIP_DIRS:
            continue
        # Also skip any file/dir whose clean URL path matches a SKIP_DIR entry
        clean = rel
        if clean.endswith("/index.html"):
            clean = clean[:-11]
        elif clean.endswith(".html"):
            clean = clean[:-5]
        if clean in SKIP_DIRS:
            continue
        if "/" + clean in redirected:
            dropped["redirect"] += 1
            continue
        if has_noindex(path):
            dropped["noindex"] += 1
            continue
        pages.append((path, rel))

    print(
        f"excluded: {dropped['redirect']} redirected (301), "
        f"{dropped['noindex']} noindex"
    )

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

        alternates = pepperoni_alternates(rel)
        if not alternates:
            partners = by_key.get(key, {})
            if len(partners) >= 2 or (lang == "en" and "ru" in partners) or (lang == "ru" and "en" in partners):
                for l in ("ru", "en"):
                    if l in partners:
                        alternates.append((l, html_to_url(partners[l])))
                x_default = html_to_url(partners.get("ru") or partners.get("en"))
                alternates.append(("x-default", x_default))

        entries.append({
            "url":        url,
            "lastmod":    mtime_iso(path, url, previous_lastmod, changed),
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
