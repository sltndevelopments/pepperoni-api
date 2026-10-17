#!/usr/bin/env python3
"""SEO batch: query-targeted titles/H1s and cluster links on existing keep pages."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html(rel: str) -> str:
    return (PUBLIC / rel).read_text(encoding="utf-8")


def title_of(rel: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html(rel), re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def h1_of(rel: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html(rel), re.I | re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""


def desc_of(rel: str) -> str:
    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html(rel),
        re.I | re.S,
    )
    return m.group(1) if m else ""


def main() -> int:
    products = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))["products"]
    by_sku = {p["sku"]: p for p in products}
    check(by_sku["KD-009"]["category"] == "Котлеты для бургеров", "KD-009 is burger patty")
    check(by_sku["KD-010"]["category"] == "Котлеты для бургеров", "KD-010 is burger patty")
    check(by_sku["KD-008"]["category"] != "Котлеты для бургеров", "KD-008 is not a patty")
    check(by_sku["KD-044"]["category"] == "Премиум Казылык", "KD-044 is kazylyk")
    check(by_sku["KD-045"]["category"] == "Премиум Казылык", "KD-045 is kazylyk")

    kazy = html("kazylyk.html")
    check("Казылык оптом — сыровяленая колбаса из конины" in title_of("kazylyk.html"), "RU kazylyk title")
    check(h1_of("kazylyk.html").startswith("Казылык оптом"), "RU kazylyk H1")
    check("конины" in desc_of("kazylyk.html"), "RU kazylyk desc names horse meat")
    check('href="/blog/kazylyk"' in kazy, "RU kazylyk links to informational blog")
    check("KD-044" in kazy and "KD-045" in kazy, "RU kazylyk lists catalog SKUs")

    kot = html("kotlety-dlya-burgerov.html")
    check("Котлеты для бургеров оптом" in title_of("kotlety-dlya-burgerov.html"), "RU kotlety title")
    check("гамбургеров" in desc_of("kotlety-dlya-burgerov.html"), "RU kotlety desc covers гамбургеров")
    check('href="/blog/kotlety-dlya-burgerov-optom"' in kot, "RU kotlety links to guide")
    check("KD-009" in kot and "KD-010" in kot, "RU kotlety lists KD-009/010")
    check("KD-008" not in kot or "хот" in kot.lower(), "RU kotlety does not treat KD-008 as a patty")

    hot = html("sosiski-dlya-hotdog.html")
    check("Сосиски для хот-догов оптом" in title_of("sosiski-dlya-hotdog.html"), "RU hotdog title")
    check('href="/blog/sosiski-dlya-hot-dogov-optom"' in hot, "RU hotdog links to guide")

    pep = html("pepperoni.html")
    check("Пепперони халяль — купить оптом" in title_of("pepperoni.html"), "RU pepperoni title")
    check("куриный" in h1_of("pepperoni.html").lower() or "куриный" in pep, "RU pepperoni H1/body is chicken")
    check("паллет" in pep.lower() and "+7 987 217-02-02" in pep, "RU pepperoni hero has MOQ and phone")

    check("Казылык — что это" in title_of("blog/kazylyk.html"), "blog/kazylyk informational title")
    check("купить оптом" not in title_of("blog/kazylyk.html").lower(), "blog/kazylyk title has no купить оптом")
    check('href="/kazylyk"' in html("blog/kazylyk.html"), "blog/kazylyk bridges to commercial")

    desc_meat = desc_of("blog/pepperoni-iz-kakogo-myasa.html")
    check("куриная" in desc_meat, "pepperoni meat desc names chicken")
    check("KD-013" in desc_meat, "pepperoni meat desc names KD-013")
    check("не выпускаются" in desc_meat, "pepperoni meat desc says beef/horse are not in the line")

    check("Котлеты для бургеров оптом" in title_of("blog/kotlety-dlya-burgerov-optom.html"), "kotlety blog title")
    check("гамбургеров" in desc_of("blog/kotlety-dlya-burgerov-optom.html"), "kotlety blog covers гамбургеров")
    check("Сосиски для хот-догов оптом" in title_of("blog/sosiski-dlya-hot-dogov-optom.html"), "hotdog blog title")

    en_kot = html("en/kotlety-dlya-burgerov.html")
    check("KD-009" in title_of("en/kotlety-dlya-burgerov.html"), "EN kotlety title has KD-009")
    check("KD-008" not in en_kot.split("site-links")[0], "EN kotlety body has no KD-008")
    check("KD-010" in en_kot, "EN kotlety lists KD-010")
    check("100% beef" not in en_kot.lower() or "not 100% beef" in en_kot.lower(), "EN kotlety does not claim 100% beef")
    check('href="/en/blog/burger-patties-wholesale-halal"' in en_kot, "EN kotlety links to guide")

    en_kazy = html("en/kazylyk.html")
    check('href="/en/blog/kazylyk-horse-meat-sausage"' in en_kazy, "EN kazylyk links to guide")
    check("What is kazylyk" in title_of("en/blog/kazylyk-horse-meat-sausage.html"), "EN kazylyk blog title")
    check("wholesale from the maker" not in title_of("en/blog/kazylyk-horse-meat-sausage.html"), "EN kazylyk blog title not commercial")

    check("supplier" in title_of("en/pepperoni.html").lower(), "EN pepperoni title is B2B supplier")
    check("chicken" in desc_of("en/pepperoni.html").lower(), "EN pepperoni desc names chicken")

    man = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    keep = [e for e in man["entries"] if e.get("status") == "keep"]
    check(180 <= len(keep) <= 250, f"keep count {len(keep)} in 180–250")
    keep_urls = {e["url"] for e in keep}
    for url in (
        "/kazylyk",
        "/kotlety-dlya-burgerov",
        "/sosiski-dlya-hotdog",
        "/pepperoni",
        "/blog/kazylyk",
        "/blog/kotlety-dlya-burgerov-optom",
        "/blog/pepperoni-iz-kakogo-myasa",
        "/chak-chak-optom",
        "/halyal-vypechka-optom-dlya-pekaren",
    ):
        check(url in keep_urls, f"{url} stays keep")

    if fail:
        print(f"\n{fail} checks failed")
        return 1
    print("\nall seo-batch-rank checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
