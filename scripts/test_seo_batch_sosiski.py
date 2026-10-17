#!/usr/bin/env python3
"""Gates for the Topvisor SEO batch: /sosiski-halyal-optom and retargets."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
fail = 0

WANTED = ["KD-017", "KD-019", "KD-020", "KD-021", "KD-022", "KD-023", "KD-024", "KD-035"]


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html_of(rel: str) -> str:
    return (PUBLIC / rel).read_text(encoding="utf-8")


def products() -> dict[str, dict]:
    payload = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    return {p["sku"]: p for p in payload["products"]}


def price_token(p: dict) -> str:
    raw = str((p.get("offers") or {}).get("price") or "")
    return raw


def main() -> int:
    catalog = products()
    present = [sku for sku in WANTED if sku in catalog]
    check(present == WANTED, f"all chilled sausage SKUs exist ({len(present)})")

    ru = html_of("sosiski-halyal-optom.html")
    check("<h1" in ru and ru.lower().count("<h1") == 1, "new page one H1")
    check("Сосиски халяль оптом" in ru, "new page title/H1 query")
    check('class="hero"' in ru and 'class="hero__media"' in ru, "new page uses jerky-style hero")
    check('class="tbl"' in ru and "<table" in ru, "new page has catalog table")
    check("Минимальный заказ — 1 паллета" in ru, "canonical MOQ")
    check("/sosiski-dlya-hotdog" in ru and "/products" in ru, "new page links hubs")
    check("по всей России" in ru and "Москв" in ru and "Санкт-Петербург" in ru,
          "new page phrases Russia / Moscow / SPb")
    check('id="dostavka"' in ru and "Доставка в Москву и СПб" in ru, "new page delivery section")
    check('id="po-myasu"' in ru and "Говяжьи" in ru and "Куриные" in ru, "new page meat-type blocks")
    check("/kotlety-dlya-burgerov#dostavka" in ru and "/kazylyk#dostavka" in ru,
          "new page links cutlet/kazylyk delivery")
    check('"@type": "ItemList"' in ru or '"@type":"ItemList"' in ru, "ItemList schema")
    check('"@type": "FAQPage"' in ru or '"@type":"FAQPage"' in ru, "FAQ schema")
    orgs = len(re.findall(r'"@type"\s*:\s*"Organization"', ru))
    # Organization may appear as author/provider; top-level #organization once
    check(ru.count("https://pepperoni.tatar/#organization") >= 1, "Organization @id present")
    for sku in present:
        check(sku in ru, f"new page lists {sku}")
        token = price_token(catalog[sku])
        if token:
            check(token.split(".")[0] in ru or token in ru, f"{sku} price from products.json")
    check("KD-001" not in ru, "frozen hot-dog SKUs stay off the chilled page")

    products_ru = html_of("products/index.html")
    products_en = html_of("en/products/index.html")
    check("Халяль колбасы и сосиски оптом от производителя" in products_ru, "RU /products title")
    check("<h1>Халяль колбасы и сосиски оптом от производителя</h1>" in products_ru, "RU /products H1")
    check("/sosiski-halyal-optom" in products_ru, "/products links new page")
    check("/kotlety-dlya-burgerov#dostavka" in products_ru, "/products links cutlet delivery")
    check("/kazylyk#dostavka" in products_ru, "/products links kazylyk delivery")
    check("<title>Product catalog — SKU pages | Kazan Delicacies</title>" in products_en,
          "EN /products keeps original catalog title")
    check("<h1>Product catalog</h1>" in products_en, "EN /products keeps original H1")

    smoked = html_of("kolbasy-kopchyonye.html")
    check("сервелат" in smoked.lower() and "ханск" in smoked.lower(), "smoked has ханский")
    check("татарск" in smoked.lower(), "smoked has татарский")
    check("полукопч" in smoked.lower() and "говяд" in smoked.lower(), "smoked has полукопчёная говяжья")
    check("KD-031" in smoked and "KD-032" in smoked, "smoked lists KD-031/032")
    if "KD-034" in catalog:
        check("KD-034" in smoked, "smoked lists KD-034 полукопчёная")

    boiled = html_of("kolbasy-varenye.html")
    check("варёная колбаса халяль" in boiled.lower() or "Варёная колбаса халяль" in boiled,
          "boiled targets варёная колбаса халяль")
    check("мусульманск" in boiled.lower(), "boiled targets мусульманская")

    hotdog = html_of("sosiski-dlya-hotdog.html")
    check("Гриль, колбаски для хот-догов и френч-дог" in hotdog, "hotdog H2 grill/french-dog")
    check("френч-дог" in hotdog.lower(), "hotdog FAQ/copy has френч-дог")
    check("/sosiski-halyal-optom" in hotdog, "hotdog links chilled sausages")
    check("по всей России" in hotdog and 'id="dostavka"' in hotdog, "hotdog Russia delivery")
    check('id="po-myasu"' in hotdog and "Говяжьи" in hotdog and "Куриные" in hotdog,
          "hotdog meat-type blocks")
    check("KD-005" not in (hotdog.split('id="po-myasu"', 1)[-1].split('id="dostavka"', 1)[0]),
          "lamb-named KD-005 stays out of beef/chicken blocks")

    kot = html_of("kotlety-dlya-burgerov.html")
    kaz = html_of("kazylyk.html")
    check('id="dostavka"' in kot and "Доставка в Москву и СПб" in kot, "cutlets delivery section")
    check('id="dostavka"' in kaz and "Доставка в Москву и СПб" in kaz, "kazylyk delivery section")
    check("Москв" not in re.search(r"<title>(.*?)</title>", kot).group(1),
          "cutlets title still has no Москва")

    home = html_of("index.html")
    check("/sosiski-halyal-optom" in home, "home links new page")

    pizza = html_of("pepperoni-dlya-pizzerii.html")
    check("Какая колбаса для пиццы" not in pizza, "pizzeria pizza-sausage block dropped")
    pep = html_of("en/blog/what-is-halal-pepperoni.html")
    check("porkless" not in pep.lower() and "poultry-only" not in pep.lower(),
          "EN pepperoni article has no porkless / poultry-only add-on")

    hot_blog = html_of("en/blog/beef-hotdog-sausages-halal.html")
    burg_blog = html_of("en/blog/burger-patties-wholesale-halal.html")
    check("Are hot dogs halal?" in hot_blog, "EN hot-dog blog retitled")
    check("Is a beef burger halal?" in burg_blog, "EN burger blog retitled")
    check("/en/sosiski-dlya-hotdog" in hot_blog, "hot-dog blog links hub")
    check("/en/kotlety-dlya-burgerov" in burg_blog, "burger blog links hub")
    check('data-price-field="pricePerPiece"' in burg_blog, "burger blog stamps per-piece from catalog")

    bahrain = html_of("export/bahrain.html")
    check(re.search(r'name="robots"[^>]*content="noindex', bahrain, re.I),
          "/export/bahrain is noindex")
    check((PUBLIC / "export/bahrain.html").is_file(), "bahrain page kept")

    man = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    keep = {r["url"]: r for r in man["entries"] if r.get("status") == "keep"}
    check("/sosiski-halyal-optom" in keep, "new page is keep")
    check("/export/bahrain" not in keep, "bahrain dropped from keep")
    check("/en/export/bahrain" in keep, "EN bahrain still keep")
    keep_n = len(keep)
    check(keep_n == 250, f"keep count stays 250 (got {keep_n})")

    sitemap = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
    check("sosiski-halyal-optom" in sitemap, "sitemap has new page")
    check("https://pepperoni.tatar/export/bahrain<" not in sitemap
          and ">https://pepperoni.tatar/export/bahrain<" not in sitemap
          and "pepperoni.tatar/export/bahrain</loc>" not in sitemap,
          "sitemap dropped RU bahrain")

    print(f"test_seo_batch_sosiski: {'ok' if fail == 0 else f'{fail} FAIL'}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
