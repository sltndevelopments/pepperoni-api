#!/usr/bin/env python3
"""One set of facts on every public surface.

Canonical sources:
  * public/products.json — SKUs, names, weights, RUB prices, shelf life (Sheet)
  * data/company_facts.json — legal name, INN/OGRN, address, phones, email,
    founding year, halal certs 0008 / 614A/2024 / 884A/2025, capacity, MOQ, EXW

Surfaces scanned: RU+EN HTML (JSON-LD Organization / Product / Offer),
llms.txt / llms-full.txt, products.json (including seoDescription),
YML + Google Merchant feeds, /halal, API/MCP JSON.

Unresolved source conflicts are not guessed here — they stay out of
company_facts.json and are listed in the PR.

  python3 scripts/check_fact_consistency.py
"""
from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
sys.path.insert(0, str(ROOT / "scripts"))
from catalog_prices import catalog, iter_jsonld_nodes, iter_ld_offers, num, rub  # noqa: E402

COMPANY_PATH = ROOT / "data" / "company_facts.json"
SITE_FACTS_PATH = ROOT / "data" / "site_facts.json"
LD_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
SKU_RE = re.compile(r"\bKD-(\d{3})\b", re.I)
PHONE_E164 = re.compile(r"\+?7[\s\-()]?987[\s\-()]?217[\s\-()]?02[\s\-()]?02")
WRONG_WA = "79274297220"
CHAK_SKU = {"KD-053", "KD-054"}
CHAK_HINT = re.compile(r"чак-?чак|chak-?chak|KD-053|KD-054", re.I)
SHELF_60 = re.compile(r"(?<!\d)60\s*(?:суток|сут\.?|days?)\b", re.I)
KD012_OK = re.compile(
    r"(?:not in the (?:current )?catalog|is retired|снят(?:а|о)?\b|"
    r"в текущем каталоге нет|нет в (?:текущем )?каталог)",
    re.I,
)
ARCHIVE_DIR = re.compile(r"^public/[0-9](/|$)")


def load_company() -> dict:
    return json.loads(COMPANY_PATH.read_text(encoding="utf-8"))


def close(a: float | None, b: float | None, tol: float = 0.011) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def parse_ld(html: str, rel: str = "") -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    issues: list[str] = []
    for raw in LD_RE.findall(html):
        try:
            node = json.loads(raw)
        except json.JSONDecodeError as exc:
            if rel:
                issues.append(f"{rel} malformed JSON-LD: {exc}")
            continue
        out.extend(n for n in iter_jsonld_nodes(node) if isinstance(n, dict))
    return out, issues


def jsonld_prices(html: str) -> set[float]:
    out = set()
    for m in re.finditer(r'"price"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?', html):
        out.add(float(m.group(1)))
    return out


def visible_weights(html: str, lang: str) -> set[float]:
    body = html.split("<body", 1)[-1]
    unit = "кг" if lang == "ru" else "kg"
    return {num(m.group(1)) for m in re.finditer(rf">\s*([0-9]+(?:[.,][0-9]+)?)\s*{unit}\s*<", body)}


def visible_prices_rub(html: str) -> set[float]:
    body = html.split("<body", 1)[-1]
    found = set()
    for m in re.finditer(r">\s*([0-9][0-9\s\u00a0]*(?:[.,][0-9]{2})?)\s*₽", body):
        found.add(num(m.group(1)))
    for m in re.finditer(r">\s*([0-9][0-9\s\u00a0]*(?:[.,][0-9]{2})?)\s*RUB\b", body, re.I):
        found.add(num(m.group(1)))
    return {x for x in found if x is not None}


def pricelist_row(md: str, sku: str) -> dict | None:
    for line in md.splitlines():
        if line.startswith(f"| {sku} |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            return {"name": cells[1], "weight": num(cells[2]), "price": num(cells[3]),
                    "shelf": cells[8], "storage": cells[9]}
    return None


def pricelist_row_txt(txt: str, sku: str) -> dict | None:
    """Plain-text price list: `KD-NNN  Name` line followed by two indented
    `Label: value | Label: value` lines (RU and EN labels differ)."""
    lines = txt.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith(f"{sku}  "):
            continue
        fields = {}
        for extra in lines[i + 1:i + 3]:
            for cell in extra.split("|"):
                if ":" in cell:
                    k, v = cell.split(":", 1)
                    fields[k.strip().lower()] = v.strip()

        def pick(*keys):
            for k in fields:
                if any(k.startswith(x) for x in keys):
                    return fields[k]
            return ""

        return {"name": line.split("  ", 1)[1].strip(),
                "weight": num(pick("масса", "net weight")), "price": num(pick("цена", "price")),
                "shelf": pick("срок", "shelf"), "storage": pick("хранение", "storage")}
    return None


def walk_public_files() -> list[Path]:
    skip_suffix = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".woff",
                   ".woff2", ".ttf", ".ico", ".mp4", ".zip", ".xlsx"}
    files: list[Path] = []
    for path in PUBLIC.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if ARCHIVE_DIR.search(rel):
            continue
        if path.suffix.lower() in skip_suffix:
            continue
        if path.suffix.lower() in {".html", ".txt", ".xml", ".json", ".md", ".yml", ".yaml"}:
            files.append(path)
    return files


def shelf_days(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:суток|сут\.?|days?)\b", text or "", re.I)
    return int(m.group(1)) if m else None


def catalog_shelf_days(row: dict) -> int | None:
    return shelf_days(str(row.get("shelfLife") or ""))


def issues_company(company: dict, site: dict) -> list[str]:
    issues = []
    co = site.get("company") or {}
    if co.get("inn") and co["inn"] != company["inn"]:
        issues.append(f"site_facts.inn {co['inn']!r} != company_facts.inn")
    if co.get("ogrn") and co["ogrn"] != company["ogrn"]:
        issues.append(f"site_facts.ogrn {co['ogrn']!r} != company_facts.ogrn")
    if co.get("email") and co["email"] != company["email"]:
        issues.append(f"site_facts.email {co['email']!r} != company_facts.email")
    if co.get("legal_name_ru") and co["legal_name_ru"] != company["legal_name_ru"]:
        issues.append("site_facts.legal_name_ru != company_facts")
    terms = site.get("terms") or {}
    if terms.get("capacity") and terms["capacity"] != company["production_capacity"]:
        issues.append("site_facts.terms.capacity != company_facts.production_capacity")
    if terms.get("moq") and terms["moq"] != company["moq"]:
        issues.append("site_facts.terms.moq != company_facts.moq")
    if terms.get("basis") and terms["basis"] != company["delivery_terms"]:
        issues.append("site_facts.terms.basis != company_facts.delivery_terms")
    certs = {c["number"]: c for c in company["halal_certificates"]}
    mapping = {
        "0008": (site.get("certificates") or {}).get("halal_0008") or {},
        "614A/2024": (site.get("certificates") or {}).get("halal_614a") or {},
        "884A/2025": (site.get("certificates") or {}).get("halal_bakery") or {},
    }
    for number, row in mapping.items():
        if not row:
            continue
        canon = certs[number]
        if row.get("valid_from") and row["valid_from"] != canon["valid_from"]:
            issues.append(f"{number} valid_from site_facts != company_facts")
        if row.get("valid_until") and row["valid_until"] != canon["valid_until"]:
            issues.append(f"{number} valid_until site_facts != company_facts")
    return issues


def check_products_self(by_sku: dict[str, dict]) -> list[str]:
    issues = []
    for sku, row in by_sku.items():
        want = catalog_shelf_days(row)
        if want is None:
            continue
        for key in ("seoDescriptionRU", "seoDescriptionEN"):
            text = str(row.get(key) or "")
            got = shelf_days(text)
            if got is not None and got != want:
                issues.append(
                    f"{sku} {row.get('name')} {key} says {got} days, "
                    f"products.json shelfLife is {row.get('shelfLife')}"
                )
        offers = row.get("offers") or {}
        currency = offers.get("priceCurrency")
        if currency and currency != "RUB":
            issues.append(f"{sku} products.json offers.priceCurrency is {currency}, expected RUB")
    return issues


def check_jsonld(rel: str, html: str, company: dict, by_sku: dict[str, dict]) -> list[str]:
    issues = []
    nodes, ld_issues = parse_ld(html, rel)
    issues.extend(ld_issues)
    for node in nodes:
        types = node.get("@type")
        typeset = {types} if isinstance(types, str) else set(types or [])
        if typeset & {"Organization", "LocalBusiness"}:
            tax = str(node.get("taxID") or "")
            if tax and tax != company["inn"]:
                issues.append(f"{rel} JSON-LD taxID {tax} != {company['inn']}")
            email = str(node.get("email") or "")
            if email and email.lower() != company["email"].lower():
                issues.append(f"{rel} JSON-LD email {email} != {company['email']}")
            tel = re.sub(r"\D", "", str(node.get("telephone") or ""))
            if tel and tel not in {company["phone_e164"].lstrip("+"), "79872170202"}:
                issues.append(f"{rel} JSON-LD telephone {node.get('telephone')}")
    for raw in LD_RE.findall(html):
        try:
            root = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for sku, offer in iter_ld_offers(root):
            currency = offer.get("priceCurrency")
            price = num(offer.get("price"))
            if sku == "KD-012":
                issues.append(f"{rel} JSON-LD Product SKU KD-012 (retired, not in catalog)")
                continue
            if sku and sku in by_sku:
                if currency and currency != "RUB":
                    issues.append(
                        f"{rel} {sku} Offer priceCurrency {currency} "
                        f"(catalog is RUB {rub(sku)})"
                    )
                if price is not None and not close(price, rub(sku)):
                    issues.append(
                        f"{rel} {sku} {by_sku[sku].get('name')} "
                        f"Offer price {price} != catalog {rub(sku)}"
                    )
            elif price is not None and rel.startswith(("products/kd-", "en/products/kd-")):
                issues.append(f"{rel} Offer price {price} has no sku/url → SKU mapping")
    return issues


# Naive "60 days" → "90 days" replace also hits "360 days" → "390 days".
SHELF_390 = re.compile(r"(?<!\d)390\s*(?:суток|сут\.?|days?)\b", re.I)


def check_corrupt_shelf(rel: str, text: str) -> list[str]:
    """Catch '360 days' → '390 days' from a naive 60→90 replace."""
    if SHELF_390.search(text):
        return [f"{rel} has 390-day shelf life (catalog has 90 or 360, never 390)"]
    return []


def check_chak_text(rel: str, text: str) -> list[str]:
    if not CHAK_HINT.search(text):
        return []
    issues = []
    for m in SHELF_60.finditer(text):
        start = max(0, m.start() - 160)
        window = text[start:m.end() + 160]
        if CHAK_HINT.search(window):
            issues.append(f"{rel} chak-chak shelf life says 60 (catalog KD-053/KD-054 is 90 суток)")
            break
    return issues


def check_kd012(rel: str, text: str) -> list[str]:
    if "KD-012" not in text.upper():
        return []
    # Denials are allowed; in-stock / current-assortment claims are not.
    if KD012_OK.search(text):
        return []
    if re.search(r"KD-012[^.\n]{0,80}(?:в каталоге|on sale|InStock|в наличии)", text, re.I):
        return [f"{rel} KD-012 presented as a current catalog SKU"]
    # Remaining bare mentions after the owner asked to drop horse-pepperoni SKU copy.
    return [f"{rel} mentions KD-012 (retired horse pepperoni — drop or mark as not in catalog)"]


def check_company_mentions(rel: str, text: str, company: dict) -> list[str]:
    issues = []
    if WRONG_WA in text.replace("-", "").replace(" ", ""):
        issues.append(f"{rel} public WhatsApp 79274297220 (must be {company['phone_e164']})")
    for m in re.finditer(r"(?:ИНН|INN|taxID)\D{0,12}(\d{10})", text):
        if m.group(1) != company["inn"]:
            issues.append(f"{rel} INN {m.group(1)} != {company['inn']}")
    for m in re.finditer(r"(?:ОГРН|OGRN)\D{0,12}(\d{13})", text):
        if m.group(1) != company["ogrn"]:
            issues.append(f"{rel} OGRN {m.group(1)} != {company['ogrn']}")
    return issues


def check_feeds(by_sku: dict[str, dict]) -> list[str]:
    issues = []
    yml = PUBLIC / "yml.xml"
    if yml.is_file():
        body = yml.read_text(encoding="utf-8")
        for block in re.findall(r'<offer id="(KD-\d{3})"[^>]*>(.*?)</offer>', body, re.S):
            sku, inner = block[0], block[1]
            if sku not in by_sku:
                if sku == "KD-012":
                    issues.append("yml.xml still offers KD-012")
                continue
            currency = re.search(r"<currencyId>(\w+)</currencyId>", inner)
            price = num((re.search(r"<price>([^<]+)</price>", inner) or [None, None])[1])
            if currency and currency.group(1) != "RUB":
                issues.append(f"yml.xml {sku} currency {currency.group(1)}")
            if price is not None and not close(price, rub(sku), 0.51):
                issues.append(f"yml.xml {sku} {by_sku[sku].get('name')} price {price} != {rub(sku)}")
            param = re.search(r'<param name="Срок годности">([^<]+)</param>', inner)
            want = str(by_sku[sku].get("shelfLife") or "").strip()
            if param and want and param.group(1).strip() != want:
                issues.append(f"yml.xml {sku} shelf {param.group(1)!r} != {want!r}")
            issues.extend(check_chak_text(f"yml.xml:{sku}", inner))
    # Canonical Merchant feed is RUB. Country feeds (AED, KZT, …) are
    # conversions from the Sheet RUB offer — do not demand they equal RUB.
    main_feed = PUBLIC / "products-feed.xml"
    if main_feed.is_file():
        rel = "products-feed.xml"
        body = main_feed.read_text(encoding="utf-8")
        for item in re.findall(r"<item>(.*?)</item>", body, re.S):
            sku_m = re.search(r"<g:id>(KD-\d{3})</g:id>", item)
            if not sku_m:
                continue
            sku = sku_m.group(1)
            if sku not in by_sku:
                continue
            price_m = re.search(r"<g:price>([0-9.]+)\s*(\w+)</g:price>", item)
            if not price_m:
                continue
            price, currency = num(price_m.group(1)), price_m.group(2)
            if currency != "RUB":
                issues.append(f"{rel} {sku} g:price currency {currency}")
            if price is not None and not close(price, rub(sku)):
                issues.append(
                    f"{rel} {sku} {by_sku[sku].get('name')} g:price {price} != {rub(sku)}"
                )
            issues.extend(check_chak_text(f"{rel}:{sku}", item))
    return issues


def check_llms(by_sku: dict[str, dict]) -> list[str]:
    issues = []
    for rel in ("llms.txt", "llms-full.txt", "en/llms.txt", "en/llms-full.txt",
                ".well-known/llms.txt"):
        path = PUBLIC / rel
        if not path.is_file():
            issues.append(f"{rel} missing")
            continue
        text = path.read_text(encoding="utf-8")
        issues.extend(check_chak_text(rel, text))
        issues.extend(check_kd012(rel, text))
        for sku, row in by_sku.items():
            # Table rows: | name | KD-NNN | weight | price | shelf |
            for line in text.splitlines():
                if f"| {sku} |" not in line and f"|{sku}|" not in line:
                    continue
                price = rub(sku)
                if f"{price:.2f}" not in line and f"{price:.0f}" not in line:
                    # bakery tables may put piece + box
                    issues.append(
                        f"{rel} table row {sku} {row.get('name')} missing catalog price {price:.2f}"
                    )
                want = str(row.get("shelfLife") or "")
                if want and sku in CHAK_SKU and "90" not in line:
                    issues.append(f"{rel} table row {sku} missing 90-day shelf life")
    return issues


def check_api_mcp(company: dict) -> list[str]:
    issues = []
    products = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    pub = products.get("publisher") or {}
    if pub.get("email") and pub["email"] != company["email"]:
        issues.append("products.json publisher.email != company_facts")
    phone = re.sub(r"\D", "", str(pub.get("phone") or ""))
    if phone and phone not in {"79872170202"}:
        issues.append(f"products.json publisher.phone {pub.get('phone')}")
    mcp = PUBLIC / ".well-known" / "mcp.json"
    if mcp.is_file():
        data = json.loads(mcp.read_text(encoding="utf-8"))
        email = ((data.get("publisher") or {}).get("email"))
        if email and email != company["email"]:
            issues.append("mcp.json publisher.email != company_facts")
    return issues


def catalog_rows(html: str, sku: str, lang: str) -> tuple[float | None, float | None]:
    prefix = "/en" if lang == "en" else ""
    m = re.search(
        rf'<li><a href="{prefix}/products/{sku.lower()}">[^<]*</a>'
        rf'<span class="cs-meta">([^<]*)(?:<span class=cs-price>([^<]*)</span>)?',
        html,
    )
    if not m:
        return None, None
    meta = unescape(m.group(1))
    w = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*(?:кг|kg)", meta)
    return (num(w.group(1)) if w else None), num(m.group(2)) if m.group(2) else None


def check_cards_and_lists(by_sku: dict[str, dict]) -> list[str]:
    """Product cards (JSON-LD + visible ₽/kg), catalog blocks, four wholesale lists."""
    issues = []
    catalogs = {}
    for lang, rel in (
        ("ru", "index.html"),
        ("en", "en/index.html"),
        ("ru", "products/index.html"),
        ("en", "en/products/index.html"),
    ):
        path = PUBLIC / rel
        catalogs[(lang, rel)] = path.read_text(encoding="utf-8") if path.is_file() else ""
    pricelists = {}
    for rel in (
        "wholesale-price-list-ru.md",
        "wholesale-price-list.md",
        "wholesale-price-list-ru.txt",
        "wholesale-price-list.txt",
    ):
        path = PUBLIC / rel
        if not path.is_file():
            issues.append(f"{rel} missing")
            continue
        pricelists[rel] = path.read_text(encoding="utf-8")

    for sku, row in by_sku.items():
        price = rub(sku)
        weight = num(row.get("weight"))
        shelf = str(row.get("shelfLife") or "").strip()
        storage = str(row.get("storage") or "").strip()
        for lang in ("ru", "en"):
            rel = f"{'en/' if lang == 'en' else ''}products/{sku.lower()}.html"
            path = PUBLIC / rel
            if not path.is_file():
                issues.append(f"{sku} card missing: {rel}")
                continue
            html = path.read_text(encoding="utf-8")
            ld = jsonld_prices(html)
            if price is not None and not any(close(price, x) for x in ld):
                issues.append(
                    f"{rel} {sku} {row.get('name')} JSON-LD price {sorted(ld)} != catalog {price}"
                )
            vw = visible_weights(html, lang)
            if weight is not None and not any(close(weight, x, 0.0011) for x in vw if x):
                issues.append(
                    f"{rel} {sku} visible weight {sorted(x for x in vw if x)} != {weight}"
                )
            vp = visible_prices_rub(html)
            if price is not None and not any(close(price, x) for x in vp):
                issues.append(
                    f"{rel} {sku} {row.get('name')} visible price {sorted(vp)} != catalog {price}"
                )
            if lang == "ru" and shelf and shelf not in html:
                issues.append(f"{rel} missing shelfLife {shelf}")
            if lang == "ru" and storage and storage not in html:
                issues.append(f"{rel} missing storage {storage}")
            if lang == "en":
                days = catalog_shelf_days(row)
                if days and not re.search(rf"{days}\s*days", html, re.I) and shelf not in html:
                    issues.append(f"{rel} missing shelf-life {days} days")
        for (lang, rel), html in catalogs.items():
            if not html:
                issues.append(f"{rel} catalog missing")
                continue
            w, pr = catalog_rows(html, sku, lang)
            if w is None and pr is None:
                issues.append(f"{rel} {sku} catalog row missing")
                continue
            if weight is not None and w is not None and not close(weight, w, 0.0011):
                issues.append(f"{rel} {sku} weight {w} != {weight}")
            if pr is not None and not close(price, pr, 0.51):
                issues.append(f"{rel} {sku} {row.get('name')} catalog price {pr} != {price}")
        for rel, body in pricelists.items():
            row_pl = (pricelist_row_txt if rel.endswith(".txt") else pricelist_row)(body, sku)
            if not row_pl:
                issues.append(f"{rel} {sku} row missing")
                continue
            if price is not None and not close(price, row_pl["price"]):
                issues.append(
                    f"{rel} {sku} {row.get('name')} price {row_pl['price']} != {price}"
                )
            if weight is not None and not close(weight, row_pl["weight"], 0.0011):
                issues.append(f"{rel} {sku} weight {row_pl['weight']} != {weight}")
            if "-ru." in rel and shelf and row_pl["shelf"] != shelf:
                issues.append(f"{rel} {sku} shelf {row_pl['shelf']!r} != {shelf!r}")
            if storage and row_pl["storage"] != storage:
                issues.append(f"{rel} {sku} storage {row_pl['storage']!r} != {storage!r}")
    return issues


def check_halal(company: dict) -> list[str]:
    issues = []
    path = PUBLIC / "halal.html"
    if not path.is_file():
        return ["public/halal.html missing"]
    text = path.read_text(encoding="utf-8")
    for cert in company["halal_certificates"]:
        if cert["number"] not in text and cert["number"].replace("A", "А") not in text:
            issues.append(f"/halal missing cert {cert['number']}")
    issues.extend(check_company_mentions("halal.html", text, company))
    return issues


def main() -> int:
    if not COMPANY_PATH.is_file():
        print("check_fact_consistency: missing data/company_facts.json", file=sys.stderr)
        return 1
    company = load_company()
    site = json.loads(SITE_FACTS_PATH.read_text(encoding="utf-8")) if SITE_FACTS_PATH.is_file() else {}
    cat = catalog()
    by_sku = cat["by_sku"]

    issues: list[str] = []
    issues.extend(issues_company(company, site))
    issues.extend(check_products_self(by_sku))
    issues.extend(check_cards_and_lists(by_sku))
    issues.extend(check_feeds(by_sku))
    issues.extend(check_llms(by_sku))
    issues.extend(check_api_mcp(company))
    issues.extend(check_halal(company))

    html_files = [p for p in walk_public_files() if p.suffix == ".html"]
    # Offer currency/price: RU root + /en only (canonical locales). Other
    # geo-locale copies are not a second catalog and stay out of this gate.
    locale_skip = re.compile(r"^(hy|tg|ka|kk|ky|uz|az|zh|ar|he)/")
    for path in html_files:
        rel = path.relative_to(PUBLIC).as_posix()
        text = path.read_text(encoding="utf-8")
        if not locale_skip.match(rel):
            issues.extend(check_jsonld(rel, text, company, by_sku))
        issues.extend(check_chak_text(rel, text))
        issues.extend(check_corrupt_shelf(rel, text))
        issues.extend(check_kd012(rel, text))
        issues.extend(check_company_mentions(rel, text, company))

    for rel in ("llms-full.txt", "en/llms-full.txt", "llms.txt", "en/llms.txt"):
        path = PUBLIC / rel
        if path.is_file():
            issues.extend(check_company_mentions(rel, path.read_text(encoding="utf-8"), company))

    # Dedup while keeping order
    seen = set()
    uniq = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            uniq.append(item)

    print(f"fact consistency: {len(by_sku)} SKU, {len(html_files)} HTML, "
          f"company_facts {company['inn']} → {len(uniq)} issue(s)")
    for item in uniq[:80]:
        print(f"  {item}")
    if len(uniq) > 80:
        print(f"  … {len(uniq) - 80} more")
    return 1 if uniq else 0


if __name__ == "__main__":
    sys.exit(main())
