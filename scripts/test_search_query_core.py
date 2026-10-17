#!/usr/bin/env python3
"""Guards for the search-query-core URL and page repairs. No network."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_index_manifest import build_manifest  # noqa: E402
from inject_site_links import site_organizations, url_to_file  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
NGINX = ROOT / "deploy" / "nginx"
MANIFEST = ROOT / "data" / "index_manifest.json"
RETIRE = ROOT / "data" / "url_consolidation_map.json"
SITEMAP = PUBLIC / "sitemap.xml"
ORIGIN = "https://pepperoni.tatar"

LOC_301 = re.compile(
    r"location\s*=\s*(\S+)\s*\{[^}]*return\s+301\s+(\S+);", re.S
)
LOC_410 = re.compile(
    r"location\s*=\s*(\S+)\s*\{[^}]*return\s+410\s*;", re.S
)
HREF_RE = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
CANON_RE = re.compile(
    r"""<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']""", re.I
)
NOINDEX_RE = re.compile(
    r"""<meta[^>]+name=["']robots["'][^>]*content=["'][^"']*noindex""", re.I
)
FAQ_LD_RE = re.compile(r'"@type"\s*:\s*"FAQPage"')
ORG_LD_RE = re.compile(r'"@type"\s*:\s*"Organization"')


def _norm(path: str) -> str:
    parsed = urlparse(path)
    value = parsed.path if parsed.scheme else path
    value = re.sub(r"\.html$", "", value)
    value = "/" + value.lstrip("/")
    return value.rstrip("/") or "/"


def nginx_raw_301() -> dict[str, str]:
    """Exact nginx 301 sources (keep .html and trailing slash) → dest path."""
    redirects: dict[str, str] = {}
    for conf in sorted(NGINX.glob("*redirects.conf")):
        text = conf.read_text(encoding="utf-8", errors="replace")
        for src, dst in LOC_301.findall(text):
            source = src.strip().strip('"')
            if not source.startswith("/"):
                source = "/" + source
            redirects[source] = _norm(dst.strip('"'))
    return redirects


def nginx_maps() -> tuple[dict[str, str], set[str]]:
    raw = nginx_raw_301()
    redirects = {_norm(src): dst for src, dst in raw.items()}
    gone: set[str] = set()
    gone_text = (NGINX / "trust-reset-gone.conf").read_text(
        encoding="utf-8", errors="replace"
    )
    for src in LOC_410.findall(gone_text):
        gone.add(_norm(src.strip('"')))
    return redirects, gone


def generated_html_files(manifest: dict, retire: dict) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    rows = list(manifest.get("entries") or []) + list(retire.get("entries") or [])
    for row in rows:
        if row.get("status") not in {"keep", "noindex"}:
            continue
        rel = row.get("file") or ""
        if not rel or rel in seen:
            continue
        path = PUBLIC / rel
        if path.is_file():
            seen.add(rel)
            files.append(path)
    return files


def follow(path: str, redirects: dict[str, str]) -> list[str]:
    seen = [path]
    cur = path
    for _ in range(8):
        nxt = redirects.get(cur)
        if not nxt:
            return seen
        if nxt in seen:
            seen.append(nxt)
            return seen
        seen.append(nxt)
        cur = nxt
    return seen


def html(rel: str) -> str:
    return (PUBLIC / rel).read_text(encoding="utf-8")


def title_of(rel: str) -> str:
    match = TITLE_RE.search(html(rel))
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def check(cond: bool, label: str, failures: list[str]) -> None:
    if not cond:
        failures.append(label)
        print(f"FAIL  {label}")
    else:
        print(f"ok    {label}")


def main() -> int:
    failures: list[str] = []
    redirects, gone = nginx_maps()
    retire = json.loads(RETIRE.read_text(encoding="utf-8"))
    by_url = {row["url"]: row for row in retire["entries"]}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keep = {row["url"] for row in manifest["entries"] if row.get("status") == "keep"}
    keep_n = sum(1 for row in manifest["entries"] if row.get("status") == "keep")

    # 1) OEM / private-label stay on contract manufacturing (git: genuine СТМ).
    for src in (
        "/oem/hotdog-sausages",
        "/oem/hotdog-sausages.html",
        "/private-label/kotlety-dlya-burgerov-optom",
    ):
        check(
            redirects.get(_norm(src)) == "/kontraktnoe-proizvodstvo",
            f"{src} → /kontraktnoe-proizvodstvo",
            failures,
        )

    # 3) kazylyk / tatar sausage, not bakery wholesale.
    for src in ("/blog/tatarskaya-kolbasa", "/blog/tatarskaya-kolbasa-iz-koniny"):
        check(
            redirects.get(src) == "/kazylyk",
            f"{src} → /kazylyk",
            failures,
        )
        check(
            redirects.get(src) != "/halyal-vypechka-optom-dlya-pekaren",
            f"{src} is not bakery wholesale",
            failures,
        )

    # 4) ham / chicken demand URLs are not 410.
    ham = (
        "/blog/halal-ham-wholesale-guide-2026",
        "/blog/vetchina-iz-indeyki-halyal",
        "/blog/vetchina-iz-kuricy-halyal",
        "/blog/vetchina-fileynaya-halyal",
        "/en/blog/halal-ham-wholesale-guide-2026",
        "/blog/kurica-halyal-optom",
    )
    for src in ham:
        check(src not in gone, f"{src} is not 410", failures)
        target = redirects.get(src)
        check(target in keep, f"{src} 301s to a keep page ({target})", failures)

    # 7) bakery blog redirects undone.
    check(
        redirects.get("/blog/echpochmak-eto") == "/blog/echpochmak",
        "/blog/echpochmak-eto → /blog/echpochmak",
        failures,
    )
    check(
        redirects.get("/blog/elesh-s-kuricey") == "/blog/elesh",
        "/blog/elesh-s-kuricey → /blog/elesh",
        failures,
    )
    check(
        redirects.get("/blog/gubadiya-chto-eto") == "/vyipechka-halyal",
        "/blog/gubadiya-chto-eto → /vyipechka-halyal",
        failures,
    )
    for src in (
        "/blog/echpochmak-eto",
        "/blog/elesh-s-kuricey",
        "/blog/gubadiya-chto-eto",
        "/blog/gubadiya-eto",
        "/blog/what-is-echpochmak",
    ):
        check(
            redirects.get(src) != "/halyal-vypechka-optom-dlya-pekaren",
            f"{src} is not bakery wholesale",
            failures,
        )
    check(
        by_url["/blog/gubadiya-eto"]["status"] == "noindex",
        "/blog/gubadiya-eto restored as noindex",
        failures,
    )

    echo = html("blog/echpochmak.html")
    check(not NOINDEX_RE.search(echo), "/blog/echpochmak is indexable", failures)
    canon = CANON_RE.search(echo)
    check(canon is not None and canon.group(1).rstrip("/") == f"{ORIGIN}/blog/echpochmak",
          "/blog/echpochmak canonical is self", failures)
    check("/halyal-vypechka-optom-dlya-pekaren" in echo,
          "/blog/echpochmak links bakery wholesale", failures)
    check("/halyal-vypechka-optom-dlya-pekaren" in html("blog/elesh.html"),
          "/blog/elesh links bakery wholesale", failures)
    check("/halyal-vypechka-optom-dlya-pekaren" in html("blog/gubadiya-eto.html"),
          "/blog/gubadiya-eto links bakery wholesale", failures)

    # Redirect graph: one hop, no loops.
    chains = []
    loops = []
    for src, dst in redirects.items():
        hops = follow(src, redirects)
        if hops[-1] in hops[:-1]:
            loops.append(" → ".join(hops))
        elif len(hops) > 2:
            chains.append(" → ".join(hops))
    check(not loops, f"no redirect loops ({len(loops)})", failures)
    check(not chains, f"no redirect chains ({len(chains)})", failures)
    if chains:
        print("  chain sample:", "; ".join(chains[:5]))
    if loops:
        print("  loop sample:", "; ".join(loops[:5]))

    # Allowlist.
    check(180 <= keep_n <= 250, f"allowlist keep={keep_n} in 180..250", failures)
    check("/blog/echpochmak" in keep, "/blog/echpochmak is keep", failures)
    check("/blog/elesh" in keep, "/blog/elesh is keep", failures)
    check("/north-star" in keep, "/north-star is keep", failures)
    check("/en/editorial-policy" in keep, "/en/editorial-policy is keep", failures)
    check("/blog/karmin-e120-haram" not in keep, "/blog/karmin-e120-haram is not keep", failures)
    check("/en/blog/private-label-meat-products" not in keep,
          "/en/blog/private-label-meat-products is not keep", failures)
    check("/blog/private-label-kolbasnyh-izdeliy" in keep,
          "/blog/private-label-kolbasnyh-izdeliy stays keep", failures)
    check(by_url["/blog/karmin-e120-haram"]["status"] == "noindex",
          "/blog/karmin-e120-haram is noindex", failures)
    check(by_url["/en/blog/private-label-meat-products"]["status"] == "noindex",
          "/en/blog/private-label-meat-products is noindex", failures)
    check(
        redirects.get("/blog/karmin-e120-halyal") == "/blog/tolko-halyal-kakie-kategorii-myasa",
        "/blog/karmin-e120-halyal → keep guide",
        failures,
    )
    raw_301 = nginx_raw_301()
    check(
        raw_301.get("/blog/karmin-e120-halyal/") == "/blog/tolko-halyal-kakie-kategorii-myasa",
        "/blog/karmin-e120-halyal/ is a one-hop 301",
        failures,
    )
    variant_miss = []
    for src, dst in raw_301.items():
        hops = follow(dst, redirects)
        if len(hops) > 1:
            variant_miss.append(f"{src} dest chains {hops}")
            continue
        if src == "/" or src.endswith(".html") or src.endswith("/"):
            continue
        for variant in (src + ".html", src + "/"):
            if variant not in raw_301:
                variant_miss.append(f"missing {variant}")
            elif raw_301[variant] != dst:
                variant_miss.append(f"{variant} → {raw_301[variant]} != {dst}")
    check(not variant_miss, f"redirect variants are one hop ({len(variant_miss)})", failures)
    if variant_miss:
        print("  sample:", "; ".join(variant_miss[:8]))

    robots_tolko = re.search(
        r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)["\']',
        html("blog/tolko-halyal-kakie-kategorii-myasa.html"),
        re.I,
    )
    check(
        robots_tolko is not None
        and "index" in robots_tolko.group(1).lower()
        and "noindex" not in robots_tolko.group(1).lower(),
        "/blog/tolko-halyal-kakie-kategorii-myasa has index, follow",
        failures,
    )

    # Money pages do not link to 410 or noindex URLs.
    noindex_urls = {row["url"] for row in retire["entries"] if row.get("status") == "noindex"}
    money = [
        "pepperoni.html", "en/pepperoni.html",
        "kotlety-dlya-burgerov.html", "kazylyk.html",
        "price.html", "kak-zakazat.html",
        "chak-chak-optom.html",
        "halyal-vypechka-optom-dlya-pekaren.html",
        "vyipechka-halyal.html",
        "export.html",
    ]
    bad_links = []
    for rel in money:
        page_url = "/" + rel.removesuffix(".html")
        if rel.endswith("index.html"):
            page_url = "/" + rel[:-11].rstrip("/")
        text = html(rel)
        for raw in HREF_RE.findall(text):
            if raw.startswith(("mailto:", "tel:", "https://wa.me", "http://", "https://")):
                if raw.startswith(ORIGIN):
                    target = _norm(raw)
                else:
                    continue
            else:
                target = _norm(urljoin(page_url + "/", raw))
            if target in gone:
                bad_links.append(f"{page_url} → {target} (410)")
            elif target in noindex_urls and (
                target.startswith(("/blog/", "/en/blog/"))
                or target in {"/blog/gubadiya-eto"}
            ):
                bad_links.append(f"{page_url} → {target} (noindex)")
    check(not bad_links, f"money pages do not link 410/noindex ({len(bad_links)})", failures)
    if bad_links:
        print("  sample:", "; ".join(bad_links[:8]))

    # Page intent.
    kot = html("kotlety-dlya-burgerov.html")
    check("опт" in title_of("kotlety-dlya-burgerov.html").lower(),
          "kotlety title has wholesale intent", failures)
    check("опт" in re.search(r"<h1[^>]*>(.*?)</h1>", kot, re.I | re.S).group(1).lower(),
          "kotlety H1 has wholesale intent", failures)
    check("Получить КП" in kot and "<table" in kot and FAQ_LD_RE.search(kot),
          "kotlety has КП + spec table + FAQ", failures)
    check("Москв" not in title_of("kotlety-dlya-burgerov.html"),
          "kotlety title has no Москва", failures)

    kaz = html("kazylyk.html")
    check("опт" in title_of("kazylyk.html").lower(), "kazylyk title wholesale", failures)
    check("Получить КП" in kaz, "kazylyk has wholesale КП", failures)
    check(len(title_of("kazylyk.html")) <= 60, "kazylyk title ≤60", failures)

    pep = html("pepperoni.html")
    en_pep = html("en/pepperoni.html")
    check("Получить КП" in pep, "RU pepperoni has Получить КП", failures)
    check("Get a quote" in en_pep, "EN pepperoni has Get a quote", failures)
    check("/pepperoni" in html("blog/pepperoni-iz-kakogo-myasa.html"),
          "meat article links /pepperoni", failures)
    check("/en/pepperoni" in html("en/blog/what-is-halal-pepperoni.html"),
          "EN article links /en/pepperoni", failures)

    en_art = html("en/blog/what-is-halal-pepperoni.html")
    lead = re.search(r"<p class=\"lead\">(.*?)</p>", en_art, re.S)
    lead_txt = re.sub(r"<[^>]+>", " ", lead.group(1)).lower() if lead else ""
    check("chicken" in lead_txt and "made from" in lead_txt,
          "EN article first paragraph answers made-of", failures)
    check(FAQ_LD_RE.search(en_art), "EN article has FAQPage", failures)
    en_canon = CANON_RE.search(en_art)
    check(
        en_canon is not None
        and en_canon.group(1).rstrip("/") == f"{ORIGIN}/en/blog/what-is-halal-pepperoni",
        "EN article canonical is itself, not /en/blog",
        failures,
    )
    blog_list = html("en/blog.html")
    list_canon = CANON_RE.search(blog_list)
    check(
        list_canon is not None
        and list_canon.group(1).rstrip("/") == f"{ORIGIN}/en/blog",
        "/en/blog list canonical is the list",
        failures,
    )

    check(ORG_LD_RE.search(html("price.html")), "Organization JSON-LD on /price", failures)
    check(ORG_LD_RE.search(html("pepperoni.html")), "Organization JSON-LD on /pepperoni", failures)
    org_dupes = []
    for path in generated_html_files(manifest, retire):
        orgs = site_organizations(path.read_text(encoding="utf-8"))
        if len(orgs) != 1:
            org_dupes.append(f"{path.relative_to(PUBLIC)}={len(orgs)}")
    check(not org_dupes, f"exactly one Organization on generated pages ({len(org_dupes)})", failures)
    if org_dupes:
        print("  sample:", "; ".join(org_dupes[:8]))

    fresh = build_manifest()
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check(committed.get("counts") == fresh.get("counts"),
          "committed manifest counts match regenerated", failures)
    check(committed.get("entries") == fresh.get("entries"),
          "committed manifest entries match regenerated", failures)
    north_statuses = {row["status"] for row in committed["entries"] if row["url"] == "/north-star"}
    en_ed_statuses = {
        row["status"] for row in committed["entries"] if row["url"] == "/en/editorial-policy"
    }
    check(north_statuses == {"keep"}, "manifest /north-star is keep only", failures)
    check(en_ed_statuses == {"keep"}, "manifest /en/editorial-policy is keep only", failures)
    check(committed["counts"]["keep"] == 250, "manifest keep count is 250", failures)

    for rel, needle in (
        ("kotlety-dlya-burgerov.html", "/images/products/kd-009"),
        ("kazylyk.html", "/images/products/kd-044"),
        ("vetchina-optom.html", "/images/products/kd-028"),
    ):
        page = html(rel)
        check('class="hero"' in page and 'class="hero__media"' in page,
              f"{rel} has jerky/pepperoni hero", failures)
        check(needle in page, f"{rel} hero uses catalog product image", failures)
        check('class="tbl"' in page and "<table" in page, f"{rel} has styled spec table", failures)
        check("Получить КП" in page, f"{rel} has КП CTA", failures)
    check("Оптовым покупателям" in html("blog/what-is-halal-pepperoni.html")
          or "wholesale-buyers" in html("blog/what-is-halal-pepperoni.html"),
          "blog template has wholesale-buyers block", failures)

    products = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))["products"]
    skus = {p["sku"] for p in products}
    check({"KD-044", "KD-045"} <= skus, "kazylyk SKUs exist in products.json", failures)
    check({"KD-028", "KD-029", "KD-030"} <= skus, "ham SKUs exist in products.json", failures)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall search-query-core checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
