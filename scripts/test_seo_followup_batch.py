#!/usr/bin/env python3
"""Gates for the post-#58 follow-up batch."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html_of(rel: str) -> str:
    return (PUBLIC / rel).read_text(encoding="utf-8")


def title_of(rel: str) -> str:
    return re.search(r"<title>(.*?)</title>", html_of(rel), re.I | re.S).group(1)


def main() -> int:
    ru = html_of("sosiski-halyal-optom.html")
    check('class="cards"' in ru and 'class="card"' in ru, "sosiski lower part uses jerks cards")
    check('id="dlya-kogo"' in ru and 'id="dokumenty"' in ru, "sosiski audience/docs are card sections")
    check('id="preimushestva"' in ru, "sosiski features are a card section")
    check("<ul>" not in ru.split('id="dlya-kogo"', 1)[-1].split('id="assortiment"', 1)[0]
          or 'class="card"' in ru.split('id="dlya-kogo"', 1)[-1].split('id="assortiment"', 1)[0],
          "audience block is cards, not a lone list")
    check("есть</td>" not in ru, "Формат column is not the casing yes-field")
    gen_src = (SCRIPTS / "gen_category_pages.py").read_text(encoding="utf-8")
    fmt_fn = gen_src[gen_src.find("def _table_format"):gen_src.find("def _sku_table")]
    check("seoDescription" not in fmt_fn, "_table_format does not read SEO text")
    check("6 × 80 г" not in ru and "5 × 130 г" not in ru,
          "Формат does not take pack size from SEO text")
    for sku in ("KD-017", "KD-019", "KD-021"):
        row = re.search(rf"<tr>\s*<td><a[^>]*>{sku}</a></td>.*?</tr>", ru, re.S)
        check(row is not None, f"{sku} row exists in sosiski table")
        if row:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(0), re.S)
            fmt = re.sub(r"<[^>]+>", "", cells[2]).strip() if len(cells) > 2 else ""
            check(fmt == "—", f"{sku} Формат is — when pack math ≠ weight (got {fmt!r})")

    src = (SCRIPTS / "check_fact_consistency.py").read_text(encoding="utf-8")
    check("seoDescriptionRU" in src and "seoDescriptionEN" in src,
          "shelf-life check covers SEO text for all SKUs")
    check("дней" in src and "SHELF_UNIT" in src,
          "shelf-life regex includes дней")
    check('r"не можем постав")' not in src and "не можем постав[^.\\n]{0,140}" in src,
          "cannot-supply ban is scoped to UZ/AZ/Cerberus")
    ban_block = src[src.find("UNAVAILABLE_EXPORT"):src.find("LOCALE_SKIP")]
    check(ban_block.count("re.compile(") >= 8
          and ban_block.count("re.compile(") == ban_block.count("re.I"),
          "RU unavailable-export bans are case-insensitive")

    burg = html_of("en/blog/burger-patties-wholesale-halal.html")
    article = None
    for raw in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', burg, re.I | re.S
    ):
        try:
            node = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(node, dict) and node.get("@type") == "Article":
            article = node
            break
    check(article is not None, "burger blog has Article JSON-LD")
    if article:
        for key in ("author", "publisher"):
            val = article.get(key) or {}
            check(
                set(val.keys()) == {"@id"}
                and val.get("@id") == "https://pepperoni.tatar/#organization",
                f"burger Article {key} is @id only",
            )
    check(len(re.findall(r'"@type"\s*:\s*"Organization"', burg)) == 1,
          "burger blog has one Organization object")

    moq_src = (SCRIPTS / "check_wholesale_moq.py").read_text(encoding="utf-8")
    check("PACK_WEIGHT" in moq_src and "</(?:li|p|tr" in moq_src,
          "MOQ check distinguishes pack weight / list items")
    sys.path.insert(0, str(SCRIPTS))
    import check_wholesale_moq as moq
    gfc = html_of("cases/gfc.html")
    check(moq.scan(PUBLIC / "cases/gfc.html") == [],
          "/cases/gfc pack weight 0,5 кг is not a MOQ hit")
    check(any("0,5" in s or "0.5" in s for s in [gfc]), "gfc still mentions 0,5 кг pack")
    # Concatenate so this test file is not itself a MOQ-scanner hit.
    moq_pack = moq.scan_text("<p>" + "Минимальный заказ — " + "упаковка 100 кг" + "</p>")
    check(len(moq_pack) >= 1,
          "MOQ «упаковка 100 кг» still fails (not stripped as pack weight)")

    kaz_title = title_of("kazylyk.html")
    check("казылык" in kaz_title.lower() and "опт" in kaz_title.lower(),
          "kazylyk title keeps query + wholesale")
    check("что это" in kaz_title.lower() or "купить" in kaz_title.lower(),
          "kazylyk title targets что это / купить")
    check("₽" not in kaz_title and not re.search(r"\d{2,}", kaz_title),
          "kazylyk title has no price")
    check(len(kaz_title) <= 60, f"kazylyk title ≤60 ({len(kaz_title)})")
    kaz_desc = re.search(r'<meta name="description" content="([^"]*)"', html_of("kazylyk.html")).group(1)
    check("что это" in kaz_desc.lower() and "₽" not in kaz_desc,
          "kazylyk meta has что это and no ruble price")

    pep_title = title_of("pepperoni.html")
    check("купить" in pep_title.lower() and "колбаса" in pep_title.lower(),
          "/pepperoni title is commercial (купить / колбаса)")
    check("что это" not in pep_title.lower(),
          "/pepperoni title leaves «что это» to the blog")
    check("₽" not in pep_title, "/pepperoni title has no price")
    what = title_of("blog/what-is-halal-pepperoni.html")
    meat = title_of("blog/pepperoni-iz-kakogo-myasa.html")
    check(what != pep_title, "what-is-halal-pepperoni title differs from /pepperoni")
    check("что такое" in what.lower() and "халяль-пепперони" in what.lower()
          and "из чего" in what.lower(),
          "what-is-halal-pepperoni title is informational")
    check("из какого" in meat.lower() or "из чего" in meat.lower(),
          "pepperoni-iz-kakogo-myasa title CTR")

    chicken = PUBLIC / "blog/kuritsa-halyal-chem-otlichaetsya.html"
    check(chicken.is_file(), "chicken guide HTML restored")
    ch = chicken.read_text(encoding="utf-8")
    check("index, follow" in ch and "ДУМ РТ" in ch, "chicken guide is indexable and factual")
    check("Минимальный заказ — 1 паллета" in ch, "chicken guide has canonical MOQ")
    check(ch.count('"@type":"Organization"') + ch.count('"@type": "Organization"') == 1,
          "chicken guide has one Organization node")
    check("/halal" in ch and "/products" in ch, "chicken guide links hubs")
    check("аккредитованн" in ch and "убойн" in ch,
          "chicken raw meat from accredited slaughterhouses")
    check(re.search(r"производств\w*.{0,80}сертифицир", ch, re.I)
          and "0008" in ch and ("614А/2024" in ch or "614A/2024" in ch),
          "chicken plant production certified 0008 / 614А/2024")
    check(not re.search(
        r"забое?н?\w*.{0,80}заводе в Казани|заводе в Казани.{0,80}забое",
        ch, re.I,
    ), "chicken does not claim slaughter at the Kazan plant")
    check(not re.search(
        r"забое?н?\w*.{0,80}подтвержда.{0,60}сертификат|"
        r"сертификат.{0,40}подтвержда.{0,40}забое",
        ch, re.I,
    ), "chicken plant certs do not confirm slaughter")

    gone = (ROOT / "deploy/nginx/trust-reset-gone.conf").read_text(encoding="utf-8")
    check("kuritsa-halyal-chem-otlichaetsya" not in gone,
          "chicken guide is not 410 in nginx")
    redir = (ROOT / "deploy/nginx/pepperoni-blog-redirects.conf").read_text(encoding="utf-8")
    check("postavki-myasa-restorany-horeca" in redir and "dlya-horeca" in redir,
          "HoReCa meat-supply URL 301s to /dlya-horeca")
    check(not (PUBLIC / "blog/postavki-myasa-restorany-horeca.html").exists(),
          "retired HoReCa blog HTML stays gone")

    man = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    keep = {r["url"]: r for r in man["entries"] if r.get("status") == "keep"}
    check("/blog/kuritsa-halyal-chem-otlichaetsya" in keep, "chicken guide is keep")
    check("/export/kuwait" not in keep, "kuwait dropped from keep (0 impressions)")
    check("/en/export/kuwait" in keep, "EN kuwait still keep")
    check("/export/bahrain" not in keep, "bahrain stays noindex")
    check(len(keep) == 250, f"keep count stays 250 (got {len(keep)})")

    kw = html_of("export/kuwait.html")
    check(re.search(r'name="robots"[^>]*content="noindex', kw, re.I),
          "/export/kuwait is noindex")

    print(f"test_seo_followup_batch: {'ok' if fail == 0 else f'{fail} FAIL'}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
