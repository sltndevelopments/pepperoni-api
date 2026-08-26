#!/usr/bin/env python3
"""Yaratu-specific indexing nudge with explicit property/domain inputs.

No credential or domain is embedded in this file. In dry-run mode no network
request is made and every configured action is reported as ``skip``.
Google Indexing API is disabled unless ``--google-indexing`` is explicit,
because that API is not intended for ordinary product/content pages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    payload: dict | None = None,
    timeout: int = 45,
) -> tuple[int | None, str | None]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read()
            return response.status, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")[:300]
        except Exception:
            body = str(exc.reason)[:300]
        return exc.code, body
    except Exception as exc:
        return None, str(exc)[:300]


def _get_json(url: str, *, headers: dict, timeout: int = 45) -> tuple[dict | None, int | None, str | None]:
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), response.status, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")[:300]
        except Exception:
            body = str(exc.reason)[:300]
        return None, exc.code, body
    except Exception as exc:
        return None, None, str(exc)[:300]


def _google_token(scope: str, credentials_file: str | None) -> tuple[str | None, str | None]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        return None, "google-auth is not installed"

    raw = os.environ.get("GSC_SERVICE_ACCOUNT_KEY", "").strip()
    raw_b64 = os.environ.get("GSC_SERVICE_ACCOUNT_KEY_B64", "").strip()
    try:
        if raw:
            info = json.loads(raw)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=[scope]
            )
        elif raw_b64:
            import base64
            info = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=[scope]
            )
        elif credentials_file:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file, scopes=[scope]
            )
        else:
            return None, "missing Google service-account credentials"
        credentials.refresh(Request())
        return credentials.token, None
    except Exception as exc:
        return None, str(exc)[:300]


def _entry(status: str, *, http_status: int | None = None, error: str | None = None) -> dict:
    return {"status": status, "http_status": http_status, "error": error}


def submit_gsc_sitemap(property_id: str, sitemap_url: str, credentials_file: str | None) -> dict:
    token, error = _google_token(
        "https://www.googleapis.com/auth/webmasters", credentials_file
    )
    if error:
        return _entry("skip", error=error)
    endpoint = (
        "https://www.googleapis.com/webmasters/v3/sites/"
        f"{urllib.parse.quote(property_id, safe='')}/sitemaps/"
        f"{urllib.parse.quote(sitemap_url, safe='')}"
    )
    code, error = _request("PUT", endpoint, headers={"Authorization": f"Bearer {token}"})
    return _entry("ok" if code and 200 <= code < 300 else "fail", http_status=code, error=error)


def submit_google_hot(urls: list[str], credentials_file: str | None) -> dict:
    token, error = _google_token(
        "https://www.googleapis.com/auth/indexing", credentials_file
    )
    if error:
        return {**_entry("skip", error=error), "items": []}
    items = []
    for url in urls:
        code, item_error = _request(
            "POST",
            "https://indexing.googleapis.com/v3/urlNotifications:publish",
            headers={"Authorization": f"Bearer {token}"},
            payload={"url": url, "type": "URL_UPDATED"},
        )
        items.append({
            "url": url,
            **_entry("ok" if code and 200 <= code < 300 else "fail",
                     http_status=code, error=item_error),
        })
    status = "ok" if items and all(item["status"] == "ok" for item in items) else "fail"
    return {**_entry(status), "items": items}


def submit_yandex_hot(user_id: str, host_id: str, token: str, urls: list[str]) -> dict:
    if not (user_id and host_id and token):
        return {
            **_entry("skip", error="missing YANDEX_WM_USER_ID, host id or token"),
            "items": [],
        }
    endpoint = (
        "https://api.webmaster.yandex.net/v4/user/"
        f"{urllib.parse.quote(user_id, safe='')}/hosts/"
        f"{urllib.parse.quote(host_id, safe='')}/recrawl/queue/"
    )
    items = []
    for url in urls:
        code, error = _request(
            "POST",
            endpoint,
            headers={"Authorization": f"OAuth {token}"},
            payload={"url": url},
        )
        items.append({
            "url": url,
            **_entry("ok" if code and 200 <= code < 300 else "fail",
                     http_status=code, error=error),
        })
    status = "ok" if items and all(item["status"] == "ok" for item in items) else "fail"
    return {**_entry(status), "items": items}


def submit_yandex_sitemap(
    user_id: str,
    host_id: str,
    token: str,
    sitemap_url: str,
) -> dict:
    if not (user_id and host_id and token):
        return _entry(
            "skip",
            error="missing YANDEX_WM_USER_ID, YANDEX_WM_HOST_ID or YANDEX_WM_TOKEN",
        )
    base = (
        "https://api.webmaster.yandex.net/v4/user/"
        f"{urllib.parse.quote(user_id, safe='')}/hosts/"
        f"{urllib.parse.quote(host_id, safe='')}"
    )
    headers = {"Authorization": f"OAuth {token}"}
    data, code, error = _get_json(f"{base}/sitemaps", headers=headers)
    if error:
        status = "skip" if code == 404 else "fail"
        reason = (
            "Yandex host is not registered or is inaccessible"
            if code == 404 else error
        )
        return _entry(status, http_status=code, error=reason)

    registered = next(
        (
            item for item in (data or {}).get("sitemaps", [])
            if item.get("sitemap_url") == sitemap_url
        ),
        None,
    )
    sitemap_id = (registered or {}).get("sitemap_id")
    if not sitemap_id:
        return _entry(
            "skip",
            http_status=code,
            error=f"sitemap is not registered in Yandex Webmaster: {sitemap_url}",
        )

    recrawl_url = (
        f"{base}/sitemaps/{urllib.parse.quote(str(sitemap_id), safe='')}/recrawl"
    )
    recrawl_code, recrawl_error = _request("POST", recrawl_url, headers=headers)
    if recrawl_code == 409:
        return _entry(
            "skip",
            http_status=recrawl_code,
            error="sitemap recrawl is already pending",
        )
    return _entry(
        "ok" if recrawl_code and 200 <= recrawl_code < 300 else "fail",
        http_status=recrawl_code,
        error=recrawl_error,
    )


def submit_indexnow(domain: str, key: str, key_location: str, urls: list[str]) -> dict:
    if not key:
        return _entry("skip", error="missing INDEXNOW_KEY")
    code, error = _request(
        "POST",
        "https://api.indexnow.org/indexnow",
        payload={
            "host": domain,
            "key": key,
            "keyLocation": key_location,
            "urlList": urls,
        },
    )
    return _entry("ok" if code and 200 <= code < 300 else "fail",
                  http_status=code, error=error)


def _load_urls(values: list[str], file_path: Path | None) -> list[str]:
    urls = list(values)
    if file_path:
        urls.extend(
            line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return list(dict.fromkeys(urls))


def _validate_urls(domain: str, sitemap_url: str, urls: list[str]) -> None:
    if not domain or "/" in domain or "://" in domain:
        raise ValueError("--domain must be a hostname, for example yaratu.com")
    for value in [sitemap_url, *urls]:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme != "https" or parsed.hostname != domain:
            raise ValueError(f"URL must use https and match {domain}: {value}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    parser.add_argument("--gsc-property", required=True)
    parser.add_argument("--sitemap-url", required=True)
    parser.add_argument("--hot-url", action="append", default=[])
    parser.add_argument("--hot-urls-file", type=Path)
    parser.add_argument("--google-credentials-file")
    parser.add_argument(
        "--google-indexing",
        action="store_true",
        help="Opt in to Google Indexing API for eligible URL types only",
    )
    parser.add_argument("--yandex-user-id", default=os.environ.get("YANDEX_WM_USER_ID", ""))
    parser.add_argument("--yandex-host-id", default=os.environ.get("YANDEX_WM_HOST_ID", ""))
    parser.add_argument("--yandex-token", default=os.environ.get("YANDEX_WM_TOKEN", ""))
    parser.add_argument("--indexnow-key", default=os.environ.get("INDEXNOW_KEY", ""))
    parser.add_argument("--indexnow-key-location")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        urls = _load_urls(args.hot_url, args.hot_urls_file)
        if not urls:
            raise ValueError("at least one --hot-url or --hot-urls-file entry is required")
        _validate_urls(args.domain, args.sitemap_url, urls)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    key_location = args.indexnow_key_location or (
        f"https://{args.domain}/{args.indexnow_key}.txt"
        if args.indexnow_key else f"https://{args.domain}/INDEXNOW_KEY.txt"
    )
    if args.dry_run:
        planned = _entry("skip", error="dry-run")
        results = {
            "gsc_sitemap": dict(planned),
            "google_indexing": {
                **_entry(
                    "skip",
                    error="dry-run" if args.google_indexing
                    else "disabled (use --google-indexing for eligible URL types)",
                ),
                "items": [],
            },
            "yandex_url_recrawl": {**planned, "items": []},
            "yandex_sitemap_recrawl": dict(planned),
            "indexnow": dict(planned),
        }
    else:
        results = {
            "gsc_sitemap": submit_gsc_sitemap(
                args.gsc_property, args.sitemap_url, args.google_credentials_file
            ),
            "google_indexing": (
                submit_google_hot(urls, args.google_credentials_file)
                if args.google_indexing
                else {
                    **_entry(
                        "skip",
                        error="disabled (use --google-indexing for eligible URL types)",
                    ),
                    "items": [],
                }
            ),
            "yandex_url_recrawl": submit_yandex_hot(
                args.yandex_user_id, args.yandex_host_id, args.yandex_token, urls
            ),
            "yandex_sitemap_recrawl": submit_yandex_sitemap(
                args.yandex_user_id,
                args.yandex_host_id,
                args.yandex_token,
                args.sitemap_url,
            ),
            "indexnow": submit_indexnow(args.domain, args.indexnow_key, key_location, urls),
        }

    report = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "domain": args.domain,
        "gsc_property": args.gsc_property,
        "sitemap_url": args.sitemap_url,
        "hot_urls": urls,
        "results": results,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if any(item["status"] == "fail" for item in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
