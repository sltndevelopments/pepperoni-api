#!/usr/bin/env python3
"""Gates for PR #20 review fixes: certs, currencies, xlsx numbers, FAQ @graph."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from clean_faqpage_schema import has_visible_faq, remove_faqpage_scripts  # noqa: E402
from site_facts import FACTS, meat_halal_number, phone_tel, street_address  # noqa: E402

PUBLIC = ROOT / "public"
fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print(f"  ok  {msg}")
    else:
        fail += 1
        print(f"FAIL {msg}")


def main() -> int:
    n0 = meat_halal_number()
    check(n0 == FACTS["certificates"]["halal_0008"]["number"], "primary cert is 0008")
    how = (PUBLIC / "kak-zakazat.html").read_text(encoding="utf-8")
    how_en = (PUBLIC / "en" / "kak-zakazat.html").read_text(encoding="utf-8")
    check("Расчёты возможны" not in how, "RU how-to-order has no invented payment currencies")
    check("Catalog currencies" not in how_en, "EN how-to-order has no invented payment currencies")
    check("справочные экспортные цены" in how, "RU how-to-order says reference export prices")
    check("reference export prices" in how_en, "EN how-to-order says reference export prices")
    check(phone_tel() in how and phone_tel() in how_en, "tel href from site_facts")

    price = (PUBLIC / "price.html").read_text(encoding="utf-8")
    check(n0 in price, "/price lists primary cert 0008")
    check(FACTS["certificates"]["halal_614a"]["number"] in price, "/price lists 614A")
    check(FACTS["certificates"]["halal_bakery"]["number"] in price, "/price lists 884A")
    css = (ROOT / "scripts" / "commercial_page.py").read_text(encoding="utf-8")
    check(".topnav,nav.topnav" in css or ".topnav," in css, "print CSS hides div.topnav")

    addr = street_address()
    check("Аграрная" in addr and "2" in addr, f"street_address from facts ({addr})")

    xlsx = PUBLIC / "prices.xlsx"
    check(xlsx.is_file(), "prices.xlsx exists")
    if xlsx.is_file():
        with zipfile.ZipFile(xlsx) as z:
            info = z.getinfo("xl/worksheets/sheet1.xml")
            synced = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))["lastSynced"]
            y, m, d = (int(x) for x in synced[:10].split("-"))
            check(info.date_time[:3] == (y, m, d), f"xlsx ZipInfo date {info.date_time[:3]} == lastSynced {synced}")
            xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
            check('t="n"' in xml, "xlsx has numeric cells")

    graph = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "FAQPage", "mainEntity": []},
            {"@type": "Organization", "name": "X"},
        ],
    }, ensure_ascii=False)
    html = (
        '<html><body><script type="application/ld+json">' + graph + "</script>"
        "<p>no faq here</p></body></html>"
    )
    check(not has_visible_faq(html), "stray page is not a visible FAQ")
    cleaned = remove_faqpage_scripts(html)
    check("FAQPage" not in cleaned, "FAQPage stripped from @graph")
    check("Organization" in cleaned, "sibling @graph Organization kept")

    echo = (PUBLIC / "blog" / "echpochmak.html").read_text(encoding="utf-8")
    check("68,77" not in echo and "68.77" not in echo, "echpochmak FAQ not 68.77")
    products = {p["sku"]: p for p in json.loads((PUBLIC / "products.json").read_text())["products"]}
    p050 = products["KD-050"]["offers"]["pricePerUnit"]
    ru = f"{float(p050):.2f}".replace(".", ",")
    check(ru in echo, f"echpochmak FAQ has catalog piece {ru}")

    en052 = (PUBLIC / "en" / "products" / "kd-052.html").read_text(encoding="utf-8")
    usd = products["KD-052"]["offers"]["exportPrices"]["USD"]
    check(f'"price":"{usd:.2f}"' in en052 or f'"price": "{usd:.2f}"' in en052
          or f'"price":"{usd}"' in en052,
          f"EN kd-052 JSON-LD USD is {usd}")
    check("$0.91" not in en052, "EN kd-052 no longer $0.91")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
