#!/usr/bin/env python3
"""Build sitemap.xml strictly from data/index_manifest.json.

The filesystem is not an index policy.  Unknown HTML, retired URLs and
noindexed advertising pages are never discovered into the sitemap.  Lastmod is
content-hash based, so a generator touching a file without changing its bytes
does not advertise false freshness.
"""

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

ROOT    = Path(__file__).parent.parent
PUBLIC  = ROOT / "public"
NGINX   = ROOT / "deploy" / "nginx"
MANIFEST = ROOT / "data" / "index_manifest.json"
CONTENT_STATE = ROOT / "data" / "sitemap_content_state.json"
BASE    = "https://pepperoni.tatar"
TODAY   = date.today().isoformat()

# page type → (priority, changefreq)
RULES = {
    "root":     (1.00, "weekly"),
    "catalog":  (0.70, "weekly"),
    "product":  (0.80, "weekly"),
    "home":     (1.00, "weekly"),
    "guide":    (0.70, "monthly"),
    "hub":      (0.80, "monthly"),
    "export-country": (0.70, "monthly"),
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
                paths.add(path.strip().strip('"').rstrip("/") or "/")
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


def mtime_iso(path: Path) -> str:
    """W3C-datetime lastmod from file mtime; falls back to today."""
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return TODAY


def content_lastmods(paths: list[Path]) -> dict[str, str]:
    """Return stable lastmod values and persist hashes for the next run."""
    try:
        previous = json.loads(CONTENT_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        previous = {}
    old_files = previous.get("files", {}) if isinstance(previous, dict) else {}
    new_files: dict[str, dict[str, str]] = {}
    out: dict[str, str] = {}
    for path in paths:
        rel = str(path.relative_to(PUBLIC))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        old = old_files.get(rel, {})
        lastmod = (
            old.get("lastmod")
            if old.get("sha256") == digest and old.get("lastmod")
            else mtime_iso(path)
        )
        out[rel] = lastmod
        new_files[rel] = {"sha256": digest, "lastmod": lastmod}
    CONTENT_STATE.write_text(
        json.dumps(
            {"version": 1, "updated_at": TODAY, "files": new_files},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return out


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
    if not MANIFEST.exists():
        raise SystemExit(
            "index manifest missing; run python3 scripts/build_index_manifest.py")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep_rows = [
        row for row in manifest.get("entries", [])
        if row.get("status") == "keep"
    ]
    minimum = int(manifest.get("policy", {}).get("indexable_min", 180))
    maximum = int(manifest.get("policy", {}).get("indexable_max", 250))
    if not minimum <= len(keep_rows) <= maximum:
        raise SystemExit(
            f"manifest keep count {len(keep_rows)} outside {minimum}..{maximum}")

    redirected = redirect_sources()
    pages: list[tuple[Path, str, dict]] = []
    errors: list[str] = []
    seen_urls: set[str] = set()
    for row in keep_rows:
        rel = str(row.get("file") or "")
        url_path = str(row.get("url") or "")
        path = PUBLIC / rel
        if not rel or not url_path.startswith("/"):
            errors.append(f"invalid manifest row: {row}")
            continue
        if url_path in seen_urls:
            errors.append(f"duplicate manifest URL: {url_path}")
        seen_urls.add(url_path)
        if not path.is_file():
            errors.append(f"missing keep file: {rel}")
            continue
        if row.get("language") not in {"ru", "en"}:
            errors.append(f"unsupported language for {url_path}: {row.get('language')}")
        expected_lang = "en" if rel.startswith("en/") else "ru"
        if row.get("language") != expected_lang:
            errors.append(
                f"language/file mismatch for {url_path}: "
                f"{row.get('language')} != {expected_lang}")
        clean = url_path.rstrip("/") or "/"
        if clean in redirected:
            errors.append(f"keep URL is redirected by nginx: {url_path}")
        if has_noindex(path):
            errors.append(f"keep URL carries noindex: {url_path}")
        pages.append((path, rel, row))
    if errors:
        raise SystemExit("sitemap allowlist errors:\n" + "\n".join(errors))

    by_key: dict[str, dict[str, Path]] = {}
    for path, rel, _row in pages:
        key = pair_key(rel)
        lang = "en" if rel.startswith("en/") else "ru"
        by_key.setdefault(key, {})[lang] = path

    lastmods = content_lastmods([path for path, _rel, _row in pages])
    entries = []
    for path, rel, row in pages:
        key = pair_key(rel)
        url = html_to_url(path)
        expected = BASE + row["url"]
        if row["url"] == "/":
            expected = BASE + "/"
        if url.rstrip("/") != expected.rstrip("/"):
            raise SystemExit(
                f"manifest URL/file mismatch: {row['url']} != {url} ({rel})")
        kind = str(row.get("kind") or classify(rel))
        pri, freq = RULES.get(kind, RULES["static"])
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
            "lastmod":    lastmods[rel],
            "changefreq": freq,
            "priority":   pri,
            "alternates": alternates,
            "kind":       kind,
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
    kinds = Counter(e["kind"] for e in entries)
    print("\nBreakdown:")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k:12} {v:4} pages")

    with_alt = sum(1 for e in entries if e["alternates"])
    print(f"\nURLs with hreflang alternates: {with_alt}/{len(entries)}")


if __name__ == "__main__":
    main()
