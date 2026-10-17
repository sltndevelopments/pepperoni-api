#!/usr/bin/env python3
"""Stamper field must match the offer: pricePerUnit only when the SKU has it."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from stamp_catalog_prices import catalog, stamp_text  # noqa: E402
from test_no_hardcoded_prices import main as gate_main  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
        return
    fail += 1
    print("  FAIL", msg)


def main() -> int:
    prices = catalog()
    check(prices.get("KD-044", {}).get("field") == "price",
          "KD-044 (pack / no pricePerUnit) stamps as price")
    check(prices.get("KD-009", {}).get("field") == "price",
          "KD-009 (pack) stamps as price")
    check(prices.get("KD-053", {}).get("field") == "pricePerUnit",
          "KD-053 (bakery) stamps as pricePerUnit")
    check(prices.get("KD-050", {}).get("field") == "pricePerUnit",
          "KD-050 (bakery) stamps as pricePerUnit")

    pack_amt = "650" + ",00 " + "\u20bd"
    pack_row = (
        "<tr><td><a href=\"/products/kd-044\">KD-044</a></td>"
        f"<td>name</td><td>200 г</td><td>{pack_amt}</td>"
        "<td>180 суток</td></tr>"
    )
    stamped = stamp_text(f"<table>{pack_row}</table>", prices, "blog/kazylyk.html")
    check('data-price-field="price"' in stamped, "pack row tagged price")
    check("pricePerUnit" not in stamped, "pack row is not tagged pricePerUnit")

    piece_row = (
        "<tr><td><a href=\"/products/kd-053\">KD-053</a></td>"
        "<td>name</td><td>211,80</td><td>—</td><td>4680638720820</td></tr>"
    )
    stamped = stamp_text(f"<table>{piece_row}</table>", prices, "blog/chak-chak.html")
    check('data-price-field="pricePerUnit"' in stamped,
          "bakery row tagged pricePerUnit")

    # Rebuild live blog pages from products.json, then the price gate must pass.
    import stamp_catalog_prices as stamper
    rc = stamper.main()
    check(rc == 0, "stamp_catalog_prices.main() rebuilds")
    gate_rc = gate_main()
    check(gate_rc == 0, "price gate passes after stamp rebuild")

    if fail:
        print(f"test_stamp_catalog_prices: {fail} FAIL")
        return 1
    print("test_stamp_catalog_prices: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
