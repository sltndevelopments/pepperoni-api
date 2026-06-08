#!/usr/bin/env python3
"""Post-process DeepSeek override files to enforce halal/factual rules.

DeepSeek occasionally adds (a) redundant "no pork / no alcohol" phrasing that the
user explicitly forbade (halal already implies it), and (b) invented certification
numbers (specific GOST standards) we cannot verify. This cleaner:

  • removes whole <p>/sentence fragments that assert "no pork", "no alcohol",
    "no pork fat/gelatin", etc. (sentence-level so grammar stays intact)
  • strips invented "ГОСТ Р NNNNN-YYYY" / "GOST" references, keeping the sentence
    but removing the fabricated number, or dropping the clause if it is only about
    the standard
  • leaves storage percentages (humidity/shelf life) intact — those are factual

Idempotent. Run after gen_sku_deep.py, before regenerating product pages.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "product_overrides"

# Sentence-ending split that keeps the delimiter out; works for RU/EN.
_SENT = re.compile(r"[^.!?；;]*[.!?；;]")

# A sentence is dropped entirely if it matches any of these (it exists only to
# assert the forbidden/redundant claim).
DROP_SENTENCE = re.compile(
    r"(свинин|свин(ого|ой|ому|ым)\s+жир|свиного\s+белка|"
    r"\bpork\b|\balcohol|\bбекон|\bсало\b|\blard\b)",
    re.I,
)

# Invented standards: remove the specific number; if the whole sentence is just
# about the standard, drop it.
GOST_NUM = re.compile(r"\s*(ГОСТ\s*Р?\s*[\d.\u2013\u2014-]+(?:-\d{4})?|GOST\s*R?\s*[\d.\u2013\u2014-]+)", re.I)


def clean_text_node(text: str) -> str:
    """Operate on visible text between tags."""
    if not DROP_SENTENCE.search(text) and not GOST_NUM.search(text):
        return text
    out = []
    pos = 0
    for m in _SENT.finditer(text):
        sent = m.group(0)
        pos = m.end()
        if DROP_SENTENCE.search(sent):
            continue  # drop the whole sentence
        had_gost = bool(GOST_NUM.search(sent))
        sent = GOST_NUM.sub("", sent)
        if had_gost:
            # Tidy dangling clauses left after removing the standard number.
            sent = re.sub(r"по\s+стандарт(ам|у)\s+(с\s+)", r"\2", sent, flags=re.I)
            sent = re.sub(r"по\s+стандарт(ам|у)\s*[.,]", ".", sent, flags=re.I)
            sent = re.sub(r"(certified|made|produced)\s+(to|under|according to)\s+(,|\.|with)", r"\1 \3", sent, flags=re.I)
        out.append(sent)
    tail = text[pos:]
    if tail and not DROP_SENTENCE.search(tail):
        out.append(GOST_NUM.sub("", tail))
    cleaned = "".join(out)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    return cleaned


def clean_html(html: str) -> str:
    # Walk text nodes only (outside tags), preserving markup.
    parts = re.split(r"(<[^>]+>)", html)
    for i, part in enumerate(parts):
        if part.startswith("<"):
            continue
        parts[i] = clean_text_node(part)
    out = "".join(parts)
    # Remove now-empty paragraphs.
    out = re.sub(r"<p[^>]*>\s*</p>", "", out)
    out = re.sub(r"<div class=\"section-block\">\s*(<h2[^>]*>.*?</h2>)?\s*</div>", "", out, flags=re.S)
    return out


def main() -> int:
    files = sorted(OUT.glob("*.html"))
    changed = 0
    for f in files:
        html = f.read_text(encoding="utf-8")
        cleaned = clean_html(html)
        if cleaned != html:
            f.write_text(cleaned, encoding="utf-8")
            changed += 1
            print(f"  cleaned {f.name}")
    print(f"\nDONE cleaned {changed}/{len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
