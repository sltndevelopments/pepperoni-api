#!/usr/bin/env python3
"""Inject one idempotent cross-link block into every sitemap page.

Why (audit 2026-10-15): money/segment pages (/pepperoni, /jerky, /pizzeria,
/en/sosiska-v-teste, /dlya-*) had <=1 internal inlink; kazandelikates.tatar
(brand site) was not referenced as such; pages without /assets/lead-form.js
sent no Metrika goals for phone/WhatsApp/e-mail clicks.

Blocks (cron-safe, rewritten in place after generators in sync-vps.sh):
  <!-- site-links:start --> … footer cross-links …
  <!-- company-footer:start --> … requisites from site_facts.json …
  <!-- localbusiness-ld:start --> … LocalBusiness JSON-LD in <head> …

No canonical or hreflang is touched. Usage: inject_site_links.py [--check]
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from organization_ld import LOCAL_SCRIPT, ORG_ID, ORGANIZATION, SCRIPT  # noqa: E402
from site_facts import FACTS, ROOT, phone_tel  # noqa: E402
from wholesale_nav import (  # noqa: E402
    WHOLESALE_END,
    WHOLESALE_START,
    wholesale_block,
)

PUBLIC = ROOT / "public"
START, END = "<!-- site-links:start -->", "<!-- site-links:end -->"
BLOCK_RX = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.S)
REQ_START, REQ_END = "<!-- company-footer:start -->", "<!-- company-footer:end -->"
REQ_RX = re.compile(re.escape(REQ_START) + r".*?" + re.escape(REQ_END) + r"\n?", re.S)
LB_START, LB_END = "<!-- localbusiness-ld:start -->", "<!-- localbusiness-ld:end -->"
LB_RX = re.compile(re.escape(LB_START) + r".*?" + re.escape(LB_END) + r"\n?", re.S)
ORG_START, ORG_END = "<!-- organization-ld:start -->", "<!-- organization-ld:end -->"
ORG_RX = re.compile(re.escape(ORG_START) + r".*?" + re.escape(ORG_END) + r"\n?", re.S)
WHOLESALE_RX = re.compile(
    re.escape(WHOLESALE_START) + r".*?" + re.escape(WHOLESALE_END) + r"\n?", re.S
)
ORG_MARKED = f"{ORG_START}{SCRIPT}{ORG_END}"
LD_RE = re.compile(
    r'(<script\s+type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)',
    re.I | re.S,
)
BRAND = FACTS["company"]["brand_site"]
_CO = FACTS["company"]
TEL = phone_tel()

LINKS = {
    "ru": [("/price", "Прайс-лист"), ("/kak-zakazat", "Как заказать"),
           ("/pepperoni", "Пепперони халяль оптом"), ("/pizzeria", "Для пиццерий"),
           ("/jerky", "Джерки под СТМ"), ("/sosiska-v-teste", "Сосиска в тесте"),
           ("/dlya-horeca", "HoReCa"), ("/dlya-azs", "АЗС"), ("/dlya-setey", "Сети"),
           ("/dlya-pekaren", "Пекарни"),
           ("/zamorozhennaya-vypechka-dlya-kofeen", "Выпечка для кофеен"),
           ("/dlya-distributorov", "Дистрибьюторам"),
           ("/chak-chak-optom", "Чак-чак оптом"),
           ("/halyal-vypechka-optom-dlya-pekaren", "Выпечка для пекарен"),
           ("/vyipechka-halyal", "Выпечка халяль"),
           ("/export", "Экспорт"),
           ("/kontraktnoe-proizvodstvo", "Контрактное производство (СТМ)")],
    "en": [("/en/price", "Price list"), ("/en/kak-zakazat", "How to order"),
           ("/en/pepperoni", "Halal pepperoni wholesale"), ("/en/pizzeria", "For pizzerias"),
           ("/en/jerky", "Private-label jerky"), ("/en/sosiska-v-teste", "Sausage rolls"),
           ("/en/dlya-horeca", "HoReCa"), ("/en/dlya-azs", "Fuel stations"),
           ("/en/dlya-setey", "Retail chains"),            ("/en/dlya-pekaren", "Bakeries"),
           ("/en/zamorozhennaya-vypechka-dlya-kofeen", "Bakery for coffee shops"),
           ("/en/dlya-distributorov", "Distributors"),
           ("/en/chak-chak-optom", "Chak-chak wholesale"),
           ("/en/halyal-vypechka-optom-dlya-pekaren", "Bakery for bakeries"),
           ("/en/vyipechka-halyal", "Halal bakery"),
           ("/en/export", "Export"),
           ("/en/private-label", "Private label")],
}
BRAND_TXT = {"ru": "Бренд-сайт компании", "en": "Company brand site"}
NAV_LABEL = {"ru": "Направления", "en": "Directions"}


def _types(node: dict) -> list[str]:
    kind = node.get("@type")
    if isinstance(kind, list):
        return [str(item) for item in kind]
    return [str(kind)] if kind else []


def top_level_jsonld_nodes(data) -> list[dict]:
    """Root objects of a JSON-LD document, including @graph members."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    graph = data.get("@graph")
    if isinstance(graph, list):
        return [item for item in graph if isinstance(item, dict)]
    return [data]


def top_level_organizations(html: str) -> list[dict]:
    found: list[dict] = []
    for raw in LD_RE.findall(html):
        try:
            data = json.loads(raw[1].strip())
        except (json.JSONDecodeError, IndexError, TypeError):
            continue
        for node in top_level_jsonld_nodes(data):
            if "Organization" in _types(node):
                found.append(node)
    return found


def _lone_organization(data) -> bool:
    """True when this JSON-LD document is only the shared Organization node."""
    if isinstance(data, dict):
        return (
            data.get("@id") == ORG_ID
            and "Organization" in _types(data)
            and not isinstance(data.get("@graph"), list)
        )
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        return data[0].get("@id") == ORG_ID and "Organization" in _types(data[0])
    return False


def merge_organization_credentials(html: str) -> tuple[str, bool]:
    """Fold hasCredential into one existing top-level #organization node.

    Extra lone Organization scripts with the same @id are removed so the page
    keeps a single top-level Organization. Returns whether such a node existed;
    callers must not inject organization_ld.SCRIPT when the flag is True.
    """
    hits: list[tuple[re.Match[str], object, list[dict]]] = []
    for match in LD_RE.finditer(html):
        try:
            data = json.loads(match.group(2).strip())
        except json.JSONDecodeError:
            continue
        nodes = [
            node for node in top_level_jsonld_nodes(data)
            if node.get("@id") == ORG_ID and "Organization" in _types(node)
        ]
        if nodes:
            hits.append((match, data, nodes))
    if not hits:
        return html, False

    def richness(item: tuple[re.Match[str], object, list[dict]]) -> int:
        return max(len(node.keys()) for node in item[2])

    keeper_match, keeper_data, keeper_nodes = max(hits, key=richness)
    creds = ORGANIZATION.get("hasCredential")
    for node in keeper_nodes:
        node["hasCredential"] = creds

    edits: list[tuple[int, int, str]] = []
    dumped = json.dumps(keeper_data, ensure_ascii=False, separators=(",", ":"))
    edits.append((
        keeper_match.start(),
        keeper_match.end(),
        f"{keeper_match.group(1)}{dumped}{keeper_match.group(3)}",
    ))
    for match, data, _nodes in hits:
        if match.start() == keeper_match.start():
            continue
        if _lone_organization(data):
            start, end = match.start(), match.end()
            if end < len(html) and html[end] == "\n":
                end += 1
            edits.append((start, end, ""))

    edits.sort(key=lambda item: item[0], reverse=True)
    out = html
    for start, end, repl in edits:
        out = out[:start] + repl + out[end:]
    return out, True


def url_to_file(path: str) -> Path | None:
    if path in ("/", ""):
        return PUBLIC / "index.html"
    if path == "/en/":
        return PUBLIC / "en" / "index.html"
    for c in (PUBLIC / (path.strip("/") + ".html"), PUBLIC / path.strip("/") / "index.html"):
        if c.is_file():
            return c
    return None


def block(path: str, html: str) -> str:
    lang = "en" if path.startswith("/en") else "ru"
    items = " · ".join(f'<a href="{h}">{t}</a>' for h, t in LINKS[lang] if h != path.rstrip("/"))
    brand = f'{BRAND_TXT[lang]}: <a href="{BRAND}" rel="noopener">kazandelikates.tatar</a>'
    goals = "" if "lead-form.js" in html else '\n<script src="/assets/lead-goals.js" defer></script>'
    return (f'{START}\n<nav class="site-links" aria-label="{NAV_LABEL[lang]}" '
            f'style="font-size:.85rem;line-height:1.7;padding:12px 16px;text-align:center">'
            f'{items}<br>{brand}</nav>{goals}\n{END}\n')


def requisites(path: str) -> str:
    lang = "en" if path.startswith("/en") else "ru"
    if lang == "ru":
        line = (
            f'{_CO["legal_name_ru"]} · ИНН {_CO["inn"]} · ОГРН {_CO["ogrn"]}<br>'
            f'{_CO["address_ru"]}<br>'
            f'<a href="{TEL}">{_CO["phone"]}</a> · '
            f'<a href="mailto:{_CO["email"]}">{_CO["email"]}</a> · '
            f'<a href="/price">Прайс</a> · <a href="/kak-zakazat">Как заказать</a>'
        )
    else:
        line = (
            f'{_CO["legal_name_en"]} · INN {_CO["inn"]} · OGRN {_CO["ogrn"]}<br>'
            f'{_CO["address_en"]}<br>'
            f'<a href="{TEL}">{_CO["phone"]}</a> · '
            f'<a href="mailto:{_CO["email"]}">{_CO["email"]}</a> · '
            f'<a href="/en/price">Price list</a> · '
            f'<a href="/en/kak-zakazat">How to order</a>'
        )
    return (
        f'{REQ_START}\n<div class="company-requisites" style="'
        f'font-size:.82rem;line-height:1.65;padding:14px 16px;text-align:center;'
        f'border-top:1px solid rgba(127,127,127,.25)">{line}</div>\n{REQ_END}\n'
    )


def main() -> int:
    check = "--check" in sys.argv
    sm = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
    paths = [re.sub(r"^https://pepperoni\.tatar", "", u) or "/" for u in re.findall(r"<loc>(.*?)</loc>", sm)]
    for extra in ("/en/price", "/en/kak-zakazat"):
        if extra not in paths:
            paths.append(extra)
    changed = missing = 0
    for path in paths:
        f = url_to_file(path)
        if not f:
            missing += 1
            continue
        html = f.read_text(encoding="utf-8")
        base = BLOCK_RX.sub("", html)
        base = REQ_RX.sub("", base)
        base = LB_RX.sub("", base)
        base = ORG_RX.sub("", base)
        base = WHOLESALE_RX.sub("", base)
        if "</head>" in base and LB_START not in base:
            base = base.replace("</head>", LOCAL_SCRIPT + "\n</head>", 1)
        base, has_org = merge_organization_credentials(base)
        if "</head>" in base and not has_org:
            base = base.replace("</head>", ORG_MARKED + "\n</head>", 1)
        lang = "en" if path.startswith("/en") else "ru"
        wants_wholesale = path.startswith(
            ("/blog/", "/en/blog/", "/products/", "/en/products/")
        ) or path in {"/blog", "/en/blog"}
        extra = wholesale_block(lang, path) if wants_wholesale else ""
        b = extra + block(path, base) + requisites(path)
        idx = base.rfind("</footer>")
        if idx < 0:
            idx = base.rfind("</body>")
        if idx < 0:
            continue
        new = base[:idx] + b + base[idx:]
        if new != html:
            changed += 1
            if not check:
                f.write_text(new, encoding="utf-8")
    print(f"site-links: {changed} page(s) {'need update' if check else 'updated'}, {missing} sitemap URL(s) without file")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
