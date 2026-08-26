#!/usr/bin/env python3
"""Validate the explicit index, redirect and evidence policy."""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
MANIFEST = DATA / "index_manifest.json"
RETIRE_MAP = DATA / "url_consolidation_map.json"
SITEMAP = PUBLIC / "sitemap.xml"
NGINX = ROOT / "deploy" / "nginx"
BASE = "https://pepperoni.tatar"
ORG_ID = f"{BASE}/#organization"

VERIFY_RE = re.compile(
    r"(?:^|/)(?:yandex_?[0-9a-f]+|google[0-9a-f]+|[0-9a-f]{16})\.html$")
NOINDEX_RE = re.compile(
    r"""<meta[^>]+name=["']robots["'][^>]*content=["'][^"']*noindex""", re.I)
CANONICAL_RE = re.compile(
    r"""<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']""", re.I)
CANONICAL_RE2 = re.compile(
    r"""<link[^>]+href=["']([^"']+)["'][^>]+rel=["']canonical["']""", re.I)
LANG_RE = re.compile(r"""<html[^>]+lang=["']([^"']+)["']""", re.I)
TEL_RE = re.compile(r"""href=["']tel:([^"']+)["']""", re.I)
MAIL_RE = re.compile(r"""href=["']mailto:([^"'?]+)""", re.I)
JSON_LD_RE = re.compile(
    r"""<script\b[^>]*type=["']application/ld\+json["'][^>]*>(.*?)</script>""",
    re.I | re.S,
)
NGINX_301_RE = re.compile(
    r"""location\s*=\s*(\S+)\s*\{[^{}]*?return\s+301\s+"""
    r"""(https://pepperoni\.tatar[^\s;]+);""",
    re.I | re.S,
)
NGINX_EXACT_LOCATION_RE = re.compile(r"""location\s*=\s*(\S+)\s*\{""", re.I)
SUPERLATIVE_RE = re.compile(
    r"\b(?:лучший|номер\s+один|лидер\s+рынка)\b"
    r"|единственн\w+\s+(?:производител|поставщик)"
    r"|\b(?:best|number\s+one|market[- ]leading|leading)\s+"
    r"(?:manufacturer|supplier|producer|brand|company|product|quality|pepperoni|sausage)\b",
    re.I,
)
UNSUPPORTED_CLAIM_RE = re.compile(
    r"(?:сертифицир|аккредит|одобрен|признан|поставля\w*|достав\w*)"
    r".{0,60}(?:JAKIM|SFDA|GSO|GCC|ОАЭ|Сауд)"
    r"|(?:JAKIM|SFDA|GSO|GCC).{0,60}"
    r"(?:certif|approv|recogn|deliver|supply)",
    re.I | re.S,
)
FIXED_LOGISTICS_RE = re.compile(
    r"(?:достав\w*|срок\s+производства|delivery|lead\s*time)"
    r".{0,50}\b\d+\s*(?:час|дн|day|hour)"
    r"|\bMOQ\b.{0,20}\d+\s*(?:kg|кг)",
    re.I | re.S,
)
NEGATED_CLAIM_RE = re.compile(
    r"(?:не\s+заявля\w*|нет\s+заявления|не\s+утвержда\w*|"
    r"does\s+not\s+claim|not\s+claimed)\b[^.!?]{0,400}[.!?]",
    re.I | re.S,
)


def normalize_url(value: str) -> str:
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    path = re.sub(r"\.html$", "", path)
    return ("/" + path.lstrip("/")).rstrip("/") or "/"


def clean_url(rel: str) -> str:
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[:-11].rstrip("/")
    return "/" + rel.removesuffix(".html")


def own_org_ids(node) -> list[str | None]:
    ids: list[str | None] = []
    if isinstance(node, list):
        for item in node:
            ids.extend(own_org_ids(item))
        return ids
    if not isinstance(node, dict):
        return ids
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    name = str(node.get("name") or node.get("legalName") or "")
    if "Organization" in kinds and re.search(
            r"Казанские Деликатесы|Kazan Delicac", name, re.I):
        ids.append(node.get("@id"))
    for value in node.values():
        ids.extend(own_org_ids(value))
    return ids


def valid_gtin(value, expected_length: int | None = None) -> bool:
    digits = str(value or "").strip()
    if not digits.isdigit():
        return False
    allowed = {expected_length} if expected_length else {8, 12, 13, 14}
    if len(digits) not in allowed:
        return False
    payload = [int(char) for char in digits]
    check = payload.pop()
    total = sum(
        digit * (3 if (len(payload) - index) % 2 else 1)
        for index, digit in enumerate(payload)
    )
    return (10 - total % 10) % 10 == check


def gtin_errors(node) -> list[str]:
    errors: list[str] = []
    if isinstance(node, list):
        for item in node:
            errors.extend(gtin_errors(item))
        return errors
    if not isinstance(node, dict):
        return errors
    for key, length in (
        ("gtin", None), ("gtin8", 8), ("gtin12", 12),
        ("gtin13", 13), ("gtin14", 14),
    ):
        if key in node and not valid_gtin(node[key], length):
            errors.append(f"invalid {key}: {node[key]!r}")
    for value in node.values():
        errors.extend(gtin_errors(value))
    return errors


def html_errors(path: Path, row: dict) -> list[str]:
    source = path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    expected_lang = "en" if row["language"] == "en" else "ru"
    lang = LANG_RE.search(source)
    if not lang or lang.group(1).lower().split("-", 1)[0] != expected_lang:
        errors.append(f"html lang must be {expected_lang}")
    if NOINDEX_RE.search(source):
        errors.append("allowlisted page carries noindex")
    canonical = CANONICAL_RE.search(source) or CANONICAL_RE2.search(source)
    expected_url = row["url"]
    if not canonical:
        errors.append("missing canonical")
    elif normalize_url(canonical.group(1)) != normalize_url(expected_url):
        errors.append(
            f"canonical {normalize_url(canonical.group(1))} != {expected_url}")
    for match in TEL_RE.finditer(source):
        digits = re.sub(r"\D", "", match.group(1))
        if digits != "79872170202":
            errors.append(f"unapproved tel link: {match.group(1)}")
    for match in MAIL_RE.finditer(source):
        if match.group(1).lower() != "info@kazandelikates.tatar":
            errors.append(f"unapproved mailto: {match.group(1)}")
    for forbidden in (
        "LocalBusiness",
        "shippingDetails",
        "hasMerchantReturnPolicy",
        'rel="llms"',
        "rel='llms'",
    ):
        if forbidden in source:
            errors.append(f"forbidden indexable markup: {forbidden}")
    if SUPERLATIVE_RE.search(source):
        errors.append("unsupported superlative")
    claim_source = NEGATED_CLAIM_RE.sub(" ", source)
    if UNSUPPORTED_CLAIM_RE.search(claim_source):
        errors.append("unsupported country/certification claim")
    if FIXED_LOGISTICS_RE.search(source):
        errors.append("fixed logistics/MOQ claim requires evidence")
    for raw in JSON_LD_RE.findall(source):
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"invalid JSON-LD: {exc}")
            continue
        errors.extend(gtin_errors(payload))
        for org_id in own_org_ids(payload):
            if org_id != ORG_ID:
                errors.append(
                    f"own Organization @id must be {ORG_ID}, got {org_id!r}")
    return sorted(set(errors))


def run_checks() -> list[str]:
    errors: list[str] = []
    if not MANIFEST.exists() or not RETIRE_MAP.exists():
        return ["index_manifest.json or url_consolidation_map.json missing"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("entries", [])
    keep = [row for row in entries if row.get("status") == "keep"]
    minimum = int(manifest.get("policy", {}).get("indexable_min", 180))
    maximum = int(manifest.get("policy", {}).get("indexable_max", 250))
    if not minimum <= len(keep) <= maximum:
        errors.append(f"keep count {len(keep)} outside {minimum}..{maximum}")

    keep_urls = {normalize_url(row["url"]) for row in keep}
    keep_files = {row["file"] for row in keep}
    if len(keep_urls) != len(keep):
        errors.append("duplicate keep URLs in manifest")
    for row in keep:
        if row.get("language") not in {"ru", "en"}:
            errors.append(f"unsupported keep language: {row.get('url')}")
        path = PUBLIC / row["file"]
        if not path.is_file():
            errors.append(f"missing keep file: {row['file']}")
            continue
        for error in html_errors(path, row):
            errors.append(f"{row['url']}: {error}")

    retire = json.loads(RETIRE_MAP.read_text(encoding="utf-8")).get("entries", [])
    retire_by_file = {row["file"]: row for row in retire}
    for row in retire:
        status = row.get("status")
        target = row.get("canonical_target")
        path = PUBLIC / row["file"]
        if status == "301":
            if normalize_url(target or "") not in keep_urls:
                errors.append(f"301 target is not keep: {row['url']} → {target}")
            if normalize_url(target or "") == normalize_url(row["url"]):
                errors.append(f"self redirect: {row['url']}")
            if path.exists():
                errors.append(f"301 source file still exists: {row['file']}")
        elif status == "410":
            if path.exists():
                errors.append(f"410 source file still exists: {row['file']}")
        elif status == "noindex":
            if not path.exists():
                errors.append(f"noindex file missing: {row['file']}")
            elif not NOINDEX_RE.search(
                    path.read_text(encoding="utf-8", errors="replace")):
                errors.append(f"noindex meta missing: {row['file']}")
        else:
            errors.append(f"invalid retire status {status}: {row.get('url')}")

    nginx_routes: dict[str, str] = {}
    active_configs = [
        path for path in sorted(NGINX.glob("*.conf"))
        if path.name not in {"yaratu.conf", "test1-noindex.conf"}
    ]
    for config in active_configs:
        source = config.read_text(encoding="utf-8", errors="replace")
        for route in NGINX_EXACT_LOCATION_RE.findall(source):
            prior = nginx_routes.get(route)
            if prior:
                errors.append(
                    f"duplicate nginx exact location {route}: "
                    f"{prior}, {config.name}")
            else:
                nginx_routes[route] = config.name
        for route, target in NGINX_301_RE.findall(source):
            if normalize_url(target) not in keep_urls:
                errors.append(
                    f"{config.name}: redirect target is not keep: "
                    f"{normalize_url(route)} → {normalize_url(target)}")

    for path in sorted(PUBLIC.rglob("*.html")):
        rel = str(path.relative_to(PUBLIC))
        if rel in keep_files or VERIFY_RE.search(rel):
            continue
        row = retire_by_file.get(rel)
        if not row or row.get("status") != "noindex":
            errors.append(f"unknown indexable HTML outside manifest: {rel}")

    try:
        root = ET.parse(SITEMAP).getroot()
        sitemap_urls = {
            normalize_url(node.text or "")
            for node in root.findall(
                ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        }
        if sitemap_urls != keep_urls:
            missing = sorted(keep_urls - sitemap_urls)
            extra = sorted(sitemap_urls - keep_urls)
            errors.append(
                f"sitemap/manifest mismatch missing={missing[:5]} extra={extra[:5]}")
    except (OSError, ET.ParseError) as exc:
        errors.append(f"invalid sitemap: {exc}")

    for feed in sorted(PUBLIC.glob("products-feed*.xml")):
        try:
            root = ET.parse(feed).getroot()
        except (OSError, ET.ParseError) as exc:
            errors.append(f"{feed.name}: invalid XML: {exc}")
            continue
        for node in root.iter("{http://base.google.com/ns/1.0}gtin"):
            if not valid_gtin(node.text):
                errors.append(f"{feed.name}: invalid GTIN {node.text!r}")

    json_feed = PUBLIC / "products-feed.json"
    if json_feed.exists():
        try:
            errors.extend(
                f"{json_feed.name}: {error}"
                for error in gtin_errors(
                    json.loads(json_feed.read_text(encoding="utf-8")))
            )
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{json_feed.name}: invalid JSON: {exc}")

    try:
        from similarity_audit import audit
        errors.extend(audit())
    except Exception as exc:
        errors.append(f"similarity audit failed to run: {exc}")
    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        print(f"index policy: {len(errors)} FAIL")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print("index policy: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
