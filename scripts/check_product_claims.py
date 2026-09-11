#!/usr/bin/env python3
"""Fail when a public surface describes a pepperoni we do not make.

Source of truth: products.json. The pepperoni SKUs are read from it and the set
of meats they contain is derived from names + ingredient lists (today: chicken).
Every surface an agent or buyer reads — AI manifests, llms files, OpenAPI,
feeds, price lists, and the indexed HTML pages (title, meta description,
JSON-LD strings, visible text) — is scanned for phrases that attach another
meat or another curing method to "pepperoni":

    beef pepperoni · horse-meat pepperoni · dry-cured pepperoni
    говяжья пепперони · пепперони из говядины / конины · сырокопчёный пепперони
    пепперони: говядина, конина …  (list after a colon)

Classes:
  FAIL     assortment claim — first-person / catalog context ("supplying",
           "в ассортименте", "производим", "наш"), or any hit inside <title>,
           meta description, JSON-LD or a machine surface.
  CUSTOM   the same words inside a private-label / custom-order sentence.
           Capability, not catalog — listed for the owner to confirm.
  GENERIC  body-text statement about pepperoni as a product class ("pepperoni
           is traditionally made from beef") with no first-person marker.
           Listed; does not fail. Blog editors decide.

Exit 1 on any FAIL. Runs in sync-vps.sh after the generators.
  python3 scripts/check_product_claims.py [--all-html] [--quiet]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

MACHINE_SURFACES = [
    "public/.well-known/ai-plugin.json", "public/ai.json", "public/openapi.yaml",
    "public/llms.txt", "public/llms-full.txt", "public/en/llms.txt", "public/en/llms-full.txt",
    "public/.well-known/llms.txt", "public/sitemap-llms.xml",
    "public/wholesale-price-list.txt", "public/wholesale-price-list-ru.txt",
    "public/wholesale-price-list.md", "public/wholesale-price-list-ru.md",
    "public/brand.txt", "mcp/create-server.js",
]

MEATS = {
    "beef": r"beef|говя\w*",
    "lamb": r"lamb|mutton|баран\w*",
    "horse": r"horse(?:[- ]?meat)?|конин\w*|конск\w*",
    "turkey": r"turkey|индей\w*|индюш\w*",
    "chicken": r"chicken|poultry|кур\w*|птиц\w*|цыпл\w*",
    "pork": r"pork|свин\w*",
    "dry-cured": r"dry[- ]cured|сырокопч\w*|сыровял\w*",
}
MEAT_ANY = "|".join(f"(?P<{k.replace('-', '_')}>{v})" for k, v in MEATS.items())
PEPP = r"(?:пепперон\w*|pepperoni)"

# Tight attachment patterns: the meat must qualify *pepperoni*, not merely share a sentence.
ATTACH = [
    re.compile(rf"\b(?:{MEAT_ANY})\s+(?:halal\s+|халяль\w*\s+)?{PEPP}", re.I),              # beef pepperoni / говяжья пепперони
    re.compile(rf"{PEPP}\s+(?:made\s+)?(?:from|of|with)\s+(?P<list>[^.;!?\n]{{0,80}})", re.I),  # pepperoni from beef and chicken
    re.compile(rf"{PEPP}[^.;!?\n]{{0,50}}?\b(?:из|с)\s+(?P<list>[^.;!?\n]{{0,80}})", re.I),      # пепперони из говядины и из конины
    re.compile(rf"{PEPP}\s*[:—-]\s*(?P<list>[^.;!?\n]{{0,80}})", re.I),                          # пепперони: говядина, курица
    re.compile(rf"{PEPP}[^.;!?\n]{{0,40}}?(?:производ\w+|делают|made)\s+(?:из|from)\s+(?P<list>[^.;!?\n]{{0,80}})", re.I),
]
FIRST_PERSON = re.compile(r"\b(мы|наш\w*|производим|выпускаем|поставляем|предлагаем|ассортимент\w*|каталог\w*|"
                          r"we|our|supply\w*|offer\w*|catalog\w*|assortment|in stock|available)\b", re.I)
CUSTOM_CTX = re.compile(r"стм|private[- ]label|white[- ]label|под заказ|под ваш\w* бренд|custom|кастомиз|"
                        r"по (?:индивидуальн|запрос)|контрактн|contract manufactur|по согласован|индивидуальн|"
                        r"гибк\w* рецептур|recipe", re.I)
NEGATED_PORK = re.compile(r"(?:без|no|zero|free|not|не содерж\w*|никак\w*|исключ\w*|вместо|instead of)[^.]{0,25}(?:свин\w*|pork)|"
                          r"(?:свин\w*|pork)[- ]?(?:free|нет|не использ\w*|исключ\w*)", re.I)
CONVENTIONAL = re.compile(r"обычн\w* (?:американск\w* )?пепперони|традиционн\w*|классическ\w* американск|conventional|"
                          r"traditional(?:ly)?|american pepperoni|в сша|in the us", re.I)
URLISH = re.compile(r"https?://\S+|pepperoni\.tatar|kazandelikates\.tatar|/pepperoni\S*", re.I)


def catalog_pepperoni_meats() -> tuple[set[str], list[str]]:
    data = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    skus, meats = [], set()
    for p in data["products"]:
        if not re.search(PEPP, p["name"], re.I):
            continue
        skus.append(p["sku"])
        text = " ".join(str(p.get(k) or "") for k in ("name", "ingredients", "ingredientsRU", "ingredientsEN")).lower()
        for meat, rx in MEATS.items():
            if meat != "pork" and re.search(rx, text):
                meats.add(meat)
    return meats, skus


def meats_in(text: str) -> set[str]:
    found = set()
    for m in re.finditer(MEAT_ANY, text, re.I):
        found.add(m.lastgroup.replace("_", "-"))
    return found


def hits_in(sentence: str, allowed: set[str]) -> set[str]:
    s = URLISH.sub(" ", sentence)
    if not re.search(PEPP, s, re.I) or CONVENTIONAL.search(s) or s.rstrip().endswith("?"):
        return set()
    found = set()
    for rx in ATTACH:
        for m in rx.finditer(s):
            chunk = m.group("list") if "list" in m.groupdict() and m.group("list") else m.group(0)
            found |= meats_in(chunk)
    found -= allowed
    if "pork" in found and NEGATED_PORK.search(s):
        found.discard("pork")
    return found


def split_sentences(text: str):
    for sent in re.split(r"(?<=[.!?…])\s+|\n+", text):
        sent = sent.strip()
        if sent:
            yield sent


def jsonld_strings(html_src: str):
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html_src, re.S | re.I):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, str):
                yield cur


def body_text(html_src: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_src, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(s)


def scan_html(path: Path, allowed: set[str], results: dict):
    src = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(ROOT))
    strict = []
    m = re.search(r"<title>(.*?)</title>", src, re.S | re.I)
    if m:
        strict.append(("title", html.unescape(m.group(1))))
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', src, re.I)
    if m:
        strict.append(("meta", html.unescape(m.group(1))))
    strict += [("json-ld", s) for s in jsonld_strings(src)]
    for where, text in strict:
        for sent in split_sentences(text):
            h = hits_in(sent, allowed)
            if h:
                results["FAIL"].append((rel, where, sorted(h), sent[:200]))
    prev = ""
    for sent in split_sentences(body_text(src)):
        ctx, prev = prev + " " + sent, sent
        h = hits_in(sent, allowed)
        if not h:
            continue
        if "pork" in h:
            results["FAIL"].append((rel, "text", sorted(h), sent[:200]))
        elif CUSTOM_CTX.search(ctx):
            results["CUSTOM"].append((rel, "text", sorted(h), sent[:200]))
        elif FIRST_PERSON.search(sent):
            results["FAIL"].append((rel, "text", sorted(h), sent[:200]))
        else:
            results["GENERIC"].append((rel, "text", sorted(h), sent[:200]))


def scan_machine(path: Path, allowed: set[str], results: dict):
    text = path.read_text(encoding="utf-8", errors="replace").replace("\\n", "\n")
    rel = str(path.relative_to(ROOT))
    prev = ""
    for sent in split_sentences(text):
        ctx, prev = prev + " " + sent, sent
        if re.search(r"e\.g\.|например|for example", sent, re.I):
            continue
        h = hits_in(sent, allowed)
        if not h:
            continue
        if "pork" not in h and CUSTOM_CTX.search(ctx):
            results["CUSTOM"].append((rel, "machine", sorted(h), sent[:200]))
        else:
            results["FAIL"].append((rel, "machine", sorted(h), sent[:200]))


def keep_html_pages() -> list[Path]:
    manifest = json.loads((ROOT / "data" / "index_manifest.json").read_text(encoding="utf-8"))
    return [PUBLIC / e["file"] for e in manifest["entries"]
            if e.get("status") == "keep" and e.get("file") and (PUBLIC / e["file"]).exists()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-html", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print only FAIL lines and the summary")
    ns = ap.parse_args()

    allowed, skus = catalog_pepperoni_meats()
    print(f"catalog pepperoni: {', '.join(skus)} → meats {sorted(allowed) or '∅'}; other meats / curing attached to pepperoni = violation")

    results = {"FAIL": [], "CUSTOM": [], "GENERIC": []}
    machine = [ROOT / r for r in MACHINE_SURFACES if (ROOT / r).exists()]
    for p in machine:
        scan_machine(p, allowed, results)
    pages = sorted(PUBLIC.rglob("*.html")) if ns.all_html else keep_html_pages()
    pages = [p for p in pages if "/geo/" not in str(p) and not p.name.endswith(".bak")]
    for p in pages:
        scan_html(p, allowed, results)

    for kind in ("GENERIC", "CUSTOM", "FAIL"):
        if ns.quiet and kind != "FAIL":
            continue
        for rel, where, h, sent in results[kind]:
            print(f"{kind:<8}{rel} [{where}: {', '.join(h)}] {sent}")
    print(f"product claims: {len(pages)} pages + {len(machine)} machine surfaces → "
          f"{len(results['FAIL'])} FAIL, {len(results['CUSTOM'])} CUSTOM (owner to confirm), "
          f"{len(results['GENERIC'])} GENERIC (blog class statements)")
    return 1 if results["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
