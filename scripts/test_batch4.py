#!/usr/bin/env python3
"""Batch 4: non-snap Chrome selection, DejaVu PDF fallback, Yandex IPv4 helper."""
from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from gen_price_lists import _is_snap, _python_pdf, load  # noqa: E402
from ipv4_http import IPv4HTTPSConnection  # noqa: E402
from price_pdf import DEJAVU, write_catalog_pdf  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def main() -> int:
    check(_is_snap("/snap/bin/chromium"), "snap path is snap")
    check(_is_snap("/snap/chromium/current/usr/lib/chromium-browser/chrome"), "snap prefix is snap")
    check(not _is_snap("/usr/bin/chromium-browser"), "apt chromium-browser is not snap")
    check(not _is_snap("/usr/bin/google-chrome-stable"), "google-chrome-stable is not snap")

    check(DEJAVU.is_file(), "DejaVuSans.ttf present")
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "prices.pdf"
        write_catalog_pdf(
            dest, "Казанские Деликатесы", ["65 SKU"],
            ["SKU", "Наименование"], [["KD-001", "Сосиски"]],
        )
        check(dest.is_file() and dest.stat().st_size > 1000, "table PDF bytes > 1000")
        check(dest.read_bytes()[:8] == b"%PDF-1.4", "PDF header")

        meta, products, tr = load()
        dest2 = Path(tmp) / "from-rows.pdf"
        ok = _python_pdf(meta, products, tr, dest2)
        check(ok, "python fallback from catalog rows")
        check(dest2.stat().st_size > 5000 if dest2.is_file() else False, "catalog PDF not empty")

    # getaddrinfo AF_INET for Yandex Webmaster (the AAAA is what broke the VPS)
    infos = socket.getaddrinfo(
        "api.webmaster.yandex.net", 443, socket.AF_INET, socket.SOCK_STREAM
    )
    check(bool(infos), "Yandex Webmaster has an A record")
    check(all(r[0] == socket.AF_INET for r in infos), "AF_INET results are IPv4")
    check(hasattr(IPv4HTTPSConnection, "connect"), "IPv4 HTTPS connection override")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "yandex_index", ROOT / "scripts" / "yandex-index.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    probe = mod._ipv4_probe("api.webmaster.yandex.net")
    check(isinstance(probe, str) and len(probe) > 2, f"IPv4 probe returns status ({probe})")

    coffee = ROOT / "public" / "zamorozhennaya-vypechka-dlya-kofeen.html"
    setey = ROOT / "public" / "dlya-setey.html"
    if coffee.is_file():
        html = coffee.read_text(encoding="utf-8")
        check("KD-055" in html, "coffee page has KD-055")
        check("350 °C" not in html and "350°C" not in html, "coffee page has no invented 350°C")
        check("GSO" not in html and "JAKIM" not in html, "coffee page no GSO/JAKIM")
    if setey.is_file():
        html = setey.read_text(encoding="utf-8")
        check("0008" in html, "setey primary cert 0008")
        check("Мираторг" not in html, "setey does not invent Miratorg")
        check("fill-rate" not in html.lower() and "ниже 1%" not in html, "setey no invented SLA %")
    setey_en = ROOT / "public" / "en" / "dlya-setey.html"
    if setey_en.is_file():
        html = setey_en.read_text(encoding="utf-8")
        check("fill-rate" not in html.lower(), "EN setey no fill-rate")
        check("Miratorg" not in html, "EN setey does not invent Miratorg")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
