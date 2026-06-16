#!/usr/bin/env python3
"""Deterministic QA gate for generated HTML pages (no LLM, free, fast).

Runs in the pipeline BEFORE git commit. Checks every new/modified page in
public/ for brand-critical defects that an LLM can hallucinate:

  • halal violations: pork/свинина/سجق الخنزير, lard, bacon, alcohol
  • invented contacts: 8-800 numbers, phones other than +7 987 217-02-02,
    emails other than info@kazandelikates.tatar
  • broken generation: markdown fences, unclosed </html>, missing <title>,
    lorem ipsum, leftover prompt text
  • invented certifications (GOST numbers, kosher/USDA we don't hold)

Modes:
  qa_pages.py                  — check git-changed *.html in public/
  qa_pages.py --all            — check the whole public/ tree
  qa_pages.py path [path…]     — check specific files/dirs
  qa_pages.py --quarantine     — move FAILed files to data/quarantine/ and
                                 notify Telegram, exit 0 (pipeline continues
                                 with clean pages only). Without the flag the
                                 script exits 1 on any FAIL (CI gate).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"
QUARANTINE = ROOT / "data" / "quarantine"

GOOD_PHONE = "79872170202"
GOOD_EMAIL = "info@kazandelikates.tatar"

# (compiled regex, label). Checked against visible text + attributes.
# NB: «бекон» сам по себе НЕ запрещён — говяжий/куриный халяль-бекон есть в
# ассортименте (топпинги). Запрещён только свиной.
FORBIDDEN = [
    (re.compile(r"свинин|шпик\b|\bсало\b|свино[йг]", re.I), "халяль: свинина/сало (RU)"),
    (re.compile(r"\bpork\b|\blard\b|fatback", re.I), "halal: pork/lard (EN)"),
    (re.compile(r"خنزير"), "halal: لحم خنزير (AR)"),
    (re.compile(r"\bалкогол|\bвин[оа]\b|\bпив[оа]\b|\balcohol\b|\bwine\b|\bbeer\b", re.I),
     "халяль: алкоголь"),
    (re.compile(r"8[\s(‑-]?800"), "выдуманный номер 8-800"),
    (re.compile(r"```"), "markdown-фенс в HTML"),
    (re.compile(r"lorem ipsum", re.I), "lorem ipsum"),
    # Claim-контекст: «соответствие/сертифицирован по ГОСТ N» — выдумка LLM
    # (мы заявляем ХАССП, ISO 22000, халяль ДУМ РТ). Просто упоминание
    # отраслевого ГОСТа в обзорной статье — допустимо.
    (re.compile(r"(соответств\w+|сертифицирован\w*|по)\s+ГОСТ\s*Р?\s*\d", re.I),
     "выдуманный номер ГОСТ"),
    (re.compile(r"\bkosher\b|\bкошер|\bUSDA\b", re.I), "чужая сертификация"),
    (re.compile(r"(?:Вот|Конечно|Here is|Certainly)[,!]? (?:HTML|готов|the page)", re.I),
     "остаток ответа LLM в странице"),
]

PHONE_RE = re.compile(r"(?:\+7|%2B7|tel:\+?7)[\s\-‑–()]*(\d[\s\-‑–()]*){10}")

# Search-engine verification stubs — не страницы, проверять нечего.
SKIP_RE = re.compile(r"(?:^|/)(?:yandex_?[0-9a-f]+|google[0-9a-f]+|[0-9a-f]{16})\.html$")
# Domain must contain a letter — отсекает bootstrap@5.3.0 и прочие CDN-пути.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]*[a-zA-Z][\w-]*\.[a-zA-Z][\w.]+")
# Emails that may legitimately appear besides ours (none today).
EMAIL_ALLOW = {GOOD_EMAIL}

# «без алкоголя», «не содержит свинины», «классическое пепперони — из свинины,
# а наше — из говядины» — легитимные халяль-клеймы и образовательные сравнения.
NEGATION_RE = re.compile(
    r"без|не содерж|не использ|не должно|не допуск|недопустим|не могут?|нет\b"
    r"|ноль|никак|исключ|отсутств|запрещ|не явля|не кошерн|вместо|в отличие"
    r"|замен|разн|альтернатив|классическ|традиционн|обычн|говядин|есть ли"
    r"|не ед|не куша|не употр|принципиально|мусульман|халяльн|вер[ау]ющ"
    r"|\bno\b|zero|free|without|absence|exclu|prohibit|forbidden|unacceptable"
    r"|must not|not allowed|instead|unlike|classic|traditional|beef|haram"
    r"|харам|tidak|\?|بدون|خالية|بقر|محظور|يحرم|لا\s",
    re.I)

# Labels where surrounding negation makes the mention legitimate
# («без свинины», «не кошерный», «никаких 8-800»).
NEGATABLE = ("халяль", "halal", "чужая сертификация", "выдуманный номер 8-800")


def _negated(html: str, start: int, end: int) -> bool:
    return bool(NEGATION_RE.search(html[max(0, start - 250):end + 140]))


MIN_WORDS = 250          # new page must have at least this many visible words
NEAR_DUP_UNIQUE = 40    # after stripping city/product tokens, must have this many unique words

# Product card pages are intentionally compact — never flag as thin.
_CARD_RE = re.compile(r"[/\\]products[/\\]kd-\d+\.html$")
# Geo-page paths that the brain generates — apply thin/dup gate to these.
_GEO_PATH_RE = re.compile(r"[/\\](?:geo|en[/\\]geo|ar[/\\]geo|kk[/\\]geo|uz[/\\]geo)[/\\]")


def _visible_words(html: str) -> int:
    """Count words in text visible to a user (strips tags, scripts, styles)."""
    # Remove <script>, <style>, <head> blocks entirely.
    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html,
                     flags=re.I | re.S)
    # Strip remaining tags.
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Normalise whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned)
    return len([w for w in cleaned.split() if len(w) > 1])


def _near_duplicate(html: str, path: Path) -> bool:
    """True if the page content is almost entirely boilerplate.

    Heuristic: strip common city/country/product names (pulled from the slug),
    then count unique words left in the visible body. If too few, it's a
    template with only the city swapped in.
    """
    # Extract slug tokens from path (e.g. "pepperoni-halyalniy-kazan" → {"pepperoni","halyalniy","kazan"})
    slug_tokens = set(re.split(r"[-_]", path.stem.lower())) - {"html", ""}

    cleaned = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", " ", html,
                     flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    words = [w.lower() for w in re.split(r"\W+", cleaned) if len(w) > 3]
    unique = {w for w in words if w not in slug_tokens}
    return len(unique) < NEAR_DUP_UNIQUE


def check_file(path: Path, is_new: bool = False) -> list[str]:
    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"unreadable: {e}"]
    errs = []
    for rx, label in FORBIDDEN:
        for m in rx.finditer(html):
            if label.startswith(NEGATABLE) and _negated(html, m.start(), m.end()):
                continue
            errs.append(f"{label}: «…{html[max(0, m.start()-30):m.end()+30].strip()}…»")
            break
    for m in PHONE_RE.finditer(html):
        digits = re.sub(r"\D", "", m.group(0))[-11:]
        if digits and digits != GOOD_PHONE:
            errs.append(f"чужой телефон: {m.group(0).strip()[:30]}")
    for m in EMAIL_RE.finditer(html):
        e = m.group(0).lower().rstrip(".")
        # skip schema.org URLs etc. (no @ in them) and known-good
        if e not in EMAIL_ALLOW and not e.endswith((".png", ".jpg", ".webp")):
            errs.append(f"чужой email: {e}")
    if "<title" not in html.lower():
        errs.append("нет <title>")
    if "</html>" not in html.lower():
        errs.append("нет </html> — страница обрезана")

    # ── Value gate — only for genuinely NEW pages, never for product cards ──
    # Applied only when is_new=True AND the path looks like a generated geo/blog page.
    # Skips product cards (kd-*.html) and all existing pages being merely modified.
    if is_new and not _CARD_RE.search(str(path)):
        wc = _visible_words(html)
        if wc < MIN_WORDS:
            errs.append(f"тонкая страница: {wc} слов < {MIN_WORDS}")
        elif _GEO_PATH_RE.search(str(path)) and _near_duplicate(html, path):
            errs.append(f"шаблон-дубликат: слишком мало уникального контента")

    return errs


def changed_pages() -> list[tuple[Path, bool]]:
    """New/modified *.html under public/ according to git.

    Returns list of (path, is_new) where is_new=True means the file is
    git-untracked or staged as Added ('??' or 'A' status) — i.e. a brand-new
    page that hasn't been published before. Modified existing pages get False.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", "public"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=60).stdout
    except Exception:
        return []
    files = []
    for line in out.splitlines():
        st = line[:2]
        rel = line[3:].strip().strip('"')
        if "D" in st:
            continue
        if not rel.endswith(".html"):
            continue
        p = ROOT / rel
        if not p.exists():
            continue
        # '??' = untracked (new file not yet staged), 'A' = staged as Added
        is_new = st.strip() in ("??", "A") or st[0] == "A" or st[1] == "A"
        files.append((p, is_new))
    return files


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quarantine = "--quarantine" in sys.argv
    # --new-only: apply thin/dup gate to all files (useful for testing)
    force_new = "--new-only" in sys.argv

    # Build list of (path, is_new) tuples.
    if "--all" in sys.argv:
        # --all checks everything but never marks as is_new (don't mass-quarantine existing).
        pairs: list[tuple[Path, bool]] = [(f, False) for f in sorted(PUBLIC.rglob("*.html"))]
    elif args:
        pairs = []
        for a in args:
            p = Path(a) if Path(a).is_absolute() else ROOT / a
            fs = sorted(p.rglob("*.html")) if p.is_dir() else [p]
            pairs += [(f, force_new) for f in fs]
    else:
        pairs = changed_pages()

    if not pairs:
        print("qa_pages: nothing to check")
        return 0

    failed: dict[Path, list[str]] = {}
    for f, is_new in pairs:
        if SKIP_RE.search(str(f)):
            continue
        errs = check_file(f, is_new=is_new)
        if errs:
            failed[f] = errs

    print(f"qa_pages: {len(files)} checked, {len(failed)} FAIL")
    for f, errs in failed.items():
        rel = f.relative_to(ROOT)
        for e in errs:
            print(f"  ✗ {rel}: {e}")

    if failed and quarantine:
        QUARANTINE.mkdir(parents=True, exist_ok=True)
        for f in failed:
            dest = QUARANTINE / f.relative_to(PUBLIC)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
        print(f"  → {len(failed)} page(s) moved to data/quarantine/")
        try:
            import daily_ledger
            halal_violations = [
                (f, e) for f, errs in failed.items() for e in errs
                if any(kw in e.lower() for kw in ("халяль", "halal", "свинина", "pork", "алкогол"))
            ]
            if halal_violations:
                lines = ["🚨 БРЕНД/ХАЛЯЛЬ нарушение в QA:"]
                for f, e in halal_violations[:3]:
                    lines.append(f"• {f.relative_to(PUBLIC)}: {e[:80]}")
                daily_ledger.append_event("emergency", "\n".join(lines))
            else:
                lines = [f"QA карантин: {len(failed)} стр."]
                for f, errs in list(failed.items())[:4]:
                    lines.append(f"• {f.relative_to(PUBLIC)}: {errs[0][:80]}")
                daily_ledger.append_event("done", "\n".join(lines))
        except Exception:
            pass
        return 0

    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.exit(main())
