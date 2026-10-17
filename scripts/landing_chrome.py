"""Shared jerky/investors chrome for commercial landings.

Used by content_plan_pages.shell(), commercial_page.page(),
gen_category_pages.py and apply_landing_shell.py so future pages inherit
the same topbar + stylesheet without rewriting article text.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CSS_HREF = "/assets/kd-landing.css"
CSS_START = "<!-- kd-landing-css:start -->"
CSS_END = "<!-- kd-landing-css:end -->"
TOP_START = "<!-- kd-landing-topbar:start -->"
TOP_END = "<!-- kd-landing-topbar:end -->"

# Rel paths under public/ that this design system owns.
LANDINGS: list[tuple[str, str, str]] = [
    ("chak-chak-optom.html", "ru", "chak-chak-optom"),
    ("en/chak-chak-optom.html", "en", "chak-chak-optom"),
    ("halyal-vypechka-optom-dlya-pekaren.html", "ru", "halyal-vypechka-optom-dlya-pekaren"),
    ("en/halyal-vypechka-optom-dlya-pekaren.html", "en", "halyal-vypechka-optom-dlya-pekaren"),
    ("dlya-setey.html", "ru", "dlya-setey"),
    ("en/dlya-setey.html", "en", "dlya-setey"),
    ("dlya-distributorov.html", "ru", "dlya-distributorov"),
    ("en/dlya-distributorov.html", "en", "dlya-distributorov"),
    ("dlya-horeca.html", "ru", "dlya-horeca"),
    ("en/dlya-horeca.html", "en", "dlya-horeca"),
    ("sosiski-dlya-hotdog.html", "ru", "sosiski-dlya-hotdog"),
    ("en/sosiski-dlya-hotdog.html", "en", "sosiski-dlya-hotdog"),
    ("zamorozhennaya-vypechka-dlya-kofeen.html", "ru", "zamorozhennaya-vypechka-dlya-kofeen"),
    ("en/zamorozhennaya-vypechka-dlya-kofeen.html", "en", "zamorozhennaya-vypechka-dlya-kofeen"),
    ("export/uzbekistan.html", "ru", "export/uzbekistan"),
    ("en/export/uzbekistan.html", "en", "export/uzbekistan"),
    ("price.html", "ru", "price"),
    ("en/price.html", "en", "price"),
    ("kak-zakazat.html", "ru", "kak-zakazat"),
    ("en/kak-zakazat.html", "en", "kak-zakazat"),
    ("halal.html", "ru", "halal"),
    ("en/halal.html", "en", "halal"),
]


def stylesheet_link() -> str:
    return f'{CSS_START}<link rel="stylesheet" href="{CSS_HREF}">{CSS_END}'


def _home(lang: str) -> str:
    return "/" if lang == "ru" else "/en/"


def _href(lang: str, slug: str) -> str:
    slug = slug.lstrip("/")
    return f"/{slug}" if lang == "ru" else f"/en/{slug}"


def topbar_html(lang: str, slug: str, *, cta_href: str | None = None,
                bilingual: bool = True) -> str:
    home = _home(lang)
    here = _href(lang, slug)
    alt_lang = "en" if lang == "ru" else "ru"
    alt_href = _href(alt_lang, slug)
    if lang == "ru":
        links = [
            (home, "Каталог"),
            ("/kontraktnoe-proizvodstvo", "OEM"),
            ("/price", "Прайс"),
            ("/kak-zakazat", "Как заказать"),
            ("/delivery", "Доставка"),
            ("/about", "О компании"),
        ]
        lang_label = "Русский"
        alt_label = "English"
        cta = "Заявка"
        cta_href = cta_href or "/kak-zakazat"
        phone_label = "+7 987 217-02-02"
        nav_label = "Разделы"
        menu_label = "Меню"
    else:
        links = [
            (home, "Catalog"),
            ("/en/private-label", "Private Label"),
            ("/en/price", "Price list"),
            ("/en/kak-zakazat", "How to order"),
            ("/en/delivery", "Delivery"),
            ("/en/about", "About"),
        ]
        lang_label = "English"
        alt_label = "Русский"
        cta = "Enquire"
        cta_href = cta_href or "/en/kak-zakazat"
        phone_label = "+7 987 217-02-02"
        nav_label = "Sections"
        menu_label = "Menu"
    nav = "".join(
        f'<a href="{escape(href)}"'
        + (' aria-current="page"' if href == here else "")
        + f">{escape(label)}</a>"
        for href, label in links
    )
    langs = ""
    if bilingual:
        langs = (
            f'  <details class="kd-langs"><summary aria-label="Language">'
            f'<span aria-hidden="true">🌐</span> {lang_label}</summary>\n'
            f'    <div class="kd-langs__menu"><a href="{escape(here)}" aria-current="page">'
            f'{lang_label}</a><a href="{escape(alt_href)}">{alt_label}</a></div>\n'
            f'  </details>\n'
        )
    inner = (
        f'<header class="kd-topbar"><div class="kd-topbar__in">\n'
        f'  <a class="kd-brand" href="{home}">Kazan <span>Delicacies</span></a>\n'
        f'  <details class="kd-navwrap">\n'
        f'    <summary class="kd-navtoggle">{escape(menu_label)}</summary>\n'
        f'    <nav class="kd-topnav" aria-label="{nav_label}">{nav}</nav>\n'
        f'  </details>\n'
        f'  <div class="kd-topbar__spacer"></div>\n'
        f'  <a class="kd-topphone" href="tel:+79872170202">{phone_label}</a>\n'
        f'{langs}'
        f'  <a class="kd-btn kd-btn--primary" href="{escape(cta_href)}">{cta}</a>\n'
        f'</div></header>'
    )
    return f"{TOP_START}\n{inner}\n{TOP_END}"


_BODY_RE = re.compile(r"(<body\b)([^>]*)(>)", re.I)
_CLASS_DQ = re.compile(r'\bclass="([^"]*)"', re.I)
_CLASS_SQ = re.compile(r"\bclass='([^']*)'", re.I)
_MARKED_CSS = re.compile(
    re.escape(CSS_START) + r".*?" + re.escape(CSS_END), re.S
)
_MARKED_TOP = re.compile(
    re.escape(TOP_START) + r".*?" + re.escape(TOP_END), re.S
)


def _with_body_class(html: str) -> str:
    def repl(m: re.Match[str]) -> str:
        attrs = m.group(2)
        if re.search(r"\bkd-landing\b", attrs):
            return m.group(0)
        if _CLASS_DQ.search(attrs):
            attrs = _CLASS_DQ.sub(lambda x: f'class="kd-landing {x.group(1).strip()}"', attrs, count=1)
        elif _CLASS_SQ.search(attrs):
            attrs = _CLASS_SQ.sub(lambda x: f"class='kd-landing {x.group(1).strip()}'", attrs, count=1)
        else:
            attrs = attrs + ' class="kd-landing"'
        return f"{m.group(1)}{attrs}{m.group(3)}"

    out, n = _BODY_RE.subn(repl, html, count=1)
    if n != 1:
        raise SystemExit("landing_chrome: <body> not found")
    return out


def apply_chrome(html: str, lang: str, slug: str) -> str:
    """Idempotent: add stylesheet, body class and topbar. Does not rewrite article."""
    link = stylesheet_link()
    top = topbar_html(lang, slug)
    if _MARKED_CSS.search(html):
        html = _MARKED_CSS.sub(link, html)
    else:
        if "</head>" not in html.lower():
            raise SystemExit("landing_chrome: </head> missing")
        html = re.sub(
            r"</head>",
            link + "\n</head>",
            html,
            count=1,
            flags=re.I,
        )
    html = _with_body_class(html)
    if _MARKED_TOP.search(html):
        html = _MARKED_TOP.sub(top, html)
    else:
        gtm = re.search(
            r"(<!-- Google Tag Manager \(noscript\) -->.*?</noscript>\s*"
            r"<!-- End Google Tag Manager \(noscript\) -->)",
            html,
            re.S | re.I,
        )
        if gtm:
            insert_at = gtm.end()
            html = html[:insert_at] + "\n" + top + html[insert_at:]
        else:
            m = _BODY_RE.search(html)
            if not m:
                raise SystemExit("landing_chrome: cannot place topbar")
            html = html[: m.end()] + "\n" + top + html[m.end():]
    return html


def apply_file(rel: str, lang: str, slug: str) -> bool:
    path = PUBLIC / rel
    before = path.read_text(encoding="utf-8")
    after = apply_chrome(before, lang, slug)
    if after == before:
        return False
    path.write_text(after, encoding="utf-8")
    return True
