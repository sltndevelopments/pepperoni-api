#!/usr/bin/env python3
"""
Blog topic near-duplicate detection — shared by audit, strategy executor, and brain digest.

Normalization collapses known typos / aliases (halyal↔halal, sosiki↔sosiski, …)
and strips weak commercial suffixes so "sosiski-dlya-hot-dogov-optom" and
"sosiski-dlya-hot-dogov-kupit-optom" land in the same cluster.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

# Alias tokens applied after lowercasing / hyphen-normalize.
_TOKEN_ALIASES = {
    "halyal": "halal",
    "sosiki": "sosiski",
    "sosisok": "sosiski",
    "peperoni": "pepperoni",
    "ecpochmak": "echpochmak",
    "hotdog": "hot-dog",
    "hotdogs": "hot-dog",
    "gamburgerov": "burgerov",
    "gamburgera": "burgera",
    "sertifikaciya": "certification",
    "podark": "gift",
    "myasnye": "meat",
    "delikatesy": "delicacies",
    "produkcii": "products",
    "markirovka": "labeling",
    "myasnoy": "meat",
}

# Definitional suffixes — safe to collapse into the root topic.
_DEF_SUFFIXES = (
    "chto-eto",
    "eto",
    "what-is",
)

# Commercial suffixes — collapse only for *new-topic* near-dup gate,
# not for clustering existing posts (optom ≠ «что такое»).
_COMMERCIAL_SUFFIXES = (
    "kupit-optom",
    "kupit",
    "optom-halal",
    "optom-gid",
    "optom",
    "gid",
    "proizvoditel",
)

_TITLE_RE = re.compile(
    r"<title[^>]*>(.*?)</title>|"
    r'property=["\']og:title["\']\s+content=["\']([^"\']+)|'
    r'content=["\']([^"\']+)["\']\s+property=["\']og:title["\']',
    re.I | re.S,
)
_DATE_RE = re.compile(
    r'"datePublished"\s*:\s*"([^"]+)"|'
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def _alias_tokens(s: str) -> str:
    parts = [p for p in s.split("-") if p]
    norm_parts: list[str] = []
    for p in parts:
        tok = _TOKEN_ALIASES.get(p, p)
        if tok == "hot-dog":
            norm_parts.extend(["hot", "dog"])
        else:
            norm_parts.append(tok)
    return "-".join(norm_parts)


def _strip_suffixes(s: str, suffixes: tuple[str, ...]) -> str:
    changed = True
    while changed and s:
        changed = False
        for suf in suffixes:
            if s.endswith("-" + suf):
                s = s[: -(len(suf) + 1)]
                changed = True
            elif s == suf:
                s = ""
                changed = True
    return s.strip("-")


def _strip_def_prefixes(s: str) -> str:
    if s.startswith("what-is-"):
        s = s[8:]
    if s.startswith("chto-takoe-"):
        s = s[11:]
    if s.startswith("chto-eto-"):
        s = s[9:]
    return s.strip("-")


def normalize_slug(slug: str) -> str:
    """Cluster key: typo aliases + definitional affixes only (not commercial)."""
    s = (slug or "").strip().lower().strip("/")
    if s.startswith("blog/"):
        s = s[5:]
    if s.startswith("en/blog/"):
        s = s[8:]
    s = re.sub(r"[_\s]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    s = _alias_tokens(s)
    s = _strip_def_prefixes(s)
    s = _strip_suffixes(s, _DEF_SUFFIXES)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "empty"


def commercial_key(slug: str) -> str:
    """Stricter key for new-topic gate: also collapses kupit/optom variants."""
    s = normalize_slug(slug)
    s = _strip_suffixes(s, _COMMERCIAL_SUFFIXES)
    # collapse halal/halyal already done; also drop trailing -halal after optom strip
    s = _strip_suffixes(s, ("halal",))
    return s or "empty"


def title_tokens(title: str) -> set[str]:
    t = (title or "").lower()
    t = re.sub(r"[«»\"'.,:;!?()\[\]|/\\]+", " ", t)
    raw = [w for w in re.split(r"\s+", t) if len(w) >= 3]
    out = set()
    for w in raw:
        w = _TOKEN_ALIASES.get(w, w)
        # light stemming for RU commercial noise
        # Strip pure commercial noise, keep halal/халяль (product-defining).
        if w in ("опт", "оптом", "купить", "wholesale", "buy"):
            continue
        out.add(w)
    return out


def title_overlap(a: str, b: str) -> float:
    """Jaccard overlap of title tokens."""
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)


def title_recall(new: str, existing: str) -> float:
    """How much of the *new* title is covered by an existing title."""
    ta, tb = title_tokens(new), title_tokens(existing)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def extract_meta(html: str) -> dict:
    title = ""
    m = _TITLE_RE.search(html or "")
    if m:
        title = _strip_tags(next(g for g in m.groups() if g))
    date = ""
    dm = _DATE_RE.search(html or "")
    if dm:
        date = next(g for g in dm.groups() if g)
    h1 = ""
    hm = _H1_RE.search(html or "")
    if hm:
        h1 = _strip_tags(hm.group(1))
    # rough content length (body text)
    body = re.sub(r"<script[\s\S]*?</script>", " ", html or "", flags=re.I)
    body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.I)
    text_len = len(_strip_tags(body))
    return {"title": title, "h1": h1, "datePublished": date, "text_len": text_len}


def _typo_penalty(slug: str) -> int:
    """Higher = worse spelling (prefer correct forms as canon)."""
    s = slug.lower()
    penalty = 0
    for bad in ("sosiki", "peperoni", "ecpochmak", "snг", "hotdog-optom"):
        if bad in s:
            penalty += 3
    # Prefer fewer stacked commercial suffixes on canon
    for suf in ("kupit-optom", "optom-halal", "optom-gid"):
        if s.endswith(suf) or f"-{suf}" in s:
            penalty += 1
    return penalty


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            if fmt.endswith("Z") and s.endswith("Z"):
                return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
            if "%z" in fmt:
                return datetime.strptime(s.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            continue
    return None


# Force-merge known near-duplicate slug sets (applied after auto-clustering).
# Commercial pepperoni blog cluster is NOT merged here — nginx 301s those
# slugs to money hub /pepperoni (deploy/nginx/pepperoni-halyal-redirects.conf).
HARD_CLUSTERS = [
    {
        "canonical": "sosiski-dlya-hot-dogov-optom",
        "members": [
            "sosiski-dlya-hot-dogov-optom",
            "sosiski-dlya-hot-dogov-kupit-optom",
            "sosiski-dlya-hot-dogov-optom-halal",
            "sosiski-dlya-hot-dogov-kupit-optom-v-moskve",
            "sosiski-dlya-hotdog-optom",
            "sosiki-dlya-hotdog-optom",
            "halyal-sosiski-dlya-hot-dogov-optom",
            "halal-sosiski-dlya-hot-dogov-optom",
            "postavschik-sosisok-dlya-hot-dogov",
        ],
    },
    {
        "canonical": "kotlety-dlya-burgerov-optom",
        "members": [
            "kotlety-dlya-burgerov-optom",
            "kotlety-dlya-burgerov-kupit-optom",
            "kotlety-dlya-burgerov-optom-gid",
            "kotlety-dlya-burgerov-optom-halal",
            "kotlety-dlya-gamburgerov-optom",
            "kupit-kotlety-dlya-burgerov-optom",
        ],
    },
]

# Explicit preferred canons for known high-value clusters (override heuristics).
PREFERRED_CANON = {
    # pepperoni-halyal* commercial → /pepperoni via nginx, not blog canon
    "sosiski-dlya-hot-dogov": "sosiski-dlya-hot-dogov-optom",
    "sosiski-dlya-hot-dogov-optom": "sosiski-dlya-hot-dogov-optom",
    "kotlety-dlya-burgerov": "kotlety-dlya-burgerov-optom",
    "kotlety-dlya-burgerov-optom": "kotlety-dlya-burgerov-optom",
    "echpochmak": "echpochmak",
    "echpochmak-eto": "echpochmak",
    "ecpochmak": "echpochmak",
    "kazylyk": "kazylyk",
    "kazylyk-eto": "kazylyk",
    "pepperoni-iz-kakogo-myasa": "pepperoni-iz-kakogo-myasa",
    "peperoni-iz-kakogo-myasa": "pepperoni-iz-kakogo-myasa",
}


def pick_canonical(members: list[dict]) -> str:
    """Pick best slug among cluster members.

    Prefer: explicit PREFERRED_CANON, correct spelling, longer content,
    earlier datePublished, shorter slug.
    """
    slugs = {m["slug"] for m in members}
    for m in members:
        pref = PREFERRED_CANON.get(m["slug"])
        if pref and pref in slugs:
            return pref

    def key(m: dict):
        d = _parse_date(m.get("datePublished") or "")
        epoch = d.timestamp() if d else 1e18
        # Prefer root over -eto / -chto-eto when spelling equal
        def_penalty = 1 if re.search(r"-(eto|chto-eto)$", m["slug"]) else 0
        return (
            _typo_penalty(m["slug"]),
            def_penalty,
            -int(m.get("text_len") or 0),
            epoch,
            len(m["slug"]),
            m["slug"],
        )

    return sorted(members, key=key)[0]["slug"]


def scan_blog(lang: str = "ru") -> list[dict]:
    directory = PUBLIC / "blog" if lang == "ru" else PUBLIC / "en" / "blog"
    if not directory.is_dir():
        return []
    rows = []
    for path in sorted(directory.glob("*.html")):
        if path.name.startswith("_"):
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        meta = extract_meta(html)
        slug = path.stem
        rows.append({
            "lang": lang,
            "slug": slug,
            "path": f"/blog/{slug}" if lang == "ru" else f"/en/blog/{slug}",
            "file": str(path.relative_to(ROOT)),
            "norm": normalize_slug(slug),
            "title": meta["title"] or meta["h1"] or slug,
            "datePublished": meta["datePublished"],
            "text_len": meta["text_len"],
        })
    return rows


def cluster_posts(rows: list[dict], title_threshold: float = 0.72) -> list[dict]:
    """Cluster by normalize_slug and by commercial_key; merge on high title overlap."""
    for r in rows:
        r["norm"] = r.get("norm") or normalize_slug(r["slug"])
        r["ckey"] = commercial_key(r["slug"])

    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        # Bucket definitional duplicates together (same norm).
        by_key[f"n:{r['norm']}"].append(r)
        # Bucket commercial variants only when the slug itself looks commercial
        # (avoids merging «что такое X» into «X оптом»).
        if (
            r["ckey"]
            and r["ckey"] != "empty"
            and len(r["ckey"]) >= 8
            and re.search(r"(optom|kupit|gid|proizvoditel|wholesale)", r["slug"])
        ):
            by_key[f"c:{r['ckey']}"].append(r)

    clusters: list[list[dict]] = [list(v) for v in by_key.values() if len(v) >= 2]

    parent = list(range(len(clusters)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Merge clusters that share a slug or high title overlap + ≥2 shared tokens
    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            si = {m["slug"] for m in clusters[i]}
            sj = {m["slug"] for m in clusters[j]}
            if si & sj:
                union(i, j)
                continue
            a, b = clusters[i][0], clusters[j][0]
            shared = set(a["norm"].split("-")) & set(b["norm"].split("-"))
            if len(shared) >= 2 and title_overlap(a["title"], b["title"]) >= title_threshold:
                union(i, j)

    merged: dict[int, list[dict]] = defaultdict(list)
    for i, c in enumerate(clusters):
        merged[find(i)].extend(c)

    out = []
    for members in merged.values():
        seen = {}
        for m in members:
            seen[m["slug"]] = m
        members = list(seen.values())
        if len(members) < 2:
            continue
        canon = pick_canonical(members)
        out.append({
            "norm": normalize_slug(canon),
            "canonical": canon,
            "members": sorted(members, key=lambda m: (m["slug"] != canon, m["slug"])),
            "redirect_from": sorted(m["slug"] for m in members if m["slug"] != canon),
        })
    # Apply hard clusters: replace/merge any auto clusters that overlap.
    by_slug = {r["slug"]: r for r in rows}
    hard_slugs: set[str] = set()
    hard_out: list[dict] = []
    for hc in HARD_CLUSTERS:
        present = [by_slug[s] for s in hc["members"] if s in by_slug]
        if len(present) < 2:
            continue
        canon = hc["canonical"] if hc["canonical"] in by_slug else pick_canonical(present)
        hard_out.append({
            "norm": normalize_slug(canon),
            "canonical": canon,
            "members": sorted(present, key=lambda m: (m["slug"] != canon, m["slug"])),
            "redirect_from": sorted(m["slug"] for m in present if m["slug"] != canon),
        })
        hard_slugs.update(m["slug"] for m in present)

    filtered = []
    for c in out:
        # Drop auto-cluster if fully covered by a hard cluster; trim overlap otherwise
        remaining = [m for m in c["members"] if m["slug"] not in hard_slugs]
        if len(remaining) < 2:
            continue
        canon = pick_canonical(remaining)
        filtered.append({
            "norm": normalize_slug(canon),
            "canonical": canon,
            "members": sorted(remaining, key=lambda m: (m["slug"] != canon, m["slug"])),
            "redirect_from": sorted(m["slug"] for m in remaining if m["slug"] != canon),
        })

    out = hard_out + filtered
    out.sort(key=lambda c: (-len(c["members"]), c["canonical"]))
    return out


def is_near_duplicate(
    slug: str,
    title: str,
    existing: list[dict],
    title_threshold: float = 0.72,
) -> tuple[bool, str]:
    """Return (is_dup, reason). existing items need slug+title (+ optional norm)."""
    if not slug and not title:
        return False, ""
    norm = normalize_slug(slug or title)
    ckey = commercial_key(slug or title)
    for e in existing:
        e_slug = e.get("slug") or ""
        e_title = e.get("title") or e.get("title_ru") or ""
        e_norm = e.get("norm") or normalize_slug(e_slug)
        e_ckey = e.get("ckey") or commercial_key(e_slug)
        if e_slug and slug and e_slug == slug:
            return True, f"exact slug exists: {e_slug}"
        if norm and e_norm and norm == e_norm:
            return True, f"normalized slug collision with /blog/{e_slug} (norm={norm})"
        if ckey and e_ckey and ckey == e_ckey and "-" in ckey:
            return True, f"commercial-key collision with /blog/{e_slug} (ckey={ckey})"
        if title and e_title:
            if title_overlap(title, e_title) >= title_threshold:
                return True, f"title overlap with /blog/{e_slug}: «{e_title[:80]}»"
            # Short new titles that are fully covered by a longer existing title
            if len(title_tokens(title)) >= 2 and title_recall(title, e_title) >= 0.85:
                return True, f"title covered by /blog/{e_slug}: «{e_title[:80]}»"
    return False, ""


def blog_inventory_for_digest(limit: int = 120) -> dict:
    """Compact inventory for seo_brain digest (counts + sample + norms)."""
    ru = scan_blog("ru")
    en = scan_blog("en")
    clusters_ru = cluster_posts(ru)
    # Prefer listing recent / shorter titles for brain; include all norms as set
    norms = sorted({r["norm"] for r in ru if r["norm"] != "empty"})
    sample = [
        {"slug": r["slug"], "title": (r["title"] or "")[:90], "norm": r["norm"]}
        for r in sorted(ru, key=lambda x: x.get("datePublished") or "", reverse=True)[:limit]
    ]
    return {
        "blog_ru": len(ru),
        "blog_en": len(en),
        "near_dup_clusters_ru": len(clusters_ru),
        "existing_norms_sample": norms[:200],
        "existing_posts_sample": sample,
        "dedup_rule": (
            "НЕ предлагай new_blog_topics чей slug/norm совпадает с existing_norms_sample "
            "или title overlap ≥0.72 с existing_posts_sample. "
            "Синонимы (halyal/halal, sosiki/sosiski, peperoni/pepperoni) = дубль."
        ),
    }


if __name__ == "__main__":
    import json
    ru = scan_blog("ru")
    clusters = cluster_posts(ru)
    print(json.dumps({
        "ru_posts": len(ru),
        "clusters": len(clusters),
        "top": [
            {"canonical": c["canonical"], "n": len(c["members"]),
             "redirect_from": c["redirect_from"]}
            for c in clusters[:25]
        ],
    }, ensure_ascii=False, indent=2))
