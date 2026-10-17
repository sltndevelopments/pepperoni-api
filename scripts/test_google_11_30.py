#!/usr/bin/env python3
"""Exact-query wording on Google 11–30 landings outside the wholesale hubs."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CSV_PATH = ROOT / "docs" / "seo" / "google-11-30-2026-10-17.csv"
WHOLESALE = {
    "/sosiski-dlya-hotdog",
    "/kotlety-dlya-burgerov",
    "/vetchina-optom",
    "/pepperoni",
    "/sosiski-halyal-optom",
    "/dlya-horeca",
    "/en/pepperoni",
}
LCP_HUBS = (
    "sosiski-dlya-hotdog.html",
    "kotlety-dlya-burgerov.html",
    "sosiski-halyal-optom.html",
)
TITLE_SYNC = (
    "blog/echpochmak.html",
    "blog/elesh.html",
    "blog/kazylyk.html",
    "en/blog/what-is-halal-pepperoni.html",
    "kontraktnoe-proizvodstvo.html",
    "pepperoni-dlya-pizzerii.html",
)

# query → file; must appear in title or H1 or lead/FAQ
QUERIES = [
    ("татарская колбаса из конины", "kazylyk.html"),
    ("конская колбаса название у татар", "blog/kazylyk.html"),
    ("what is halal pepperoni made of", "en/blog/what-is-halal-pepperoni.html"),
    ("is pepperoni halal", "en/blog/what-is-halal-pepperoni.html"),
    ("эчпочмак это", "blog/echpochmak.html"),
    ("элеш это", "blog/elesh.html"),
    ("что такое эчпочмак", "blog/echpochmak.html"),
    ("губадия это", "blog/echpochmak.html"),
    ("что такое эчпочмак в казани", "blog/echpochmak.html"),
    ("что значит курица халяль", "halal.html"),
    ("размеры пиццы", "pepperoni-dlya-pizzerii.html"),
]

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def visible(html: str) -> str:
    title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    parts = [
        title.group(1) if title else "",
        re.sub(r"<[^>]+>", " ", h1.group(1)) if h1 else "",
        html,
    ]
    return re.sub(r"\s+", " ", " ".join(parts)).lower()


def title_text(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def h1_of(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1) if m else "")).strip()


def og_title(html: str) -> str:
    m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        html,
        re.I,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            html,
            re.I,
        )
    return (m.group(1).strip() if m else "")


def jsonld_nodes(html: str, rel: str) -> list:
    nodes = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    ):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError as exc:
            check(False, f"{rel} JSON-LD is valid JSON ({exc})")
            continue
        if isinstance(data, list):
            nodes.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            nodes.append(data)
    return nodes


def article_headline(html: str, rel: str = "") -> str | None:
    found = None
    for node in jsonld_nodes(html, rel):
        if node.get("@type") == "Article":
            found = str(node.get("headline") or "").strip()
    return found


def main() -> int:
    check(CSV_PATH.is_file(), "CSV report exists")
    if CSV_PATH.is_file():
        rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
        check(rows and {"query", "gsc_pos", "url", "old_title", "new_title", "old_h1", "new_h1"}
              <= set(rows[0]), "CSV has required columns")
        queries = [row["query"] for row in rows]
        check("контрактное производство печенья" not in queries,
              "CSV dropped cookie STM row")
        for row in rows:
            check(row["url"] not in WHOLESALE, f"CSV row not a wholesale hub: {row['query']}")
            check("казанские деликатесы" not in row["query"].lower()
                  or "brand" in row.get("query", ""),
                  f"no brand-intent row: {row['query']}")
    for query, rel in QUERIES:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        check(query.lower() in visible(html), f"{rel} contains «{query}»")
        check("халяль бургер" not in html.lower(), f"{rel} has no burger-halal claim")

    stm = (PUBLIC / "kontraktnoe-proizvodstvo.html").read_text(encoding="utf-8")
    check(title_text(stm) == "Контрактное производство халяль продукции под СТМ",
          "STM title is sausage/pepperoni private-label")
    check(h1_of(stm) == "Контрактное производство халяль колбас, сосисок и пепперони под вашим брендом",
          "STM H1 is sausage/pepperoni private-label")
    check("печень" not in title_text(stm).lower() and "печень" not in h1_of(stm).lower(),
          "STM title/H1 have no cookie claim")
    check("Печенья в каталоге нет" in stm and "/vyipechka-halyal" in stm,
          "STM has one honest bakery sentence")

    pizza = (PUBLIC / "pepperoni-dlya-pizzerii.html").read_text(encoding="utf-8")
    check("поставки мяса в рестораны" not in title_text(pizza).lower(),
          "pizza title does not own HoReCa query")
    check("поставки мяса в рестораны" not in h1_of(pizza).lower(),
          "pizza H1 does not own HoReCa query")
    check("/dlya-horeca" in pizza, "pizza links to /dlya-horeca")
    check("50–55" in pizza or "50-55" in pizza, "pizza FAQ uses catalog slice diameter")

    for rel in TITLE_SYNC:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        title = title_text(html)
        h1 = h1_of(html)
        og = og_title(html)
        check(bool(title) and og == title, f"{rel} og:title equals <title>")
        headline = article_headline(html, rel)
        if headline is not None:
            check(headline == title, f"{rel} Article headline equals <title>")
            check(headline == h1, f"{rel} Article headline equals H1")

    kazylyk = (PUBLIC / "blog/kazylyk.html").read_text(encoding="utf-8")
    check("как называется конская колбаса у татар" in title_text(kazylyk).lower(),
          "kazylyk title is natural and keeps the query")
    ech = (PUBLIC / "blog/echpochmak.html").read_text(encoding="utf-8")
    check("татарский пирожок" in title_text(ech).lower(),
          "echpochmak title is natural")

    en_home = (PUBLIC / "en/index.html").read_text(encoding="utf-8")
    crumbs = []
    for node in jsonld_nodes(en_home, "en/index.html"):
        if node.get("@type") == "BreadcrumbList":
            crumbs = node.get("itemListElement") or []
    check(len(crumbs) == 1, "EN homepage BreadcrumbList has one level")
    if crumbs:
        item = crumbs[0].get("item") if isinstance(crumbs[0], dict) else ""
        check(str(item).rstrip("/") == "https://pepperoni.tatar/en",
              "EN homepage breadcrumb points at /en")

    for rel in LCP_HUBS:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        head = html.split("</head>", 1)[0]
        check('rel="preload"' in html and "as=\"font\"" in html.replace("'", '"'),
              f"{rel} preloads the main font")
        check("font-display:swap" in html.replace(" ", ""),
              f"{rel} fonts use font-display:swap")
        check('id="kd-hero-critical"' in head, f"{rel} inlines hero critical CSS")
        check("animation:none" in html.replace(" ", ""),
              f"{rel} hero text has no opacity/transform animation")
        check("gtm.js" not in head.lower() and "GTM-W2Q5S8HF" not in head,
              f"{rel} has no GTM in <head>")
        check("googletagmanager.com" not in head and "mc.yandex.ru" not in head,
              f"{rel} does not preconnect third-party analytics")
        check("application/ld+json" not in head, f"{rel} keeps JSON-LD out of <head>")
        body = html.split("</head>", 1)[1] if "</head>" in html else ""
        body_no_js = re.sub(
            r"<script\b(?![^>]*application/ld\+json)[^>]*>.*?</script>",
            "",
            body,
            flags=re.I | re.S,
        )
        check("application/ld+json" in body_no_js, f"{rel} keeps JSON-LD as static body HTML")
        check('"@type":"Organization"' in body_no_js.replace(" ", ""),
              f"{rel} static HTML has Organization JSON-LD")
        check('"@type":"BreadcrumbList"' in body_no_js.replace(" ", ""),
              f"{rel} static HTML has BreadcrumbList JSON-LD")
        check("loadAnalytics" in html, f"{rel} delays GTM/Metrika until after load")
        check("setTimeout(loadAnalytics,1500)" in html.replace(" ", ""),
              f"{rel} Metrika has a 1.5s timeout so bounces still count")
        check("addEventListener('load',armAnalytics)" in html
              or 'addEventListener("load",armAnalytics)' in html,
              f"{rel} arms analytics on window load")
        check(
            re.search(r'<script[^>]+src=["\']/assets/lead-form\.js["\'][^>]*\bdefer', html, re.I),
            f"{rel} lead-form.js is defer",
        )
        head_wo_ns = re.sub(r"<noscript\b[^>]*>.*?</noscript>", "", head, flags=re.I | re.S)
        blocking_css = re.findall(
            r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', head_wo_ns, re.I,
        )
        extra = [tag for tag in blocking_css if 'media="print"' not in tag]
        check(not extra, f"{rel} has no render-blocking stylesheet")

    chrome_src = (ROOT / "scripts" / "landing_chrome.py").read_text(encoding="utf-8")
    cat_src = (ROOT / "scripts" / "gen_category_pages.py").read_text(encoding="utf-8")
    check("setTimeout(loadAnalytics,1500)" in chrome_src.replace(" ", ""),
          "landing_chrome Metrika timeout is bounce-safe")
    check("application/ld+json" not in chrome_src,
          "landing_chrome does not inject JSON-LD from JS")
    check('"ld_tail": ld_html' in cat_src and "insertAdjacent" not in cat_src,
          "category generator emits JSON-LD as static ld_tail markup")

    if fail:
        print(f"test_google_11_30: {fail} FAIL")
        return 1
    print("test_google_11_30: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
