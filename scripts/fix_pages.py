#!/usr/bin/env python3
"""Deterministic page repairer (no LLM) — fixes legacy generation defects
found by qa_pages.py across public/:

  • invented phones (+7-800-555-35-35, +7 (843) 203-03-39, 8-800-…)
      → +7 987 217-02-02 / tel:+79872170202 / wa.me link kept intact
  • invented emails (info@pepperoni.tatar, <city>@pepperoni.tatar, …)
      → info@kazandelikates.tatar
  • markdown fences (```/```html) left in HTML
  • LLM preamble remnants («Вот HTML-код …») before/inside markup
  • «ГОСТ Р 51705.1…» claims → «ХАССП (HACCP)» (we certify HACCP/ISO 22000,
    not GOST; the GOST number is the LLM's invention)
  • Arabic mistranslation: «لحم الخنزير» (pork!) in product/anchor names
      → «اللحم البقري المدخن» (smoked beef) — critical for Gulf markets

Idempotent. Run: fix_pages.py [--all | path…]; default = git-changed pages.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"

GOOD_DISPLAY = "+7 987 217-02-02"
GOOD_TEL = "+79872170202"
GOOD_EMAIL = "info@kazandelikates.tatar"

TEL_HREF_RE = re.compile(r"tel:\+?[\d\-‑–\s().]{7,18}")
PHONE_TEXT_RE = re.compile(r"(?:\+7|8)[\s\-‑–()]*\d(?:[\s\-‑–()]*\d){9}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]*[a-zA-Z][\w-]*\.[a-zA-Z][\w.]{1,11}")
FENCE_RE = re.compile(r"[ \t]*```[a-zA-Z]*[ \t]*\n?")
# LLM preamble: bare text before the first tag, e.g. «Вот HTML-код лендинга,
# созданный … климат)». Eats up to the next tag, capped so real content is safe.
PREAMBLE_RE = re.compile(
    r"(?:Конечно[,!]?\s*)?Вот\s+(?:HTML|готовый|код)[^<>{}]{0,600}(?=<)", re.I)
GOST_RE = re.compile(r"ГОСТ\s?Р?\s?51705(?:\.1)?(?:-\d{4})?")
# «соответствие ГОСТ N» — выдуманный клейм; меняем на обязательный по закону
# техрегламент ЕАЭС на мясную продукцию (истинно для любой легальной продукции).
GOST_CLAIM_RE = re.compile(r"(соответств\w+|сертифицирован\w*)\s+ГОСТ\s*Р?\s*[\d.\-]+", re.I)
GOST_BADGE_RE = re.compile(r">\s*ГОСТ\s*Р?\s*\d[\d.\-]*\s*<")
# Arabic mistranslations: «лحم خنزير» (свинина!) вместо ветчины/бекона.
AR_HAM_RE = re.compile(r"لحم خنزير حلال|لحم الخنزير الحلال")
AR_SUB_RE = re.compile(r"لحم خنزير بديل")
AR_PORK_RE = re.compile(r"لحم الخنزير المدخن|لحم الخنزير|لحم خنزير")
KOSHER_RE = re.compile(r"кошерно для мусульман", re.I)


def fix_html(html: str) -> tuple[str, list[str]]:
    fixes = []

    def sub(rx, repl, label, s):
        new, n = rx.subn(repl, s)
        if n:
            fixes.append(f"{label} ×{n}")
        return new

    # Phones: any tel: or visible +7/8-pattern whose digits differ from ours.
    def tel_repl(m):
        digits = re.sub(r"\D", "", m.group(0))
        if digits.endswith(GOOD_TEL[1:]):
            return m.group(0)
        fixes.append(f"tel: {m.group(0)[:24]}")
        return f"tel:{GOOD_TEL}"

    def phone_repl(m):
        digits = re.sub(r"\D", "", m.group(0))
        norm = "7" + digits[1:] if digits.startswith("8") else digits
        if norm == GOOD_TEL[1:]:
            return m.group(0)
        fixes.append(f"phone: {m.group(0)[:24]}")
        return GOOD_DISPLAY

    def email_repl(m):
        e = m.group(0)
        core, tail = e.rstrip("."), e[len(e.rstrip(".")):]
        if core.lower() == GOOD_EMAIL or "@" not in core:
            return e
        fixes.append(f"email: {core[:40]}")
        return GOOD_EMAIL + tail

    html = TEL_HREF_RE.sub(tel_repl, html)
    html = PHONE_TEXT_RE.sub(phone_repl, html)
    html = EMAIL_RE.sub(email_repl, html)
    html = sub(FENCE_RE, "", "fence", html)
    html = sub(PREAMBLE_RE, "", "llm-preamble", html)
    html = sub(GOST_RE, "ХАССП (HACCP)", "gost", html)
    html = sub(GOST_CLAIM_RE, r"\1 ТР ТС 034/2013", "gost-claim", html)
    html = sub(GOST_BADGE_RE, ">ТР ТС 034/2013<", "gost-badge", html)
    html = sub(AR_HAM_RE, "جامبون بقري حلال", "ar-ham", html)
    html = sub(AR_SUB_RE, "بدائل حلال", "ar-substitute", html)
    html = sub(AR_PORK_RE, "اللحم البقري المدخن", "ar-pork", html)
    html = sub(KOSHER_RE, "халяль для мусульман", "kosher-copy", html)
    # Collapse doubled HACCP from «ХАССП (ХАССП (HACCP))» if template already had it
    html = html.replace("ХАССП (ХАССП (HACCP))", "ХАССП (HACCP)")
    # Truncated generation (old max_tokens cap): close the document so crawlers
    # get valid HTML. Real regeneration is queued for the strategy worker.
    if "<html" in html.lower() and "</html>" not in html.lower():
        html = html.rstrip() + "\n</div>\n</section>\n</body>\n</html>\n"
        fixes.append("closed-truncated")
    return html, fixes


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all" in sys.argv:
        files = sorted(PUBLIC.rglob("*.html"))
    elif args:
        files = []
        for a in args:
            p = Path(a) if Path(a).is_absolute() else ROOT / a
            files += sorted(p.rglob("*.html")) if p.is_dir() else [p]
    else:
        sys.path.insert(0, str(Path(__file__).parent))
        from qa_pages import changed_pages
        # changed_pages() returns list[tuple[Path, is_new]] — unwrap to just
        # the paths. This mismatch previously crashed with AttributeError
        # ('tuple' object has no attribute 'read_text') on every default
        # (no-args) run; only --all / explicit-path invocations worked.
        files = [p for p, _is_new in changed_pages()]

    touched = 0
    for f in files:
        try:
            html = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new, fixes = fix_html(html)
        if fixes:
            f.write_text(new, encoding="utf-8")
            touched += 1
            if touched <= 30:
                print(f"  {f.relative_to(ROOT)}: {', '.join(fixes[:4])}")
    print(f"✅ fix_pages: {len(files)} scanned, {touched} repaired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
