#!/usr/bin/env python3
"""Gates for the MOQ-phrasing gap and noindex hreflang rule."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
fail = 0

sys.path.insert(0, str(SCRIPTS))
import check_wholesale_moq as moq  # noqa: E402
from hreflang_policy import filter_page_alternates, is_keep, is_noindex  # noqa: E402


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


HREFLANG = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]*hreflang=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']',
    re.I,
)


def main() -> int:
    # Concatenate so this file is not itself a scanner hit.
    bad = [
        "Минимальная партия — " + "упаковка 100 кг",
        "от " + "упаковки 100 кг",
        "минимальный объём — " + "100 кг",
        "MOQ " + "100 kg",
        "minimum batch " + "50 kg",
    ]
    for phrase in bad:
        hits = moq.scan_text("<p>" + phrase + "</p>")
        check(len(hits) >= 1, f"bad MOQ fails: {phrase}")

    for phrase in ("нарезка 0,5 кг", "Масса 0,4 кг"):
        check(moq.scan_text("<p>" + phrase + "</p>") == [],
              f"pack weight passes: {phrase}")

    check(moq.scan_text("<p>Минимальный заказ — 1 паллета</p>") == [],
          "canonical RU MOQ passes")
    check(moq.scan_text("<p>Minimum order: 1 pallet</p>") == [],
          "canonical EN MOQ passes")

    src = (SCRIPTS / "check_fact_consistency.py").read_text(encoding="utf-8")
    check("scan_moq_text" in src, "fact-consistency runs the MOQ scanner")

    man = json.loads((ROOT / "data" / "index_manifest.json").read_text())
    noindex = {r["url"].rstrip("/") or "/" for r in man["entries"] if r.get("status") == "noindex"}

    check(is_noindex("https://pepperoni.tatar/export/kuwait"), "kuwait RU is noindex")
    check(is_keep("https://pepperoni.tatar/en/export/kuwait"), "kuwait EN is keep")
    check(is_noindex("https://pepperoni.tatar/export/bahrain"), "bahrain RU is noindex")

    en_kw = (PUBLIC / "en/export/kuwait.html").read_text(encoding="utf-8")
    ru_kw = (PUBLIC / "export/kuwait.html").read_text(encoding="utf-8")
    check(not re.search(r'hreflang="ru(?:-KW)?"[^>]+/export/kuwait"', en_kw),
          "EN kuwait has no ru/ru-KW hreflang to noindex RU")
    check("/export/kuwait" not in " ".join(
        m.group(2) for m in HREFLANG.finditer(en_kw) if m.group(1).lower().startswith("ru")
    ), "EN kuwait ru* hrefs are gone")
    check(not re.search(r'hreflang="en(?:-KW)?"[^>]+/en/export/kuwait"', ru_kw),
          "noindex RU kuwait has no EN alternate")

    # Generator is allowlist-driven.
    gen = (SCRIPTS / "gen_export_pages.py").read_text(encoding="utf-8")
    check("filter_page_alternates" in gen, "export generator filters by allowlist")

    leaked = []
    for row in man["entries"]:
        if row.get("status") != "keep":
            continue
        path = PUBLIC / row["file"]
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lang, href in HREFLANG.findall(text):
            path_url = href.replace("https://pepperoni.tatar", "").rstrip("/") or "/"
            if path_url in noindex:
                leaked.append(f"{row['url']} {lang} → {path_url}")
    check(not leaked, f"no indexable hreflang → noindex ({len(leaked)})")
    if leaked:
        for item in leaked[:12]:
            print("   ", item)

    sm = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
    sm_leaked = [
        href for href in re.findall(
            r'<xhtml:link[^>]+hreflang="[^"]+"[^>]+href="([^"]+)"', sm
        )
        if (href.replace("https://pepperoni.tatar", "").rstrip("/") or "/") in noindex
    ]
    check(not sm_leaked, f"sitemap has no hreflang → noindex ({len(sm_leaked)})")
    if sm_leaked:
        for item in sm_leaked[:12]:
            print("   ", item)

    # Policy helper: keep page drops noindex twin.
    filtered = filter_page_alternates(
        "https://pepperoni.tatar/en/export/kuwait",
        [
            ("ru", "https://pepperoni.tatar/export/kuwait"),
            ("ru-KW", "https://pepperoni.tatar/export/kuwait"),
            ("en", "https://pepperoni.tatar/en/export/kuwait"),
            ("x-default", "https://pepperoni.tatar/en/export/kuwait"),
        ],
    )
    hrefs = {href for _, href in filtered}
    check("https://pepperoni.tatar/export/kuwait" not in hrefs,
          "policy drops noindex RU from EN kuwait cluster")
    check("https://pepperoni.tatar/en/export/kuwait" in hrefs,
          "policy keeps EN self on kuwait")

    print(f"test_moq_hreflang: {'ok' if fail == 0 else f'{fail} FAIL'}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
