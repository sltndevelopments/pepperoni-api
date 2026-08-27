#!/usr/bin/env python3
"""Build the explicit index allowlist for pepperoni.tatar.

Only real catalog records, deliberately selected commercial/trust pages and a
small set of cornerstone articles may receive ``status=keep``.  Retired URLs
are merged from ``data/url_consolidation_map.json`` so the manifest remains the
single machine-readable registry for keep/301/410/noindex decisions.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
OUT = DATA / "index_manifest.json"
RETIRE_MAP = DATA / "url_consolidation_map.json"

MIN_INDEXABLE = 180
MAX_INDEXABLE = 250


def _page(path: str, intent: str, owner: str, source: str) -> dict:
    return {
        "file": path,
        "intent": intent,
        "owner": owner,
        "source": source,
    }


RU_PAGES = [
    _page("index.html", "manufacturer and catalog home", "marketing", "brand.txt + products.json"),
    _page("products/index.html", "current wholesale catalog", "sales", "Google Sheets"),
    _page("blog.html", "cornerstone guide index", "editorial", "index manifest"),
    _page("about.html", "verified company identity", "management", "evidence registry"),
    _page("capabilities.html", "documented production capabilities", "production", "evidence registry"),
    _page("cases.html", "independently verifiable supply examples", "sales", "evidence registry"),
    _page("certificates.html", "certificate scope and verification", "quality", "evidence registry"),
    _page("editorial-policy.html", "fact checking and content ownership", "editorial", "evidence registry"),
    _page("faq.html", "buyer questions", "sales", "brand.txt + products.json"),
    _page("halal.html", "halal controls and certificate", "quality", "evidence registry"),
    _page("delivery.html", "delivery terms", "sales", "products.json"),
    _page("pepperoni.html", "halal pepperoni wholesale", "sales", "Google Sheets"),
    _page("pepperoni-v-narezke.html", "sliced pepperoni specification", "sales", "Google Sheets"),
    _page("pepperoni-dlya-pizzerii.html", "pepperoni for pizzerias", "sales", "Google Sheets"),
    _page("pizzeria.html", "foodservice products for pizzerias", "sales", "Google Sheets"),
    _page("sosiski-dlya-hotdog.html", "hot-dog sausages wholesale", "sales", "Google Sheets"),
    _page("sosiska-v-teste.html", "sausage-in-dough wholesale", "sales", "Google Sheets"),
    _page("kotlety-dlya-burgerov.html", "burger patties wholesale", "sales", "Google Sheets"),
    _page("kazylyk.html", "kazylyk wholesale", "sales", "Google Sheets"),
    _page("kolbasy-kopchyonye.html", "smoked halal sausages", "sales", "Google Sheets"),
    _page("kolbasy-varenye.html", "cooked halal sausages", "sales", "Google Sheets"),
    _page("vetchina-optom.html", "halal ham wholesale", "sales", "Google Sheets"),
    _page("vyipechka-halyal.html", "halal bakery wholesale", "sales", "Google Sheets"),
    _page("kontraktnoe-proizvodstvo.html", "private-label manufacturing", "sales", "evidence registry"),
    _page("dlya-horeca.html", "assortment for HoReCa", "sales", "Google Sheets"),
    _page("dlya-azs.html", "assortment for petrol stations", "sales", "Google Sheets"),
    _page("dlya-setey.html", "assortment for retail chains", "sales", "Google Sheets"),
    _page("dlya-pekaren.html", "assortment for bakeries", "sales", "Google Sheets"),
    _page("dlya-distributorov.html", "assortment for distributors", "sales", "Google Sheets"),
    _page("export.html", "documented export capability", "export", "evidence registry"),
]

EXPORT_COUNTRIES = [
    ("armenia", "export landing Armenia"),
    ("azerbaijan", "export landing Azerbaijan"),
    ("bahrain", "export landing Bahrain"),
    ("belarus", "export landing Belarus"),
    ("egypt", "export landing Egypt"),
    ("georgia", "export landing Georgia"),
    ("kazakhstan", "export landing Kazakhstan"),
    ("kuwait", "export landing Kuwait"),
    ("kyrgyzstan", "export landing Kyrgyzstan"),
    ("oman", "export landing Oman"),
    ("qatar", "export landing Qatar"),
    ("saudi-arabia", "export landing Saudi Arabia"),
    ("tajikistan", "export landing Tajikistan"),
    ("uae", "export landing UAE"),
    ("yemen", "export landing Yemen"),
]
RU_PAGES.extend(
    _page(f"export/{slug}.html", intent, "export", "owner-approved country export landing")
    for slug, intent in EXPORT_COUNTRIES
)

EN_PAGES = [
    _page("en/index.html", "manufacturer and catalog home", "marketing", "brand.txt + products.json"),
    _page("en/products/index.html", "current wholesale catalog", "sales", "Google Sheets"),
    _page("en/blog.html", "cornerstone guide index", "editorial", "index manifest"),
    _page("en/about.html", "verified company identity", "management", "evidence registry"),
    _page("en/capabilities.html", "documented production capabilities", "production", "evidence registry"),
    _page("en/cases.html", "independently verifiable supply examples", "sales", "evidence registry"),
    _page("en/certificates.html", "certificate scope and verification", "quality", "evidence registry"),
    _page("en/editorial-policy.html", "fact checking and content ownership", "editorial", "evidence registry"),
    _page("en/faq.html", "buyer questions", "sales", "brand.txt + products.json"),
    _page("en/halal.html", "halal controls and certificate", "quality", "evidence registry"),
    _page("en/delivery.html", "delivery terms", "sales", "products.json"),
    _page("en/pepperoni.html", "halal pepperoni wholesale", "sales", "Google Sheets"),
    _page("en/pepperoni-v-narezke.html", "sliced pepperoni specification", "sales", "Google Sheets"),
    _page("en/pepperoni-dlya-pizzerii.html", "pepperoni for pizzerias", "sales", "Google Sheets"),
    _page("en/pizzeria.html", "foodservice products for pizzerias", "sales", "Google Sheets"),
    _page("en/sosiski-dlya-hotdog.html", "hot-dog sausages wholesale", "sales", "Google Sheets"),
    _page("en/sosiska-v-teste.html", "sausage-in-dough wholesale", "sales", "Google Sheets"),
    _page("en/kotlety-dlya-burgerov.html", "burger patties wholesale", "sales", "Google Sheets"),
    _page("en/kazylyk.html", "kazylyk wholesale", "sales", "Google Sheets"),
    _page("en/kolbasy-kopchyonye.html", "smoked halal sausages", "sales", "Google Sheets"),
    _page("en/kolbasy-varenye.html", "cooked halal sausages", "sales", "Google Sheets"),
    _page("en/vetchina-optom.html", "halal ham wholesale", "sales", "Google Sheets"),
    _page("en/vyipechka-halyal.html", "halal bakery wholesale", "sales", "Google Sheets"),
    _page("en/private-label.html", "private-label manufacturing", "sales", "evidence registry"),
    _page("en/dlya-horeca.html", "assortment for HoReCa", "sales", "Google Sheets"),
    _page("en/dlya-azs.html", "assortment for petrol stations", "sales", "Google Sheets"),
    _page("en/dlya-setey.html", "assortment for retail chains", "sales", "Google Sheets"),
    _page("en/dlya-pekaren.html", "assortment for bakeries", "sales", "Google Sheets"),
    _page("en/dlya-distributorov.html", "assortment for distributors", "sales", "Google Sheets"),
    _page("en/export.html", "documented export capability", "export", "evidence registry"),
]
EN_PAGES.extend(
    _page(f"en/export/{slug}.html", intent, "export", "owner-approved country export landing")
    for slug, intent in EXPORT_COUNTRIES
)

RU_GUIDES = [
    ("blog/what-is-halal-pepperoni.html", "what halal pepperoni is"),
    ("blog/pepperoni-iz-kakogo-myasa.html", "pepperoni ingredients"),
    ("blog/pepperoni-for-pizzeria-horeca.html", "pepperoni procurement for pizzerias"),
    ("blog/narezka-pepperoni-parametry.html", "sliced pepperoni specification"),
    ("blog/kak-hranit-pepperoni.html", "pepperoni storage"),
    ("blog/kazylyk.html", "what kazylyk is"),
    ("blog/echpochmak.html", "what echpochmak is"),
    ("blog/sosiski-dlya-hot-dogov-optom.html", "hot-dog sausage procurement"),
    ("blog/kotlety-dlya-burgerov-optom.html", "burger patty procurement"),
    ("blog/tatarskaya-vypechka-optom.html", "Tatar bakery procurement"),
    ("blog/private-label-kolbasnyh-izdeliy.html", "private-label buying guide"),
    ("blog/halal-certification-russia.html", "halal certification in Russia"),
    ("blog/iso-22000-iaf-certsearch.html", "ISO certificate verification"),
    ("blog/karmin-e120-haram.html", "carmine E120 policy"),
]

EN_GUIDES = [
    ("en/blog/what-is-halal-pepperoni.html", "what halal pepperoni is"),
    ("en/blog/wholesale-pepperoni-russia-export.html", "pepperoni export procurement"),
    ("en/blog/pepperoni-for-pizzeria-horeca.html", "pepperoni procurement for pizzerias"),
    ("en/blog/pepperoni-slicing-specs.html", "sliced pepperoni specification"),
    ("en/blog/kazylyk-horse-meat-sausage.html", "what kazylyk is"),
    ("en/blog/echpochmak-halyal.html", "what echpochmak is"),
    ("en/blog/beef-hotdog-sausages-halal.html", "hot-dog sausage procurement"),
    ("en/blog/burger-patties-wholesale-halal.html", "burger patty procurement"),
    ("en/blog/tatar-bakery-wholesale.html", "Tatar bakery procurement"),
    ("en/blog/private-label-meat-products.html", "private-label buying guide"),
    ("en/blog/halal-certification-russia.html", "halal certification in Russia"),
]


def clean_url(rel: str) -> str:
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[:-11]
    return "/" + rel.removesuffix(".html")


def locale_for(rel: str) -> str:
    return "en" if rel.startswith("en/") else "ru"


def kind_for(rel: str) -> str:
    if re.fullmatch(r"(?:en/)?products/kd-\d{3}\.html", rel):
        return "product"
    if re.fullmatch(r"(?:en/)?export/[a-z0-9-]+\.html", rel):
        return "export-country"
    if rel.startswith(("blog/", "en/blog/")):
        return "guide"
    if rel.endswith("products/index.html"):
        return "catalog"
    if rel in {"index.html", "en/index.html"}:
        return "home"
    return "hub"


def _keep_entry(page: dict) -> dict:
    rel = page["file"]
    return {
        "url": clean_url(rel),
        "file": rel,
        "intent": page["intent"],
        "language": locale_for(rel),
        "owner": page["owner"],
        "source": page["source"],
        "canonical_target": clean_url(rel),
        "status": "keep",
        "kind": kind_for(rel),
    }


def _product_pages() -> list[dict]:
    payload = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    products = payload.get("products") or []
    entries: list[dict] = []
    for product in products:
        sku = str(product.get("sku") or "").lower()
        if not re.fullmatch(r"kd-\d{3}", sku):
            raise SystemExit(f"invalid product sku in products.json: {sku!r}")
        for language, prefix in (("ru", ""), ("en", "en/")):
            rel = f"{prefix}products/{sku}.html"
            entries.append({
                "url": clean_url(rel),
                "file": rel,
                "intent": f"verified SKU {sku.upper()}",
                "language": language,
                "owner": "catalog",
                "source": "Google Sheets via public/products.json",
                "canonical_target": clean_url(rel),
                "status": "keep",
                "kind": "product",
            })
    return entries


def _retired_entries() -> list[dict]:
    if not RETIRE_MAP.exists():
        return []
    payload = json.loads(RETIRE_MAP.read_text(encoding="utf-8"))
    rows = payload.get("entries") if isinstance(payload, dict) else payload
    return [row for row in (rows or []) if row.get("status") != "keep"]


def build_manifest() -> dict:
    static = RU_PAGES + EN_PAGES
    guides = [
        _page(path, intent, "editorial", "evidence registry + cited sources")
        for path, intent in RU_GUIDES + EN_GUIDES
    ]
    keep = [_keep_entry(page) for page in static + guides]
    keep.extend(_product_pages())

    duplicates = sorted({
        row["url"] for row in keep
        if sum(1 for other in keep if other["url"] == row["url"]) > 1
    })
    if duplicates:
        raise SystemExit(f"duplicate keep URLs: {duplicates}")

    missing = sorted(row["file"] for row in keep if not (PUBLIC / row["file"]).exists())
    if missing:
        raise SystemExit("manifest keep files missing:\n" + "\n".join(missing))

    if not MIN_INDEXABLE <= len(keep) <= MAX_INDEXABLE:
        raise SystemExit(
            f"indexable count {len(keep)} outside {MIN_INDEXABLE}..{MAX_INDEXABLE}")

    entries = sorted(
        [*keep, *_retired_entries()],
        key=lambda row: (row.get("status") != "keep", row["url"]),
    )
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "indexable_min": MIN_INDEXABLE,
            "indexable_max": MAX_INDEXABLE,
            "languages": ["ru", "en"],
            "new_page_requirements": [
                "demonstrated demand",
                "unique user task",
                "first-party evidence or owned data",
            ],
        },
        "counts": {
            "keep": len(keep),
            "retired": len(entries) - len(keep),
            "all": len(entries),
        },
        "entries": entries,
    }


def main() -> int:
    manifest = build_manifest()
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"index manifest: {manifest['counts']['keep']} keep, "
        f"{manifest['counts']['retired']} retired → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
