#!/usr/bin/env python3
"""#62 landings: deploy generators must emit the committed title/H1/og:title/FAQ."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import content_plan_pages as plan  # noqa: E402
import gen_category_pages as cat  # noqa: E402
import gen_pepperoni_landing as pep  # noqa: E402

LOCK_PAGES = (
    "pepperoni-dlya-pizzerii.html",
    "en/pepperoni-dlya-pizzerii.html",
    "kazylyk.html",
    "en/pepperoni.html",
)

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def title_text(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def h1_of(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1) if m else "")).strip()


def og_title(html: str) -> str:
    m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        html,
        re.I,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            html,
            re.I,
        )
    return (m.group(1).strip() if m else "")


def faq_pairs(html: str) -> list[tuple[str, str]]:
    pairs = []
    for block in re.findall(
        r"<details\b[^>]*>.*?</details>", html, re.I | re.S
    ):
        q = re.search(r"<summary\b[^>]*>(.*?)</summary>", block, re.I | re.S)
        a = re.search(r'<div class="ans">(.*?)</div>', block, re.I | re.S)
        question = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", q.group(1) if q else "")).strip()
        answer = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", a.group(1) if a else "")).strip()
        pairs.append((question, answer))
    return pairs


def compare_fields(rel: str, generated: str, committed: str) -> None:
    check(title_text(generated) == title_text(committed), f"{rel} title matches generator")
    check(h1_of(generated) == h1_of(committed), f"{rel} H1 matches generator")
    check(og_title(generated) == og_title(committed), f"{rel} og:title matches generator")
    check(og_title(generated) == title_text(generated), f"{rel} generator og:title equals title")
    check(faq_pairs(generated) == faq_pairs(committed), f"{rel} FAQ matches generator")


def pizza_generated() -> dict[str, str]:
    data = plan.catalog()
    items = plan.by_sku(data, "KD-013", "KD-014")
    return {
        "pepperoni-dlya-pizzerii.html": plan.pizzeria_page("ru", items),
        "en/pepperoni-dlya-pizzerii.html": plan.pizzeria_page("en", items),
    }


def kazylyk_generated() -> str:
    cfg = next(row for row in cat.PAGES if row.get("slug") == "kazylyk")
    return cat.build_page(cfg)


def main() -> int:
    check(plan.format_diameter("50-55", "ru") == "50–55 мм", "RU diameter pretty-print")
    check(plan.format_diameter("50-55", "en") == "50–55 mm", "EN diameter pretty-print")
    check(plan.format_diameter("", "ru") == "", "empty diameter omitted")
    check(
        plan.pizzeria_caliber(
            [{"sku": "KD-013", "weight": "0,5", "diameter": ""},
             {"sku": "KD-014", "weight": "0,8", "diameter": ""}],
            "ru",
        ) == "",
        "empty KD-013/KD-014 diameter drops caliber clause",
    )

    catalog = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    by_sku = {p.get("sku"): p for p in catalog.get("products") or []}
    check(by_sku.get("KD-013", {}).get("diameter") == "50-55", "KD-013 diameter in catalog")
    check(by_sku.get("KD-014", {}).get("diameter") == "50-55", "KD-014 diameter in catalog")

    pizza = pizza_generated()
    for rel, html in pizza.items():
        committed = (PUBLIC / rel).read_text(encoding="utf-8")
        compare_fields(rel, html, committed)
        check("50–55" in html, f"{rel} generator FAQ uses catalog diameter")
        check("no diameter field" not in html.lower(), f"{rel} does not claim missing diameter")
        check("поставки мяса в рестораны" not in title_text(html).lower(),
              f"{rel} title is not the HoReCa query")

    kazy = kazylyk_generated()
    compare_fields("kazylyk.html", kazy, (PUBLIC / "kazylyk.html").read_text(encoding="utf-8"))
    check(h1_of(kazy) == "Казылык оптом — татарская колбаса из конины",
          "kazylyk generator H1 keeps the horse-sausage query")

    i18n = pep.load_i18n()
    family = pep.load_products()
    en_pep = pep.render("en", i18n, family)
    committed = (PUBLIC / "en/pepperoni.html").read_text(encoding="utf-8")
    compare_fields("en/pepperoni.html", en_pep, committed)
    title = title_text(en_pep)
    check(title.startswith("Pepperoni Halal Wholesale"),
          "EN pepperoni title leads with pepperoni halal")
    check(title.split(" | ", 1)[0] == "Pepperoni Halal Wholesale — Halal Chicken Pepperoni from Kazan",
          "EN pepperoni title ≤70 chars before the brand suffix")
    check(len(title.split(" | ", 1)[0]) <= 70, "EN pepperoni title prefix ≤70")
    check(h1_of(en_pep) == "Halal pepperoni wholesale — cooked-smoked chicken from Kazan",
          "EN pepperoni H1 stays commercial")
    check(og_title(en_pep) == title, "EN pepperoni og:title equals title")
    details = re.findall(r"<details\b[^>]*>.*?</details>", en_pep, re.I | re.S)
    faq_qas = []
    for block in details:
        q = re.search(r"<summary\b[^>]*>(.*?)</summary>", block, re.I | re.S)
        a = re.search(r"<p>(.*?)</p>", block, re.I | re.S)
        question = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", q.group(1) if q else "")).strip()
        answer = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", a.group(1) if a else "")).strip()
        faq_qas.append((question, answer))
    check(any(q == "Is this pepperoni halal?" for q, _a in faq_qas),
          "EN pepperoni FAQ question is «Is this pepperoni halal?»")
    first = next((a for q, a in faq_qas if q == "Is this pepperoni halal?"), "")
    check(first.startswith("Yes — the pepperoni is halal: chicken only, certified by DUM RT (certificate No. 0008)."),
          "EN pepperoni FAQ answer starts with the DUM RT 0008 sentence")
    check("/en/blog/what-is-halal-pepperoni" in en_pep
          and "our guide" in en_pep,
          "EN pepperoni FAQ links the what-is-halal-pepperoni guide")
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', en_pep, re.I)
    check(desc and desc.group(1).startswith("Pepperoni halal-certified by DUM RT (No. 0008):"),
          "EN pepperoni meta starts with DUM RT No. 0008")
    check("Minimum order: 1 pallet, EXW Kazan" in (desc.group(1) if desc else ""),
          "EN pepperoni meta keeps the 1 pallet MOQ")
    art = (PUBLIC / "en/blog/what-is-halal-pepperoni.html").read_text(encoding="utf-8")
    check(re.search(r'<a[^>]+href=["\']/en/pepperoni["\'][^>]*>halal pepperoni wholesale</a>', art, re.I),
          "what-is-halal-pepperoni already links /en/pepperoni with the wholesale anchor")

    if fail:
        print(f"test_gsc_generator_lock: {fail} FAIL")
        return 1
    print("test_gsc_generator_lock: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
