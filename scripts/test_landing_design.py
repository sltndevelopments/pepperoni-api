#!/usr/bin/env python3
"""Gates for the shared kd-landing design system on listed commercial pages."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from landing_chrome import LANDINGS, apply_chrome, stylesheet_link, topbar_html  # noqa: E402

fail = 0


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def html_of(rel: str) -> str:
    return (ROOT / "public" / rel).read_text(encoding="utf-8")


def core_facts(html: str) -> dict:
    """Title, robots, canonical, JSON-LD — chrome must not change these."""
    title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    desc = re.search(r'<meta name="description" content="([^"]*)"', html, re.I)
    robots = re.search(r'<meta name="robots" content="([^"]*)"', html, re.I)
    canon = re.search(r'<link rel="canonical" href="([^"]*)"', html, re.I)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    lds = []
    for blob in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S | re.I
    ):
        try:
            lds.append(json.loads(blob))
        except json.JSONDecodeError:
            lds.append(blob.strip())
    return {
        "title": title.group(1).strip() if title else "",
        "desc": desc.group(1) if desc else "",
        "robots": robots.group(1) if robots else "",
        "canonical": canon.group(1) if canon else "",
        "h1": re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else "",
        "ld": lds,
    }


def git_show(rel: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:public/{rel}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def main() -> int:
    css = (ROOT / "public" / "assets" / "kd-landing.css").read_text(encoding="utf-8")
    check("--brand:#16723c" in css.replace(" ", "") or "--brand: #16723c" in css,
          "shared CSS has jerky brand token")
    check(".kd-topbar" in css and "backdrop-filter" in css, "shared CSS has sticky topbar")
    check("body.kd-landing" in css and "body.kd-landing h1" in css,
          "shared CSS scopes overrides to .kd-landing")

    from content_plan_pages import shell  # noqa: E402
    sample = shell("ru", "demo-slug", "T", "D", "H1", "<p>body</p>",
                   [("Q?", "A.")])
    check("/assets/kd-landing.css" in sample, "content_plan shell links shared CSS")
    check('class="kd-landing"' in sample, "content_plan shell sets body class")
    check("kd-topbar" in sample, "content_plan shell emits topbar")

    from commercial_page import page as wrap  # noqa: E402
    comm = wrap(lang="ru", title="T", description="D",
                canonical="https://pepperoni.tatar/price",
                hreflang_ru="https://pepperoni.tatar/price",
                hreflang_en="https://pepperoni.tatar/en/price",
                nav_html="<nav></nav>", body="<h1>Прайс</h1>", slug="price")
    check("/assets/kd-landing.css" in comm and "kd-topbar" in comm,
          "commercial_page inherits shared chrome")

    src = (ROOT / "scripts" / "gen_category_pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in src and "topbar_html(" in src,
          "gen_category_pages uses shared chrome")

    check(len(LANDINGS) == 22, f"22 listed landings (got {len(LANDINGS)})")

    for rel, lang, slug in LANDINGS:
        html = html_of(rel)
        check("/assets/kd-landing.css" in html, f"{rel} links shared CSS")
        check("kd-landing" in html and "kd-topbar" in html, f"{rel} has chrome")
        check(html.count("<h1") == html.lower().count("<h1"), f"{rel} h1 well-formed")
        h1n = len(re.findall(r"<h1\b", html, re.I))
        check(h1n == 1, f"{rel} still one H1 ({h1n})")
        again = apply_chrome(html, lang, slug)
        check(again == apply_chrome(again, lang, slug), f"{rel} apply is idempotent")
        old = git_show(rel)
        if old is None:
            check(False, f"{rel} exists in HEAD for fact compare")
            continue
        check(core_facts(old) == core_facts(html),
              f"{rel} title/desc/robots/canonical/h1/JSON-LD unchanged")

    # Chrome helpers stay fact-free
    bar = topbar_html("ru", "price")
    check("tel:+79872170202" in bar and "info@" not in bar.split("tel:")[0],
          "topbar uses canonical phone")
    check('class="kd-navwrap"' in bar and 'class="kd-navtoggle"' in bar,
          "topbar has details/summary hamburger")
    check('href="/delivery"' in bar and 'href="/about"' in bar,
          "RU topbar has Доставка and О компании")
    en_bar = topbar_html("en", "price")
    check('href="/en/delivery"' in en_bar and 'href="/en/about"' in en_bar,
          "EN topbar has Delivery and About")
    check('class="kd-langs"' in bar and 'href="/en/price"' in bar,
          "RU topbar has language switch to EN")
    check('class="kd-langs"' in en_bar and 'href="/price"' in en_bar,
          "EN topbar has language switch to RU")
    compact = css.replace(" ", "").replace("\n", "")
    check(".kd-topnav--wide" in css and ".kd-navwrap{display:none;}" in compact,
          "desktop CSS shows wide nav and hides the hamburger")
    check(".kd-topnav--wide{display:none;}" in compact
          and ".kd-navwrap{display:block;" in compact,
          "CSS shows hamburger panel under 900px instead of hiding nav")
    check(stylesheet_link().startswith("<!-- kd-landing-css:start -->"),
          "stylesheet marker present")

    uz_src = (ROOT / "scripts" / "content_plan_pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in uz_src and 'topbar_html(lang, "export/uzbekistan")' in uz_src,
          "write_uzbekistan emits shared chrome")
    exp_src = (ROOT / "scripts" / "gen_export_pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in exp_src and "topbar_html(" in exp_src,
          "gen_export_pages emit shared chrome")
    geo_src = (ROOT / "scripts" / "gen-geo-pages.py").read_text(encoding="utf-8")
    check("stylesheet_link()" in geo_src and "topbar_html(" in geo_src,
          "gen-geo-pages emit shared chrome")

    def no_html_git_add(rel: str) -> None:
        text = (ROOT / rel).read_text(encoding="utf-8")
        active = "\n".join(
            line for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        hits = [line.strip() for line in active.splitlines()
                if "git add" in line and ".html" in line]
        check(not hits, f"{rel} does not git-add generated HTML")

    no_html_git_add("scripts/seo-agent-vps.sh")
    no_html_git_add(".github/workflows/seo-agent.yml")

    former = {
        "price.html": ["/", "/kak-zakazat", "/delivery", "/about", "/en/price"],
        "kak-zakazat.html": ["/", "/price", "/delivery", "/about", "/en/kak-zakazat"],
        "en/price.html": ["/en/", "/en/kak-zakazat", "/en/delivery", "/en/about", "/price"],
        "en/kak-zakazat.html": ["/en/", "/en/price", "/en/delivery", "/en/about", "/kak-zakazat"],
    }
    for rel, hrefs in former.items():
        page = html_of(rel)
        missing = [h for h in hrefs if f'href="{h}"' not in page]
        check(not missing, f"{rel} keeps former nav links {hrefs}")

    if fail:
        print(f"test_landing_design: {fail} FAIL")
        return 1
    print("test_landing_design: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
