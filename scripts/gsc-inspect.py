#!/usr/bin/env python3
"""Read-only Google Search Console URL Inspection.

Does not submit sitemaps or ping IndexNow. Never prints the token or the key.
Reuse _load_gsc_key / get_access_token from gsc-sitemap.py with the
webmasters.readonly scope.

  python3 scripts/gsc-inspect.py
  python3 scripts/gsc-inspect.py --urls-file data/inspect_urls.txt
  python3 scripts/gsc-inspect.py --urls 'https://pepperoni.tatar/\nhttps://pepperoni.tatar/en/'
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _load_sitemap_helpers():
    spec = importlib.util.spec_from_file_location(
        "gsc_sitemap", SCRIPTS / "gsc-sitemap.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod._load_gsc_key, mod.get_access_token


_load_gsc_key, get_access_token = _load_sitemap_helpers()

SITE_URL = "sc-domain:pepperoni.tatar"
INSPECT_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
DEFAULT_LIST = ROOT / "data" / "inspect_urls.txt"
SITEMAP_FILE = ROOT / "public" / "sitemap.xml"
REPORTS = ROOT / "reports"
ORIGIN = "https://pepperoni.tatar"
MAX_URLS = 200
MIN_INTERVAL = 1.0
COLUMNS = (
    "url",
    "verdict",
    "coverageState",
    "indexingState",
    "robotsTxtState",
    "pageFetchState",
    "lastCrawlTime",
    "googleCanonical",
    "userCanonical",
    "canonical_match",
    "sitemap",
    "richResultsVerdict",
    "richResultsTypes",
    "richResultsIssues",
    "mobileUsability",
)


def _public_rel(url: str) -> str | None:
    if not url.startswith(ORIGIN):
        return None
    path = url[len(ORIGIN):].split("?", 1)[0]
    if not path or path == "/":
        return "index.html"
    path = path.lstrip("/")
    if path.endswith("/"):
        path = path[:-1]
    candidate = ROOT / "public" / f"{path}.html"
    if candidate.is_file():
        return f"{path}.html"
    if path.endswith(".html") and (ROOT / "public" / path).is_file():
        return path
    return f"{path}.html"


def urls_changed_since(days: int = 1, limit: int = MAX_URLS) -> list[str]:
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        out = subprocess.check_output(
            ["git", "log", f"--since={since}", "--name-only", "--pretty=format:", "--", "public"],
            cwd=ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        out = ""
    changed = {
        line[len("public/"):]
        for line in out.splitlines()
        if line.startswith("public/") and line.endswith(".html")
    }
    if not SITEMAP_FILE.is_file():
        return []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tree = ET.parse(SITEMAP_FILE)
    found = []
    for loc in tree.findall(".//s:url/s:loc", ns):
        url = (loc.text or "").strip()
        rel = _public_rel(url)
        if rel and rel in changed:
            found.append(url)
        if len(found) >= limit:
            break
    return found


def read_url_list(path: Path) -> list[str]:
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls[:MAX_URLS]


def parse_urls_arg(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()][:MAX_URLS]


def resolve_urls(urls_arg: str, urls_file: Path | None, days: int) -> list[str]:
    if urls_arg.strip():
        return parse_urls_arg(urls_arg)
    if urls_file and urls_file.is_file():
        listed = read_url_list(urls_file)
        if listed:
            return listed
    return urls_changed_since(days=days)


def _safe_join(items) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return items
    return "|".join(str(x) for x in items)


def flatten_inspect(url: str, payload: dict) -> dict:
    result = payload.get("inspectionResult") or payload
    index = result.get("indexStatusResult") or {}
    rich = result.get("richResultsResult") or {}
    mobile = result.get("mobileUsabilityResult") or {}
    google_can = index.get("googleCanonical") or ""
    user_can = index.get("userCanonical") or ""
    items = rich.get("detectedItems") or []
    types = []
    issues = []
    for item in items:
        if isinstance(item, dict):
            if item.get("richResultType"):
                types.append(item["richResultType"])
            for issue in item.get("items") or []:
                if isinstance(issue, dict) and issue.get("issues"):
                    issues.extend(
                        i.get("issueMessage") or i.get("severity") or ""
                        for i in issue["issues"]
                        if isinstance(i, dict)
                    )
    return {
        "url": url,
        "verdict": index.get("verdict") or result.get("verdict") or "",
        "coverageState": index.get("coverageState") or "",
        "indexingState": index.get("indexingState") or "",
        "robotsTxtState": index.get("robotsTxtState") or "",
        "pageFetchState": index.get("pageFetchState") or "",
        "lastCrawlTime": index.get("lastCrawlTime") or "",
        "googleCanonical": google_can,
        "userCanonical": user_can,
        "canonical_match": "yes" if google_can and user_can and google_can == user_can else "no",
        "sitemap": _safe_join(index.get("sitemap")),
        "richResultsVerdict": rich.get("verdict") or "",
        "richResultsTypes": _safe_join(types),
        "richResultsIssues": _safe_join([i for i in issues if i]),
        "mobileUsability": mobile.get("verdict") or "",
    }


def inspect_url(url: str, token: str, opener=None) -> dict:
    body = json.dumps({
        "inspectionUrl": url,
        "siteUrl": SITE_URL,
        "languageCode": "ru",
    }).encode()
    req = urllib.request.Request(
        INSPECT_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    http = opener or urllib.request.urlopen
    last_err = None
    for attempt in range(3):
        try:
            with http(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_err  # type: ignore[misc]


def write_csv(rows: list[dict], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in COLUMNS})


def _redact(text: str, secrets: list[str]) -> str:
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only GSC URL Inspection")
    parser.add_argument("--urls", default=os.environ.get("GSC_INSPECT_URLS", ""))
    parser.add_argument("--urls-file", default=str(DEFAULT_LIST))
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    urls = resolve_urls(args.urls, Path(args.urls_file), args.days)
    if not urls:
        print("gsc-inspect: no URLs to inspect")
        return 0

    key_json = _load_gsc_key()
    if not key_json:
        print("gsc-inspect: GSC_SERVICE_ACCOUNT_KEY is not set")
        return 1
    try:
        sa = json.loads(key_json)
    except json.JSONDecodeError:
        print("gsc-inspect: service account JSON is invalid")
        return 1
    token = get_access_token(sa, scope=READONLY_SCOPE)
    secrets = [token, key_json, sa.get("private_key", ""), sa.get("private_key_id", "")]

    rows = []
    for i, url in enumerate(urls):
        if i:
            time.sleep(MIN_INTERVAL)
        try:
            payload = inspect_url(url, token)
            rows.append(flatten_inspect(url, payload))
            print(f"gsc-inspect: {url} {rows[-1]['verdict'] or 'ok'}")
        except Exception as exc:
            print(_redact(f"gsc-inspect: {url} error {exc}", secrets))
            rows.append(flatten_inspect(url, {"indexStatusResult": {"verdict": "ERROR"}}))

    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    dest = Path(args.out) if args.out else REPORTS / f"gsc-inspect-{day}.csv"
    write_csv(rows, dest)
    print(f"gsc-inspect: wrote {dest.name} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
