#!/usr/bin/env python3
"""#kd-hero-critical spacing must match kd-landing.css, not hardcoded numbers.

Breadcrumb, eyebrow and container margin/padding/line-height/max-width are
read from the shared sheet and required in the inline critical CSS so a late
kd-landing.css cannot move the H1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PUBLIC = ROOT / "public"
sys.path.insert(0, str(SCRIPTS))

from landing_chrome import HERO_CRITICAL_CSS, LCP_RENDER_SLUGS  # noqa: E402

SHEET = (PUBLIC / "assets" / "kd-landing.css").read_text(encoding="utf-8")

fail = 0
HUBS = (
    "sosiski-dlya-hotdog.html",
    "en/sosiski-dlya-hotdog.html",
    "kotlety-dlya-burgerov.html",
    "sosiski-halyal-optom.html",
)


def check(cond: bool, msg: str) -> None:
    global fail
    if cond:
        print("  ok ", msg)
    else:
        fail += 1
        print("  FAIL", msg)


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def strip_at_rules(css: str) -> str:
    out = []
    i = 0
    while i < len(css):
        if css.startswith("@", i):
            brace = css.find("{", i)
            if brace == -1:
                break
            depth = 1
            j = brace + 1
            while j < len(css) and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            i = j
            continue
        out.append(css[i])
        i += 1
    return "".join(out)


def split_rules(css: str) -> list[tuple[str, str]]:
    """Return (selector, body) for non-nested rules."""
    out = []
    for match in re.finditer(r"([^{}@][^{}]*)\{([^{}]*)\}", css):
        sel = re.sub(r"\s+", " ", match.group(1)).strip()
        if sel:
            out.append((sel, match.group(2)))
    return out


def decls(body: str) -> dict[str, str]:
    found = {}
    for part in body.split(";"):
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        found[prop.strip().lower()] = compact(value.strip())
    return found


def media_inner(css: str, query: str) -> str:
    match = re.search(
        rf"@media\s*\(\s*{re.escape(query)}\s*\)\s*\{{",
        css,
        re.I,
    )
    if not match:
        return ""
    start = match.end()
    depth = 1
    i = start
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return css[start : i - 1]


def sel_match(part: str, want: str) -> bool:
    if part == want:
        return True
    return part.endswith(want)


def rule_for(rules: list[tuple[str, str]], needle: str) -> dict[str, str]:
    want = compact(needle)
    merged: dict[str, str] = {}
    for sel, body in rules:
        for part in (compact(item) for item in sel.split(",")):
            if sel_match(part, want):
                merged.update(decls(body))
                break
    return merged


def require_props(sheet_decls: dict[str, str], critical: str, props: list[str], label: str) -> None:
    crit = compact(critical)
    for prop in props:
        value = sheet_decls.get(prop)
        check(bool(value), f"kd-landing.css has {label} {prop}")
        if not value:
            continue
        token = f"{prop}:{value}"
        check(token in crit, f"critical CSS matches {label} {prop} ({value})")


def main() -> int:
    sheet = strip_comments(SHEET)
    sheet_rules = split_rules(strip_at_rules(sheet))
    # Drop @media contents from the top-level walk by parsing the full sheet
    # then overlaying the 560px block separately.
    media560 = media_inner(sheet, "max-width: 560px")
    if not media560:
        media560 = media_inner(sheet, "max-width:560px")
    media_rules = split_rules(media560)

    container = rule_for(sheet_rules, "body.kd-landing .container")
    crumb = rule_for(sheet_rules, "nav:not(.kd-topnav):not(.site-links):not(.kd-langs)")
    eyebrow = rule_for(sheet_rules, ".eyebrow")
    hero = rule_for(sheet_rules, "body.kd-landing .hero")
    h1 = rule_for(sheet_rules, "body.kd-landing h1")
    p = rule_for(sheet_rules, "body.kd-landing p")
    container_sm = rule_for(media_rules, "body.kd-landing .container")
    h1_sm = rule_for(media_rules, "body.kd-landing h1")
    topbar_in = rule_for(sheet_rules, ".kd-topbar__in")

    body_decls = rule_for(sheet_rules, "body.kd-landing")

    crit = HERO_CRITICAL_CSS
    require_props(container, crit, ["max-width", "margin", "padding"], "container")
    require_props(crumb, crit, ["font-size", "margin-bottom"], "breadcrumb nav")
    require_props(eyebrow, crit, ["font-size", "max-width"], "eyebrow")
    require_props(hero, crit, ["padding"], "hero")
    require_props(h1, crit, ["font-size", "margin", "line-height"], "h1")
    require_props(p, crit, ["margin-bottom"], "paragraph")
    require_props(container_sm, crit, ["padding"], "container@560px")
    require_props(h1_sm, crit, ["font-size"], "h1@560px")
    if "line-height" in body_decls:
        require_props({"line-height": body_decls["line-height"]}, crit, ["line-height"], "body")
    require_props(topbar_in, crit, ["padding", "min-height", "gap"], "topbar inner")

    check(".lede" in crit and ".hero-subtitle" in crit and ".hero__sub" in crit,
          "critical eyebrow group includes lede/hero-subtitle/hero__sub")

    check(LCP_RENDER_SLUGS == {
        "sosiski-dlya-hotdog",
        "kotlety-dlya-burgerov",
        "sosiski-halyal-optom",
    }, "critical CSS applies to the four hub slugs")
    for rel in HUBS:
        html = (PUBLIC / rel).read_text(encoding="utf-8")
        head = html.split("</head>", 1)[0]
        match = re.search(r'<style id="kd-hero-critical">(.*?)</style>', head, re.I | re.S)
        check(bool(match), f"{rel} inlines #kd-hero-critical")
        if not match:
            continue
        inline = match.group(1)
        require_props(container, inline, ["padding", "max-width", "margin"], f"{rel} container")
        require_props(crumb, inline, ["margin-bottom", "font-size"], f"{rel} breadcrumb")
        require_props(eyebrow, inline, ["font-size", "max-width"], f"{rel} eyebrow")
        require_props(container_sm, inline, ["padding"], f"{rel} container@560px")

    if fail:
        print(f"test_hub_critical_css: {fail} FAIL")
        return 1
    print("test_hub_critical_css: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
