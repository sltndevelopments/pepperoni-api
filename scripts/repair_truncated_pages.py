#!/usr/bin/env python3
"""
Repair geo HTML pages truncated by the old bulk generator (missing </html>).

Scans public/**/geo/*.html and appends closing tags via ensure_complete_html()
without calling Claude API.

Usage:
  python3 scripts/repair_truncated_pages.py --dry-run
  python3 scripts/repair_truncated_pages.py
  python3 scripts/repair_truncated_pages.py --limit 100
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"

# Copied from scripts/generate_geo_bulk.py (origin/main) — avoids import issues on
# older Python / PEP604 type hints in the generator module.
_FALLBACK_FOOTER = (
    '\n<footer class="py-4 mt-5" style="background:#1f3b2c;color:#fff">'
    '<div class="container">'
    '<p class="mb-1">Казанские деликатесы (Pepperoni Tatar) — производство халяльной '
    'мясной продукции и татарской выпечки в Казани.</p>'
    '<p class="small mb-0">'
    '<a href="https://pepperoni.tatar/" style="color:#fff">pepperoni.tatar</a> · '
    'info@kazandelikates.tatar · +7 987 217-02-02</p>'
    '</div></footer>\n'
)

CONFLICT_MARKERS = ("<<<<<<<", ">>>>>>>")


def ensure_complete_html(html: str) -> str:
    """Guarantee the page is structurally closed."""
    html = html.rstrip()

    has_body_open = "<body" in html.lower()
    has_body_close = "</body>" in html.lower()
    has_html_close = "</html>" in html.lower()

    if has_body_close and has_html_close:
        return html

    lines = html.split("\n")
    if lines:
        last = lines[-1]
        opens = last.count("<")
        closes = last.count(">")
        if opens > closes:
            lines = lines[:-1]
            html = "\n".join(lines).rstrip()

    if has_body_open and not has_body_close:
        if "<main" in html.lower() and "</main>" not in html.lower():
            html += "\n</main>"
        if "</footer>" not in html.lower():
            html += _FALLBACK_FOOTER
        html += "\n</body>"

    if not has_html_close:
        html += "\n</html>"

    return html + "\n"


def has_conflict_markers(text: str) -> bool:
    return any(m in text for m in CONFLICT_MARKERS)


def is_complete(text: str) -> bool:
    return "</html>" in text.lower()


def iter_geo_html_files() -> list[Path]:
    files: list[Path] = []
    if not PUBLIC.is_dir():
        return files
    for path in sorted(PUBLIC.rglob("*.html")):
        if path.parent.name == "geo":
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair truncated geo HTML pages")
    parser.add_argument("--dry-run", action="store_true", help="Count only, do not write")
    parser.add_argument("--limit", type=int, default=0, help="Max files to repair (0 = all)")
    args = parser.parse_args()

    files = iter_geo_html_files()
    scanned = 0
    skipped_ok = 0
    repaired = 0
    manual_review: list[str] = []
    errors: list[str] = []

    for path in files:
        scanned += 1
        if scanned % 500 == 0:
            print(f"  … scanned {scanned} files (repaired {repaired}, manual {len(manual_review)})")

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"{path}: read error: {exc}")
            continue

        if has_conflict_markers(text):
            manual_review.append(str(path.relative_to(ROOT)))
            continue

        if is_complete(text):
            skipped_ok += 1
            continue

        if args.limit and repaired >= args.limit:
            break

        fixed = ensure_complete_html(text)
        if fixed == text:
            # Still incomplete after repair — shouldn't happen, but flag it
            manual_review.append(str(path.relative_to(ROOT)))
            continue

        repaired += 1
        if not args.dry_run:
            path.write_text(fixed, encoding="utf-8")

    print()
    print("=" * 60)
    print("Geo page repair summary")
    print("=" * 60)
    print(f"  Scanned:        {scanned}")
    print(f"  Already OK:     {skipped_ok}")
    print(f"  Repaired:       {repaired}{' (dry-run)' if args.dry_run else ''}")
    print(f"  Manual review:  {len(manual_review)}")
    if errors:
        print(f"  Errors:         {len(errors)}")

    if manual_review:
        print("\nManual review (conflict markers or unrepaired):")
        for p in manual_review[:30]:
            print(f"  - {p}")
        if len(manual_review) > 30:
            print(f"  … and {len(manual_review) - 30} more")

    if errors:
        print("\nErrors:")
        for e in errors[:10]:
            print(f"  - {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
