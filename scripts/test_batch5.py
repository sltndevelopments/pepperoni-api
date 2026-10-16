#!/usr/bin/env python3
"""Batch 5: PDF-after-inject, Uzbekistan readiness, money-page SEO, keep swap."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from gen_price_lists import main as price_main  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def title_of(rel: str) -> str:
    html = (ROOT / "public" / rel).read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def html_of(rel: str) -> str:
    return (ROOT / "public" / rel).read_text(encoding="utf-8")


def h1_count(html: str) -> int:
    return len(re.findall(r"<h1\b", html, re.I))


def main() -> int:
    src = (ROOT / "scripts" / "sync-vps.sh").read_text(encoding="utf-8")
    inject_at = src.find("inject_site_links.py")
    pdf_only_at = src.find("gen_price_lists.py --pdf-only")
    check(inject_at != -1 and pdf_only_at > inject_at, "sync-vps: --pdf-only after inject")

    price_src = (ROOT / "scripts" / "gen_price_lists.py").read_text(encoding="utf-8")
    check("--pdf-only" in price_src, "gen_price_lists has --pdf-only")
    tree = ast.parse(price_src)
    check(any(isinstance(n, ast.FunctionDef) and n.name == "write_pdf_only" for n in tree.body),
          "write_pdf_only exists")

    uz = html_of("export/uzbekistan.html")
    uz_en = html_of("en/export/uzbekistan.html")
    check("RU-016/SB88273" in uz and "Цербер" in uz, "UZ RU has Cerberus id")
    check("Cerberus" in uz_en and "RU-016/SB88273" in uz_en, "UZ EN has Cerberus id")
    check("не текущая отгрузка" in uz or "не обещание" in uz, "UZ RU readiness, not shipment")
    check("not a current shipment" in uz_en.lower() or "not a promise" in uz_en.lower(),
          "UZ EN readiness, not shipment")
    check("ЕАЭС" in uz and "не входит" in uz, "UZ states not EAEU")
    check("not an EAEU" in uz_en, "UZ EN states not EAEU")
    check("варено-копченый" not in uz_en, "UZ EN sku table uses EN names")
    check("суток" not in uz_en, "UZ EN sku table uses EN shelf-life units")
    check("Cooked-Smoked Chicken Pepperoni" in uz_en, "UZ EN has translated KD-013 name")
    check(not re.search(r"\bUZS\b.{0,40}\d", uz), "UZ RU has no UZS amount")
    check("Оферты в UZS нет" in uz or "в сумах" in uz, "UZ RU refuses UZS offer")
    check("no UZS offer" in uz_en.lower() or "no som" in uz_en.lower(), "UZ EN refuses UZS offer")
    check(not re.search(r"\d+\s*[–-]\s*\d+\s*(?:рабочих\s+)?дн", uz), "UZ RU no transit days")
    check(h1_count(uz) == 1 and h1_count(uz_en) == 1, "UZ pages have one H1")

    man = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    keep_files = {r["file"] for r in man["entries"] if r.get("status") == "keep"}
    check("export/uzbekistan.html" in keep_files, "UZ RU is keep")
    check("en/export/uzbekistan.html" in keep_files, "UZ EN is keep")
    check("export/yemen.html" not in keep_files, "Yemen RU not keep")
    check("en/export/yemen.html" not in keep_files, "Yemen EN not keep")
    keep_n = len(keep_files)
    check(180 <= keep_n <= 260, f"keep count {keep_n} in 180–260")

    pepp = html_of("pepperoni.html")
    piz = html_of("pepperoni-dlya-pizzerii.html")
    check("Казахстан, Беларусь, Узбекистан" not in pepp,
          "/pepperoni does not list Uzbekistan as a current shipment")
    i18n = json.loads((ROOT / "data" / "pepperoni_landing_i18n.json").read_text(encoding="utf-8"))
    check("Казахстан, Беларусь, Узбекистан" not in i18n["ru"]["export"]["sub"],
          "i18n RU export.sub does not list UZ as current")
    check("для пиццерий" not in title_of("pepperoni.html").lower(),
          "/pepperoni title does not target pizzerias")
    check("пиццер" in title_of("pepperoni-dlya-pizzerii.html").lower(),
          "/pepperoni-dlya-pizzerii title targets pizzerias")
    check("куриный" in piz or "KD-013" in piz, "pizzeria page is chicken KD-013/014")
    check(h1_count(pepp) == 1 and h1_count(piz) == 1, "pepperoni pair one H1 each")

    llms = (ROOT / "public" / "llms.txt").read_text(encoding="utf-8")
    llms_en = (ROOT / "public" / "en" / "llms.txt").read_text(encoding="utf-8")
    check("/export/uzbekistan" in llms, "llms.txt links Uzbekistan")
    check("/en/export/uzbekistan" in llms_en, "en/llms.txt links Uzbekistan")

    mcp = (ROOT / "mcp" / "api-client.js").read_text(encoding="utf-8")
    check("/export/uzbekistan" in mcp, "MCP DELIVERY_INFO mentions Uzbekistan")
    jerky_en = html_of("en/jerky.html")
    jerky_ru = html_of("jerky.html")
    check('href="/oem"' not in jerky_en and 'href="/en/oem"' not in jerky_en,
          "EN jerky does not link retired /oem")
    check('href="/oem"' not in jerky_ru, "RU jerky does not link retired /oem")
    check("/en/private-label" in jerky_en, "EN jerky STM URL is /en/private-label")
    check("/kontraktnoe-proizvodstvo" in jerky_ru, "RU jerky STM URL is /kontraktnoe-proizvodstvo")
    write_pdf_fn = price_src[price_src.find("def write_pdf("):price_src.find("def _strip_runtime")]
    check("return dest.is_file() and dest.stat().st_size > 1000" not in write_pdf_fn,
          "write_pdf does not treat leftover PDF as success")
    check("after > before" in price_src, "write_pdf_only checks mtime actually moved")
    check("Do not quote UZS as an offer" in mcp, "MCP does not treat UZS as offer")

    meta = json.loads((ROOT / "public" / ".well-known" / "ai-meta.json").read_text())
    check(meta["commercial_canon"].get("export_uzbekistan", "").endswith("/export/uzbekistan"),
          "ai-meta commercial_canon has Uzbekistan")

    nginx = (ROOT / "deploy" / "nginx" / "export-country-redirects.conf").read_text()
    check("location = /export/yemen" in nginx and "return 301" in nginx, "yemen nginx 301")

    for rel in (
        "pepperoni.html", "pepperoni-dlya-pizzerii.html", "jerky.html",
        "kazylyk.html", "sosiska-v-teste.html", "vyipechka-halyal.html",
        "halal.html", "dlya-horeca.html", "dlya-setey.html",
        "dlya-distributorov.html", "export.html", "export/kazakhstan.html",
        "export/uzbekistan.html",
    ):
        html = html_of(rel)
        check(h1_count(html) == 1, f"{rel} has exactly one H1")
        check('hreflang="ru"' in html and 'hreflang="en"' in html, f"{rel} has ru+en hreflang")

    # argparse of --pdf-only must parse (do not write during unit check if possible)
    check(callable(price_main), "price main importable")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
