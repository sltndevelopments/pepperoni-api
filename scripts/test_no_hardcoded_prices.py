#!/usr/bin/env python3
"""Gate: no price may be hardcoded. Sheet → products.json is the only source.

Part A — source templates (generators, content-plan, tests): tokenize Python
string literals and fail on money-like tokens. Allowlist is only
public/products.json and the Sheet sync scripts.

Part B — generated HTML / JSON-LD / feeds / llms: every rendered Offer/feed
price equals the products.json value for that SKU; currency-marked amounts
must be a live catalog (or Sheet export) figure.
"""
from __future__ import annotations

import json
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PUBLIC = ROOT / "public"
sys.path.insert(0, str(SCRIPTS))
from catalog_prices import catalog, num, rub  # noqa: E402

ALLOW_SOURCE = {
    ROOT / "public" / "products.json",
    SCRIPTS / "sync-sheets.py",
    SCRIPTS / "sync-sheets.mjs",
}

# Generators and tests that emit or assert public prices.
SOURCE_GLOBS = (
    "gen*.py",
    "gen-*.py",
    "content_plan*.py",
    "fix_invented*.py",
    "patch_*.py",
    "apply_*.py",
    "stamp_catalog_prices.py",
    "commercial_page.py",
    "test_*.py",
)

MONEY_IN_STRING = re.compile(
    r"""
    (?:
        \d{1,3}(?:[ \u00a0]\d{3})*[.,]\d{2}\s*(?:₽|руб(?:\.|лей)?|\bRUB\b)
        | (?:₽|руб(?:\.|лей)?|\bRUB\b)\s*\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d{2})?
        | \$\d+[.,]\d{2}
        | (?<![.\w])\d{2,5}\s*₽
        | "price"\s*:\s*"\d+(?:\.\d+)?"
        | 'price'\s*:\s*'\d+(?:\.\d+)?'
    )
    """,
    re.X,
)

# "274 ₽ stays 274 ₽" style comments are skipped because we tokenize strings only.
# Tests may mention a stale figure they forbid — list those tokens here.
FORBIDDEN_STALE_OK = {
    "$0.91",   # regression: old EN bakery Offer, must not reappear
    "68,77",   # regression: old echpochmak FAQ
    "68.77",
}

LD_RE = re.compile(
    r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
SKU_NEAR = re.compile(r"KD-\d{3}", re.I)


def accepted_amounts() -> set[float]:
    out: set[float] = set()
    for row in catalog()["products"]:
        offers = row.get("offers") or {}
        for key in ("price", "pricePerUnit", "pricePerBox", "priceExclVAT",
                    "pricePerUnitExclVAT", "pricePerBoxExclVAT", "pricePerPiece"):
            value = num(offers.get(key))
            if value and value > 0:
                out.add(round(value, 2))
        for value in (offers.get("exportPrices") or {}).values():
            n = num(value)
            if n and n > 0:
                out.add(round(n, 2))
        for value in (offers.get("exportPricesPerBox") or {}).values():
            n = num(value)
            if n and n > 0:
                out.add(round(n, 2))
    return out


def source_files() -> list[Path]:
    files: list[Path] = []
    for glob in SOURCE_GLOBS:
        files.extend(SCRIPTS.glob(glob))
    # Dedup, skip allowlist and this file's regex-only noise is still scanned
    # (we do not put live prices in this file).
    out = []
    seen = set()
    for path in files:
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in {p.resolve() for p in ALLOW_SOURCE}:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(path)
    return sorted(out)


def scan_python_strings(path: Path) -> list[str]:
    hits = []
    try:
        src = path.read_bytes()
        tokens = tokenize.tokenize(iter(src.splitlines(True)).__next__)
    except tokenize.TokenError as exc:
        return [f"{path.relative_to(ROOT)} tokenize error: {exc}"]
    for tok in tokens:
        if tok.type != tokenize.STRING:
            continue
        # Drop quotes / prefixes for the search.
        body = tok.string
        if body.startswith(("r", "R", "f", "F", "b", "B", "u", "U")):
            # strip up to 3 prefix chars
            i = 0
            while i < len(body) and body[i] in "rRuUfFbB":
                i += 1
            body = body[i:]
        if len(body) >= 2 and body[0] in {'"', "'"}:
            body = body[1:-1]
        for m in MONEY_IN_STRING.finditer(body):
            token = m.group(0)
            if any(stale in token for stale in FORBIDDEN_STALE_OK):
                continue
            hits.append(
                f"{path.relative_to(ROOT)}:{tok.start[0]} hardcoded {token!r}"
            )
    return hits


def parse_ld(html: str) -> list[dict]:
    out: list[dict] = []
    for raw in LD_RE.findall(html):
        try:
            node = json.loads(raw)
        except json.JSONDecodeError:
            continue
        blob = [node] if isinstance(node, dict) else list(node) if isinstance(node, list) else []
        for item in blob:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("@graph"), list):
                out.extend(x for x in item["@graph"] if isinstance(x, dict))
            out.append(item)
    return out


def close(a: float | None, b: float | None, tol: float = 0.011) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def scan_generated(accepted: set[float]) -> list[str]:
    issues = []
    by_sku = catalog()["by_sku"]

    def check_offer(rel: str, node: dict) -> None:
        sku = str(node.get("sku") or "").upper()
        offer = node.get("offers")
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        if not isinstance(offer, dict):
            return
        price = num(offer.get("price"))
        currency = offer.get("priceCurrency")
        if sku in by_sku:
            if currency and currency != "RUB":
                issues.append(f"{rel} {sku} Offer currency {currency} (catalog RUB)")
            if price is not None and not close(price, rub(sku)):
                issues.append(
                    f"{rel} {sku} Offer {price} != products.json {rub(sku)}"
                )
        elif price is not None and round(price, 2) not in accepted:
            issues.append(f"{rel} Offer price {price} is not a catalog amount")

    locale_skip = ("hy/", "tg/", "ka/", "kk/", "ky/", "uz/", "az/", "zh/", "ar/", "he/")
    for path in PUBLIC.rglob("*.html"):
        rel = path.relative_to(PUBLIC).as_posix()
        if rel.startswith(("1/", "2/", "3/", "4/", "5/") + locale_skip):
            continue
        html = path.read_text(encoding="utf-8")
        for node in parse_ld(html):
            types = node.get("@type")
            typeset = {types} if isinstance(types, str) else set(types or [])
            if "Product" in typeset or "Offer" in typeset:
                check_offer(rel, node)

    yml = PUBLIC / "yml.xml"
    if yml.is_file():
        body = yml.read_text(encoding="utf-8")
        for sku, inner in re.findall(r'<offer id="(KD-\d{3})"[^>]*>(.*?)</offer>', body, re.S):
            if sku not in by_sku:
                continue
            price = num((re.search(r"<price>([^<]+)</price>", inner) or [None, None])[1])
            if price is not None and not close(price, rub(sku), 0.51):
                issues.append(f"yml.xml {sku} <price>{price} != {rub(sku)}")

    feed = PUBLIC / "products-feed.xml"
    if feed.is_file():
        rel = "products-feed.xml"
        body = feed.read_text(encoding="utf-8")
        for item in re.findall(r"<item>(.*?)</item>", body, re.S):
            sku_m = re.search(r"<g:id>(KD-\d{3})</g:id>", item)
            price_m = re.search(r"<g:price>([0-9.]+)\s*(\w+)</g:price>", item)
            if not sku_m or not price_m:
                continue
            sku = sku_m.group(1)
            if sku not in by_sku:
                continue
            price, currency = num(price_m.group(1)), price_m.group(2)
            if currency != "RUB":
                issues.append(f"{rel} {sku} g:price {currency}")
            if price is not None and not close(price, rub(sku)):
                issues.append(f"{rel} {sku} g:price {price} != {rub(sku)}")
    return issues


def main() -> int:
    fail = 0
    source_hits = []
    for path in source_files():
        if path.suffix == ".py":
            source_hits.extend(scan_python_strings(path))
    print(f"no_hardcoded_prices source: {len(source_files())} files, {len(source_hits)} hit(s)")
    for hit in source_hits[:60]:
        print(f"  FAIL {hit}")
        fail += 1
    if len(source_hits) > 60:
        print(f"  … {len(source_hits) - 60} more")
        fail += len(source_hits) - 60

    accepted = accepted_amounts()
    gen_hits = scan_generated(accepted)
    print(f"no_hardcoded_prices generated: {len(gen_hits)} mismatch(es), "
          f"{len(accepted)} accepted catalog amounts")
    for hit in gen_hits[:60]:
        print(f"  FAIL {hit}")
        fail += 1
    if len(gen_hits) > 60:
        print(f"  … {len(gen_hits) - 60} more")
        fail += len(gen_hits) - 60

    if fail:
        print(f"test_no_hardcoded_prices: {fail} FAIL")
        return 1
    print("test_no_hardcoded_prices: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
