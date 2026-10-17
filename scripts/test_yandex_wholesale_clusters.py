#!/usr/bin/env python3
"""Yandex wholesale-cluster retargets on existing keep hubs (2026-10-17)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
fail = 0

QUERIES = {
    "sosiski-dlya-hotdog.html": [
        "сосиски для хот догов оптом",
        "сосиски для хот догов купить оптом",
        "поставщик сосисок для хот догов",
        "халяль сосиски для хот догов",
        "сосиски для хот догов купить оптом в москве",
    ],
    "kotlety-dlya-burgerov.html": [
        "котлеты для бургеров оптом",
        "котлеты для гамбургеров оптом",
        "котлеты для бургеров купить оптом",
        "купить котлеты для бургеров оптом",
        "котлеты для бургеров опт",
    ],
    "vetchina-optom.html": [
        "ветчина халяль",
        "ветчина из курицы халяль",
    ],
    "pepperoni.html": [
        "пепперони халяль купить",
        "пепперони халяль колбаса",
        "колбаса пепперони халяль",
    ],
    "sosiski-halyal-optom.html": [
        "сосиски халяль оптом",
    ],
    "dlya-horeca.html": [
        "поставки мяса в рестораны",
    ],
}


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html_of(rel: str) -> str:
    return (PUBLIC / rel).read_text(encoding="utf-8")


def title_of(rel: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html_of(rel), re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def h1_of(rel: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html_of(rel), re.I | re.S)
    return re.sub(r"<[^>]+>", " ", m.group(1)).strip() if m else ""


def first_p(rel: str) -> str:
    text = html_of(rel)
    m = re.search(r"<h1[^>]*>.*?</h1>(.*?)(?:<h2|id=\"assortiment\")", text, re.I | re.S)
    chunk = m.group(1) if m else text
    return re.sub(r"<[^>]+>", " ", chunk)


def fold(text: str) -> str:
    return re.sub(r"[\s\-]+", " ", text).lower()


def faq_text(rel: str) -> str:
    text = html_of(rel)
    bits = re.findall(r"<summary>(.*?)</summary>", text, re.I | re.S)
    bits += re.findall(r'"@type":\s*"Question"[^}]*"name":\s*"([^"]+)"', text)
    return fold(" ".join(re.sub(r"<[^>]+>", " ", b) for b in bits))


def org_nodes(rel: str) -> int:
    n = 0
    for blob in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html_of(rel), re.I | re.S
    ):
        try:
            node = json.loads(blob)
        except json.JSONDecodeError:
            continue
        stack = node if isinstance(node, list) else [node]
        for item in stack:
            if isinstance(item, dict) and item.get("@type") == "Organization":
                n += 1
    return n


def main() -> int:
    for rel, queries in QUERIES.items():
        title, h1, lead, faq = fold(title_of(rel)), fold(h1_of(rel)), fold(first_p(rel)), faq_text(rel)
        page = fold(html_of(rel))
        surface = " ".join((title, h1, lead, faq))
        for q in queries:
            qn = fold(q)
            check(qn in surface, f"{rel} title/H1/lead/FAQ has {q!r}")
            check(qn in title or qn in h1 or qn in lead, f"{rel} title/H1/lead has {q!r}")
        check("минимальный заказ — 1 паллета" in page or "minimum order: 1 pallet" in page,
              f"{rel} canonical MOQ")
        check(org_nodes(rel) == 1, f"{rel} one Organization node")
        check("₽" not in title_of(rel) and "$" not in title_of(rel), f"{rel} title has no price")

    kot = fold(html_of("kotlety-dlya-burgerov.html"))
    check("100% говядин" not in kot, "kotlety does not claim 100% beef")
    check("халяль бургер" not in kot, "kotlety has no burger-halal claim")
    check("говядин" in kot and "окорочк" in kot, "kotlety names beef + chicken thigh")
    check("москв" not in fold(title_of("kotlety-dlya-burgerov.html")),
          "kotlety title has no Москва")

    vet = html_of("vetchina-optom.html")
    check("/products/kd-030" in vet and "KD-011" in vet and "KD-030" in vet,
          "vetchina chicken-ham section lists KD-011/030")
    check("/vetchina-optom" in html_of("products/kd-030.html"),
          "KD-030 links the ham hub")

    hot = html_of("sosiski-dlya-hotdog.html")
    check('id="dostavka"' in hot and "Москв" in hot, "hotdog has Moscow delivery block")
    check("/about" in hot and "/delivery" in hot, "hotdog delivery cites /about and /delivery")
    check(not re.search(r"\d+\s*(день|дня|дней|сут)", hot.split('id="dostavka"', 1)[-1][:800]),
          "hotdog delivery invents no transit days")

    pep = title_of("pepperoni.html")
    what = title_of("blog/what-is-halal-pepperoni.html")
    check(pep != what, "pepperoni titles stay distinct")
    check("что такое" in what.lower() or "из чего" in what.lower(),
          "what-is-halal-pepperoni stays informational")

    home = html_of("index.html")
    products = html_of("products/index.html")
    for href in (
        "/sosiski-dlya-hotdog",
        "/kotlety-dlya-burgerov",
        "/vetchina-optom",
        "/pepperoni",
        "/sosiski-halyal-optom",
        "/dlya-horeca",
    ):
        check(href in home, f"home links {href}")
        check(href in products, f"/products links {href}")

    check("kd-landing" in html_of("kotlety-dlya-burgerov.html"), "kotlety uses kd-landing")
    check("kd-landing" in html_of("vetchina-optom.html"), "vetchina uses kd-landing")
    check("jerks-landing" in html_of("sosiski-halyal-optom.html"), "chilled sausages keep jerks cards")

    print(f"test_yandex_wholesale_clusters: {'ok' if fail == 0 else f'{fail} FAIL'}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
