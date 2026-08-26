#!/usr/bin/env python3
"""Apply the SEO trust-reset keep/301/410/noindex policy.

Dry-run is the default. ``--apply`` deletes retired HTML, adds noindex to
explicit non-organic landings, strips unsupported structured-data claims and
generates nginx snippets plus ``data/url_consolidation_map.json``.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
NGINX = ROOT / "deploy" / "nginx"
MANIFEST = DATA / "index_manifest.json"
OUT = DATA / "url_consolidation_map.json"
DB = DATA / "seo_data.db"

ORG_ID = "https://pepperoni.tatar/#organization"
ORG_NAME = "Казанские Деликатесы"
ORG_LEGAL = "ООО «Казанские Деликатесы»"
ORG_URL = "https://pepperoni.tatar/"
ORG_SAME_AS = [
    "https://kazandelikates.tatar/",
    "https://www.youtube.com/@kazandelikates",
]

VERIFY_RE = re.compile(
    r"(?:^|/)(?:yandex_?[0-9a-f]+|google[0-9a-f]+|[0-9a-f]{16})\.html$")
ROBOTS_RE = re.compile(
    r"""<meta[^>]+name=["']robots["'][^>]*>""", re.I)
LLMS_LINK_RE = re.compile(
    r"""\s*<link\b[^>]*\brel=["']llms["'][^>]*>\s*""", re.I)
JSON_LD_RE = re.compile(
    r"""(<script\b[^>]*type=["']application/ld\+json["'][^>]*>)(.*?)(</script>)""",
    re.I | re.S,
)
LOC_RE = re.compile(
    r"location\s*=\s*(\S+)\s*\{[^}]*return\s+30[178]\s+(\S+);", re.S)


def clean_url(rel: str) -> str:
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[:-11].rstrip("/")
    return "/" + rel.removesuffix(".html")


def normalize_url(value: str) -> str:
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    path = re.sub(r"\.html$", "", path)
    path = "/" + path.lstrip("/")
    return path.rstrip("/") or "/"


def load_keep() -> tuple[set[str], set[str]]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = [r for r in payload.get("entries", []) if r.get("status") == "keep"]
    return (
        {normalize_url(r["url"]) for r in rows},
        {r["file"] for r in rows},
    )


def candidate_html_files() -> set[str]:
    """Include deleted tracked files and prior retire-map rows for idempotency."""
    files = {
        str(path.relative_to(PUBLIC))
        for path in PUBLIC.rglob("*.html")
    }
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "public"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.splitlines()
        files.update(
            path.removeprefix("public/")
            for path in tracked
            if path.endswith(".html")
        )
    except (OSError, subprocess.SubprocessError):
        pass
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
            files.update(
                str(row["file"])
                for row in previous.get("entries", [])
                if row.get("file")
            )
        except (OSError, ValueError, TypeError):
            pass
    return files


def gsc_metrics() -> tuple[dict[str, dict[str, float]], str | None]:
    if not DB.exists():
        return {}, None
    conn = sqlite3.connect(str(DB))
    newest = conn.execute("SELECT MAX(date) FROM gsc_queries").fetchone()[0]
    if not newest:
        conn.close()
        return {}, None
    cutoff = (date.fromisoformat(newest) - timedelta(days=27)).isoformat()
    rows = conn.execute(
        """SELECT page, SUM(clicks), SUM(impressions)
           FROM gsc_queries WHERE date >= ? GROUP BY page""",
        (cutoff,),
    ).fetchall()
    conn.close()
    out: dict[str, dict[str, float]] = {}
    for page, clicks, impressions in rows:
        path = normalize_url(str(page))
        out[path] = {
            "clicks_28d": float(clicks or 0),
            "impressions_28d": float(impressions or 0),
        }
    return out, newest


def old_redirects() -> dict[str, str]:
    out: dict[str, str] = {}
    for conf in sorted(NGINX.glob("*redirects.conf")):
        text = conf.read_text(encoding="utf-8", errors="replace")
        for source, target in LOC_RE.findall(text):
            out[normalize_url(source.strip('"'))] = normalize_url(target.strip('"'))
    return out


def language_for(rel: str) -> str:
    first = rel.split("/", 1)[0]
    if first == "en":
        return "en"
    if first in {
        "ar", "az", "be", "fr", "hy", "id", "ka", "kk", "ky", "mn",
        "ms", "ro", "tg", "tr", "uz", "zh",
    }:
        return first
    return "ru"


def noindex_reason(rel: str) -> str | None:
    exact = {
        "privacy.html", "terms.html", "returns.html", "search.html",
        "en/privacy.html", "en/terms.html", "en/returns.html", "en/search.html",
        "china.html", "en/investment.html", "en/investors.html",
    }
    if rel in exact:
        return "useful non-organic/legal page"
    if rel.startswith(("export/", "en/export/")):
        return "country landing lacks importer and shipment evidence"
    lang = language_for(rel)
    if lang not in {"ru", "en"} and "/geo/" not in f"/{rel}":
        if rel.endswith(("pepperoni.html", "index.html")):
            return "unsupported locale retained only as non-organic landing"
    return None


def static_target(path: str, lang: str) -> tuple[str | None, bool]:
    en = lang == "en"
    pepperoni = "/en/pepperoni" if en else "/pepperoni"
    stm = "/en/private-label" if en else "/kontraktnoe-proizvodstvo"
    bakery = "/en/vyipechka-halyal" if en else "/vyipechka-halyal"
    hotdog = "/en/sosiski-dlya-hotdog" if en else "/sosiski-dlya-hotdog"
    mappings = {
        "/oem": "/kontraktnoe-proizvodstvo",
        "/private-label": "/kontraktnoe-proizvodstvo",
        "/pepperoni-private-label": "/kontraktnoe-proizvodstvo",
        "/en/oem": "/en/private-label",
        "/en/kontraktnoe-proizvodstvo": "/en/private-label",
        "/bakery": "/vyipechka-halyal",
        "/en/bakery": "/en/vyipechka-halyal",
        "/sosiski": "/sosiski-dlya-hotdog",
        "/sosiski-halyal": "/sosiski-dlya-hotdog",
        "/en/sosiski-halyal": "/en/sosiski-dlya-hotdog",
        "/kazylyk-v2": "/kazylyk",
        "/pepperoni-halyal-v2": "/pepperoni",
        "/vetchina-fileynaya-halyal-v2": "/vetchina-optom",
        "/vetchina-iz-kuricy-halyal-v2": "/vetchina-optom",
        "/wholesale-halal-pepperoni-supplier": "/pepperoni",
        "/en/wholesale-halal-pepperoni-supplier": "/en/pepperoni",
        "/what-is-halal-pepperoni-v2": "/blog/what-is-halal-pepperoni",
        "/what-is-echpochmak-v2": "/blog/echpochmak",
    }
    if path in mappings:
        return mappings[path], True
    if path.startswith(("/private-label/", "/oem/", "/en/private-label/", "/en/oem/")):
        return stm, True
    slug = path.rsplit("/", 1)[-1]
    if "pepperoni" in slug or "peperoni" in slug:
        return pepperoni, True
    if slug in {"jerks", "dzherki"}:
        return "/en/jerky" if en else "/jerky", True
    if "vypech" in slug or "bakery" in slug:
        return bakery, True
    if "sosis" in slug or "hotdog" in slug or "hot-dog" in slug:
        return hotdog, True
    return None, False


def topic_target(path: str, lang: str) -> str | None:
    en = lang == "en"
    slug = path.rsplit("/", 1)[-1].lower()
    prefix = "/en" if en else ""
    if "kazylyk" in slug or "казылык" in slug:
        return "/en/blog/kazylyk-horse-meat-sausage" if en else "/blog/kazylyk"
    if "echpoch" in slug:
        return "/en/blog/echpochmak-halyal" if en else "/blog/echpochmak"
    if any(x in slug for x in ("hotdog", "hot-dog", "sosis", "sausage")):
        return (
            "/en/blog/beef-hotdog-sausages-halal"
            if en else "/blog/sosiski-dlya-hot-dogov-optom")
    if any(x in slug for x in ("burger", "kotlet", "patt")):
        return (
            "/en/blog/burger-patties-wholesale-halal"
            if en else "/blog/kotlety-dlya-burgerov-optom")
    if any(x in slug for x in ("private-label", "stm", "kontrakt")):
        return "/en/private-label" if en else "/kontraktnoe-proizvodstvo"
    if "iso-22000" in slug:
        return f"{prefix}/blog/iso-22000-iaf-certsearch"
    if any(x in slug for x in ("certif", "sertifik", "halal-production", "halal-meat-production")):
        return f"{prefix}/blog/halal-certification-russia"
    if "karmin" in slug or "carmine" in slug or "e120" in slug:
        return f"{prefix}/blog/karmin-e120-haram"
    if any(x in slug for x in ("tatar", "vypech", "bakery", "gubad", "elesh")):
        return (
            "/en/blog/tatar-bakery-wholesale"
            if en else "/blog/tatarskaya-vypechka-optom")
    if "pepperoni" in slug or "peperoni" in slug:
        if any(x in slug for x in ("slice", "narez", "diametr", "razmer", "spec")):
            return (
                "/en/blog/pepperoni-slicing-specs"
                if en else "/blog/narezka-pepperoni-parametry")
        if any(x in slug for x in ("store", "storage", "shelf", "hranit")):
            return (
                "/en/blog/wholesale-pepperoni-russia-export"
                if en else "/blog/kak-hranit-pepperoni")
        if any(x in slug for x in ("pizzeria", "pizza", "horeca", "source")):
            return f"{prefix}/blog/pepperoni-for-pizzeria-horeca"
        if any(x in slug for x in ("iz-kakogo", "made-of", "ingredient")):
            return (
                "/en/blog/what-is-halal-pepperoni"
                if en else "/blog/pepperoni-iz-kakogo-myasa")
        return f"{prefix}/blog/what-is-halal-pepperoni"
    return None


def geo_target(path: str, lang: str) -> str | None:
    slug = path.rsplit("/", 1)[-1].lower()
    en = lang == "en"
    prefix = "/en" if en else ""
    if "kazylyk" in slug:
        return f"{prefix}/kazylyk"
    if any(x in slug for x in ("pepperoni", "topping")):
        return f"{prefix}/pepperoni"
    if any(x in slug for x in ("sosis", "hotdog")):
        return f"{prefix}/sosiski-dlya-hotdog"
    if any(x in slug for x in ("kotlet", "burger")):
        return f"{prefix}/kotlety-dlya-burgerov"
    if any(x in slug for x in ("vypech", "echpoch", "gubad", "elesh", "pastry")):
        return f"{prefix}/vyipechka-halyal"
    if "vetchina" in slug or "ham" in slug:
        return f"{prefix}/vetchina-optom"
    if any(x in slug for x in ("private-label", "stm")):
        return "/en/private-label" if en else "/kontraktnoe-proizvodstvo"
    return f"{prefix}/products"


def ensure_noindex(text: str) -> str:
    meta = '<meta name="robots" content="noindex,follow">'
    if ROBOTS_RE.search(text):
        return ROBOTS_RE.sub(meta, text, count=1)
    return re.sub(r"(<head[^>]*>)", rf"\1\n{meta}", text, count=1, flags=re.I)


def _own_organization(node: dict) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    if "Organization" not in kinds:
        return False
    name = str(node.get("name") or node.get("legalName") or "")
    return bool(re.search(r"Казанские Деликатесы|Kazan Delicac", name, re.I))


def clean_schema(node):
    if isinstance(node, list):
        cleaned = [clean_schema(item) for item in node]
        return [item for item in cleaned if item is not None]
    if not isinstance(node, dict):
        return node
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    if "LocalBusiness" in kinds:
        return None
    node = dict(node)
    node.pop("shippingDetails", None)
    node.pop("hasMerchantReturnPolicy", None)
    if _own_organization(node):
        node.update({
            "@id": ORG_ID,
            "name": ORG_NAME,
            "legalName": ORG_LEGAL,
            "url": ORG_URL,
            "sameAs": ORG_SAME_AS,
        })
    for key, value in list(node.items()):
        cleaned = clean_schema(value)
        if cleaned is None:
            node.pop(key, None)
        else:
            node[key] = cleaned
    return node


def clean_html(text: str, *, noindex: bool) -> str:
    text = LLMS_LINK_RE.sub("\n", text)
    if noindex:
        text = ensure_noindex(text)

    def replace(match: re.Match) -> str:
        try:
            payload = json.loads(match.group(2))
        except (ValueError, TypeError):
            return match.group(0)
        cleaned = clean_schema(payload)
        if cleaned is None or cleaned == []:
            return ""
        body = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
        return match.group(1) + body + match.group(3)

    return JSON_LD_RE.sub(replace, text)


def render_locations(rows: list[dict], status: str, header: str) -> str:
    lines = [header]
    for row in sorted(rows, key=lambda r: r["url"]):
        source = row["url"]
        variants = [source]
        if source != "/" and not source.endswith(".html"):
            variants.append(source + ".html")
        for variant in variants:
            if status == "301":
                target = "https://pepperoni.tatar" + row["canonical_target"]
                lines.append(f"location = {variant} {{ return 301 {target}; }}")
            else:
                lines.append(f"location = {variant} {{ return 410; }}")
    return "\n".join(lines) + "\n"


def classify(rel: str, keep_urls: set[str], metrics: dict[str, dict[str, float]],
             redirects: dict[str, str]) -> dict:
    path = clean_url(rel)
    norm = normalize_url(path)
    lang = language_for(rel)
    signal = metrics.get(norm, {"clicks_28d": 0.0, "impressions_28d": 0.0})
    reason = noindex_reason(rel)
    if lang not in {"ru", "en"} and "/geo/" in f"/{rel}":
        status = "410"
        target = None
        reason = "unsupported locale city page"
    elif reason:
        status = "noindex"
        target = norm
    else:
        explicit = False
        if "/geo/" in f"/{rel}":
            target = geo_target(norm, lang)
        elif norm.startswith(("/blog/", "/en/blog/")):
            target = topic_target(norm, lang)
        else:
            target, explicit = static_target(norm, lang)
        if target:
            target = normalize_url(target)
        prior = redirects.get(norm)
        if prior in keep_urls:
            target = prior
            explicit = True
        has_signal = signal["clicks_28d"] > 0 or signal["impressions_28d"] > 0
        if target in keep_urls and (explicit or has_signal):
            status = "301"
            reason = "equivalent canonical with search signal" if has_signal else "explicit duplicate"
        else:
            status = "410"
            target = None
            reason = "no distinct supported intent or evidence"
    return {
        "url": norm,
        "file": rel,
        "intent": "legacy URL retirement",
        "language": lang,
        "owner": "seo",
        "source": "fresh GSC query×page + index policy",
        "canonical_target": target,
        "status": status,
        "reason": reason,
        **signal,
    }


def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("--apply", action="store_true")
    ns = args.parse_args()

    keep_urls, keep_files = load_keep()
    metrics, newest = gsc_metrics()
    redirects = old_redirects()
    rows: list[dict] = []
    verification_files: list[str] = []

    for rel in sorted(candidate_html_files()):
        if rel in keep_files:
            continue
        if VERIFY_RE.search(rel):
            verification_files.append(rel)
            continue
        rows.append(classify(rel, keep_urls, metrics, redirects))

    counts = {status: sum(1 for r in rows if r["status"] == status)
              for status in ("301", "410", "noindex")}
    payload = {
        "version": 1,
        "generated_at": date.today().isoformat(),
        "gsc_latest_date": newest,
        "policy": {
            "keep_count": len(keep_urls),
            "target_range": [180, 250],
            "city_product_indexable": 0,
            "languages_indexable": ["ru", "en"],
        },
        "counts": counts,
        "verification_files_excluded": verification_files,
        "entries": rows,
    }
    print(
        f"consolidation dry-run={not ns.apply}: keep={len(keep_urls)} "
        f"301={counts['301']} 410={counts['410']} noindex={counts['noindex']} "
        f"GSC={newest or 'unavailable'}")
    if not ns.apply:
        return 0

    by_file = {row["file"]: row for row in rows}
    for rel in sorted(candidate_html_files()):
        path = PUBLIC / rel
        row = by_file.get(rel)
        if row and row["status"] in {"301", "410"} and path.exists():
            path.unlink()
            continue
        if not path.exists():
            continue
        is_noindex = bool(row and row["status"] == "noindex")
        text = path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_html(text, noindex=is_noindex)
        if cleaned != text:
            path.write_text(cleaned, encoding="utf-8")

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    external_redirect_sources = {
        source for source, target in redirects.items()
        if target in keep_urls
    }
    ru_geo = [r for r in rows if r["status"] == "301" and r["url"].startswith("/geo/")]
    en_geo = [r for r in rows if r["status"] == "301" and r["url"].startswith("/en/geo/")]
    blog = [
        r for r in rows
        if r["status"] == "301"
        and r["url"].startswith(("/blog/", "/en/blog/"))
        and r["url"] not in external_redirect_sources
    ]
    other_redirects = [
        r for r in rows
        if r["status"] == "301"
        and r not in ru_geo and r not in en_geo and r not in blog
        and r["url"] not in external_redirect_sources
    ]
    gone = [
        r for r in rows
        if r["status"] == "410"
        and not r["url"].startswith(("/geo/", "/en/geo/"))
    ]
    (NGINX / "geo-cleanup-redirects.conf").write_text(
        render_locations(
            ru_geo, "301",
            "# AUTO-GENERATED by apply_index_consolidation.py — RU geo → canonical."),
        encoding="utf-8",
    )
    (NGINX / "en-geo-cleanup-redirects.conf").write_text(
        render_locations(
            en_geo, "301",
            "# AUTO-GENERATED by apply_index_consolidation.py — EN geo → canonical."),
        encoding="utf-8",
    )
    (NGINX / "pepperoni-blog-redirects.conf").write_text(
        render_locations(
            blog, "301",
            "# AUTO-GENERATED by apply_index_consolidation.py — legacy guides → cornerstone."),
        encoding="utf-8",
    )
    (NGINX / "trust-reset-redirects.conf").write_text(
        render_locations(
            other_redirects, "301",
            "# AUTO-GENERATED by apply_index_consolidation.py — duplicate hubs → canonical."),
        encoding="utf-8",
    )
    (NGINX / "trust-reset-gone.conf").write_text(
        render_locations(
            gone, "410",
            "# AUTO-GENERATED by apply_index_consolidation.py — unsupported URLs are Gone."),
        encoding="utf-8",
    )
    print(f"wrote {OUT}; removed {counts['301'] + counts['410']} HTML files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
