#!/usr/bin/env python3
"""Mutation tests for the hardcoded-price gate (review P3–P6, P9–P12 + f-string).

Each plant is assembled at runtime so this file itself does not contain a
currency-marked literal. The four review-round-3 plants (E1/E2/E9/E5) go
through main() so discovery and skip rules are exercised.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_no_hardcoded_prices import (  # noqa: E402
    accepted_amounts,
    main as gate_main,
    scan_html_loose_text,
    scan_source_text,
    scan_visible_text,
)

PEPPERONI = ROOT / "public" / "pepperoni.html"
PROMO = ROOT / "public" / "promo-test.html"
SEGMENTS = ROOT / "scripts" / "gen-en-segments.py"


def _join(*parts: str) -> str:
    return "".join(parts)


def _check(name: str, hits: list[str], failures: list[str]) -> None:
    if hits:
        print(f"  ok {name} → {hits[0]}")
        return
    print(f"  FAIL {name}: gate missed the plant")
    failures.append(name)


def _expect_main_fail(name: str, apply, revert, failures: list[str]) -> None:
    apply()
    try:
        rc = gate_main()
        if rc != 0:
            print(f"  ok {name} → main() rc={rc}")
            return
        print(f"  FAIL {name}: main() returned 0")
        failures.append(name)
    finally:
        revert()


def main() -> int:
    accepted = accepted_amounts()
    failures: list[str] = []

    # P3 integer '274 руб.' (no decimals) in a generator string
    p3 = _join('msg = "', "от ", "274", " руб.", ' за упаковку"')
    _check("P3 integer руб.", scan_source_text("scripts/gen-en-segments.py", p3), failures)

    # P4 bare int tied to a price name
    p4 = _join("PRICE_KD", "013", " = ", "274", "\n")
    _check("P4 PRICE_KD013 = 274", scan_source_text("scripts/gen-geo-products.py", p4), failures)

    # P5 USD 3.37
    p5 = _join('msg = "', "USD ", "3.37", ' per pack"')
    _check("P5 dollar-prefixed export amount", scan_source_text("scripts/gen-en-segments.py", p5), failures)

    # P6 visible page text without SKU / stamp
    p6 = _join("<p>Цена ", "274", " ₽ за упаковку</p>")
    _check("P6 visible HTML", scan_html_loose_text("pepperoni.html", p6, accepted), failures)

    # P9 JS (lib/ never used to be scanned)
    p9 = _join('label = "', "от ", "274", ' ₽"')
    _check("P9 lib/product-page.mjs", scan_source_text("lib/product-page.mjs", p9), failures)

    # P10 script outside the old SOURCE_GLOBS allowlist
    p10 = _join('label = "', "от ", "274", ' ₽"')
    _check(
        "P10 scripts/render_static_catalog.py",
        scan_source_text("scripts/render_static_catalog.py", p10),
        failures,
    )

    # P11 blog page: amount next to KD-053 is not that SKU's price
    p11 = _join("<p>Чак-чак от ", "199,00", " ₽ (KD-053)</p>")
    _check(
        "P11 blog chak-chak",
        scan_visible_text("blog/chak-chak.html", p11, accepted, unbound_ok=True),
        failures,
    )

    # P12 llms.txt
    p12 = _join("KD-013 price: ", "999", " RUB")
    _check("P12 llms.txt", scan_visible_text("llms.txt", p12, accepted, unbound_ok=True), failures)

    # f-string on 3.12+ (FSTRING_MIDDLE) and 3.11 (STRING)
    p2 = _join("x = 1\ns = f\"от ", "274", " ₽ {x}\"\n")
    _check("P2 f-string", scan_source_text("scripts/gen-en-segments.py", p2), failures)

    original_pepperoni = PEPPERONI.read_text(encoding="utf-8")
    original_segments = SEGMENTS.read_text(encoding="utf-8")
    promo_existed = PROMO.exists()
    promo_original = PROMO.read_text(encoding="utf-8") if promo_existed else None

    e1 = _join('<p data-catalog-price="KD-013">', "999", " ₽</p>\n")

    def apply_e1() -> None:
        PEPPERONI.write_text(original_pepperoni + e1, encoding="utf-8")

    def revert_pepperoni() -> None:
        PEPPERONI.write_text(original_pepperoni, encoding="utf-8")

    _expect_main_fail("E1 stamped 999 on KD-013", apply_e1, revert_pepperoni, failures)

    e2 = _join(
        '<div class="promo">Цена ', "999", " ₽</div>\n",
        "<table><tr><td>KD-013</td><td>", "999", " ₽</td></tr></table>\n",
    )

    def apply_e2() -> None:
        PEPPERONI.write_text(original_pepperoni + e2, encoding="utf-8")

    _expect_main_fail("E2 div/td 999 on landing", apply_e2, revert_pepperoni, failures)

    e9 = _join("<html><body><div>KD-013 ", "999", " ₽</div></body></html>\n")

    def apply_e9() -> None:
        PROMO.write_text(e9, encoding="utf-8")

    def revert_e9() -> None:
        if promo_existed:
            PROMO.write_text(promo_original or "", encoding="utf-8")
        elif PROMO.exists():
            PROMO.unlink()

    _expect_main_fail("E9 new page with price", apply_e9, revert_e9, failures)

    e5 = _join("\nprice = \"", "274", "\"\n")

    def apply_e5() -> None:
        SEGMENTS.write_text(original_segments + e5, encoding="utf-8")

    def revert_e5() -> None:
        SEGMENTS.write_text(original_segments, encoding="utf-8")

    _expect_main_fail("E5 price = string 274", apply_e5, revert_e5, failures)

    if failures:
        print(f"test_no_hardcoded_prices_mutation: {len(failures)} missed: {failures}")
        return 1
    print("test_no_hardcoded_prices_mutation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
