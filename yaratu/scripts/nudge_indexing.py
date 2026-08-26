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


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    payload: dict | None = None,
    timeout: int = 45,
) -> tuple[int | None, dict | None, str | None]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw.strip() else {}
            return response.status, parsed if isinstance(parsed, dict) else {}, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")[:300]
        except Exception:
            body = str(exc.reason)[:300]
        return exc.code, None, body
    except Exception as exc:
        return None, None, str(exc)[:300]


def _request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    payload: dict | None = None,
    timeout: int = 45,
) -> tuple[int | None, str | None]:
    code, _payload, error = _request_json(
        method, url, headers=headers, payload=payload, timeout=timeout
    )
    return code, error


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


def gsc_property_candidates(property_id: str, domain: str | None = None) -> list[str]:
    candidates = [property_id]
    host = (domain or "").strip().lower()
    if host:
        candidates.extend(
            [
                f"sc-domain:{host}",
                f"https://{host}/",
                f"https://www.{host}/",
            ]
        )
    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def list_gsc_sites(credentials_file: str | None) -> tuple[list[str], str | None]:
    token, error = _google_token(
        "https://www.googleapis.com/auth/webmasters", credentials_file
    )
    if error:
        return [], error
    data, _code, list_error = _get_json(
        "https://www.googleapis.com/webmasters/v3/sites",
        headers={"Authorization": f"Bearer {token}"},
    )
    if list_error:
        return [], list_error
    return [
        str(entry.get("siteUrl"))
        for entry in (data or {}).get("siteEntry", [])
        if entry.get("siteUrl")
    ], None


def submit_gsc_sitemap(
    property_id: str,
    sitemap_url: str,
    credentials_file: str | None,
    *,
    domain: str | None = None,
) -> dict:
    token, error = _google_token(
        "https://www.googleapis.com/auth/webmasters", credentials_file
    )
    if error:
        return _entry("skip", error=error)
    last = _entry("fail", error="no GSC property candidates")
    for candidate in gsc_property_candidates(property_id, domain):
        endpoint = (
            "https://www.googleapis.com/webmasters/v3/sites/"
            f"{urllib.parse.quote(candidate, safe='')}/sitemaps/"
            f"{urllib.parse.quote(sitemap_url, safe='')}"
        )
        code, item_error = _request(
            "PUT", endpoint, headers={"Authorization": f"Bearer {token}"}
        )
        last = _entry(
            "ok" if code and 200 <= code < 300 else "fail",
            http_status=code,
            error=item_error,
        )
        last["property"] = candidate
        if last["status"] == "ok":
            return last
    sites, sites_error = list_gsc_sites(credentials_file)
    if last.get("http_status") == 403:
        last["status"] = "skip"
        last["error"] = (
            "service account has no permission on the Yaratu GSC property; "
            "add it as owner of sc-domain:yaratu.com or https://yaratu.com/"
        )
        last["accessible_sites"] = sites
        last["service_account"] = _service_account_email(credentials_file)
        if sites_error:
            last["sites_error"] = sites_error
    return last


def _service_account_email(credentials_file: str | None) -> str | None:
    raw = os.environ.get("GSC_SERVICE_ACCOUNT_KEY", "").strip()
    raw_b64 = os.environ.get("GSC_SERVICE_ACCOUNT_KEY_B64", "").strip()
    try:
        if raw:
            info = json.loads(raw)
        elif raw_b64:
            import base64
            info = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
        elif credentials_file:
            info = json.loads(Path(credentials_file).read_text(encoding="utf-8"))
        else:
            return None
        email = info.get("client_email")
        return str(email) if email else None
    except Exception:
        return None


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


def _yandex_sitemap_items(*payloads: dict | None) -> list[dict]:
    items: list[dict] = []
    for payload in payloads:
        if not payload:
            continue
        for key in ("sitemaps", "user_added_sitemaps"):
            value = payload.get(key)
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
    return items


def _yandex_sitemap_url(item: dict) -> str:
    if item.get("sitemap_url"):
        return str(item["sitemap_url"])
    data = item.get("sitemap_data")
    if isinstance(data, dict) and data.get("url"):
        return str(data["url"])
    return ""


def _yandex_sitemap_id(items: list[dict], sitemap_url: str) -> str | None:
    for item in items:
        if _yandex_sitemap_url(item) == sitemap_url and item.get("sitemap_id"):
            return str(item["sitemap_id"])
    return None


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
    discovered, code, error = _get_json(f"{base}/sitemaps", headers=headers)
    if error and code not in (404,):
        return _entry("fail", http_status=code, error=error)
    added, _added_code, _added_error = _get_json(
        f"{base}/user-added-sitemaps", headers=headers
    )
    sitemap_id = _yandex_sitemap_id(
        _yandex_sitemap_items(discovered, added), sitemap_url
    )
    registered = bool(sitemap_id)
    if not sitemap_id:
        register_code, register_payload, register_error = _request_json(
            "POST",
            f"{base}/user-added-sitemaps",
            headers=headers,
            payload={"url": sitemap_url},
        )
        if register_code == 409:
            registered = True
        elif register_code and 200 <= register_code < 300:
            registered = True
            if register_payload and register_payload.get("sitemap_id"):
                sitemap_id = str(register_payload["sitemap_id"])
        elif register_error:
            return _entry(
                "fail",
                http_status=register_code,
                error=register_error,
            )
        if not sitemap_id:
            discovered, code, error = _get_json(f"{base}/sitemaps", headers=headers)
            added, _added_code, _added_error = _get_json(
                f"{base}/user-added-sitemaps", headers=headers
            )
            sitemap_id = _yandex_sitemap_id(
                _yandex_sitemap_items(discovered, added), sitemap_url
            )
        if not sitemap_id:
            status = "ok" if registered else "skip"
            reason = (
                "sitemap registered; Yandex has not assigned a recrawl id yet"
                if registered
                else f"sitemap is not registered in Yandex Webmaster: {sitemap_url}"
            )
            return _entry(status, http_status=code, error=reason)

    processed_id = _yandex_sitemap_id(_yandex_sitemap_items(discovered), sitemap_url)
    if not processed_id:
        discovered, code, error = _get_json(f"{base}/sitemaps", headers=headers)
        processed_id = _yandex_sitemap_id(_yandex_sitemap_items(discovered), sitemap_url)
    if not processed_id:
        return {
            **_entry(
                "ok",
                http_status=code,
                error="sitemap registered; Yandex has not processed it for recrawl yet",
            ),
            "registered": True,
            "sitemap_id": sitemap_id,
        }

    recrawl_url = (
        f"{base}/sitemaps/{urllib.parse.quote(str(processed_id), safe='')}/recrawl"
    )
    recrawl_code, recrawl_error = _request("POST", recrawl_url, headers=headers)
    if recrawl_code in (404, 409):
        return {
            **_entry(
                "skip",
                http_status=recrawl_code,
                error=(
                    "sitemap recrawl is already pending"
                    if recrawl_code == 409
                    else "sitemap registered; recrawl id is not ready"
                ),
            ),
            "registered": True,
            "sitemap_id": processed_id,
        }
    return {
        **_entry(
            "ok" if recrawl_code and 200 <= recrawl_code < 300 else "fail",
            http_status=recrawl_code,
            error=recrawl_error,
        ),
        "registered": True,
        "sitemap_id": processed_id,
    }


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
                args.gsc_property,
                args.sitemap_url,
                args.google_credentials_file,
                domain=args.domain,
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
