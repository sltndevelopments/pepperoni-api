#!/usr/bin/env python3
"""Every keep page and every semantic-core landing needs ≥3 inbound keep links.

    python3 scripts/check_inbound_links.py           # exit 1 on orphans
    python3 scripts/check_inbound_links.py --apply   # inject keep-inbound blocks

Counts only hrefs from other allowlist (keep) pages. Self-links, mailto/tel,
external hosts and fragment-only hrefs are ignored.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
MANIFEST = ROOT / "data" / "index_manifest.json"
ORIGIN = "https://pepperoni.tatar"
MIN_INBOUND = 3
START, END = "<!-- keep-inbound:start -->", "<!-- keep-inbound:end -->"
BLOCK_RX = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.S)
HREF_RE = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
HIDDEN_MARKUP_RE = re.compile(
    r"<!--.*?-->|<script\b[^>]*>.*?</script>|<template\b[^>]*>.*?</template>",
    re.I | re.S,
)

# Unique target URLs from the 58-query core (yadro-zaprosov-v2, 17.10.2026).
CORE_LANDINGS = (
    "/",
    "/blog/kazylyk",
    "/kazylyk",
    "/en/blog/kazylyk-horse-meat-sausage",
    "/blog/pepperoni-iz-kakogo-myasa",
    "/en/blog/what-is-halal-pepperoni",
    "/blog/what-is-halal-pepperoni",
    "/vetchina-optom",
    "/products/kd-030",
    "/en/products/kd-011",
    "/pepperoni",
    "/en/pepperoni",
    "/sosiski-dlya-hotdog",
    "/kotlety-dlya-burgerov",
    "/blog/echpochmak",
    "/blog/elesh",
    "/en",
    "/halal",
    "/pepperoni-dlya-pizzerii",
    "/sosiska-v-teste",
    "/kontraktnoe-proizvodstvo",
    "/en/chak-chak-optom",
)

# Parallel wholesale PR owns these files — never rewrite them here.
DISJOINT_SKIP = {
    "index.html",
    "dlya-horeca.html",
    "en/pepperoni.html",
    "kotlety-dlya-burgerov.html",
    "pepperoni.html",
    "products/index.html",
    "products/kd-030.html",
    "sosiski-dlya-hotdog.html",
    "sosiski-halyal-optom.html",
    "vetchina-optom.html",
    "blog/pepperoni-for-pizzeria-horeca.html",
}

RU_CLUSTER = [
    ("/blog/echpochmak", "эчпочмак это"),
    ("/blog/elesh", "элеш это"),
    ("/blog/kazylyk", "казылык — что это"),
    ("/blog/kuritsa-halyal-chem-otlichaetsya", "курица халяль чем отличается"),
    ("/blog/halal-certification-russia", "халяль-сертификация в России"),
    ("/blog/pepperoni-for-pizzeria-horeca", "пепперони для пиццерии"),
    ("/blog/private-label-kolbasnyh-izdeliy", "СТМ колбасных изделий"),
    ("/blog/tolko-halyal-kakie-kategorii-myasa", "какие категории мяса халяль"),
    ("/editorial-policy", "редакционная политика"),
    ("/pepperoni-v-narezke", "пепперони в нарезке"),
    ("/kazylyk", "казылык оптом"),
    ("/halal", "халяль сертификат"),
    ("/pepperoni-dlya-pizzerii", "пепперони для пиццерии оптом"),
    ("/kontraktnoe-proizvodstvo", "контрактное производство"),
]

EN_CLUSTER = [
    ("/en/blog/what-is-halal-pepperoni", "what is halal pepperoni made of"),
    ("/en/blog/wholesale-pepperoni-russia-export", "wholesale pepperoni export"),
    ("/en/blog/halal-certification-russia", "halal certification in Russia"),
    ("/en/blog/pepperoni-for-pizzeria-horeca", "pepperoni for pizzerias"),
    ("/en/editorial-policy", "editorial policy"),
    ("/en/pepperoni-v-narezke", "sliced pepperoni"),
    ("/en/chak-chak-optom", "chak-chak wholesale"),
]

RU_DONORS = (
    "about.html",
    "delivery.html",
    "faq.html",
    "price.html",
    "kak-zakazat.html",
    "vyipechka-halyal.html",
    "kontraktnoe-proizvodstvo.html",
    "pepperoni-dlya-pizzerii.html",
    "kazylyk.html",
    "halal.html",
    "blog.html",
    "blog/echpochmak.html",
    "blog/elesh.html",
    "blog/kazylyk.html",
    "blog/what-is-halal-pepperoni.html",
    "export.html",
    "halyal-vypechka-optom-dlya-pekaren.html",
)

EN_DONORS = (
    "en/about.html",
    "en/delivery.html",
    "en/faq.html",
    "en/price.html",
    "en/kak-zakazat.html",
    "en/halal.html",
    "en/blog.html",
    "en/blog/what-is-halal-pepperoni.html",
    "en/pepperoni-dlya-pizzerii.html",
    "en/export.html",
    "en/editorial-policy.html",
)


def norm_path(url: str) -> str:
    if not url:
        return ""
    raw = url.strip()
    if raw.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return ""
    if raw.startswith("http"):
        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        if host and "pepperoni.tatar" not in host:
            return ""
        path = parsed.path
    else:
        path = raw.split("#", 1)[0].split("?", 1)[0]
    path = re.sub(r"\.html$", "", path)
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def keep_entries() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [row for row in manifest.get("entries", []) if row.get("status") == "keep"]


def keep_url_set(entries: list[dict] | None = None) -> set[str]:
    return {norm_path(row["url"]) for row in (entries or keep_entries())}


def file_for_url(url: str, entries: list[dict] | None = None) -> str | None:
    want = norm_path(url)
    for row in entries or keep_entries():
        if norm_path(row["url"]) == want:
            return row.get("file")
    return None


def visible_markup(html: str) -> str:
    """Drop comments and non-rendered href hosts before counting inbound links."""
    return HIDDEN_MARKUP_RE.sub("", html)


def extract_hrefs(html: str, src_url: str) -> set[str]:
    found: set[str] = set()
    html = visible_markup(html)
    base = ORIGIN + (src_url if src_url != "/" else "/")
    for raw in HREF_RE.findall(html):
        dest = norm_path(urljoin(base if base.endswith("/") else base + "/", raw))
        if dest:
            found.add(dest)
    return found


def inbound_graph(entries: list[dict] | None = None) -> dict[str, set[str]]:
    rows = entries or keep_entries()
    keep = keep_url_set(rows)
    inbound: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        rel = row.get("file")
        path = PUBLIC / rel if rel else None
        if not path or not path.is_file():
            continue
        src = norm_path(row["url"])
        html = path.read_text(encoding="utf-8", errors="ignore")
        for dest in extract_hrefs(html, src):
            if dest in keep and dest != src:
                inbound[dest].add(src)
    return inbound


def required_urls(entries: list[dict] | None = None) -> list[str]:
    rows = entries or keep_entries()
    keep = keep_url_set(rows)
    required = set(keep)
    for url in CORE_LANDINGS:
        path = norm_path(url)
        if path in keep:
            required.add(path)
    return sorted(required)


def orphans(inbound: dict[str, set[str]] | None = None,
            entries: list[dict] | None = None) -> list[tuple[str, int]]:
    graph = inbound or inbound_graph(entries)
    weak = []
    for url in required_urls(entries):
        count = len(graph.get(url, set()))
        if count < MIN_INBOUND:
            weak.append((url, count))
    return weak


def cluster_block(lang: str, current: str) -> str:
    items = RU_CLUSTER if lang == "ru" else EN_CLUSTER
    here = norm_path(current)
    links = []
    for href, label in items:
        if norm_path(href) == here:
            continue
        links.append(f'<a href="{escape(href)}">{escape(label)}</a>')
    heading = "Читайте также" if lang == "ru" else "Related pages"
    joined = " · ".join(links)
    return (
        f"{START}\n"
        f'<nav class="keep-inbound" aria-label="{escape(heading)}" '
        f'style="font-size:.9rem;line-height:1.7;padding:14px 16px;margin:18px 0;'
        f'background:#f7f6f2;border:1px solid #e6e4df;border-radius:14px">'
        f"<strong>{escape(heading)}</strong><br>{joined}</nav>\n"
        f"{END}\n"
    )


def _inject(html: str, block: str) -> str:
    if BLOCK_RX.search(html):
        return BLOCK_RX.sub(block, html, count=1)
    if "<!-- site-links:start -->" in html:
        return html.replace("<!-- site-links:start -->", block + "<!-- site-links:start -->", 1)
    lowered = html.lower()
    idx = lowered.rfind("</footer>")
    if idx != -1:
        return html[:idx] + block + html[idx:]
    idx = lowered.rfind("</body>")
    if idx != -1:
        return html[:idx] + block + html[idx:]
    return html + block


def apply_blocks() -> int:
    changed = 0
    for rel, lang in [(p, "ru") for p in RU_DONORS] + [(p, "en") for p in EN_DONORS]:
        if rel in DISJOINT_SKIP:
            continue
        path = PUBLIC / rel
        if not path.is_file():
            print(f"skip missing {rel}", file=sys.stderr)
            continue
        current = "/" + rel[:-5] if rel.endswith(".html") else "/" + rel
        current = current.replace("/index", "/")
        if current.startswith("/en/"):
            pass
        html = path.read_text(encoding="utf-8")
        block = cluster_block(lang, current)
        updated = _inject(html, block)
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            changed += 1
            print(f"  inbound {rel}")
    return changed


def report(weak: list[tuple[str, int]]) -> int:
    if not weak:
        print(f"check_inbound_links: ok (≥{MIN_INBOUND} inbound for "
              f"{len(required_urls())} keep+core URLs)")
        return 0
    print(f"check_inbound_links: {len(weak)} URL(s) below {MIN_INBOUND} inbound")
    for url, count in weak:
        print(f"  {count} {url}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        print(f"injected {apply_blocks()} keep-inbound block(s)")
    return report(orphans())


if __name__ == "__main__":
    raise SystemExit(main())
