#!/usr/bin/env python3
"""
LINKER — internal-linking agent (meta-agent item C).

Internal links are the cheapest, safest ranking lever: they spread authority and
help crawlers/LLMs understand topical clusters. This agent builds a semantic graph
across blog ↔ landing ↔ OEM pages (by shared title/keyword/slug tokens) and injects
an idempotent "Читайте также" block of the most relevant cross-page links.

Design choices (static site, no embeddings/runtime):
- Topic profile per page = weighted tokens from <title> + <meta keywords> + slug.
- Similarity = weighted token overlap (Jaccard-ish), boosted for CROSS-section
  links (blog→commercial and commercial→blog) because that's where SEO value flows.
- Injection is IDEMPOTENT: a single <section data-linker="1"> before </body>.
  Re-running replaces that block, never stacks duplicates, never touches the rest.
- Safe by default: skips pages without </body>, with conflict markers, or empty.

Usage:
  python3 scripts/link_graph.py --dry-run         # report only, no writes
  python3 scripts/link_graph.py                    # apply (idempotent)
  python3 scripts/link_graph.py --max-links 5 --min-score 2.0
  python3 scripts/link_graph.py --sections blog,oem,landing
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from html import escape
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"

# Sections we cross-link (path under public/, public URL prefix, weight).
SECTIONS = {
    "blog":    {"dir": PUBLIC / "blog",    "prefix": "/blog/",    "commercial": False},
    "oem":     {"dir": PUBLIC / "oem",     "prefix": "/oem/",     "commercial": True},
    "landing": {"dir": PUBLIC / "landing", "prefix": "/landing/", "commercial": True},
}

LINKER_MARKER = 'data-linker="1"'

# Russian stopwords + structural noise we never want as topic tokens.
STOP = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще",
    "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
    "если", "уже", "или", "ни", "быть", "был", "для", "это", "этот", "эта",
    "как", "чем", "под", "над", "при", "про", "без", "до", "оптом", "опт",
    "купить", "цена", "цены", "руб", "kg", "the", "and", "for", "with", "of",
    "to", "in", "a", "халяль", "халяльный", "халяльная", "халяльное",
    "pepperoni", "tatar", "казанские", "деликатесы", "казань",
}

MIN_TOKEN_LEN = 3


def tokens(text: str) -> set[str]:
    text = re.sub(r"[^a-zA-Zа-яёА-ЯЁ0-9\s-]", " ", (text or "").lower())
    out = set()
    for w in re.split(r"[\s\-]+", text):
        w = w.strip()
        if len(w) >= MIN_TOKEN_LEN and w not in STOP and not w.isdigit():
            out.add(w)
    return out


# ---------------------------------------------------------------- page model

class Page:
    __slots__ = ("file", "section", "url", "title", "toks", "commercial")

    def __init__(self, file: Path, section: str, url: str, title: str,
                 toks: set, commercial: bool):
        self.file = file
        self.section = section
        self.url = url
        self.title = title
        self.toks = toks
        self.commercial = commercial


def _extract_title(html: str, fallback: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    t = (m.group(1).strip() if m else "").split("|")[0].strip()
    # title often "X — Y | Brand"; keep the leading clause, trim brand tails
    t = re.sub(r"\s*[—-]\s*pepperoni.*$", "", t, flags=re.I).strip()
    return t or fallback


def _extract_keywords(html: str) -> str:
    m = re.search(r'<meta\s+name="keywords"\s+content="(.*?)"', html, re.I | re.S)
    return m.group(1) if m else ""


def load_pages(sections: list[str]) -> list[Page]:
    pages = []
    for sec in sections:
        cfg = SECTIONS[sec]
        d: Path = cfg["dir"]
        if not d.exists():
            continue
        for f in sorted(d.glob("*.html")):
            html = f.read_text(encoding="utf-8", errors="ignore")
            if "</body>" not in html.lower():
                continue
            if any(m in html for m in ("<<<<<<<", ">>>>>>>")):
                continue
            slug = f.stem
            title = _extract_title(html, slug.replace("-", " ").title())
            kw = _extract_keywords(html)
            toks = tokens(title) | tokens(kw) | tokens(slug)
            if not toks:
                continue
            pages.append(Page(f, sec, cfg["prefix"] + slug, title, toks,
                              cfg["commercial"]))
    return pages


# ---------------------------------------------------------------- scoring

def score(a: Page, b: Page) -> float:
    inter = a.toks & b.toks
    if not inter:
        return 0.0
    # weighted overlap, normalised by the smaller token set (so a short, focused
    # page still scores high when fully covered by a broad one)
    base = len(inter) / max(1, min(len(a.toks), len(b.toks)))
    raw = len(inter) + base
    # boost cross-section links (informational ↔ commercial flow of authority)
    if a.section != b.section:
        raw *= 1.5
    # extra boost when one side is a commercial page (push authority to money pages)
    if b.commercial and not a.commercial:
        raw *= 1.25
    return raw


def build_graph(pages: list[Page], max_links: int, min_score: float
                ) -> dict[Path, list[Page]]:
    graph: dict[Path, list[Page]] = {}
    for a in pages:
        scored = []
        for b in pages:
            if b.url == a.url:
                continue
            s = score(a, b)
            if s >= min_score:
                scored.append((s, b))
        scored.sort(key=lambda x: x[0], reverse=True)
        # prefer at least one commercial target if available among candidates
        chosen: list[Page] = []
        seen = set()
        for _, b in scored:
            if b.url in seen:
                continue
            chosen.append(b)
            seen.add(b.url)
            if len(chosen) >= max_links:
                break
        if chosen:
            graph[a.file] = chosen
    return graph


# ---------------------------------------------------------------- injection

def render_block(targets: list[Page]) -> str:
    items = "\n".join(
        f'    <li><a href="{escape(t.url)}">{escape(t.title)}</a></li>'
        for t in targets
    )
    return (
        f'<section {LINKER_MARKER} class="container my-4" '
        f'style="border-top:1px solid #e5e5e5;padding-top:16px">\n'
        f'  <h2 class="h6" style="color:#1b7a3d">Читайте также</h2>\n'
        f'  <ul style="columns:2;font-size:.95rem">\n{items}\n  </ul>\n'
        f'</section>'
    )


_LINKER_RE = re.compile(
    r'\n?<section [^>]*data-linker="1".*?</section>', re.I | re.S)


def inject(html: str, block: str) -> str:
    # remove any previous linker block (idempotent), then insert before </body>
    html = _LINKER_RE.sub("", html)
    idx = html.lower().rfind("</body>")
    if idx == -1:
        return html
    return html[:idx] + block + "\n" + html[idx:]


# ---------------------------------------------------------------- notify

def notify_summary(applied: int, files: int, dry: bool) -> None:
    if dry or applied == 0:
        return
    try:
        import daily_ledger
        daily_ledger.append_event(
            "done",
            f"Linker: обновлено страниц {files}, ссылок {applied}"
        )
    except Exception as e:
        print(f"· telegram unavailable: {e}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Internal-linking agent (Linker)")
    ap.add_argument("--dry-run", action="store_true", help="report only, no writes")
    ap.add_argument("--max-links", type=int,
                    default=int(os.environ.get("LINKER_MAX_LINKS", "6")))
    ap.add_argument("--min-score", type=float,
                    default=float(os.environ.get("LINKER_MIN_SCORE", "1.6")))
    ap.add_argument("--sections", default="blog,oem,landing",
                    help="comma-separated sections to cross-link")
    args = ap.parse_args()

    sections = [s.strip() for s in args.sections.split(",")
                if s.strip() in SECTIONS]
    pages = load_pages(sections)
    print(f"📄 loaded {len(pages)} pages from {sections}")

    graph = build_graph(pages, args.max_links, args.min_score)
    print(f"🔗 graph: {len(graph)} pages get links "
          f"(min_score={args.min_score}, max_links={args.max_links})")

    total_links = 0
    changed = 0
    by_file = {p.file: p for p in pages}
    for file, targets in graph.items():
        src = by_file[file]
        block = render_block(targets)
        html = file.read_text(encoding="utf-8", errors="ignore")
        new = inject(html, block)
        if new != html:
            total_links += len(targets)
            changed += 1
            if args.dry_run:
                if changed <= 12:
                    tgt = ", ".join(t.url for t in targets[:3])
                    print(f"  ~ {src.url}  →  {tgt}{' …' if len(targets) > 3 else ''}")
            else:
                file.write_text(new, encoding="utf-8")

    verb = "would update" if args.dry_run else "updated"
    print(f"✅ {verb} {changed} pages, {total_links} internal links total")
    notify_summary(total_links, changed, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
