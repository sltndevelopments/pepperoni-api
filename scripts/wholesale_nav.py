"""Shared «Оптовым покупателям» / wholesale-buyer link block.

Used by product and blog templates and by inject_site_links.py so money pages
(/price, /chak-chak-optom, bakery hubs, /kak-zakazat, /export/*) get inlinks
without inventing a second catalog.
"""
from __future__ import annotations

from html import escape

from build_index_manifest import EXPORT_COUNTRIES

WHOLESALE_START = "<!-- wholesale-buyers:start -->"
WHOLESALE_END = "<!-- wholesale-buyers:end -->"

_RU_CORE = [
    ("/price", "Прайс-лист"),
    ("/kak-zakazat", "Как заказать"),
    ("/chak-chak-optom", "Чак-чак оптом"),
    ("/halyal-vypechka-optom-dlya-pekaren", "Выпечка для пекарен"),
    ("/vyipechka-halyal", "Выпечка халяль"),
    ("/dlya-pekaren", "Пекарням"),
    ("/export", "Экспорт"),
]
_EN_CORE = [
    ("/en/price", "Price list"),
    ("/en/kak-zakazat", "How to order"),
    ("/en/chak-chak-optom", "Chak-chak wholesale"),
    ("/en/halyal-vypechka-optom-dlya-pekaren", "Bakery for bakeries"),
    ("/en/vyipechka-halyal", "Halal bakery"),
    ("/en/dlya-pekaren", "For bakeries"),
    ("/en/export", "Export"),
]


def _export_links(lang: str) -> list[tuple[str, str]]:
    prefix = "/export" if lang == "ru" else "/en/export"
    return [(f"{prefix}/{slug}", slug.replace("-", " ").title()) for slug, _ in EXPORT_COUNTRIES]


def wholesale_items(lang: str) -> list[tuple[str, str]]:
    core = _RU_CORE if lang == "ru" else _EN_CORE
    return [*core, *_export_links(lang)]


def brand_title_suffix(title: str, lang: str) -> str:
    """Append the brand suffix only when the result stays within 60 characters."""
    suffix = " | Казанские Деликатесы" if lang == "ru" else " | Kazan Delicacies"
    stem = title
    for extra in (" | Казанские Деликатесы", " | Kazan Delicacies",
                  " — Казанские Деликатесы", " — Kazan Delicacies"):
        if stem.endswith(extra):
            stem = stem[: -len(extra)]
    if any(name in stem for name in ("Казанские Деликатесы", "Kazan Delicacies")):
        return stem if len(stem) <= 60 else title
    candidate = stem + suffix
    return candidate if len(candidate) <= 60 else stem


def wholesale_block(lang: str, current: str = "") -> str:
    heading = "Оптовым покупателям" if lang == "ru" else "For wholesale buyers"
    items = []
    here = current.rstrip("/")
    for href, label in wholesale_items(lang):
        if href.rstrip("/") == here:
            continue
        items.append(f'<a href="{escape(href)}">{escape(label)}</a>')
    joined = " · ".join(items)
    style = (
        "font-size:.9rem;line-height:1.7;padding:16px 18px;margin:20px 0;"
        "background:#f7f6f2;border:1px solid #e6e4df;border-radius:14px"
    )
    return (
        f"{WHOLESALE_START}\n"
        f'<aside class="wholesale-buyers" aria-label="{escape(heading)}" style="{style}">'
        f"<strong>{escape(heading)}</strong><br>{joined}</aside>\n"
        f"{WHOLESALE_END}\n"
    )
