#!/usr/bin/env python3
"""
Submit URLs to Google Indexing API.

Default: rotate through sitemap (≤180/day).
After SEO consolidations / deploys: use --hot (watchlist + home + nginx 301s).

Env: GSC_SERVICE_ACCOUNT_KEY or GSC_SERVICE_ACCOUNT_KEY_B64
"""

from __future__ import annotations

import argparse
import base64 as _b64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMITTED_FILE = ROOT / "data" / "gsc_submitted.json"
SITEMAP_URL = "https://pepperoni.tatar/sitemap.xml"
SITEMAP_FILE = ROOT / "public" / "sitemap.xml"
WATCHLIST = ROOT / "data" / "commercial_watchlist.json"
DAILY_LIMIT = 180
ORIGIN = "https://pepperoni.tatar"


def _load_gsc_key() -> str:
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_KEY", "")
    if raw.strip():
        return raw
    b64 = os.environ.get("GSC_SERVICE_ACCOUNT_KEY_B64", "")
    if b64.strip():
        try:
            return _b64.b64decode(b64).decode("utf-8")
        except Exception:
            return ""
    return ""


def _load_submitted() -> dict:
    try:
        return json.loads(SUBMITTED_FILE.read_text())
    except Exception:
        return {}


def _save_submitted(data: dict) -> None:
    try:
        SUBMITTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        SUBMITTED_FILE.write_text(json.dumps(data))
    except Exception as e:
        print(f"  ⚠️  could not save rotation state: {e}")


def priority_score(url: str) -> int:
    if url in (f"{ORIGIN}/", f"{ORIGIN}/en/"):
        return 100
    if "/pepperoni" in url and "/blog/" not in url and "/geo/" not in url:
        return 90
    if "/kazylyk" in url or "/bakery" in url:
        return 85
    if "/blog/" in url:
        return 80
    if "/products/" in url:
        return 75
    if "/geo/" in url:
        return 60
    return 50


def load_sitemap_urls() -> list[str]:
    if SITEMAP_FILE.exists():
        tree = ET.parse(str(SITEMAP_FILE))
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in tree.findall(".//sm:loc", ns) if loc.text]
        print(f"📋 Loaded {len(urls)} URLs from local sitemap.xml")
        return urls
    print("⚠️  Local sitemap not found, fetching from web...")
    try:
        with urllib.request.urlopen(SITEMAP_URL, timeout=15) as r:
            content = r.read()
        root = ET.fromstring(content)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
        print(f"📋 Fetched {len(urls)} URLs from {SITEMAP_URL}")
        return urls
    except Exception as e:
        print(f"❌ Could not load sitemap: {e}")
        return []


def _abs(url_or_path: str) -> str:
    u = (url_or_path or "").strip()
    if not u:
        return ""
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if not u.startswith("/"):
        u = "/" + u
    return ORIGIN + u


def load_hot_urls() -> list[str]:
    """Money/commercial URLs that must be re-crawled after SEO edits."""
    out: list[str] = [
        f"{ORIGIN}/",
        f"{ORIGIN}/pepperoni",
        f"{ORIGIN}/pepperoni-dlya-pizzerii",
        f"{ORIGIN}/llms.txt",
        f"{ORIGIN}/llms-full.txt",
        f"{ORIGIN}/en/llms.txt",
        f"{ORIGIN}/.well-known/llms.txt",
        f"{ORIGIN}/en/pepperoni",
    ]
    try:
        data = json.loads(WATCHLIST.read_text(encoding="utf-8"))
        for it in data.get("items") or []:
            page = it.get("page") or ""
            if page:
                out.append(_abs(page))
        hub = data.get("money_hub")
        if hub:
            out.append(_abs(hub))
    except Exception:
        pass
    # unique, preserve order
    seen: set[str] = set()
    uniq = []
    for u in out:
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def parse_nginx_redirects(paths: list[Path]) -> tuple[list[str], list[str]]:
    """Return (updated_destinations, deleted_sources) from nginx return 301 blocks."""
    loc_re = re.compile(r"location\s+=\s+(\S+)\s*\{")
    ret_re = re.compile(r"return\s+301\s+(\S+)\s*;")
    updated: list[str] = []
    deleted: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        current_loc = None
        for line in text.splitlines():
            m = loc_re.search(line)
            if m:
                current_loc = m.group(1)
                continue
            m = ret_re.search(line)
            if m and current_loc:
                dest = m.group(1).rstrip(";")
                deleted.append(_abs(current_loc))
                updated.append(_abs(dest) if dest.startswith("http") else _abs(dest))
                current_loc = None
    # unique
    def uniq(xs: list[str]) -> list[str]:
        s: set[str] = set()
        o = []
        for x in xs:
            if x and x not in s:
                s.add(x)
                o.append(x)
        return o

    return uniq(updated), uniq(deleted)


def get_access_token(sa: dict) -> str:
    import base64

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    now = int(time.time())
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/indexing",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}".encode()

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    pk = serialization.load_pem_private_key(
        sa["private_key"].encode(), password=None, backend=default_backend()
    )
    sig = pk.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    jwt_token = f"{header}.{payload}.{sig_b64}"
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token,
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def submit_url(url: str, token: str, ntype: str = "URL_UPDATED") -> str:
    body = json.dumps({"url": url, "type": ntype}).encode()
    req = urllib.request.Request(
        "https://indexing.googleapis.com/v3/urlNotifications:publish",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            return f"✅ {ntype} {result.get('urlNotificationMetadata', {}).get('url', url)}"
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if e.code == 429:
            return "⛔ QUOTA_EXCEEDED"
        return f"⚠️  {ntype} {url} → {e.code}: {err[:120]}"


def _submit_batch(
    items: list[tuple[str, str]],
    token: str,
    seen: dict,
) -> tuple[int, int]:
    ok = fail = 0
    for url, ntype in items:
        result = submit_url(url, token, ntype)
        print(f"  {result}")
        if result.startswith("✅"):
            ok += 1
            seen[url] = time.time()
        elif "QUOTA_EXCEEDED" in result:
            print("  ⛔ Daily quota reached, stopping.")
            break
        else:
            fail += 1
        time.sleep(0.35)
    return ok, fail


def main() -> int:
    ap = argparse.ArgumentParser(description="Google Indexing API submitter")
    ap.add_argument("--url", action="append", default=[], help="URL or path to URL_UPDATED")
    ap.add_argument("--delete", action="append", default=[], help="URL or path to URL_DELETED")
    ap.add_argument(
        "--hot",
        action="store_true",
        help="Submit commercial watchlist + home + nginx 301 sources/dests (post-SEO default)",
    )
    ap.add_argument(
        "--from-redirects",
        action="store_true",
        help="Parse deploy/nginx/*redirects*.conf for 301s",
    )
    ap.add_argument(
        "--sitemap",
        action="store_true",
        help="Also rotate sitemap submissions (default when no other mode)",
    )
    args = ap.parse_args()

    key_json = _load_gsc_key()
    if not key_json:
        key_file = Path(__file__).parent / "gsc-key.json"
        if key_file.exists():
            key_json = key_file.read_text()
        else:
            print("❌ GSC_SERVICE_ACCOUNT_KEY not set")
            return 1

    sa = json.loads(key_json)
    print(f"🔑 Service account: {sa['client_email']}")

    items: list[tuple[str, str]] = []

    if args.hot or args.from_redirects or args.url or args.delete:
        if args.hot:
            for u in load_hot_urls():
                items.append((u, "URL_UPDATED"))
            args.from_redirects = True
        for u in args.url:
            items.append((_abs(u), "URL_UPDATED"))
        for u in args.delete:
            items.append((_abs(u), "URL_DELETED"))
        if args.from_redirects:
            confs = sorted((ROOT / "deploy" / "nginx").glob("*redirects*.conf"))
            updated, deleted = parse_nginx_redirects(confs)
            print(f"📋 nginx redirects: {len(deleted)} sources → URL_DELETED, {len(updated)} dests → URL_UPDATED")
            for u in updated:
                items.append((u, "URL_UPDATED"))
            for u in deleted:
                items.append((u, "URL_DELETED"))
    else:
        args.sitemap = True

    if args.sitemap:
        all_urls = load_sitemap_urls()
        if not all_urls and not items:
            print("❌ No URLs to submit")
            return 1
        seen_pre = _load_submitted()

        def sort_key(u: str):
            return (seen_pre.get(u, 0.0), -priority_score(u))

        all_urls.sort(key=sort_key)
        budget = max(0, DAILY_LIMIT - len(items))
        for u in all_urls[:budget]:
            items.append((u, "URL_UPDATED"))

    # de-dupe keeping first occurrence (prefer earlier URL_UPDATED over later DELETE of same? keep first)
    seen_pair: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for pair in items:
        if pair in seen_pair:
            continue
        seen_pair.add(pair)
        deduped.append(pair)
    items = deduped[:DAILY_LIMIT]

    print(f"\n📊 Submitting {len(items)} notifications")
    print("🔐 Getting access token...")
    try:
        token = get_access_token(sa)
    except Exception as e:
        print(f"❌ Token error: {e}")
        return 1

    print("\n📤 Submitting to Google Indexing API...\n")
    seen = _load_submitted()
    ok, fail = _submit_batch(items, token, seen)
    _save_submitted(seen)
    print(f"\n{'✅' if fail == 0 else '⚠️ '} Done: {ok} submitted, {fail} errors")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
