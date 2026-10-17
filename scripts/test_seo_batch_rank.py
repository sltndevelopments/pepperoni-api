#!/usr/bin/env python3
"""SEO batch: query-targeted titles/H1s and cluster links on existing keep pages."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_facts import term  # noqa: E402
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
    check("+7 987 217-02-02" in pep, "RU pepperoni hero has phone")
    moq_ru = term("moq", "ru")
    if moq_ru:
        check(moq_ru in pep, "RU pepperoni MOQ follows site_facts.terms")
    else:
        check("паллет" not in pep.lower(), "RU pepperoni has no pallet wording without terms.moq")

    check("Казылык — что это" in title_of("blog/kazylyk.html"), "blog/kazylyk informational title")
    check("купить оптом" not in title_of("blog/kazylyk.html").lower(), "blog/kazylyk title has no купить оптом")
    check('href="/kazylyk"' in html("blog/kazylyk.html"), "blog/kazylyk bridges to commercial")

    meat_page = html("blog/pepperoni-iz-kakogo-myasa.html")
    desc_meat = desc_of("blog/pepperoni-iz-kakogo-myasa.html")
    og_meat = re.search(
        r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']',
        meat_page, re.I | re.S,
    )
    og_meat = og_meat.group(1) if og_meat else ""
    art_ld = None
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', meat_page, re.S):
        try:
            node = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if node.get("@type") == "Article":
            art_ld = node
            break
    art_desc = (art_ld or {}).get("description") or ""
    for label, text in (("meta", desc_meat), ("og", og_meat), ("Article JSON-LD", art_desc)):
        check("куриная" in text and "KD-013" in text and "KD-014" in text,
              f"pepperoni meat {label} names chicken KD-013/KD-014")
        check("не выпускаются" not in text and "конина" not in text.lower()
              and "говядина" not in text.lower() and "horse" not in text.lower(),
              f"pepperoni meat {label} does not mention other meats")

    kazy_desc = desc_of("kazylyk.html")
    check("мясная основа: конина и конский жир" in kazy_desc.lower(),
          "kazylyk desc calls composition a meat base")
    check("состав — конина и конский жир" not in kazy_desc.lower(),
          "kazylyk desc does not claim a two-ingredient composition")

    en_pep = html("en/pepperoni.html")
    en_offer = None
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', en_pep, re.S):
        try:
            node = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if node.get("@type") == "Product" and node.get("sku") == "KD-013":
            en_offer = node.get("offers") or {}
            break
    rub = str(by_sku["KD-013"]["offers"]["price"])
    check(en_offer is not None, "EN /pepperoni has KD-013 Product JSON-LD")
    check((en_offer or {}).get("priceCurrency") == "RUB",
          "EN KD-013 offer is RUB from products.json")
    check(str((en_offer or {}).get("price")) in {rub, str(float(rub)), "274", "274.0", "274.00"},
          f"EN KD-013 offer price is catalog {rub}")
    check(re.search(r'property=["\']product:price:amount["\']\s+content=["\']274(?:\.0+)?["\']', en_pep),
          "EN /pepperoni product:price:amount is 274")
    check(re.search(r'property=["\']product:price:currency["\']\s+content=["\']RUB["\']', en_pep),
          "EN /pepperoni product:price:currency is RUB")
    check("one pallet minimum" not in en_pep.lower(),
          "EN pepperoni does not invent 'one pallet minimum'")
    moq_en = term("moq", "en")
    if moq_en:
        check(moq_en.lower() in en_pep.lower(), "EN pepperoni MOQ follows site_facts.terms")
    else:
        check("mixed pallet" not in en_pep.lower() and "pallet moq" not in en_pep.lower(),
              "EN pepperoni has no pallet wording without terms.moq")

    catalog = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    sync_date = str(catalog.get("lastSynced") or "")[:10]
    en_hot = html("en/sosiski-dlya-hotdog.html")
    check(bool(sync_date), "products.json lastSynced is set")
    check(en_hot.count(sync_date) == 8,
          f"EN hotdog uses catalog lastSynced {sync_date} in 8 places")

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
