#!/usr/bin/env python3
"""Gates for /chak-chak-optom and /halyal-vypechka-optom-dlya-pekaren."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from site_facts import bakery_halal_line, FACTS  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html_of(rel: str) -> str:
    return (ROOT / "public" / rel).read_text(encoding="utf-8")


def h1_count(html: str) -> int:
    return len(re.findall(r"<h1\b", html, re.I))


def products() -> dict[str, dict]:
    payload = json.loads((ROOT / "public" / "products.json").read_text(encoding="utf-8"))
    return {p["sku"]: p for p in payload["products"]}


def price_token(p: dict) -> str:
    offers = p.get("offers") or {}
    raw = offers.get("price") or offers.get("pricePerUnit") or ""
    return str(raw)


def main() -> int:
    catalog = products()
    p053, p054 = catalog["KD-053"], catalog["KD-054"]
    cert_ru = bakery_halal_line("ru")
    cert_en = bakery_halal_line("en")
    number = FACTS["certificates"]["halal_bakery"]["number"]

    ru = html_of("chak-chak-optom.html")
    en = html_of("en/chak-chak-optom.html")
    check("KD-053" in ru and "KD-054" in ru, "RU chak-chak lists both SKUs")
    check("KD-053" in en and "KD-054" in en, "EN chak-chak lists both SKUs")
    check(price_token(p053) in ru and price_token(p054) in ru, "RU prices from products.json")
    check(price_token(p053) in en and price_token(p054) in en, "EN prices from products.json")
    check("60 суток" in ru or "60" in ru, "RU shelf-life days from Sheet SEO cell")
    check("+18" in ru and "+18" in en, "storage up to +18 from catalog")
    check(number in ru and "/halal" in ru, "RU bakery cert + /halal link")
    check(number in en and "/en/halal" in en, "EN bakery cert + /en/halal link")
    check('"@type":"Product"' in ru and '"@type":"Offer"' in ru, "RU Product/Offer schema")
    check('"@type":"FAQPage"' in ru and "<details>" in ru, "RU FAQ schema + visible FAQ")
    check('"@type":"Product"' in en and '"@type":"Offer"' in en, "EN Product/Offer schema")
    check(h1_count(ru) == 1 and h1_count(en) == 1, "chak-chak one H1 each")
    check("JAKIM" not in ru and "SFDA" not in ru and "GSO" not in ru, "chak-chak no GCC claims")
    check(cert_ru.split("—")[0].strip() in ru or number in ru, "RU cert line sourced, not freehand")

    art_ru = html_of("halyal-vypechka-optom-dlya-pekaren.html")
    art_en = html_of("en/halyal-vypechka-optom-dlya-pekaren.html")
    check("KD-018" in art_ru and "KD-061" in art_ru, "RU article has sausage-in-dough SKUs")
    check("KD-018" in art_en and "KD-061" in art_en, "EN article has sausage-in-dough SKUs")
    check("/sosiska-v-teste" in art_ru and "/vyipechka-halyal" in art_ru, "RU article cross-links hubs")
    check("/zamorozhennaya-vypechka-dlya-kofeen" in art_ru, "RU article links coffee bakery")
    check("/kak-zakazat" in art_ru and "/price" in art_ru, "RU article how-to-order")
    check("/en/kak-zakazat" in art_en and "/en/price" in art_en, "EN article how-to-order")
    check(number in art_ru and "/halal" in art_ru, "RU article cert 884A + /halal")
    check('"@type":"Article"' in art_ru and '"@type":"FAQPage"' in art_ru, "RU Article+FAQ schema")
    check("/en/sosiska-v-teste" in art_en and "/en/vyipechka-halyal" in art_en, "EN article cross-links")
    check(h1_count(art_ru) == 1 and h1_count(art_en) == 1, "article one H1 each")
    check("350 °C" not in art_ru and "350°C" not in art_ru, "article no invented oven temp")

    blog_ru = html_of("blog/chakchak-optom.html")
    gifts = html_of("blog/chakchak-wholesale-gifts.html")
    check('noindex' in blog_ru.lower() and "/chak-chak-optom" in blog_ru, "blog optom links landing")
    check('noindex' in gifts.lower() and "/chak-chak-optom" in gifts, "gifts note links landing")
    check("/chak-chak-optom" in html_of("blog/chak-chak.html"), "existing chak-chak note links landing")

    man = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    keep = {r["file"] for r in man["entries"] if r.get("status") == "keep"}
    for rel in (
        "chak-chak-optom.html", "en/chak-chak-optom.html",
        "halyal-vypechka-optom-dlya-pekaren.html",
        "en/halyal-vypechka-optom-dlya-pekaren.html",
    ):
        check(rel in keep, f"{rel} is keep")
    keep_n = len(keep)
    check(180 <= keep_n <= 260, f"keep count {keep_n} in 180–260")

    sitemap = (ROOT / "public" / "sitemap.xml").read_text(encoding="utf-8")
    check("chak-chak-optom" in sitemap, "sitemap has chak-chak-optom")
    check("halyal-vypechka-optom-dlya-pekaren" in sitemap, "sitemap has bakery article")

    retire = json.loads((ROOT / "data" / "url_consolidation_map.json").read_text(encoding="utf-8"))
    by_url = {r["url"]: r for r in retire["entries"]}
    for url in (
        "/blog/chakchak-optom", "/blog/chakchak-wholesale-gifts",
        "/en/blog/chakchak-optom", "/en/blog/chakchak-wholesale-gifts",
    ):
        check(by_url[url]["status"] == "noindex", f"{url} is noindex not 410")

    gone = (ROOT / "deploy" / "nginx" / "trust-reset-gone.conf").read_text(encoding="utf-8")
    check("chakchak-optom" not in gone and "chakchak-wholesale-gifts" not in gone,
          "nginx 410 no longer covers chakchak blogs")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
