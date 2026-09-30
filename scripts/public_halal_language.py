"""Shared public-surface swine gate.

Customer-facing text (Sheets cells, catalog JSON, HTML) may not contain
swine-family wording, including negations. The only rewrite allowed at ingest
is the known English nickname Pigs-in-Blankets → Sausage Rolls. Anything that
still matches after that alias is rejected — never paraphrased.
"""
from __future__ import annotations

import re
from typing import Any

# Order matters: longer phrase first.
SHEET_ALIASES: tuple[tuple[str, str], ...] = (
    ("Pigs-in-Blankets", "Sausage Rolls"),
    ("Pigs-in-Blanket", "Sausage Roll"),
    ("pigs-in-blankets", "sausage rolls"),
    ("pigs-in-blanket", "sausage roll"),
)

# Cyrillic boundaries: ASCII \\b does not treat Cyrillic as a word char.
UNSAFE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"свин(?!ц)", re.I),
    re.compile(r"шпик", re.I),
    re.compile(r"(?<![а-яё])сало(?![а-яё])", re.I),
    re.compile(r"pork", re.I),
    re.compile(r"\bporcine\b", re.I),
    re.compile(r"\bpigs?\b", re.I),
    re.compile(r"\bswine\b", re.I),
    re.compile(r"\bhogs?\b", re.I),
    re.compile(r"\blard\b", re.I),
    re.compile(r"\bfatback\b", re.I),
    re.compile(r"خنزير"),
)

SHEET_TEXT_FIELDS: tuple[str, ...] = (
    "name",
    "category",
    "seoDescriptionRU",
    "seoDescriptionEN",
    "ingredientsRU",
    "ingredientsEN",
    "cookingMethods",
    "nutrition",
    "packageType",
    "casing",
)


def apply_sheet_aliases(text: str) -> str:
    if not text:
        return text
    out = text
    for src, dst in SHEET_ALIASES:
        out = out.replace(src, dst)
    return out


def first_unsafe_hit(text: str) -> str | None:
    if not text:
        return None
    for rx in UNSAFE_PATTERNS:
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


def accept_sheet_public_text(text: Any) -> tuple[str | None, str | None]:
    """Return (publishable, None) or (None, hit). Empty string is publishable."""
    if text is None:
        return "", None
    raw = text if isinstance(text, str) else str(text)
    rewritten = apply_sheet_aliases(raw)
    hit = first_unsafe_hit(rewritten)
    if hit:
        return None, hit
    return rewritten, None


def load_previous_by_sku(products_json: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not products_json:
        return out
    for p in products_json.get("products") or []:
        sku = (p or {}).get("sku")
        if sku:
            out[sku] = p
    return out


def scrub_sheet_products(
    products: list[dict[str, Any]],
    previous_by_sku: dict[str, dict[str, Any]] | None = None,
    log=print,
) -> list[dict[str, Any]]:
    """Drop or revert sheet cells that stay unsafe after the known alias."""
    prev_map = previous_by_sku or {}
    kept: list[dict[str, Any]] = []
    rejected = 0
    for p in products:
        sku = p.get("sku") or "?"
        prev = prev_map.get(p.get("sku") or "") or {}
        skip = False
        for field in SHEET_TEXT_FIELDS:
            raw = p.get(field)
            if raw is None or raw == "":
                continue
            value, hit = accept_sheet_public_text(raw)
            if hit is None:
                p[field] = value
                continue
            rejected += 1
            fb, fb_hit = accept_sheet_public_text(prev.get(field)) if prev.get(field) else (None, "empty")
            if fb is not None and fb != "" and fb_hit is None:
                p[field] = fb
                log(f"     ⛔ {sku} {field}: sheet «{hit}» — kept previous clean cell")
                continue
            if field == "name":
                if prev.get("name"):
                    log(f"     ⛔ {sku} name: sheet «{hit}» — kept previous product snapshot")
                    kept.append(dict(prev))
                    skip = True
                    break
                log(f"     ⛔ {sku} name: sheet «{hit}» — no previous name, skip product")
                skip = True
                break
            p.pop(field, None)
            log(f"     ⛔ {sku} {field}: sheet «{hit}» — dropped, no clean fallback")
        if not skip:
            kept.append(p)
    if rejected:
        log(f"  ⛔ Sheet public-language: {rejected} unsafe cell(s) rejected")
    return kept
